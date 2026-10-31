"""C2 — sensibilitatea RRF pe clasamente fixe si etichete comune."""
import csv
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ET = ROOT / "etichete"
OUT = ROOT / "rezultate"
OUT.mkdir(parents=True, exist_ok=True)

VALORI_K = [0, 5, 10, 20, 40, 60, 100, 200]


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
        "backup_inainte_evaluare_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    shutil.copytree(ET, backup)

    vizuale = {
        "h05": {
            5296: 1, 5809: 1, 6144: 1, 7635: 1,
            38317: 1, 38541: 1, 43553: 1,
        },
        "h07": {
            4146: 0, 4147: 0, 4148: 0,
            4149: 1, 4552: 1, 25412: 1,
        },
    }

    for qid, valori in vizuale.items():
        cale = ET / f"{qid}.csv"
        randuri = citeste(cale)
        for r in randuri:
            produs = int(r["id_produs"])
            if produs in valori:
                r["relevant"] = str(valori[produs])
        scrie(cale, randuri)

    etichete = {}
    for cale in sorted(ET.glob("h*.csv")):
        randuri = citeste(cale)
        ids = [int(r["id_produs"]) for r in randuri]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"STOP: ID-uri duplicate in {cale.name}")

        for r in randuri:
            v = r["relevant"].strip()
            if v not in ("0", "1"):
                raise SystemExit(
                    f"STOP: eticheta lipsa/invalida: "
                    f"{cale.stem}, produs {r['id_produs']}"
                )
            etichete[(cale.stem, int(r["id_produs"]))] = int(v)

    grupuri = defaultdict(list)
    for r in citeste(ROOT / "date/clasamente_c2.csv"):
        cheie = (r["id"], r["sistem"], r["k_rrf"])
        grupuri[cheie].append(
            (int(r["pozitie"]), int(r["id_produs"]))
        )

    # Clasamentele goale nu au randuri in CSV.
    # Le includem explicit: zero rezultate inseamna P@10 = 0.
    qids_asteptate = sorted({qid for qid, produs in etichete})
    for qid in qids_asteptate:
        grupuri.setdefault((qid, "vectori", ""), [])
        grupuri.setdefault((qid, "text", ""), [])
        for k in VALORI_K:
            grupuri.setdefault((qid, "hibrid", str(k)), [])

    liste = {}
    detaliat = []
    for cheie, pozitii in sorted(grupuri.items()):
        qid, sistem, k = cheie
        pozitii.sort()
        produse = [p for _, p in pozitii]
        if len(produse) > 10 or len(produse) != len(set(produse)):
            raise SystemExit(f"STOP: clasament invalid: {cheie}")

        lipsa = [
            p for p in produse if (qid, p) not in etichete
        ]
        if lipsa:
            raise SystemExit(
                f"STOP: produse fara eticheta in {cheie}: {lipsa}"
            )

        liste[cheie] = produse
        detaliat.append({
            "id": qid,
            "sistem": sistem,
            "k_rrf": k,
            "rezultate_intoarse": len(produse),
            "P@10": sum(etichete[(qid, p)] for p in produse) / 10,
        })

    qids = sorted({r["id"] for r in detaliat})
    medii = []

    for sistem, k in (
        [("vectori", ""), ("text", "")]
        + [("hibrid", str(k)) for k in VALORI_K]
    ):
        subset = [
            r for r in detaliat
            if r["sistem"] == sistem and r["k_rrf"] == k
        ]
        if len(subset) != len(qids):
            raise SystemExit(
                f"STOP: interogari lipsa pentru {sistem}, k={k}"
            )

        overlap = []
        identice = []
        if sistem == "hibrid":
            for qid in qids:
                curent = liste[(qid, sistem, k)]
                referinta = liste[(qid, sistem, "60")]
                overlap.append(
                    len(set(curent) & set(referinta)) / 10
                )
                identice.append(int(curent == referinta))

        medii.append({
            "sistem": sistem,
            "k_rrf": k,
            "P@10_mediu": round(
                sum(r["P@10"] for r in subset) / len(subset), 4
            ),
            "suprapunere_top10_cu_k60": (
                round(sum(overlap) / len(overlap), 4)
                if overlap else ""
            ),
            "clasamente_identice_cu_k60": (
                sum(identice) if identice else ""
            ),
        })

    scrie(OUT / "c2_pe_interogare.csv", detaliat)
    scrie(OUT / "c2_medii.csv", medii)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hib = [r for r in medii if r["sistem"] == "hibrid"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(
        range(len(hib)),
        [r["P@10_mediu"] for r in hib],
        "o-", label="Hibrid",
    )
    for sistem in ("vectori", "text"):
        med = next(
            r["P@10_mediu"] for r in medii
            if r["sistem"] == sistem
        )
        ax.axhline(med, linestyle="--", label=sistem)

    ax.set_xticks(range(len(hib)), [r["k_rrf"] for r in hib])
    ax.set_xlabel("Constanta RRF k (valori testate)")
    ax.set_ylabel("P@10 mediu")
    ax.set_ylim(0, 1)
    ax.set_title("C2 — sensibilitatea constantei RRF")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "c2_sensibilitate.png", dpi=180)
    plt.close(fig)

    print("Etichete lipsa: 0")
    print(f"Interogari evaluate: {len(qids)}")
    print("\nsistem    k      P@10    suprapunere cu k60")
    for r in medii:
        print(
            f'{r["sistem"]:<9} {str(r["k_rrf"]):<6} '
            f'{r["P@10_mediu"]:<7.3f} '
            f'{r["suprapunere_top10_cu_k60"]}'
        )
    print("\nGATA: rezultate si grafic in proiect/rezultate/")


if __name__ == "__main__":
    main()
