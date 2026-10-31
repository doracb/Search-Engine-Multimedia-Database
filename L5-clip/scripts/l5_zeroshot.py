"""
L5, experimentul 3 — Clasificare zero-shot: poate CLIP ghici tipul articolului
fara sa fi vazut vreodata catalogul nostru?

Pentru cele mai frecvente tipuri de articol, fiecare clasa devine un text
(„a photo of a {nume}”); produsul primeste clasa al carei text e cel mai
apropiat de imaginea lui. Comparam cu tip_articol din catalog.

    ... l5_zeroshot.py
    ... l5_zeroshot.py --sablon "a product photo of {}, on a white background"
    ... l5_zeroshot.py --clase 10
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm, clip  # noqa: E402

DIR = Path(__file__).resolve().parents[1]

# Numele din catalog nu sunt intotdeauna engleza naturala ("Tshirts", "Kurtas").
# T5: completati aici traduceri mai bune si comparati acuratetea.
NUME_CLASA: dict[str, str] = {
    "Tshirts": "t-shirt",
    "Casual Shoes": "casual shoes",
    "Sports Shoes": "sports shoes",
    "Formal Shoes": "formal shoes",
    "Kurtas": "kurta",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clase", type=int, default=15)
    ap.add_argument("--sablon", default="a photo of a {}")
    a = ap.parse_args()

    ids, E = bdm.incarca_vectori("L5_clip.npz", "emb")
    with bdm.conectare() as conn:
        clase = [r[0] for r in conn.execute(
            """SELECT tip_articol FROM produs WHERE tip_articol IS NOT NULL
               GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT %s""", (a.clase,)).fetchall()]
        tip = dict(conn.execute("SELECT id_produs, tip_articol FROM produs").fetchall())

    texte = [a.sablon.format(NUME_CLASA.get(c, c)) for c in clase]
    T = clip.vectori_text(texte)
    pastrat = np.array([tip.get(int(i)) in clase for i in ids])
    Ep, ids_p = E[pastrat], ids[pastrat]
    adevar = np.array([clase.index(tip[int(i)]) for i in ids_p])
    pred = (Ep @ T.T).argmax(1)

    acc = float((pred == adevar).mean())
    print(f"Sablon: „{a.sablon}”   ({len(clase)} clase, {len(ids_p)} produse)\n")
    print(f"Acuratete: {acc:.1%}   (la intamplare: {1 / len(clase):.1%}; "
          f"clasa majoritara: {Counter(adevar).most_common(1)[0][1] / len(adevar):.1%})\n")

    M = np.zeros((len(clase), len(clase)), dtype=int)
    for t, p in zip(adevar, pred):
        M[t, p] += 1
    randuri = []
    for i, c in enumerate(clase):
        n = M[i].sum()
        gres = [(clase[j], M[i, j]) for j in np.argsort(-M[i]) if j != i and M[i, j]]
        randuri.append({"clasa": c, "text": texte[i], "produse": n,
                        "corect": f"{M[i, i] / n:.0%}" if n else "-",
                        "confundat_cel_mai_des_cu": f"{gres[0][0]} ({gres[0][1]})" if gres else ""})
    print(bdm.tabel(randuri))

    out = DIR / "zeroshot"
    out.mkdir(exist_ok=True)
    bdm.scrie_csv(out / "matrice_confuzie.csv",
                  [{"adevarat \\ prezis": c, **{clase[j]: int(M[i, j]) for j in range(len(clase))}}
                   for i, c in enumerate(clase)])
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        Mn = M / np.maximum(M.sum(1, keepdims=True), 1)
        fig, ax = plt.subplots(figsize=(8, 7))
        ax.imshow(Mn, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(len(clase)), clase, rotation=60, ha="right", fontsize=8)
        ax.set_yticks(range(len(clase)), clase, fontsize=8)
        ax.set_xlabel("prezis")
        ax.set_ylabel("din catalog")
        ax.set_title(f"Zero-shot: {acc:.1%}", fontsize=11)
        fig.tight_layout()
        fig.savefig(out / "matrice_confuzie.png", dpi=120)
        print(f"\nMatricea de confuzie: {out / 'matrice_confuzie.png'}")
    except ImportError:
        pass
    bdm.noteaza("L5", "3. zero-shot", f"{clip.descriere()}, {len(clase)} clase, '{a.sablon}'",
                "acuratete", round(acc, 4))


if __name__ == "__main__":
    main()
