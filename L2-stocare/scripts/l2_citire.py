"""
L2 — Latenta de citire: 200 de citiri aleatoare in fiecare varianta.

Protocolul (fisa L2, T4):
    1. reporniti serviciile  ->  rulati cu --trecere rece
    2. rulati imediat din nou ->  --trecere cald
    3. repetati de 3 ori (--rulare 1, 2, 3)

Rulare:
    docker compose exec jupyter python /home/jovyan/proiect/L2-stocare/scripts/l2_citire.py --trecere rece --rulare 1

Fiecare citire aduce imaginea COMPLETA pana in aplicatie: asta simte
utilizatorul, nu doar localizarea ei.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402

PREFIX = "l2/"


def main() -> None:
    ap = argparse.ArgumentParser(description="L2: latenta de citire")
    ap.add_argument("--citiri", type=int, default=200)
    ap.add_argument("--trecere", required=True, choices=["rece", "cald"])
    ap.add_argument("--rulare", default="1")
    ap.add_argument("--seminta", type=int, default=7)
    a = ap.parse_args()

    with bdm.conectare() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT id_produs FROM imagine_bytea ORDER BY id_produs").fetchall()]
        if not ids:
            raise SystemExit("imagine_bytea e gol: ruleaza intai l2_incarca.py")
        # Aceeasi secventa in ambele variante si in ambele treceri.
        rnd = random.Random(a.seminta)
        secventa = [rnd.choice(ids) for _ in range(a.citiri)]

        timpi_a, octeti_a = [], 0
        for idp in secventa:
            ms, rand = bdm.cronometreaza(
                lambda i: conn.execute(
                    "SELECT continut FROM imagine_bytea WHERE id_produs = %s",
                    (i,)).fetchone(), idp)
            timpi_a.append(ms)
            octeti_a += len(rand[0])

    s3 = bdm.client_s3()
    timpi_b, octeti_b = [], 0
    for idp in secventa:
        ms, corp = bdm.cronometreaza(
            lambda i: s3.get_object(Bucket=bdm.S3_BUCKET,
                                    Key=f"{PREFIX}{i}.jpg")["Body"].read(), idp)
        timpi_b.append(ms)
        octeti_b += len(corp)

    if octeti_a != octeti_b:
        print(f"ATENTIE: variantele au intors volume diferite ({octeti_a} vs {octeti_b}). "
              "Ai rulat l2_incarca.py cu --varianta AB?")

    randuri = [
        {"varianta": "A BYTEA", **bdm.rezumat_latente(timpi_a)},
        {"varianta": "B object storage", **bdm.rezumat_latente(timpi_b)},
    ]
    print(f"\nTrecerea: {a.trecere}, rularea {a.rulare}, {a.citiri} citiri\n")
    print(bdm.tabel(randuri, ["varianta", "n", "p50_ms", "p95_ms", "medie_ms", "max_ms"]))

    for r in randuri:
        cfg = f"{r['varianta']}, {a.trecere}, rulare {a.rulare}"
        bdm.noteaza("L2", "citire", cfg, "p50_ms", r["p50_ms"])
        bdm.noteaza("L2", "citire", cfg, "p95_ms", r["p95_ms"])
    print(f"\nRezultatele au fost adaugate in {bdm.REZULTATE}")


if __name__ == "__main__":
    main()
