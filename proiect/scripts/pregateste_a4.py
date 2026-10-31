"""A4 — clasamente fixe: initial, stoc, stoc + nume distincte."""
import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from comun import cautare

DATE = ROOT / "date"
ET = ROOT / "etichete"

fisier = DATE / "candidati_ficsi.json"
amprenta = hashlib.sha256(fisier.read_bytes()).hexdigest()
if amprenta != (DATE / "candidati_ficsi.sha256").read_text().strip():
    raise SystemExit("STOP: candidatii au fost modificati.")

interogari = json.loads(
    fisier.read_text(encoding="utf-8")
)["interogari"]

catalog = {
    int(r["id_produs"]): r
    for r in json.loads(
        (DATE / "catalog_comun.json").read_text(encoding="utf-8")
    )
}

backup = ROOT / (
    "backup_inainte_a4_"
    + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
)
shutil.copytree(ET, backup)


def rrf(liste, k=60):
    scoruri = {}
    for lista in liste:
        for rang, produs in enumerate(lista, 1):
            scoruri[produs] = (
                scoruri.get(produs, 0.0) + 1 / (k + rang)
            )
    return sorted(scoruri, key=lambda p: (-scoruri[p], p))


def nume_normalizat(produs):
    nume = catalog[produs].get("nume") or ""
    cheie = " ".join(re.findall(r"\w+", nume.casefold()))
    return cheie or f"produs_{produs}"


def in_stoc(produs):
    stoc = catalog[produs].get("stoc")
    return stoc is not None and stoc > 0


clasamente = []
total_lipsa = 0

for q in interogari:
    qid = q["id"]
    ordine = rrf([q["vectori"], q["text_complet"]])
    disponibile = [p for p in ordine if in_stoc(p)]

    distincte = []
    vazute = set()
    for produs in disponibile:
        cheie = nume_normalizat(produs)
        if cheie not in vazute:
            vazute.add(cheie)
            distincte.append(produs)

    variante = {
        "initial": ordine[:10],
        "stoc": disponibile[:10],
        "stoc_diversitate": distincte[:10],
    }

    for metoda, lista in variante.items():
        for pozitie, produs in enumerate(lista, 1):
            clasamente.append({
                "id": qid,
                "metoda": metoda,
                "pozitie": pozitie,
                "id_produs": produs,
            })

    cale = ET / f"{qid}.csv"
    with cale.open(newline="", encoding="utf-8-sig") as f:
        randuri = list(csv.DictReader(f))

    existente = {int(r["id_produs"]): r for r in randuri}
    pool = set().union(*[set(lst) for lst in variante.values()])

    for produs in sorted(pool):
        if produs not in existente:
            existente[produs] = {
                "id": qid,
                "id_produs": str(produs),
                "relevant": "",
                "nume": catalog[produs]["nume"],
            }

    with cale.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["id", "id_produs", "relevant", "nume"]
        )
        w.writeheader()
        for produit in sorted(existente):
            w.writerow(existente[produit])

    lipsa = [
        p for p in sorted(pool)
        if existente[p]["relevant"].strip() not in ("0", "1")
    ]
    total_lipsa += len(lipsa)

    if lipsa:
        cautare.pagina_grila(
            f"A4 — {qid}: produse de verificat",
            q["text"],
            [("Produse fara eticheta", lipsa)],
            ET / f"{qid}_a4_de_etichetat.html",
        )

    epuizate = sum(not in_stoc(p) for p in variante["initial"])
    print(
        f"{qid}: epuizate in top10 initial={epuizate}, "
        f"etichete noi lipsa={len(lipsa)}, "
        f"rezultate finale={len(variante['stoc_diversitate'])}"
    )

with (DATE / "clasamente_a4.csv").open(
    "w", newline="", encoding="utf-8"
) as f:
    w = csv.DictWriter(
        f, fieldnames=["id", "metoda", "pozitie", "id_produs"]
    )
    w.writeheader()
    w.writerows(clasamente)

print(f"\nTOTAL ETICHETE NOI LIPSA: {total_lipsa}")
print("GATA: cele trei variante A4 sunt pregatite.")
