"""
L5, experimentele 1 si 4 — Imagine -> imagine: CLIP fata de descriptorii din L3.

    ... l5_imagine.py                          # mAP, P@10: HSV, LBP, CLIP
    ... l5_imagine.py --eticheteaza --pereche p03 --interogari q04 q11
                                               # pooling: candidatii noi adusi de CLIP
    ... l5_imagine.py --compara q07            # pagina: top-10 CLIP fata de top-10 HSV / LBP

Acelasi set de interogari, aceeasi evaluare ca in L3: singura variabila noua
este reprezentarea (C5).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm, cautare, etichetare  # noqa: E402

K = 10
ADANCIME_POOL = 20
DESCRIPTORI = [("HSV", "L3_descriptori.npz", "hsv", "l1"),
               ("LBP", "L3_descriptori.npz", "lbp", "l1"),
               ("CLIP", "L5_clip.npz", "emb", "cos")]
DIR = Path(__file__).resolve().parents[1]


def clasamente(interogari, adancime=100):
    rez = {}
    for nume, fisier, cheie, metrica in DESCRIPTORI:
        ids, X = bdm.incarca_vectori(fisier, cheie)
        rez[nume] = cautare.clasamente_pentru(X, ids, metrica, interogari, adancime)
    return rez


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eticheteaza", action="store_true")
    ap.add_argument("--pereche")
    ap.add_argument("--interogari", nargs="+")
    ap.add_argument("--compara", metavar="QID")
    a = ap.parse_args()

    interogari = bdm.incarca_interogari()
    clas = clasamente(interogari)

    if a.eticheteaza:
        if not (a.pereche and a.interogari):
            raise SystemExit("--eticheteaza cere --pereche si --interogari")
        judecate = bdm.judecati("L3_relevanta.csv")
        pool = [{"id_interogare": q, "id_produs": p}
                for q in a.interogari for p in clas["CLIP"].get(q, [])[:ADANCIME_POOL]
                if p not in judecate.get(q, set())]
        print(f"{len(pool)} candidati noi (adusi de CLIP, nejudecati in L3):")
        etichetare.genereaza(pool, {q["id_interogare"]: int(q["id_produs"]) for q in interogari},
                             a.interogari, a.pereche, DIR / "etichetare", "L5 pooling")
        print("\nCompleteaza coloana `relevant` si trimite fisierele .csv profesorului.")
        return

    relevanta = bdm.incarca_relevanta()
    sursa = "L5_relevanta.csv" if (bdm.ARTEFACTE / "L5_relevanta.csv").exists() else "L3_relevanta.csv"
    rezultate, ap_q = [], {}
    for nume, *_ in DESCRIPTORI:
        medii, detalii = cautare.evalueaza(clas[nume], relevanta, K)
        rezultate.append({"reprezentare": nume, **medii})
        ap_q[nume] = {r["interogare"]: r["AP"] for r in detalii}
        for m, v in medii.items():
            bdm.noteaza("L5", "1. imagine->imagine", f"{nume}, relevanta {sursa}", m, v)

    judecate = bdm.judecati()
    nejudecate = sum(1 for q, l in clas["CLIP"].items() for p in l[:K] if p not in judecate.get(q, set()))
    print(f"\nSetul de relevanta: {sursa}\n")
    print(bdm.tabel(rezultate))
    print(f"\nIn top-{K} CLIP sunt {nejudecate} produse NEJUDECATE (considerate nerelevante). "
          "Vezi avertismentul despre pooling din fisa.")

    tip = {q["id_interogare"]: q["tip_articol"] for q in interogari}
    randuri = []
    for qid in sorted(ap_q["CLIP"]):
        cel_mai_bun = max(("HSV", "LBP"), key=lambda n: ap_q[n][qid])
        randuri.append({"interogare": qid, "tip_articol": tip.get(qid, ""),
                        "AP_CLIP": ap_q["CLIP"][qid], "AP_HSV": ap_q["HSV"][qid],
                        "AP_LBP": ap_q["LBP"][qid],
                        "CLIP_minus_clasic": round(ap_q["CLIP"][qid] - ap_q[cel_mai_bun][qid], 4)})
    randuri.sort(key=lambda r: r["CLIP_minus_clasic"])
    print("\nPe interogari; primele randuri = unde CLIP pierde (experimentul 4):\n")
    print(bdm.tabel(randuri))

    if a.compara:
        q = next((x for x in interogari if x["id_interogare"] == a.compara), None)
        if not q:
            raise SystemExit(f"Interogarea {a.compara} nu exista.")
        cale = cautare.pagina_grila(
            f"L5 — {a.compara} ({q['tip_articol']})", int(q["id_produs"]),
            [(f"{n} — AP {ap_q[n][a.compara]}", clas[n][a.compara][:K]) for n, *_ in DESCRIPTORI],
            DIR / "comparatii" / f"{a.compara}.html")
        print(f"\nPagina de comparatie: {cale}")


if __name__ == "__main__":
    main()
