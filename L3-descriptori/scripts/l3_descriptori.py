"""
L3 — Descriptorii vizuali clasici din C3, calculati pe tot catalogul.

  HSV  : histograma de culoare 8 (H) x 4 (S) x 4 (V) = 128 de valori, normalizata L1
  LBP  : histograma de textura, LBP uniform (P = 8, R = 1)  = 59 de valori, normalizata L1


    ... l3_descriptori.py                      # tot catalogul (profesor, ~2-5 min)
    ... l3_descriptori.py --verifica           # T1: dimensiuni si normalizare
    ... l3_descriptori.py --demo 1163 1164     # descriptorii a doua produse, pe ecran
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402

BINS_HSV = (8, 4, 4)
LBP_P, LBP_R = 8, 1
LATURA = 128  # imaginile se aduc la aceeasi dimensiune inainte de LBP


def histograma_hsv(img: Image.Image) -> np.ndarray:
    hsv = np.asarray(img.convert("RGB").convert("HSV"), dtype=np.uint8).reshape(-1, 3)
    h = (hsv[:, 0].astype(np.int32) * BINS_HSV[0]) // 256
    s = (hsv[:, 1].astype(np.int32) * BINS_HSV[1]) // 256
    v = (hsv[:, 2].astype(np.int32) * BINS_HSV[2]) // 256
    idx = (h * BINS_HSV[1] + s) * BINS_HSV[2] + v
    hist = np.bincount(idx, minlength=int(np.prod(BINS_HSV))).astype(np.float32)
    return hist / max(hist.sum(), 1.0)


def histograma_lbp(img: Image.Image) -> np.ndarray:
    from skimage.feature import local_binary_pattern

    g = np.asarray(img.convert("L").resize((LATURA, LATURA)), dtype=np.uint8)
    cod = local_binary_pattern(g, LBP_P, LBP_R, method="nri_uniform")
    n_bins = LBP_P * (LBP_P - 1) + 3  # 59 pentru P = 8
    hist = np.bincount(cod.astype(np.int32).ravel(), minlength=n_bins).astype(np.float32)
    return hist / max(hist.sum(), 1.0)


def descriptori(cale: Path) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(cale) as img:
        img.load()
        return histograma_hsv(img), histograma_lbp(img)


def produse_catalog() -> list[int]:
    with bdm.conectare() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT id_produs FROM imagine ORDER BY id_produs").fetchall()]


def calculeaza(iesire: Path) -> None:
    ids = produse_catalog()
    print(f"{len(ids)} produse cu imagine. Calculez descriptorii...")
    ok_ids, H, L = [], [], []
    t0 = time.perf_counter()
    for i, idp in enumerate(ids, 1):
        cale = bdm.IMAGINI / f"{idp}.jpg"
        try:
            h, l = descriptori(cale)
        except Exception as e:  # fisier lipsa sau corupt: il sarim, ca in L1
            print(f"  sarit {idp}: {e}")
            continue
        ok_ids.append(idp)
        H.append(h)
        L.append(l)
        if i % 2000 == 0:
            print(f"  {i}/{len(ids)}  ({i / (time.perf_counter() - t0):.0f} imagini/s)")
    iesire.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(iesire, ids=np.array(ok_ids, dtype=np.int64),
                        hsv=np.stack(H), lbp=np.stack(L))
    print(f"Scris {iesire}: {len(ok_ids)} produse, "
          f"{time.perf_counter() - t0:.0f} s")


def verifica() -> None:
    for cheie in ("hsv", "lbp"):
        ids, X = bdm.incarca_vectori("L3_descriptori.npz", cheie)
        sume = X.sum(1)
        print(f"{cheie.upper()}: {X.shape[0]} produse x {X.shape[1]} valori, "
              f"{X.nbytes / 1e6:.1f} MB in memorie")
        print(f"   suma pe rand: min {sume.min():.4f}, max {sume.max():.4f}")
        print(f"   valori negative: {(X < 0).sum()},  randuri nule: {(sume == 0).sum()}")
        top = np.argsort(-X.mean(0))[:3]
        print(f"   cele mai incarcate 3 componente (media pe catalog): "
              + ", ".join(f"#{j}: {X[:, j].mean():.3f}" for j in top))
    print("\nPentru HSV, componenta #j corespunde lui "
          "h = j // 16, s = (j // 4) % 4, v = j % 4 (fiecare in intervale egale).")


def demo(ids: list[int]) -> None:
    np.set_printoptions(precision=3, suppress=True, linewidth=110)
    for idp in ids:
        h, l = descriptori(bdm.IMAGINI / f"{idp}.jpg")
        print(f"\nprodus {idp}\n HSV ({h.size}):\n{h}\n LBP ({l.size}):\n{l}")


def main() -> None:
    ap = argparse.ArgumentParser(description="L3: descriptori HSV si LBP")
    ap.add_argument("--verifica", action="store_true")
    ap.add_argument("--demo", nargs="*", type=int)
    ap.add_argument("--iesire", type=Path, default=bdm.ARTEFACTE / "L3_descriptori.npz")
    a = ap.parse_args()
    if a.verifica:
        verifica()
    elif a.demo:
        demo(a.demo)
    else:
        calculeaza(a.iesire)


if __name__ == "__main__":
    main()
