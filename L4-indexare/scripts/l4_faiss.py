"""
L4, experimentele 2 si 3 — Indecsi aproximativi in FAISS: curba recall - latenta.

  Exact   : IndexFlatL2, referinta (recall = 1)
  IVF     : IndexIVFFlat, nlist liste; se variaza nprobe
  HNSW    : IndexHNSWFlat, M = 16; se variaza efSearch
  IVF-PQ  : (optional, --pq) coduri compacte; pentru extensia de proiect

Pentru fiecare setare: recall@10 fata de exact, p50/p95 pe interogare,
mAP pe setul din L3, timpul de constructie si memoria indexului.

    ... l4_faiss.py                       # experimentul 2: HSV 128d
    ... l4_faiss.py --pca 32              # experimentul 3: pe vectorii redusi
    ... l4_faiss.py --nprobe 1 4 16 --ef 16 64
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from l4_util import (bdm, esantion_interogari, faiss_un_fir, grafic, incarca,
                     latente_si_rezultate, map_pe_l3, recall_la_k)


def memorie_index(faiss, index) -> float:
    """Dimensiunea indexului serializat, MB: o aproximare buna a memoriei ocupate."""
    return round(faiss.serialize_index(index).nbytes / 1e6, 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--descriptor", default="hsv", choices=["hsv", "lbp", "clip"])
    ap.add_argument("--pca", type=int, default=0)
    ap.add_argument("--nlist", type=int, default=0, help="implicit ~ sqrt(N)")
    ap.add_argument("--nprobe", nargs="+", type=int, default=[1, 2, 4, 8, 16, 32, 64])
    ap.add_argument("--m", type=int, default=16, help="M pentru HNSW")
    ap.add_argument("--ef", nargs="+", type=int, default=[8, 16, 32, 64, 128, 256])
    ap.add_argument("--pq", type=int, default=0, help="IVF-PQ cu m subvectori (0 = nu)")
    a = ap.parse_args()
    faiss = faiss_un_fir()

    ids, X, descr = incarca(a.descriptor, a.pca)
    N, d = X.shape
    Q = esantion_interogari(X)
    nlist = a.nlist or int(np.sqrt(N))
    print(f"{descr}: {N} vectori, {len(Q)} interogari de latenta, nlist = {nlist}\n")

    # --- referinta exacta
    exact = faiss.IndexFlatL2(d)
    exact.add(X)
    t_exact, I_exact = latente_si_rezultate(exact.search, Q)
    randuri, serii = [], {}

    def masoara(nume: str, familie: str, index, construire_s: float) -> None:
        timpi, I = latente_si_rezultate(index.search, Q)
        lat = bdm.rezumat_latente(timpi)
        r = {"index": nume, "recall@10": round(recall_la_k(I, I_exact), 4),
             "p50_ms": lat["p50_ms"], "p95_ms": lat["p95_ms"],
             "mAP": map_pe_l3(index.search, ids, X),
             "constructie_s": round(construire_s, 2), "memorie_MB": memorie_index(faiss, index)}
        randuri.append(r)
        serii.setdefault(familie, []).append((r["p50_ms"], r["recall@10"]))
        for k in ("recall@10", "p50_ms", "p95_ms", "mAP", "memorie_MB"):
            bdm.noteaza("L4", "2-3. index", f"{descr}, {nume}", k, r[k])
        print(f"  {nume:<28} recall {r['recall@10']:.3f}   p50 {r['p50_ms']:.3f} ms")

    masoara("exact (Flat)", "exact", exact, 0.0)

    # --- IVF
    t0 = time.perf_counter()
    q_ivf = faiss.IndexFlatL2(d)
    ivf = faiss.IndexIVFFlat(q_ivf, d, nlist)
    ivf.train(X)
    ivf.add(X)
    t_ivf = time.perf_counter() - t0
    for p in a.nprobe:
        if p > nlist:
            continue
        ivf.nprobe = p
        masoara(f"IVF nlist={nlist} nprobe={p}", "IVF", ivf, t_ivf)

    # --- HNSW
    t0 = time.perf_counter()
    hnsw = faiss.IndexHNSWFlat(d, a.m)
    hnsw.hnsw.efConstruction = 64
    hnsw.add(X)
    t_hnsw = time.perf_counter() - t0
    for ef in a.ef:
        hnsw.hnsw.efSearch = ef
        masoara(f"HNSW M={a.m} ef={ef}", "HNSW", hnsw, t_hnsw)

    # --- IVF-PQ (optional)
    if a.pq:
        if d % a.pq:
            print(f"\nPQ sarit: dimensiunea {d} nu se imparte la m = {a.pq}")
        else:
            t0 = time.perf_counter()
            q_pq = faiss.IndexFlatL2(d)
            pq = faiss.IndexIVFPQ(q_pq, d, nlist, a.pq, 8)
            pq.train(X)
            pq.add(X)
            t_pq = time.perf_counter() - t0
            for p in a.nprobe:
                if p <= nlist:
                    pq.nprobe = p
                    masoara(f"IVF-PQ m={a.pq} nprobe={p}", f"IVF-PQ m={a.pq}", pq, t_pq)

    print()
    print(bdm.tabel(randuri))
    print(f"\nConstructie: IVF {t_ivf:.2f} s, HNSW {t_hnsw:.2f} s. "
          f"Exact: p50 {bdm.rezumat_latente(t_exact)['p50_ms']} ms.")

    nume = f"{a.descriptor}{'_pca' + str(a.pca) if a.pca else ''}"
    director = Path(__file__).resolve().parents[1]
    bdm.scrie_csv(director / "rezultate" / f"faiss_{nume}.csv", randuri)
    g = grafic({k: sorted(v) for k, v in serii.items()}, f"{descr}: recall@10 - latenta",
               "latenta p50 pe interogare (ms)", "recall@10",
               director / "grafice" / f"curba_{nume}.png")
    print(f"Tabel: {director / 'rezultate' / f'faiss_{nume}.csv'}")
    if g:
        print(f"Grafic: {g}")


if __name__ == "__main__":
    main()
