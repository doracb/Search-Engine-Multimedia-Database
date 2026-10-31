"""
L6, T1 — Aceleasi embeddings CLIP in doua sisteme: pgvector si Qdrant.

Ambele primesc acelasi index: HNSW, M = 16, ef_construction = 64, distanta cosinus.
Scriptul masoara incarcarea, constructia indexului si spatiul ocupat.

    docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L6-vectoriale/sql/01_vectori.sql
    docker compose exec jupyter python /home/jovyan/proiect/L6-vectoriale/scripts/l6_incarca.py
"""

from __future__ import annotations

import time

import numpy as np

from l6_util import COLECTIE, HNSW_EF_CONSTRUCTIE, HNSW_M, bdm, vectori


def incarca_pgvector(ids, E, model: str) -> dict:
    with bdm.conectare() as conn:
        meta = {r[0]: r[1:] for r in conn.execute(
            "SELECT id_produs, tip_articol, culoare_de_baza, pret, stoc FROM produs").fetchall()}
        conn.execute("DROP INDEX IF EXISTS idx_produs_vector_hnsw")
        conn.execute("TRUNCATE produs_vector")
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            with cur.copy("COPY produs_vector (id_produs, tip_articol, culoare_de_baza, pret, "
                          "stoc, model_versiune, emb) FROM STDIN WITH (FORMAT BINARY)") as cp:
                cp.set_types(["int4", "text", "text", "numeric", "int4", "text", "vector"])
                for idp, v in zip(ids, E):
                    m = meta.get(int(idp))
                    if m is not None:
                        cp.write_row([int(idp), *m, model, v])
        t_copy = time.perf_counter() - t0
        conn.execute("ANALYZE produs_vector")
        conn.execute("SET maintenance_work_mem = '256MB'")
        t0 = time.perf_counter()
        conn.execute(f"""CREATE INDEX idx_produs_vector_hnsw ON produs_vector
                         USING hnsw (emb vector_cosine_ops)
                         WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTIE})""")
        t_index = time.perf_counter() - t0
        n, tabel, index = conn.execute(
            """SELECT count(*), pg_total_relation_size('produs_vector')
                               - pg_indexes_size('produs_vector'),
                      pg_relation_size('idx_produs_vector_hnsw') FROM produs_vector""").fetchone()
    return {"sistem": "pgvector", "vectori": n, "incarcare_s": round(t_copy, 2),
            "index_s": round(t_index, 2), "date_MB": round(tabel / 1e6, 1),
            "index_MB": round(index / 1e6, 1)}


def incarca_qdrant(ids, E, model: str) -> dict:
    from qdrant_client.models import (Distance, HnswConfigDiff, OptimizersConfigDiff,
                                      PayloadSchemaType, PointStruct, VectorParams)

    with bdm.conectare() as conn:
        meta = {r[0]: r[1:] for r in conn.execute(
            "SELECT id_produs, tip_articol, culoare_de_baza, pret, stoc FROM produs").fetchall()}
    qc = bdm.client_qdrant()
    if qc.collection_exists(COLECTIE):
        qc.delete_collection(COLECTIE)
    qc.create_collection(
        COLECTIE, vectors_config=VectorParams(size=E.shape[1], distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCTIE),
        # Implicit, Qdrant nu indexeaza segmentele sub ~20 MB de vectori si cauta
        # exhaustiv in ele. La 20.000 de vectori, impartiti in mai multe segmente,
        # comparatia cu pgvector ar fi falsa. Pragul de 1 MB forteaza HNSW.
        optimizers_config=OptimizersConfigDiff(indexing_threshold=1000))
    for camp, tip in (("tip_articol", PayloadSchemaType.KEYWORD),
                      ("culoare_de_baza", PayloadSchemaType.KEYWORD),
                      ("pret", PayloadSchemaType.FLOAT)):
        qc.create_payload_index(COLECTIE, camp, tip)

    t0 = time.perf_counter()
    lot = []
    for idp, v in zip(ids, E):
        m = meta.get(int(idp))
        if m is None:
            continue
        lot.append(PointStruct(id=int(idp), vector=v.tolist(), payload={
            "tip_articol": m[0], "culoare_de_baza": m[1],
            "pret": float(m[2]) if m[2] is not None else None, "stoc": m[3],
            "model_versiune": model}))
        if len(lot) == 500:
            qc.upsert(COLECTIE, points=lot, wait=False)
            lot = []
    if lot:
        qc.upsert(COLECTIE, points=lot, wait=False)
    t_upsert = time.perf_counter() - t0
    # Qdrant construieste indexul in fundal; asteptam sa termine (status green).
    while True:
        info = qc.get_collection(COLECTIE)
        if str(info.status).lower().endswith("green"):
            break
        time.sleep(0.5)
    t_total = time.perf_counter() - t0
    return {"sistem": "Qdrant", "vectori": info.points_count, "incarcare_s": round(t_upsert, 2),
            "index_s": round(t_total - t_upsert, 2), "date_MB": "vezi du -sh",
            "index_MB": "vezi du -sh"}


def main() -> None:
    ids, E = vectori()
    z = np.load(bdm.artefact("L5_clip.npz"))
    model = f"{z['model']}/{z['ponderi']}" if "model" in z.files else "necunoscut"
    print(f"{len(ids)} vectori de {E.shape[1]} dimensiuni, model {model}\n")
    randuri = [incarca_pgvector(ids, E, model)]
    print("  pgvector: gata")
    randuri.append(incarca_qdrant(ids, E, model))
    print("  Qdrant: gata\n")
    print(bdm.tabel(randuri))
    for r in randuri:
        for k in ("incarcare_s", "index_s", "date_MB", "index_MB"):
            if isinstance(r[k], (int, float)):
                bdm.noteaza("L6", "incarcare", r["sistem"], k, r[k])
    print("\nSpatiul Qdrant pe disc:\n  docker compose exec qdrant du -sh "
          f"/qdrant/storage/collections/{COLECTIE}")


if __name__ == "__main__":
    main()
