"""
Test end-to-end al mediului de laborator.
Se ruleaza din containerul Jupyter:

    docker compose exec jupyter python /home/jovyan/lucru/smoke_test.py

Verifica, in ordine: Postgres + pgvector, object storage compatibil S3,
Qdrant. Fiecare sectiune e independenta; daca una cade, celelalte ruleaza.
"""

import io
import os
import sys
import time

import numpy as np

DIM = 512
N = 500
esecuri = []


def sectiune(nume):
    print(f"\n--- {nume} " + "-" * (58 - len(nume)))


def ok(mesaj, t=None):
    sufix = f"  ({t*1000:.0f} ms)" if t is not None else ""
    print(f"  [ok]   {mesaj}{sufix}")


def esec(nume, e):
    print(f"  [ESEC] {nume}: {type(e).__name__}: {e}")
    esecuri.append(nume)


# --------------------------------------------------------------------------
sectiune("Postgres + pgvector")
try:
    import psycopg
    from pgvector.psycopg import register_vector

    dsn = (
        f"host={os.environ.get('PGHOST', 'postgres')} "
        f"user={os.environ.get('PGUSER', 'bdm')} "
        f"password={os.environ.get('PGPASSWORD', 'bdm')} "
        f"dbname={os.environ.get('PGDATABASE', 'bdm')}"
    )
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)

        versiune = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()[0]
        ok(f"extensia vector, versiunea {versiune}")

        conn.execute("DROP TABLE IF EXISTS smoke_vectori")
        conn.execute(f"CREATE TABLE smoke_vectori (id int, v vector({DIM}))")

        rng = np.random.default_rng(42)
        date = rng.random((N, DIM), dtype=np.float32)
        date /= np.linalg.norm(date, axis=1, keepdims=True)

        t0 = time.perf_counter()
        with conn.cursor().copy(
            "COPY smoke_vectori (id, v) FROM STDIN WITH (FORMAT BINARY)"
        ) as copy:
            copy.set_types(["int4", "vector"])
            for i, v in enumerate(date):
                copy.write_row([i, v])
        ok(f"{N} vectori inserati prin COPY", time.perf_counter() - t0)

        t0 = time.perf_counter()
        conn.execute(
            "CREATE INDEX ON smoke_vectori USING hnsw (v vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
        ok("index HNSW construit", time.perf_counter() - t0)

        t0 = time.perf_counter()
        rezultate = conn.execute(
            "SELECT id, v <=> %s AS dist FROM smoke_vectori ORDER BY dist LIMIT 5",
            (date[0],),
        ).fetchall()
        ok(f"cautare kNN, primul rezultat id={rezultate[0][0]}",
           time.perf_counter() - t0)

        assert rezultate[0][0] == 0, "vectorul interogat ar trebui sa fie primul"
        ok("vectorul interogat se regaseste pe prima pozitie")

        conn.execute("DROP TABLE smoke_vectori")
except Exception as e:  # noqa: BLE001
    esec("Postgres", e)


# --------------------------------------------------------------------------
sectiune("Object storage (S3)")
try:
    import boto3
    from botocore.client import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION", "garage"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    bucket = os.environ.get("S3_BUCKET", "imagini")
    try:
        s3.create_bucket(Bucket=bucket)
    except Exception:
        pass  # exista deja
    ok(f"bucket '{bucket}' disponibil")

    continut = b"x" * (256 * 1024)
    t0 = time.perf_counter()
    s3.put_object(Bucket=bucket, Key="smoke/obiect.bin", Body=continut)
    ok("obiect de 256 KB incarcat", time.perf_counter() - t0)

    t0 = time.perf_counter()
    citit = s3.get_object(Bucket=bucket, Key="smoke/obiect.bin")["Body"].read()
    ok("obiect citit inapoi", time.perf_counter() - t0)
    assert citit == continut, "continutul citit difera de cel scris"
    ok("continut identic la citire")

    lista = s3.list_objects_v2(Bucket=bucket, Prefix="smoke/")
    ok(f"listare cu prefix: {lista['KeyCount']} obiect(e)")

    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": "test/obiect.bin"},
        ExpiresIn=300,
    )
    ok("URL presemnat generat")
    print(f"         {url[:90]}...")

    s3.delete_object(Bucket=bucket, Key="smoke/obiect.bin")
    ok("obiect sters")
except KeyError as e:
    esec("S3", f"variabila de mediu lipsa: {e}")
except Exception as e:  # noqa: BLE001
    esec("S3", e)


# --------------------------------------------------------------------------
sectiune("Qdrant")
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    qc = QdrantClient(url=os.environ.get("QDRANT_URL", "http://qdrant:6333"))
    ok(f"conectat, {len(qc.get_collections().collections)} colectii existente")

    colectie = "smoke"
    qc.recreate_collection(
        collection_name=colectie,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
    )
    ok("colectie creata")

    rng = np.random.default_rng(42)
    date = rng.random((N, DIM), dtype=np.float32)
    date /= np.linalg.norm(date, axis=1, keepdims=True)

    t0 = time.perf_counter()
    qc.upsert(
        collection_name=colectie,
        points=[PointStruct(id=i, vector=v.tolist()) for i, v in enumerate(date)],
    )
    ok(f"{N} puncte inserate", time.perf_counter() - t0)

    t0 = time.perf_counter()
    hits = qc.query_points(
        collection_name=colectie, query=date[0].tolist(), limit=5
    ).points
    ok(f"cautare kNN, primul rezultat id={hits[0].id}", time.perf_counter() - t0)
    assert hits[0].id == 0, "vectorul interogat ar trebui sa fie primul"
    ok("vectorul interogat se regaseste pe prima pozitie")

    qc.delete_collection(colectie)
except Exception as e:  # noqa: BLE001
    esec("Qdrant", e)


# --------------------------------------------------------------------------
print("\n" + "=" * 64)
if esecuri:
    print(f"REZULTAT: esec la {', '.join(esecuri)}")
    sys.exit(1)
print("REZULTAT: toate componentele functioneaza.")
