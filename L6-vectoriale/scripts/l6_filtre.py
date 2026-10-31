"""
L6, experimentul 2 — Cautare vectoriala cu filtre: „similare, dar doar ...”.

Trei filtre, calibrate automat pe catalog ca sa lase ~10%, ~1% si ~0,1% din produse:
  F1  tip_articol = X                                   (~10%)
  F2  tip_articol = X  si  pret <= p                    (~1%)
  F3  tip_articol = X  si  culoare = Y  si  pret <= p'  (~0,1%)

Cinci metode:
  pg exact          scanare completa + sortare: referinta
  pg HNSW           indexul, apoi filtrul (post-filtrare), ef_search = 40
  pg HNSW iterativ  idem, dar indexul continua pana gaseste destule (relaxed_order)
  pg HNSW strict    idem, strict_order
  Qdrant            filtrul aplicat in timpul parcurgerii grafului

    ... l6_filtre.py
    ... l6_filtre.py --ef 100 --explica
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from decimal import Decimal

import numpy as np

from l6_util import (bdm, exact_top_k, interogari, pg_cauta, qd_cauta, recall,
                     vectori)

TINTE = (0.10, 0.01, 0.001)


def calibreaza(ids: np.ndarray) -> list[dict]:
    with bdm.conectare() as conn:
        rows = conn.execute(
            "SELECT id_produs, tip_articol, culoare_de_baza, pret FROM produs_vector").fetchall()
    N = len(rows)
    meta = {r[0]: r[1:] for r in rows}
    tipuri = Counter(r[1] for r in rows if r[1])
    tip = min(tipuri, key=lambda t: abs(tipuri[t] / N - TINTE[0]))
    din_tip = [r for r in rows if r[1] == tip and r[3] is not None]

    preturi = sorted(float(r[3]) for r in din_tip)
    k2 = max(1, round(TINTE[1] * N))
    p2 = preturi[min(k2, len(preturi)) - 1]

    culoare = Counter(r[2] for r in din_tip if r[2]).most_common(1)[0][0]
    pret_c = sorted(float(r[3]) for r in din_tip if r[2] == culoare)
    k3 = max(1, round(TINTE[2] * N))
    p3 = pret_c[min(k3, len(pret_c)) - 1]

    filtre = [
        {"nume": "F1", "tip": tip, "culoare": None, "pret_max": None},
        {"nume": "F2", "tip": tip, "culoare": None, "pret_max": p2},
        {"nume": "F3", "tip": tip, "culoare": culoare, "pret_max": p3},
    ]
    for f in filtre:
        f["masca"] = np.array([_trece(meta.get(int(i)), f) for i in ids])
        f["n"] = int(f["masca"].sum())
        f["selectivitate"] = f["n"] / N
    return filtre


def _trece(m, f) -> bool:
    if m is None or m[0] != f["tip"]:
        return False
    if f["culoare"] and m[1] != f["culoare"]:
        return False
    return not (f["pret_max"] is not None and (m[2] is None or float(m[2]) > f["pret_max"]))


def sql_si_parametri(f) -> tuple[str, tuple]:
    unde, par = ["tip_articol = %s"], [f["tip"]]
    if f["culoare"]:
        unde.append("culoare_de_baza = %s")
        par.append(f["culoare"])
    if f["pret_max"] is not None:
        unde.append("pret <= %s")
        par.append(Decimal(str(f["pret_max"])))
    return " AND ".join(unde), tuple(par)


def filtru_qdrant(f):
    from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

    c = [FieldCondition(key="tip_articol", match=MatchValue(value=f["tip"]))]
    if f["culoare"]:
        c.append(FieldCondition(key="culoare_de_baza", match=MatchValue(value=f["culoare"])))
    if f["pret_max"] is not None:
        c.append(FieldCondition(key="pret", range=Range(lte=f["pret_max"])))
    return Filter(must=c)


def descrie(f) -> str:
    s = f"tip_articol = '{f['tip']}'"
    if f["culoare"]:
        s += f" si culoare = '{f['culoare']}'"
    if f["pret_max"] is not None:
        s += f" si pret <= {f['pret_max']}"
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ef", type=int, default=40, help="ef_search / hnsw_ef (implicit pgvector: 40)")
    ap.add_argument("--interogari", type=int, default=100)
    ap.add_argument("--explica", action="store_true", help="afiseaza planurile PostgreSQL pentru F3")
    a = ap.parse_args()

    ids, E = vectori()
    Q = interogari(E, a.interogari)
    filtre = calibreaza(ids)
    print("Filtrele calibrate pe catalog:\n")
    for f in filtre:
        print(f"  {f['nume']}: {descrie(f)}  ->  {f['n']} produse ({f['selectivitate']:.2%})")
    print()

    conn = bdm.conectare()
    qc = bdm.client_qdrant()
    randuri = []
    for f in filtre:
        unde, par = sql_si_parametri(f)
        adevar = [exact_top_k(E, ids, q, masca=f["masca"]) for q in Q]
        metode = {
            "pg exact": lambda q: pg_cauta(conn, q, mod="exact", unde=unde, parametri=par),
            "pg HNSW": lambda q: pg_cauta(conn, q, ef=a.ef, unde=unde, parametri=par),
            "pg HNSW iterativ": lambda q: pg_cauta(conn, q, ef=a.ef, iterativ="relaxed_order",
                                                   unde=unde, parametri=par),
            "pg HNSW strict": lambda q: pg_cauta(conn, q, ef=a.ef, iterativ="strict_order",
                                                 unde=unde, parametri=par),
            "Qdrant": lambda q: qd_cauta(qc, q, ef=a.ef, filtru=filtru_qdrant(f)),
        }
        for nume, m in metode.items():
            timpi, intoarse, rec = [], [], []
            for q, adv in zip(Q, adevar):
                ms, rez = m(q)
                timpi.append(ms)
                intoarse.append(len(rez))
                rec.append(recall(rez, adv))
            lat = bdm.rezumat_latente(timpi)
            r = {"filtru": f"{f['nume']} ({f['selectivitate']:.2%})", "metoda": nume,
                 "intoarse_din_10": round(float(np.mean(intoarse)), 2),
                 "recall@10": round(float(np.mean(rec)), 3),
                 "p50_ms": lat["p50_ms"], "p95_ms": lat["p95_ms"]}
            randuri.append(r)
            for k in ("intoarse_din_10", "recall@10", "p50_ms"):
                bdm.noteaza("L6", "2. filtre", f"{f['nume']} {f['selectivitate']:.2%}, {nume}, ef={a.ef}",
                            k, r[k])
        print(f"  {f['nume']} gata")

    print()
    print(bdm.tabel(randuri))

    if a.explica:
        f = filtre[2]
        unde, par = sql_si_parametri(f)
        for titlu, setari in (("HNSW fara iterative scan", "SET LOCAL hnsw.iterative_scan = off"),
                              ("HNSW cu relaxed_order", "SET LOCAL hnsw.iterative_scan = relaxed_order")):
            with conn.transaction():
                conn.execute("SET LOCAL enable_seqscan = off")
                conn.execute(f"SET LOCAL hnsw.ef_search = {a.ef}")
                conn.execute(setari)
                plan = conn.execute(
                    f"EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) SELECT id_produs FROM produs_vector "
                    f"WHERE {unde} ORDER BY emb <=> %s LIMIT 10", (*par, Q[0])).fetchall()
            print(f"\n--- Planul pentru F3, {titlu} ---")
            print("\n".join(re.sub(r"'\[[^\]]*\]'", "'[...]'", r[0]) for r in plan))
    conn.close()


if __name__ == "__main__":
    main()
