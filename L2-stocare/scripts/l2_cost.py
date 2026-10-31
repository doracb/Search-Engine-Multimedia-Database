"""
L2 — Costul lunar de stocare, dupa modelul din C2 (partea 5).

    A. in baza:  GB x pret SSD x 2 (replica)  +  4 backup-uri complete in S3
    C. object storage, totul in Standard
    C. object storage cu niveluri: 30% Standard, 70% Standard-IA, + citiri din IA

Volumul de pornire este catalogul vostru real (tabelul imagine din L1).
Preturile sunt cele din curs: preturi de lista AWS us-east-1, toamna 2026.
Sunt ordine de marime pentru o decizie, nu o oferta.

Rulare:
    docker compose exec jupyter python /home/jovyan/proiect/L2-stocare/scripts/l2_cost.py
    ... --gb 30000            # alt volum, in GB
    ... --crestere 0.20 --ani 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402

PRET = {
    "ssd_gb": 0.08,          # stocare bloc SSD, $/GB-luna (ordin de marime)
    "s3_standard_gb": 0.023,
    "s3_ia_gb": 0.0125,
    "s3_ia_citire_gb": 0.01,
}
REPLICI_A = 2
BACKUPURI_A = 4
PONDERE_STANDARD = 0.30


def costuri(gb: float, gb_cititi_ia: float) -> dict:
    a = gb * PRET["ssd_gb"] * REPLICI_A + BACKUPURI_A * gb * PRET["s3_standard_gb"]
    c_std = gb * PRET["s3_standard_gb"]
    c_niv = (gb * PONDERE_STANDARD * PRET["s3_standard_gb"]
             + gb * (1 - PONDERE_STANDARD) * PRET["s3_ia_gb"]
             + gb_cititi_ia * PRET["s3_ia_citire_gb"])
    return {"A_in_baza": a, "C_standard": c_std, "C_niveluri": c_niv}


def volum_catalog() -> tuple[float, int]:
    with bdm.conectare() as conn:
        octeti, n = conn.execute(
            "SELECT coalesce(sum(dimensiune_octeti), 0), count(*) FROM imagine").fetchone()
    return float(octeti) / 1e9, int(n)


def main() -> None:
    ap = argparse.ArgumentParser(description="L2: cost lunar de stocare")
    ap.add_argument("--gb", type=float, help="volum in GB (implicit: catalogul din L1)")
    ap.add_argument("--citit-ia", type=float, default=0.0,
                    help="GB cititi lunar din nivelul IA (implicit 0; la 30 TB cursul foloseste ~1000)")
    ap.add_argument("--crestere", type=float, default=0.20, help="crestere anuala a volumului")
    ap.add_argument("--ani", type=int, default=3)
    a = ap.parse_args()

    if a.gb is None:
        gb, n = volum_catalog()
        print(f"Catalogul din L1: {n} imagini, {gb:.3f} GB")
    else:
        gb = a.gb
        print(f"Volum dat: {gb:,.1f} GB")

    print(f"\nPreturi folosite ($/GB-luna): {PRET}\n")
    randuri = []
    for an in range(a.ani + 1):
        v = gb * (1 + a.crestere) ** an
        c = costuri(v, a.citit_ia * (1 + a.crestere) ** an)
        randuri.append({"an": an, "GB": f"{v:,.3f}" if v < 10 else f"{v:,.1f}",
                        **{k: f"{x:,.4f}" if x < 1 else f"{x:,.2f}" for k, x in c.items()}})
    print("Cost lunar, $ (an 0 = astazi):\n")
    print(bdm.tabel(randuri, ["an", "GB", "A_in_baza", "C_standard", "C_niveluri"]))

    c0 = costuri(gb, a.citit_ia)
    print(f"\nRaport A / C_standard: {c0['A_in_baza'] / c0['C_standard']:.1f}x")
    print("Nu apare in tabel: transferul (egress), identic in A si C, si timpul de "
          "backup / restaurare al variantei A.")
    for k, x in c0.items():
        bdm.noteaza("L2", "cost", f"{k}, {gb:.3f} GB", "usd_pe_luna", round(x, 4))


if __name__ == "__main__":
    main()
