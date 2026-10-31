"""
L4, T1 — Blestemul dimensionalitatii, vazut direct.

Pentru date aleatoare uniforme, cat de departe e cel mai apropiat vecin fata
de cel mai indepartat, pe masura ce creste dimensiunea?

    contrast relativ = (d_max - d_min) / d_min

Cand contrastul tinde la 0, „cel mai apropiat” nu mai inseamna mare lucru, iar
orice index care se bazeaza pe eliminarea regiunilor indepartate nu mai poate
elimina nimic.

    ... l4_contrast.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402

N, Q = 10_000, 50


def main() -> None:
    rng = np.random.default_rng(0)
    randuri = []
    for d in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024):
        X = rng.random((N, d), dtype=np.float32)
        Qm = rng.random((Q, d), dtype=np.float32)
        D = np.sqrt(np.maximum((Qm ** 2).sum(1)[:, None] - 2 * Qm @ X.T
                               + (X ** 2).sum(1)[None, :], 0))
        dmin, dmax = D.min(1), D.max(1)
        c = float(np.mean((dmax - dmin) / dmin))
        randuri.append({"dimensiune": d, "d_min_medie": round(float(dmin.mean()), 3),
                        "d_max_medie": round(float(dmax.mean()), 3),
                        "contrast_relativ": round(c, 3)})
        bdm.noteaza("L4", "contrast", f"uniform, d={d}", "contrast_relativ", round(c, 4))
    print(f"{N} puncte uniforme in [0,1]^d, {Q} interogari\n")
    print(bdm.tabel(randuri))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.plot([r["dimensiune"] for r in randuri], [r["contrast_relativ"] for r in randuri], "o-")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xlabel("dimensiune")
        ax.set_ylabel("contrast relativ")
        ax.grid(alpha=.3)
        fig.tight_layout()
        cale = Path(__file__).resolve().parents[1] / "grafice" / "contrast.png"
        cale.parent.mkdir(exist_ok=True)
        fig.savefig(cale, dpi=120)
        print(f"\nGrafic: {cale}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
