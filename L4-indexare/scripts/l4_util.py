"""Functii comune scripturilor din L4 (nu se ruleaza direct)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm, cautare  # noqa: E402,F401

N_INTEROGARI_LATENTA = 1000
SEMINTA = 11


def faiss_un_fir():
    import faiss
    faiss.omp_set_num_threads(1)  # latenta pe interogare, comparabila intre laptopuri
    return faiss


def incarca(descriptor: str, pca: int = 0) -> tuple[np.ndarray, np.ndarray, str]:
    """(ids, X, descriere). Cu pca > 0, proiectie PCA invatata pe tot catalogul."""
    fisier = "L5_clip.npz" if descriptor == "clip" else "L3_descriptori.npz"
    ids, X = bdm.incarca_vectori(fisier, "emb" if descriptor == "clip" else descriptor)
    descr = f"{descriptor.upper()} {X.shape[1]}d"
    if pca and pca < X.shape[1]:
        from sklearn.decomposition import PCA
        p = PCA(n_components=pca, random_state=0).fit(X)
        X = p.transform(X).astype(np.float32)
        descr = f"{descriptor.upper()} PCA {pca}d ({p.explained_variance_ratio_.sum():.1%} varianta)"
    return ids, np.ascontiguousarray(X, dtype=np.float32), descr


def esantion_interogari(X: np.ndarray, n: int = N_INTEROGARI_LATENTA) -> np.ndarray:
    rng = np.random.default_rng(SEMINTA)
    return X[rng.choice(len(X), size=min(n, len(X)), replace=False)]


def latente_si_rezultate(cauta, Q: np.ndarray, k: int = 10) -> tuple[list[float], np.ndarray]:
    """Ruleaza interogarile UNA CATE UNA (asa vine traficul real), dupa o incalzire."""
    for q in Q[:20]:
        cauta(q[None, :], k)
    timpi, I = [], np.empty((len(Q), k), dtype=np.int64)
    for j, q in enumerate(Q):
        t0 = time.perf_counter()
        _, idx = cauta(q[None, :], k)
        timpi.append((time.perf_counter() - t0) * 1000)
        I[j] = idx[0]
    return timpi, I


def recall_la_k(I_aprox: np.ndarray, I_exact: np.ndarray, k: int = 10) -> float:
    return float(np.mean([len(set(a[:k]) & set(e[:k])) / k for a, e in zip(I_aprox, I_exact)]))


def map_pe_l3(cauta, ids: np.ndarray, X: np.ndarray, k_lista: int = 100) -> float:
    """mAP pe cele 20 de interogari din L3, cu clasamentul produs de `cauta`."""
    interogari = bdm.incarca_interogari()
    relevanta = bdm.incarca_relevanta()
    poz = {int(v): i for i, v in enumerate(ids)}
    clas = {}
    for q in interogari:
        idp = int(q["id_produs"])
        if idp not in poz:
            continue
        _, idx = cauta(X[poz[idp]][None, :], k_lista + 1)
        clas[q["id_interogare"]] = [int(ids[i]) for i in idx[0] if i >= 0 and int(ids[i]) != idp][:k_lista]
    medii, _ = cautare.evalueaza(clas, relevanta, 10)
    return medii["mAP"]


def grafic(serii: dict[str, list[tuple[float, float]]], titlu: str, x: str, y: str,
           cale: Path, logx: bool = True) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for nume, pct in serii.items():
        ax.plot([p[0] for p in pct], [p[1] for p in pct], "o-", label=nume)
    if logx:
        ax.set_xscale("log")
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title(titlu, fontsize=11)
    ax.grid(alpha=.3)
    ax.legend()
    fig.tight_layout()
    cale.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(cale, dpi=120)
    return cale
