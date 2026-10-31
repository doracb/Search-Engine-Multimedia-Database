"""A4 — precizie, disponibilitate si repetari de nume in top 10."""
import csv
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ET = ROOT / "etichete"
OUT = ROOT / "rezultate"
OUT.mkdir(parents=True, exist_ok=True)
METODE = ["initial", "stoc", "stoc_diversitate"]


def citeste(cale):
    with cale.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def scrie(cale, randuri):
    with cale.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(randuri[0]))
        w.writeheader()
        w.writerows(randuri)


def main():
    backup = ROOT / (
        "backup_etichete_evaluare_a4_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    shutil.copytree(ET, backup)

    corectii = {
        "h02": {25669: 1, 51510: 1},
        "h03": {9173: 0, 44924: 0},
        "h07": {6681: 1},
        "h09": {2626: 0, 45377: 0},
    }

    for qid, valori in corectii.items():
        cale = ET / f"{qid}.csv"
        randuri = citeste(cale)
        for r in randuri:
            produs = int(r["id_produs"])
            if produs in valori:
                r["relevant"] = str(valori[produs])
        scrie(cale, randuri)

    catalog = {
        int(r["id_produs"]): r
        for r in json.loads(
            (ROOT / "date/catalog_comun.json").read_text(
                encoding="utf-8"
            )
        )
    }
    interogari = json.loads(
        (ROOT / "date/candidati_ficsi.json").read_text(
            encoding="utf-8"
        )
    )["interogari"]
    qids = [q["id"] for q in interogari]

    etichete = {}
    for qid in qids:
        for r in citeste(ET / f"{qid}.csv"):
            cheie = (qid, int(r["id_produs"]))
            if cheie in etichete:
                raise SystemExit(f"STOP: eticheta duplicata: {cheie}")
            if r["relevant"].strip() not in ("0", "1"):
                raise SystemExit(f"STOP: eticheta invalida: {cheie}")
            etichete[cheie] = int(r["relevant"])

    grupuri = defaultdict(list)
    for r in citeste(ROOT / "date/clasamente_a4.csv"):
        if r["id"] not in qids or r["metoda"] not in METODE:
            raise SystemExit(f"STOP: clasament necunoscut: {r}")
        grupuri[(r["id"], r["metoda"])].append(
            (int(r["pozitie"]), int(r["id_produs"]))
        )

    detaliat = []
    for qid in qids:
        for metoda in METODE:
            pozitii = sorted(grupuri[(qid, metoda)])
            produse = [p for _, p in pozitii]
            if len(produse) > 10 or len(produse) != len(set(produse)):
                raise SystemExit(f"STOP: clasament invalid: {qid}, {metoda}")
            if [poz for poz, _ in pozitii] != list(
                range(1, len(produse) + 1)
            ):
                raise SystemExit(f"STOP: pozitii invalide: {qid}, {metoda}")

            for p in produse:
                if p not in catalog or (qid, p) not in etichete:
                    raise SystemExit(
                        f"STOP: produs sau eticheta lipsa: {qid}, {p}"
                    )

            disponibile = [
                p for p in produse
                if catalog[p]["stoc"] is not None
                and catalog[p]["stoc"] > 0
            ]
            nume = [
                " ".join(re.findall(
                    r"\w+", (catalog[p].get("nume") or "").casefold()
                )) or f"produs_{p}"
                for p in produse
            ]

            detaliat.append({
                "id": qid,
                "metoda": metoda,
                "rezultate_intoarse": len(produse),
                "P@10": sum(etichete[(qid, p)] for p in produse) / 10,
                "relevante_in_stoc_din_10": (
                    sum(etichete[(qid, p)] for p in disponibile) / 10
                ),
                "epuizate_sau_stoc_necunoscut": (
                    len(produse) - len(disponibile)
                ),
                "repetari_nume": len(nume) - len(set(nume)),
            })

    medii = []
    for metoda in METODE:
        subset = [r for r in detaliat if r["metoda"] == metoda]
        medii.append({
            "metoda": metoda,
            "P@10_mediu": round(
                sum(r["P@10"] for r in subset) / len(subset), 4
            ),
            "relevante_in_stoc_din_10_mediu": round(
                sum(r["relevante_in_stoc_din_10"] for r in subset)
                / len(subset), 4
            ),
            "epuizate_total": sum(
                r["epuizate_sau_stoc_necunoscut"] for r in subset
            ),
            "repetari_nume_total": sum(
                r["repetari_nume"] for r in subset
            ),
            "rezultate_intoarse_total": sum(
                r["rezultate_intoarse"] for r in subset
            ),
        })

    scrie(OUT / "a4_pe_interogare.csv", detaliat)
    scrie(OUT / "a4_medii.csv", medii)

    print("Etichete lipsa: 0")
    print(f"Interogari evaluate: {len(qids)}")
    print(
        "\nmetoda             P@10  relevante+stoc "
        "epuizate repetari rezultate"
    )
    for r in medii:
        print(
            f'{r["metoda"]:<19}'
            f'{r["P@10_mediu"]:<6.3f}'
            f'{r["relevante_in_stoc_din_10_mediu"]:<15.3f}'
            f'{r["epuizate_total"]:<9}'
            f'{r["repetari_nume_total"]:<9}'
            f'{r["rezultate_intoarse_total"]}'
        )
    print("\nGATA: evaluarea A4 este salvata in proiect/rezultate/")


if __name__ == "__main__":
    main()
