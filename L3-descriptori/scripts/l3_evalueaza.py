"""
L3, T4-T5 — Evaluarea celor doi descriptori pe setul de relevanta al grupei.

    ... l3_evalueaza.py                         # HSV si LBP, distanta L1
    ... l3_evalueaza.py --metrica chi2          # alta distanta
    ... l3_evalueaza.py --compara q07           # pagina HTML: top-10 HSV fata de top-10 LBP

Foloseste metrici.py scris de voi in T2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm, cautare  # noqa: E402

K = 10


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrica", default="l1", choices=["l1", "l2", "chi2", "cos"])
    ap.add_argument("--compara", metavar="QID")
    a = ap.parse_args()

    interogari = bdm.incarca_interogari()
    relevanta = bdm.incarca_relevanta()
    rezultate, pe_q = [], {}
    clas = {}
    for desc in ("hsv", "lbp"):
        ids, X = bdm.incarca_vectori("L3_descriptori.npz", desc)
        clas[desc] = cautare.clasamente_pentru(X, ids, a.metrica, interogari, k=100)
        medii, detalii = cautare.evalueaza(clas[desc], relevanta, K)
        rezultate.append({"descriptor": desc.upper(), "metrica": a.metrica, **medii})
        pe_q[desc] = {r["interogare"]: r for r in detalii}
        for m, v in medii.items():
            bdm.noteaza("L3", "descriptori clasici", f"{desc.upper()}, {a.metrica}", m, v)

    print(f"\nEvaluare pe {len(interogari)} interogari, {sum(map(len, relevanta.values()))} "
          f"produse relevante in total\n")
    print(bdm.tabel(rezultate))

    tip = {q["id_interogare"]: q["tip_articol"] for q in interogari}
    randuri = []
    for qid in sorted(pe_q["hsv"]):
        h, l = pe_q["hsv"][qid], pe_q["lbp"][qid]
        randuri.append({"interogare": qid, "tip_articol": tip.get(qid, ""), "R": h["R"],
                        "AP_HSV": h["AP"], "AP_LBP": l["AP"],
                        "diferenta": round(h["AP"] - l["AP"], 4)})
    randuri.sort(key=lambda r: -abs(r["diferenta"]))
    print("\nPe interogari, ordonat dupa diferenta absoluta (cele de sus sunt pentru T5):\n")
    print(bdm.tabel(randuri))

    if a.compara:
        q = next((x for x in interogari if x["id_interogare"] == a.compara), None)
        if not q:
            raise SystemExit(f"Interogarea {a.compara} nu exista.")
        rel = relevanta.get(a.compara, set())
        cale = cautare.pagina_grila(
            f"L3 — {a.compara} ({q['tip_articol']}) — HSV fata de LBP, {a.metrica}",
            int(q["id_produs"]),
            [(f"HSV — AP {pe_q['hsv'][a.compara]['AP']}", clas["hsv"][a.compara][:K]),
             (f"LBP — AP {pe_q['lbp'][a.compara]['AP']}", clas["lbp"][a.compara][:K])],
            Path(__file__).resolve().parents[1] / "comparatii" / f"{a.compara}_{a.metrica}.html",
            nota=f"Relevante cunoscute: {len(rel)}. In top-{K}: HSV "
                 f"{sum(x in rel for x in clas['hsv'][a.compara][:K])}, LBP "
                 f"{sum(x in rel for x in clas['lbp'][a.compara][:K])}.")
        print(f"\nPagina de comparatie: {cale}")


if __name__ == "__main__":
    main()
