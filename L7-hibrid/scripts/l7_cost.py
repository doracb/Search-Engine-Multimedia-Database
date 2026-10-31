"""
L7, T4 — Modelul de cost lunar al sistemului vostru (C7, partea 5).

Fiecare componenta vine dintr-un curs:
  stocare continut     (C2)  GB x pret S3 Standard
  transfer             (C2)  (GB livrati - 100 GB gratuit) x pret egress
  server baza + index  (C4, C6)  cea mai mica instanta cu RAM suficient x 730 h
  calcul embeddings    (C5)  imagini noi / debit x pret pe ora
  operare              (toate)  ore de inginer x tarif — completati voi

Volumele de pornire se citesc din baza voastra. Rulati la volumul actual si x100.

    ... l7_cost.py
    ... l7_cost.py --factor 100
    ... l7_cost.py --gb-livrati 600 --imagini-noi 2000 --ore-operare 40 --tarif-ora 25

Preturi: lista AWS us-east-1, toamna 2026, aceleasi ca in C7. Sunt ordine de
marime pentru o decizie, nu o oferta; verificati-le inainte de a le folosi in context de business.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402

ORE_LUNA = 730
PRET = {
    "s3_gb": 0.023,
    "egress_gb": 0.09,
    "egress_gratuit_gb": 100,
}
# Instante cu memorie mare (Graviton, r7g), $/ora on-demand si GB RAM
INSTANTE = [("r7g.large", 16, 0.1071), ("r7g.xlarge", 32, 0.2142), ("r7g.2xlarge", 64, 0.4284),
            ("r7g.4xlarge", 128, 0.8568), ("r7g.8xlarge", 256, 1.7136),
            ("r7g.16xlarge", 512, 3.4272)]
RAM_DE_BAZA_GB = 16        # sistem de operare, PostgreSQL, cache pentru catalog
SUPRAINCARCARE_HNSW = 1.5  # vectori + graf HNSW, fata de vectorii singuri
DEBIT_EMB = 300            # imagini / secunda la calculul embeddings (ipoteza din C7)


def volume_actuale() -> dict:
    with bdm.conectare() as conn:
        n, octeti = conn.execute(
            "SELECT count(*), coalesce(sum(dimensiune_octeti), 0) FROM imagine").fetchone()
        try:
            d = conn.execute("SELECT vector_dims(emb) FROM produs_vector LIMIT 1").fetchone()[0]
        except Exception:
            d = 512
    return {"imagini": int(n), "gb": float(octeti) / 1e9, "dim": int(d)}


def alege_instanta(ram_gb: float):
    for nume, ram, pret in INSTANTE:
        if ram >= ram_gb:
            return nume, ram, pret
    nume, ram, pret = INSTANTE[-1]
    return f"{nume} (insuficient!)", ram, pret


def calculeaza(v: dict, gb_livrati: float, imagini_noi: float, ore_operare: float,
               tarif: float) -> tuple[list[dict], str]:
    vectori_gb = v["imagini"] * v["dim"] * 4 / 1e9
    ram = RAM_DE_BAZA_GB + 2 * vectori_gb * SUPRAINCARCARE_HNSW
    inst, ram_inst, pret_ora = alege_instanta(ram)
    ore_emb = imagini_noi / DEBIT_EMB / 3600
    comp = [
        ("Stocare continut", "C2", f"{v['gb']:,.2f} GB in S3 Standard", v["gb"] * PRET["s3_gb"]),
        ("Transfer", "C2", f"{gb_livrati:,.0f} GB livrati",
         max(gb_livrati - PRET["egress_gratuit_gb"], 0) * PRET["egress_gb"]),
        ("Server baza + index", "C4, C6",
         f"{inst}, {ram_inst} GB (necesar ~{ram:,.1f} GB)", pret_ora * ORE_LUNA),
        ("Calcul embeddings", "C5", f"{imagini_noi:,.0f} imagini noi, {ore_emb:.2f} h CPU",
         ore_emb * pret_ora),
        ("Operare", "toate", f"{ore_operare:g} h x {tarif:g} $", ore_operare * tarif),
    ]
    total = sum(c[3] for c in comp)
    rand = [{"componenta": c[0], "curs": c[1], "ipoteza": c[2], "usd_luna": f"{c[3]:,.2f}",
             "pondere": f"{c[3] / total:.0%}" if total else "-"} for c in comp]
    rand.append({"componenta": "TOTAL", "curs": "", "ipoteza": "", "usd_luna": f"{total:,.2f}",
                 "pondere": "100%"})
    dominant = max(comp, key=lambda c: c[3])[0]
    return rand, dominant


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", type=float, default=1.0, help="multiplica volumul si traficul")
    ap.add_argument("--gb-livrati", type=float, default=600.0)
    ap.add_argument("--imagini-noi", type=float, default=2000.0, help="pe luna")
    ap.add_argument("--ore-operare", type=float, default=0.0)
    ap.add_argument("--tarif-ora", type=float, default=25.0)
    a = ap.parse_args()

    v0 = volume_actuale()
    for f in sorted({1.0, a.factor}):
        v = {"imagini": v0["imagini"] * f, "gb": v0["gb"] * f, "dim": v0["dim"]}
        rand, dom = calculeaza(v, a.gb_livrati * f, a.imagini_noi * f, a.ore_operare, a.tarif_ora)
        print(f"\n=== Volum x{f:g}: {v['imagini']:,.0f} imagini, {v['gb']:,.2f} GB, "
              f"vectori de {v['dim']} dimensiuni ===\n")
        print(bdm.tabel(rand))
        print(f"\nTermenul dominant: {dom}")
        bdm.noteaza("L7", "cost", f"x{f:g}", "usd_luna_total", rand[-1]["usd_luna"].replace(",", ""))
        bdm.noteaza("L7", "cost", f"x{f:g}", "termen_dominant", dom)
    if a.ore_operare == 0:
        print("\nOperarea este 0 in calculul de mai sus. Un sfert de norma de inginer "
              "(~40 h/luna) depaseste de obicei tot restul tabelului: completati --ore-operare.")


if __name__ == "__main__":
    main()
