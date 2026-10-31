"""
L3, T3 — Paginile de etichetare pentru interogarile primite de perechea voastra.

    ... l3_eticheteaza.py --pereche p03 --interogari q04 q11 q16

Scrie in L3-descriptori/etichetare/:
    q04_p03.html   imaginea-interogare si candidatii, numerotati
    q04_p03.csv    coloana `relevant` de completat cu 1 sau 0

Dupa completare, trimiteti fisierele .csv  (nu si .html).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm, etichetare  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pereche", required=True, help="ex. p03, din repartizarea de pe tabla")
    ap.add_argument("--interogari", nargs="+", required=True)
    a = ap.parse_args()

    interogari = {q["id_interogare"]: int(q["id_produs"]) for q in bdm.incarca_interogari()}
    pool = bdm.citeste_csv(bdm.artefact("L3_pool.csv"))
    director = Path(__file__).resolve().parents[1] / "etichetare"
    etichetare.genereaza(pool, interogari, a.interogari, a.pereche, director, "L3")
    print(f"\nDeschide paginile .html din JupyterLab (click dreapta > Open in New Browser Tab)\n"
          f"si completeaza fisierele .csv (click dreapta > Open With > Editor).\n\n"
          f"Regula de relevanta:\n  {etichetare.REGULA}")


if __name__ == "__main__":
    main()
