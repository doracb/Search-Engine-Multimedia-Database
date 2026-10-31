"""
L6, experimentul 3 — Exploatare: ce se intampla cand vin produse noi.

Simuleaza sosirea a 1.000 de produse noi (copii usor perturbate ale unor
produse existente, cu identificatori de la 90.000.000 in sus) si masoara:
  - timpul de inserare in fiecare sistem, cu indexul HNSW deja construit;
  - daca un produs nou e gasit imediat dupa inserare;
  - pasii necesari ca cele doua sisteme sa ramana sincronizate.
La final, produsele de test sunt sterse din ambele sisteme.

    ... l6_exploatare.py
    ... l6_exploatare.py --n 5000 --pastreaza
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from l6_util import COLECTIE, bdm, pg_cauta, qd_cauta, vectori

ID_START = 90_000_000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--lot", type=int, default=100)
    ap.add_argument("--pastreaza", action="store_true", help="nu sterge produsele de test")
    a = ap.parse_args()

    from qdrant_client.models import PointIdsList, PointStruct

    ids, E = vectori()
    rng = np.random.default_rng(5)
    surse = rng.choice(len(ids), size=a.n, replace=False)
    noi = E[surse] + rng.normal(scale=0.02, size=(a.n, E.shape[1])).astype(np.float32)
    noi /= np.linalg.norm(noi, axis=1, keepdims=True)
    id_noi = [ID_START + i for i in range(a.n)]

    conn = bdm.conectare()
    qc = bdm.client_qdrant()
    model = conn.execute("SELECT model_versiune FROM produs_vector LIMIT 1").fetchone()[0]
    meta = {r[0]: r[1:] for r in conn.execute(
        "SELECT id_produs, tip_articol, culoare_de_baza, pret, stoc FROM produs").fetchall()}
    conn.execute("DELETE FROM produs WHERE id_produs >= %s", (ID_START,))
    qc.delete(COLECTIE, points_selector=PointIdsList(points=id_noi), wait=True)
    idx_inainte = conn.execute("SELECT pg_relation_size('idx_produs_vector_hnsw')").fetchone()[0]

    # --- PostgreSQL: produsul si vectorul, in aceeasi tranzactie
    t_pg = []
    t0 = time.perf_counter()
    for s in range(0, a.n, a.lot):
        t = time.perf_counter()
        with conn.transaction(), conn.cursor() as cur:
            rand_p, rand_v = [], []
            for j in range(s, min(s + a.lot, a.n)):
                m = meta[int(ids[surse[j]])]
                rand_p.append((id_noi[j], f"Produs de test {id_noi[j]}", m[0], m[1], m[2], m[3]))
                rand_v.append((id_noi[j], m[0], m[1], m[2], m[3], model, noi[j]))
            cur.executemany("INSERT INTO produs (id_produs, nume, tip_articol, culoare_de_baza, "
                            "pret, stoc) VALUES (%s,%s,%s,%s,%s,%s)", rand_p)
            cur.executemany("INSERT INTO produs_vector (id_produs, tip_articol, culoare_de_baza, "
                            "pret, stoc, model_versiune, emb) VALUES (%s,%s,%s,%s,%s,%s,%s)", rand_v)
        t_pg.append((time.perf_counter() - t) * 1000)
    total_pg = time.perf_counter() - t0
    idx_dupa = conn.execute("SELECT pg_relation_size('idx_produs_vector_hnsw')").fetchone()[0]

    # --- Qdrant: un al doilea sistem, scris separat
    t_qd = []
    t0 = time.perf_counter()
    for s in range(0, a.n, a.lot):
        t = time.perf_counter()
        pct = []
        for j in range(s, min(s + a.lot, a.n)):
            m = meta[int(ids[surse[j]])]
            pct.append(PointStruct(id=id_noi[j], vector=noi[j].tolist(), payload={
                "tip_articol": m[0], "culoare_de_baza": m[1],
                "pret": float(m[2]) if m[2] is not None else None, "stoc": m[3],
                "model_versiune": model}))
        qc.upsert(COLECTIE, points=pct, wait=True)
        t_qd.append((time.perf_counter() - t) * 1000)
    total_qd = time.perf_counter() - t0

    # --- Vizibilitate imediata: produsul nou trebuie sa iasa primul la propria cautare
    verif = rng.choice(a.n, size=min(50, a.n), replace=False)
    vazut_pg = sum(pg_cauta(conn, noi[j], k=1)[1][:1] == [id_noi[j]] for j in verif)
    vazut_qd = sum(qd_cauta(qc, noi[j], k=1)[1][:1] == [id_noi[j]] for j in verif)

    randuri = [
        {"sistem": "pgvector", "total_s": round(total_pg, 2),
         "p50_ms_pe_lot": bdm.rezumat_latente(t_pg)["p50_ms"],
         "gasit_imediat": f"{vazut_pg}/{len(verif)}"},
        {"sistem": "Qdrant", "total_s": round(total_qd, 2),
         "p50_ms_pe_lot": bdm.rezumat_latente(t_qd)["p50_ms"],
         "gasit_imediat": f"{vazut_qd}/{len(verif)}"},
    ]
    print(f"{a.n} produse noi, in loturi de {a.lot}\n")
    print(bdm.tabel(randuri))
    print(f"\nIndexul HNSW din PostgreSQL: {idx_inainte / 1e6:.1f} MB -> {idx_dupa / 1e6:.1f} MB")
    for r in randuri:
        bdm.noteaza("L6", "3. exploatare", f"{r['sistem']}, {a.n} produse noi", "total_s", r["total_s"])

    if not a.pastreaza:
        conn.execute("DELETE FROM produs WHERE id_produs >= %s", (ID_START,))  # cascada sterge si vectorii
        qc.delete(COLECTIE, points_selector=PointIdsList(points=id_noi), wait=True)
        print("Produsele de test au fost sterse din ambele sisteme.")
    conn.close()


if __name__ == "__main__":
    main()
