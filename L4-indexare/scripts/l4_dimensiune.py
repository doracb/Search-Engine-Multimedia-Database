"""
L4, experimentul 1 — Cat costa si cat aduce dimensiunea.

Reduce descriptorul HSV cu PCA (128 -> 64 -> 32 -> 16 -> 8) si masoara, cu
cautare EXHAUSTIVA (fara index aproximativ):
  - mAP pe setul de relevanta din L3
  - latenta pe interogare (p50, p95), un singur fir de executie
  - memoria vectorilor

    ... l4_dimensiune.py
    ... l4_dimensiune.py --descriptor lbp --dimensiuni 59 32 16 8
"""

from __future__ import annotations

import argparse
from pathlib import Path

from l4_util import (bdm, esantion_interogari, faiss_un_fir, grafic, incarca,
                     latente_si_rezultate, map_pe_l3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--descriptor", default="hsv", choices=["hsv", "lbp", "clip"])
    ap.add_argument("--dimensiuni", nargs="+", type=int, default=[128, 64, 32, 16, 8])
    a = ap.parse_args()
    faiss = faiss_un_fir()

    randuri = []
    for d in a.dimensiuni:
        ids, X, descr = incarca(a.descriptor, pca=d)
        index = faiss.IndexFlatL2(X.shape[1])
        index.add(X)
        timpi, _ = latente_si_rezultate(index.search, esantion_interogari(X))
        lat = bdm.rezumat_latente(timpi)
        m = map_pe_l3(index.search, ids, X)
        r = {"configuratie": descr, "dim": X.shape[1], "mAP": m,
             "p50_ms": lat["p50_ms"], "p95_ms": lat["p95_ms"],
             "memorie_MB": round(X.nbytes / 1e6, 2)}
        randuri.append(r)
        print(f"  {descr}: mAP {m}, p50 {lat['p50_ms']} ms")
        for k in ("mAP", "p50_ms", "p95_ms", "memorie_MB"):
            bdm.noteaza("L4", "1. dimensiunea", f"{descr}, exhaustiv L2", k, r[k])

    print(f"\n{len(ids)} vectori, cautare exhaustiva (IndexFlatL2), 1 fir de executie\n")
    print(bdm.tabel(randuri))
    g = grafic({"mAP": [(r["dim"], r["mAP"]) for r in randuri]},
               f"{a.descriptor.upper()}: mAP in functie de dimensiune",
               "dimensiune (PCA)", "mAP", Path(__file__).resolve().parents[1] / "grafice"
               / f"dimensiune_{a.descriptor}.png", logx=True)
    if g:
        print(f"\nGrafic: {g}")


if __name__ == "__main__":
    main()
