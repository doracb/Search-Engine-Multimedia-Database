"""
L6, experimentul 1 — Curbele recall@10 - latenta, pgvector fata de Qdrant.

Acelasi index (HNSW, M = 16), aceleasi 200 de interogari, aceeasi referinta
exacta (calculata in numpy). Se variaza ef_search (pgvector) si hnsw_ef (Qdrant).

    ... l6_curbe.py
    ... l6_curbe.py --ef 10 40 160 --interogari 100
"""

from __future__ import annotations

import argparse
from pathlib import Path

from l6_util import (bdm, exact_top_k, grafic, interogari, pg_cauta, qd_cauta,
                     recall, vectori)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ef", nargs="+", type=int, default=[10, 20, 40, 80, 160, 320])
    ap.add_argument("--interogari", type=int, default=200)
    a = ap.parse_args()

    ids, E = vectori()
    Q = interogari(E, a.interogari)
    adevar = [exact_top_k(E, ids, q) for q in Q]
    conn = bdm.conectare()
    qc = bdm.client_qdrant()

    for q in Q[:20]:  # incalzire, ambele sisteme
        pg_cauta(conn, q)
        qd_cauta(qc, q)

    randuri, serii = [], {"pgvector": [], "Qdrant": []}

    def ruleaza(sistem, eticheta, f):
        timpi, rec = [], []
        for q, adv in zip(Q, adevar):
            ms, rez = f(q)
            timpi.append(ms)
            rec.append(recall(rez, adv))
        lat = bdm.rezumat_latente(timpi)
        r = {"sistem": sistem, "setare": eticheta, "recall@10": round(sum(rec) / len(rec), 4),
             "p50_ms": lat["p50_ms"], "p95_ms": lat["p95_ms"]}
        randuri.append(r)
        print(f"  {sistem:<9} {eticheta:<14} recall {r['recall@10']:.3f}  p50 {r['p50_ms']} ms")
        for k in ("recall@10", "p50_ms", "p95_ms"):
            bdm.noteaza("L6", "1. curbe", f"{sistem}, {eticheta}", k, r[k])
        return r

    ruleaza("pgvector", "exact", lambda q: pg_cauta(conn, q, mod="exact"))
    ruleaza("Qdrant", "exact", lambda q: qd_cauta(qc, q, ef=None, exact=True))
    for ef in a.ef:
        r = ruleaza("pgvector", f"ef_search={ef}", lambda q, ef=ef: pg_cauta(conn, q, ef=ef))
        serii["pgvector"].append((r["p50_ms"], r["recall@10"]))
        r = ruleaza("Qdrant", f"hnsw_ef={ef}", lambda q, ef=ef: qd_cauta(qc, q, ef=ef))
        serii["Qdrant"].append((r["p50_ms"], r["recall@10"]))
    conn.close()

    print()
    print(bdm.tabel(randuri))
    d = Path(__file__).resolve().parents[1]
    bdm.scrie_csv(d / "rezultate" / "curbe.csv", randuri)
    g = grafic(serii, "pgvector fata de Qdrant: HNSW M=16, CLIP 512d", d / "grafice" / "curbe.png")
    if g:
        print(f"\nGrafic: {g}")


if __name__ == "__main__":
    main()
