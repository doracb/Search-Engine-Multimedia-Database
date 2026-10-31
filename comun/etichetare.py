"""
Etichetarea relevantei, folosita in L3, L5 si L7.

Fluxul:
  1. genereaza(...)  -> pentru fiecare interogare, o pagina HTML cu imaginile
                        numerotate si un CSV cu coloana `relevant` de completat
  2. se completeaza CSV-ul (1 = relevant, 0 = nerelevant)

"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

from . import bdm, cautare

REGULA = ("Relevant = un cumparator care a ales produsul-interogare ar accepta acest "
          "produs ca alternativa: acelasi tip de articol SI asemanare vizuala "
          "(culoare, model, stil). Judecati doar ce vedeti, nu ce ati vrea sa gaseasca "
          "sistemul. Imaginile sunt amestecate: pozitia nu spune nimic.")


def genereaza(pool: list[dict], interogari: dict[str, int | str], qids: list[str],
              pereche: str, director: Path, titlu_lab: str) -> list[Path]:
    """pool: randuri {id_interogare, id_produs}; interogari: {qid: id_produs sau text}."""
    pe_q = defaultdict(list)
    for r in pool:
        pe_q[r["id_interogare"]].append(int(r["id_produs"]))
    scrise = []
    for qid in qids:
        if qid not in pe_q:
            print(f"  {qid}: nu exista in pool, sarit")
            continue
        lista = sorted(set(pe_q[qid]))
        random.Random(f"{qid}-{pereche}").shuffle(lista)  # ordine amestecata, reproductibila
        html = cautare.pagina_grila(f"{titlu_lab} — {qid} — pereche {pereche}",
                                    interogari.get(qid), [("Candidati", lista)],
                                    director / f"{qid}_{pereche}.html", nota=REGULA)
        randuri = [{"id_interogare": qid, "pozitie": i, "id_produs": idp, "relevant": ""}
                   for i, idp in enumerate(lista, 1)]
        c = bdm.scrie_csv(director / f"{qid}_{pereche}.csv", randuri)
        scrise += [html, c]
        print(f"  {qid}: {len(lista)} candidati -> {html.name}, {c.name}")
    return scrise


def _kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agrega(director: Path, iesire: Path, dezacord: int = 0,
           anterior: Path | None = None) -> None:
    """Reuneste toate fisierele qXX_pereche.csv dintr-un director.

    O pereche (interogare, produs) judecata de doua perechi de studenti:
      acord      -> eticheta comuna
      dezacord   -> valoarea `dezacord` (implicit 0) si apare in lista de discutat
    `anterior`: un set de relevanta existent, ale carui judecati se pastreaza.
    """
    judecati = defaultdict(list)
    goale = 0
    for f in sorted(director.glob("q*_*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                v = str(r.get("relevant", "")).strip()
                if v not in ("0", "1"):
                    goale += 1
                    continue
                judecati[(r["id_interogare"], int(r["id_produs"]))].append(int(v))

    final = {}
    if anterior and anterior.exists():
        for r in bdm.citeste_csv(anterior):
            final[(r["id_interogare"], int(r["id_produs"]))] = int(r["relevant"])

    perechi_a, perechi_b, dez = [], [], []
    for cheie, v in judecati.items():
        if len(v) >= 2:
            perechi_a.append(v[0])
            perechi_b.append(v[1])
        unu, zero = v.count(1), v.count(0)
        if unu and zero:  # cel putin o judecata diferita
            dez.append({"id_interogare": cheie[0], "id_produs": cheie[1],
                        "judecati": "/".join(map(str, v))})
        if unu > zero:
            final[cheie] = 1
        elif zero > unu:
            final[cheie] = 0
        else:  # egalitate: se decide la discutie
            final[cheie] = dezacord

    randuri = [{"id_interogare": q, "id_produs": p, "relevant": r}
               for (q, p), r in sorted(final.items())]
    bdm.scrie_csv(iesire, randuri)
    dez_cale = iesire.with_name(iesire.stem + "_dezacorduri.csv")
    bdm.scrie_csv(dez_cale, dez, ["id_interogare", "id_produs", "judecati"])

    rel = sum(r["relevant"] for r in randuri)
    print(f"{len(judecati)} perechi (interogare, produs) judecate acum; "
          f"{len(randuri)} in setul final, {rel} relevante.")
    if goale:
        print(f"ATENTIE: {goale} randuri necompletate au fost ignorate.")
    if perechi_a:
        print(f"Judecate de doua ori: {len(perechi_a)}; acord {1 - len(dez) / len(perechi_a):.1%}; "
              f"kappa Cohen = {_kappa(perechi_a, perechi_b):.3f}")
    print(f"Dezacorduri de discutat: {len(dez)} -> {dez_cale}")
    print(f"Setul de relevanta: {iesire}")
