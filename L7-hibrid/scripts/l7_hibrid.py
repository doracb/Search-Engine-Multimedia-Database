"""
L7, T3 — Cautare hibrida: vectori (CLIP text -> imagine) + text complet (PostgreSQL),
reunite prin RRF. Comparatia pe P@10.

Scrieti interogarile in L7-hibrid/interogari_hibrid.csv (id, text).

    ... l7_hibrid.py --cauta --autor ionescu       # pagini + fisiere de etichetat
    ... l7_hibrid.py --evalueaza --autor ionescu   # P@10: vectori, text, hibrid
    ... l7_hibrid.py --incearca "puma black"       # o cautare rapida
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import bdm, cautare, clip  # noqa: E402
from rrf import fuziune_rrf  # noqa: E402

K = 10
ADANCIME = 50
DIR = Path(__file__).resolve().parents[1]


def lista_vectori(conn, v: np.ndarray) -> list[int]:
    return [r[0] for r in conn.execute(
        f"SELECT id_produs FROM produs_vector ORDER BY emb <=> %s LIMIT {ADANCIME}", (v,)).fetchall()]


def lista_text(conn, text: str) -> list[int]:
    return [r[0] for r in conn.execute(
        f"""SELECT id_produs FROM produs, websearch_to_tsquery('english', %s) q
            WHERE nume_tsv @@ q ORDER BY ts_rank_cd(nume_tsv, q) DESC, id_produs
            LIMIT {ADANCIME}""", (text,)).fetchall()]


def trei_clasamente(conn, text: str, v: np.ndarray, k_rrf: int) -> dict[str, list[int]]:
    lv, lt = lista_vectori(conn, v), lista_text(conn, text)
    hib = [d for d, _ in fuziune_rrf([lv, lt], k=k_rrf)]
    return {"vectori": lv[:K], "text": lt[:K], "hibrid": hib[:K]}


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cauta", action="store_true")
    g.add_argument("--evalueaza", action="store_true")
    g.add_argument("--incearca", metavar="TEXT")
    ap.add_argument("--autor", default="student")
    ap.add_argument("--k", type=int, default=60, help="constanta RRF")
    a = ap.parse_args()

    conn = bdm.conectare()
    if a.incearca:
        c = trei_clasamente(conn, a.incearca, clip.vectori_text([a.incearca])[0], a.k)
        cale = cautare.pagina_grila(f"L7 — „{a.incearca}”", a.incearca,
                                    [(n, c[n]) for n in ("vectori", "text", "hibrid")],
                                    DIR / "hibrid" / "incercare.html")
        for n, l in c.items():
            print(f"{n:<8} {l}")
        print(f"Pagina: {cale}")
        return

    intr = [r for r in bdm.citeste_csv(DIR / "interogari_hibrid.csv") if r["text"].strip()]
    director = DIR / "hibrid" / a.autor

    if a.cauta:
        V = clip.vectori_text([r["text"] for r in intr])
        for r, v in zip(intr, V):
            c = trei_clasamente(conn, r["text"], v, a.k)
            cautare.pagina_grila(f"L7 — {r['id']}", r["text"],
                                 [(f"{n} ({len(c[n])} rezultate)", c[n])
                                  for n in ("vectori", "text", "hibrid")],
                                 director / f"{r['id']}.html")
            pool = sorted(set(c["vectori"]) | set(c["text"]) | set(c["hibrid"]))
            # Etichetele deja puse (de ex. la o rulare anterioara cu alt k) se pastreaza.
            f_csv = director / f"{r['id']}.csv"
            vechi = {int(x["id_produs"]): x["relevant"] for x in bdm.citeste_csv(f_csv)} \
                if f_csv.exists() else {}
            bdm.scrie_csv(f_csv, [{"id": r["id"], "id_produs": p, "relevant": vechi.get(p, "")}
                                  for p in pool])
            bdm.scrie_csv(director / f"{r['id']}_clasamente.csv",
                          [{"sistem": n, "pozitie": i, "id_produs": p}
                           for n, lst in c.items() for i, p in enumerate(lst, 1)])
        print(f"{len(intr)} interogari. Pagini si fisiere de etichetat in {director}/\n"
              "Completeaza `relevant` (1/0), apoi ruleaza --evalueaza.")
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
        rand = {"id": r["id"], "text": r["text"]}
        for n in ("vectori", "text", "hibrid"):
            lst = [int(x["id_produs"]) for x in cl if x["sistem"] == n]
            rand[f"P@10_{n}"] = round(m.precizie_la_k([1 if x in rel else 0 for x in lst], K), 2)
        randuri.append(rand)
    print(bdm.tabel(randuri))
    print()
    for n in ("vectori", "text", "hibrid"):
        med = round(float(np.mean([x[f"P@10_{n}"] for x in randuri])), 3)
        print(f"P@10 mediu, {n:<8}: {med}")
        bdm.noteaza("L7", "hibrid", f"{n}, RRF k={a.k}", "P@10", med)


if __name__ == "__main__":
    main()
