"""
L5, experimentul 2 — Text -> imagine, in romana si in engleza.

Scrieti 10 interogari in L5-clip/interogari_text.csv (id, text_ro, text_en).

    ... l5_text.py --cauta --autor ionescu      # pagini HTML + fisiere de etichetat
    ... l5_text.py --evalueaza --autor ionescu  # P@10 RO fata de EN, dupa etichetare
    ... l5_text.py --incearca "red running shoes"   # o cautare rapida, fara evaluare
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm, cautare, clip  # noqa: E402

K = 10
DIR = Path(__file__).resolve().parents[1]


def top_k(ids: np.ndarray, E: np.ndarray, v: np.ndarray, k: int = K) -> list[int]:
    scor = E @ v  # vectori normalizati: produsul scalar este cosinusul
    idx = np.argpartition(-scor, k)[:k]
    return [int(ids[i]) for i in idx[np.argsort(-scor[idx])]]


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cauta", action="store_true")
    g.add_argument("--evalueaza", action="store_true")
    g.add_argument("--incearca", metavar="TEXT")
    ap.add_argument("--autor", default="student")
    a = ap.parse_args()

    ids, E = bdm.incarca_vectori("L5_clip.npz", "emb")
    if a.incearca:
        rez = top_k(ids, E, clip.vectori_text([a.incearca])[0])
        cale = cautare.pagina_grila(f"L5 — „{a.incearca}”", a.incearca, [("CLIP", rez)],
                                    DIR / "text" / "incercare.html")
        print(f"{rez}\nPagina: {cale}")
        return

    intr = [r for r in bdm.citeste_csv(DIR / "interogari_text.csv")
            if r["text_ro"].strip() and r["text_en"].strip()]
    if len(intr) < 10:
        print(f"ATENTIE: doar {len(intr)} interogari completate din 10 in interogari_text.csv")
    director = DIR / "text" / a.autor

    if a.cauta:
        V_ro = clip.vectori_text([r["text_ro"] for r in intr])
        V_en = clip.vectori_text([r["text_en"] for r in intr])
        for r, vr, ve in zip(intr, V_ro, V_en):
            ro, en = top_k(ids, E, vr), top_k(ids, E, ve)
            cautare.pagina_grila(f"L5 text — {r['id']}", f"{r['text_ro']}  /  {r['text_en']}",
                                 [(f"RO: {r['text_ro']}", ro), (f"EN: {r['text_en']}", en)],
                                 director / f"{r['id']}.html")
            pool = sorted(set(ro) | set(en))
            f_csv = director / f"{r['id']}.csv"  # etichetele existente se pastreaza
            vechi = {int(x["id_produs"]): x["relevant"] for x in bdm.citeste_csv(f_csv)} \
                if f_csv.exists() else {}
            bdm.scrie_csv(f_csv, [{"id": r["id"], "id_produs": p, "relevant": vechi.get(p, "")}
                                  for p in pool])
            bdm.scrie_csv(director / f"{r['id']}_clasamente.csv",
                          [{"limba": l, "pozitie": i, "id_produs": p}
                           for l, lst in (("ro", ro), ("en", en)) for i, p in enumerate(lst, 1)])
        print(f"Pagini si fisiere de etichetat in {director}/\n"
              "Completeaza `relevant` (1/0) in fiecare tXX.csv, apoi ruleaza --evalueaza.")
        return

    m = cautare.modul_metrici()
    randuri = []
    for r in intr:
        et = bdm.citeste_csv(director / f"{r['id']}.csv")
        goale = sum(1 for x in et if str(x["relevant"]).strip() not in ("0", "1"))
        if goale:
            print(f"ATENTIE: {r['id']} are {goale} randuri neetichetate (contate ca nerelevante)")
        rel = {int(x["id_produs"]) for x in et if str(x["relevant"]).strip() == "1"}
        cl = bdm.citeste_csv(director / f"{r['id']}_clasamente.csv")
        p = {}
        for limba in ("ro", "en"):
            lst = [int(x["id_produs"]) for x in cl if x["limba"] == limba]
            p[limba] = m.precizie_la_k([1 if x in rel else 0 for x in lst], K)
        randuri.append({"id": r["id"], "text_en": r["text_en"],
                        "P@10_RO": round(p["ro"], 2), "P@10_EN": round(p["en"], 2)})
    print(bdm.tabel(randuri))
    for limba in ("RO", "EN"):
        med = round(float(np.mean([x[f"P@10_{limba}"] for x in randuri])), 3)
        print(f"P@10 mediu {limba}: {med}")
        bdm.noteaza("L5", "2. text->imagine", f"{clip.descriere()}, {limba}", "P@10", med)


if __name__ == "__main__":
    main()
