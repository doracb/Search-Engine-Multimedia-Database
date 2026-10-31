"""Verifica A4, masoara procesarea in memorie si genereaza demonstratia."""
import csv
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from comun import cautare

DATE = ROOT / "date"
OUT = ROOT / "rezultate"
DEMO = ROOT / "demo"
OUT.mkdir(parents=True, exist_ok=True)
DEMO.mkdir(parents=True, exist_ok=True)

interogari = json.loads(
    (DATE / "candidati_ficsi.json").read_text(encoding="utf-8")
)["interogari"]
catalog = {
    int(r["id_produs"]): r
    for r in json.loads(
        (DATE / "catalog_comun.json").read_text(encoding="utf-8")
    )
}


def rrf(q):
    scoruri = {}
    for lista in (q["vectori"], q["text_complet"]):
        for rang, produs in enumerate(lista, 1):
            scoruri[produs] = (
                scoruri.get(produs, 0.0) + 1 / (60 + rang)
            )
    return sorted(scoruri, key=lambda p: (-scoruri[p], p))


def aplica(ordine, metoda):
    if metoda == "initial":
        return ordine[:10]

    rezultate = []
    vazute = set()
    for produs in ordine:
        meta = catalog[produs]
        if meta["stoc"] is None or meta["stoc"] <= 0:
            continue

        if metoda == "stoc_diversitate":
            cheie = " ".join(
                re.findall(r"\w+", (meta.get("nume") or "").casefold())
            ) or f"produs_{produs}"
            if cheie in vazute:
                continue
            vazute.add(cheie)

        rezultate.append(produs)
        if len(rezultate) == 10:
            break
    return rezultate


with (DATE / "clasamente_a4.csv").open(
    newline="", encoding="utf-8"
) as f:
    salvate = {}
    for r in csv.DictReader(f):
        cheie = (r["id"], r["metoda"])
        salvate.setdefault(cheie, []).append(
            (int(r["pozitie"]), int(r["id_produs"]))
        )

METODE = ["initial", "stoc", "stoc_diversitate"]
ordini = {q["id"]: rrf(q) for q in interogari}

for q in interogari:
    coloane = []
    for metoda in METODE:
        lista = aplica(ordini[q["id"]], metoda)
        referinta = [
            p for _, p in sorted(
                salvate.get((q["id"], metoda), [])
            )
        ]
        if lista != referinta:
            raise SystemExit(
                f"STOP: diferenta fata de evaluare: {q['id']}, {metoda}"
            )
        coloane.append((metoda, lista))

    cautare.pagina_grila(
        f"A4 — {q['id']}",
        q["text"],
        coloane,
        DEMO / f"{q['id']}.html",
    )

print("Verificare: toate cele 30 de clasamente coincid.")

# Incalzire; timpul include doar selectia din candidatii deja ordonati.
for _ in range(20):
    for ordine in ordini.values():
        for metoda in METODE:
            aplica(ordine, metoda)

randuri = []
for metoda in METODE:
    timpi = []
    for _ in range(200):
        for ordine in ordini.values():
            start = time.perf_counter_ns()
            aplica(ordine, metoda)
            timpi.append((time.perf_counter_ns() - start) / 1_000_000)

    randuri.append({
        "metoda": metoda,
        "masuratori": len(timpi),
        "p50_ms": round(float(np.percentile(timpi, 50)), 6),
        "p95_ms": round(float(np.percentile(timpi, 95)), 6),
        "domeniu": "selectie in memorie; fara CLIP, SQL, RRF sau HTML",
    })

with (OUT / "a4_timpi.csv").open(
    "w", newline="", encoding="utf-8"
) as f:
    w = csv.DictWriter(f, fieldnames=list(randuri[0]))
    w.writeheader()
    w.writerows(randuri)

print("\nmetoda             p50_ms      p95_ms")
for r in randuri:
    print(
        f'{r["metoda"]:<19}'
        f'{r["p50_ms"]:<12.6f}'
        f'{r["p95_ms"]:.6f}'
    )

print("\nGATA: 10 pagini demo si a4_timpi.csv.")
