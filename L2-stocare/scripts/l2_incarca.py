"""
L2 — Incarcarea acelorasi imagini in cele doua variante de stocare.

    A. BYTEA in PostgreSQL       (tabelul imagine_bytea)
    B. object storage, Garage    (bucket-ul din L1, prefixul l2/)

Ambele variante citesc ACELEASI fisiere de pe disc, in aceeasi ordine,
deci diferenta de timp vine doar din destinatie.

Rulare (de 3 ori, conform protocolului):
    docker compose exec jupyter python /home/jovyan/proiect/L2-stocare/scripts/l2_incarca.py
Optiuni:
    --n 1000         numarul de imagini (implicit 1000)
    --varianta A|B|AB
    --rulare 1       eticheta rularii, apare in rezultate.csv
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402

PREFIX = "l2/"
SEMINTA = 2024  # aceeasi selectie la toata grupa


def alege_produse(conn, n: int) -> list[int]:
    """n produse din catalog care au imagine, alese determinist."""
    ids = [r[0] for r in conn.execute(
        "SELECT DISTINCT id_produs FROM imagine ORDER BY id_produs").fetchall()]
    if not ids:
        raise SystemExit("Tabelul imagine e gol. Ruleaza intai ingestul din L1.")
    rnd = random.Random(SEMINTA)
    return sorted(rnd.sample(ids, min(n, len(ids))))


def citeste_fisiere(ids: list[int]) -> list[tuple[int, bytes]]:
    rez = []
    for i in ids:
        cale = bdm.IMAGINI / f"{i}.jpg"
        if cale.exists():
            rez.append((i, cale.read_bytes()))
    return rez


def varianta_a(conn, fisiere) -> dict:
    conn.execute("TRUNCATE imagine_bytea")
    timpi = []
    t0 = time.perf_counter()
    with conn.cursor() as cur:
        for idp, continut in fisiere:
            t = time.perf_counter()
            cur.execute(
                "INSERT INTO imagine_bytea (id_produs, continut, dimensiune_octeti) "
                "VALUES (%s, %s, %s)", (idp, continut, len(continut)))
            timpi.append((time.perf_counter() - t) * 1000)
    total = time.perf_counter() - t0
    return {"total_s": round(total, 2), **bdm.rezumat_latente(timpi)}


def goleste_prefix(s3) -> None:
    pag = s3.get_paginator("list_objects_v2")
    for p in pag.paginate(Bucket=bdm.S3_BUCKET, Prefix=PREFIX):
        chei = [{"Key": o["Key"]} for o in p.get("Contents", [])]
        if chei:
            s3.delete_objects(Bucket=bdm.S3_BUCKET, Delete={"Objects": chei})


def varianta_b(s3, fisiere) -> dict:
    goleste_prefix(s3)
    timpi = []
    t0 = time.perf_counter()
    for idp, continut in fisiere:
        t = time.perf_counter()
        s3.put_object(Bucket=bdm.S3_BUCKET, Key=f"{PREFIX}{idp}.jpg", Body=continut,
                      ContentType="image/jpeg")
        timpi.append((time.perf_counter() - t) * 1000)
    total = time.perf_counter() - t0
    return {"total_s": round(total, 2), **bdm.rezumat_latente(timpi)}


def dimensiune_b(s3) -> int:
    total = 0
    for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bdm.S3_BUCKET,
                                                           Prefix=PREFIX):
        total += sum(o["Size"] for o in p.get("Contents", []))
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="L2: incarcare BYTEA vs object storage")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--varianta", default="AB", choices=["A", "B", "AB"])
    ap.add_argument("--rulare", default="1")
    a = ap.parse_args()

    with bdm.conectare() as conn:
        ids = alege_produse(conn, a.n)
        fisiere = citeste_fisiere(ids)
        brut = sum(len(c) for _, c in fisiere)
        print(f"{len(fisiere)} imagini, {brut / 1e6:.1f} MB brut "
              f"(media {brut / max(len(fisiere), 1) / 1024:.1f} KB)\n")

        randuri = []
        if "A" in a.varianta:
            r = varianta_a(conn, fisiere)
            randuri.append({"varianta": "A BYTEA", **r})
        if "B" in a.varianta:
            s3 = bdm.client_s3()
            r = varianta_b(s3, fisiere)
            randuri.append({"varianta": "B object storage", **r})
            print(f"Varianta B: {dimensiune_b(s3) / 1e6:.1f} MB in {bdm.S3_BUCKET}/{PREFIX}"
                  " (dimensiune logica)\n")

    print(bdm.tabel(randuri, ["varianta", "total_s", "p50_ms", "p95_ms", "medie_ms", "max_ms"]))
    for r in randuri:
        cfg = f"{r['varianta']}, n={len(fisiere)}, rulare {a.rulare}"
        bdm.noteaza("L2", "ingest", cfg, "total_s", r["total_s"])
        bdm.noteaza("L2", "ingest", cfg, "p95_ms_pe_obiect", r["p95_ms"])
    print(f"\nRezultatele au fost adaugate in {bdm.REZULTATE}")


if __name__ == "__main__":
    main()
