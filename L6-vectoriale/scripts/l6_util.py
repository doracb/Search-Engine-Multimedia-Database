"""Functii comune scripturilor din L6 (nu se ruleaza direct)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun import bdm  # noqa: E402,F401

COLECTIE = "produse"
HNSW_M = 16
HNSW_EF_CONSTRUCTIE = 64
SEMINTA = 23


def vectori():
    ids, E = bdm.incarca_vectori("L5_clip.npz", "emb")
    return ids, E


def interogari(E: np.ndarray, n: int) -> np.ndarray:
    rng = np.random.default_rng(SEMINTA)
    return E[rng.choice(len(E), size=min(n, len(E)), replace=False)]


def exact_top_k(E: np.ndarray, ids: np.ndarray, q: np.ndarray, k: int = 10,
                masca: np.ndarray | None = None) -> list[int]:
    scor = E @ q
    if masca is not None:
        scor = np.where(masca, scor, -np.inf)
        k = min(k, int(masca.sum()))
    if k == 0:
        return []
    idx = np.argpartition(-scor, k - 1)[:k]
    return [int(ids[i]) for i in idx[np.argsort(-scor[idx])]]


def recall(gasite: list[int], adevar: list[int]) -> float:
    if not adevar:
        return 1.0
    return len(set(gasite) & set(adevar)) / len(adevar)


def pg_cauta(conn, q: np.ndarray, k: int = 10, ef: int = 40, mod: str = "hnsw",
             iterativ: str = "off", unde: str = "", parametri: tuple = ()) -> tuple[float, list[int]]:
    """O cautare in pgvector, intr-o tranzactie proprie, cu setarile date.

    mod = "hnsw"  : forteaza indexul HNSW (pe 20.000 de randuri planificatorul
                    ar alege altfel scanarea completa, care e ieftina)
    mod = "exact" : forteaza scanarea completa + sortare (referinta)
    """
    sql = (f"SELECT id_produs FROM produs_vector {('WHERE ' + unde) if unde else ''} "
           f"ORDER BY emb <=> %s LIMIT {int(k)}")
    with conn.transaction():
        if mod == "hnsw":
            conn.execute("SET LOCAL enable_seqscan = off")
            conn.execute(f"SET LOCAL hnsw.ef_search = {int(ef)}")
            conn.execute(f"SET LOCAL hnsw.iterative_scan = {iterativ}")
        else:
            conn.execute("SET LOCAL enable_indexscan = off")
            conn.execute("SET LOCAL enable_bitmapscan = off")
        t0 = time.perf_counter()
        rez = conn.execute(sql, (*parametri, q)).fetchall()
        ms = (time.perf_counter() - t0) * 1000
    return ms, [r[0] for r in rez]


def qd_cauta(qc, q: np.ndarray, k: int = 10, ef: int | None = 40, exact: bool = False,
             filtru=None) -> tuple[float, list[int]]:
    from qdrant_client.models import SearchParams

    t0 = time.perf_counter()
    rez = qc.query_points(COLECTIE, query=q.tolist(), limit=k, query_filter=filtru,
                          search_params=SearchParams(hnsw_ef=ef, exact=exact)).points
    ms = (time.perf_counter() - t0) * 1000
    return ms, [int(p.id) for p in rez]


def grafic(serii: dict, titlu: str, cale: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for nume, pct in serii.items():
        pct = sorted(pct)
        ax.plot([p[0] for p in pct], [p[1] for p in pct], "o-", label=nume)
    ax.set_xscale("log")
    ax.set_xlabel("latenta p50 pe interogare (ms)")
    ax.set_ylabel("recall@10")
    ax.set_title(titlu, fontsize=11)
    ax.grid(alpha=.3)
    ax.legend()
    fig.tight_layout()
    cale.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(cale, dpi=120)
    return cale
