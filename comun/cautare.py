"""
Cautare exhaustiva, evaluare si pagini de etichetare, folosite din L3 pana in L7.

Toate functiile lucreaza pe matrice numpy (N x d) si pe vectorul de
identificatori `ids` (N,), in aceeasi ordine.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

import numpy as np

from . import bdm

# ---------------------------------------------------------------------
# Metrici de evaluare. Din L4 se foloseste comun/metrici.py, publicat de
# profesor dupa L3; in L3 fiecare student foloseste propria implementare.
# ---------------------------------------------------------------------


def modul_metrici():
    try:
        from . import metrici  # versiunea publicata dupa L3
        return metrici
    except ImportError:
        import importlib.util
        cale = bdm.PROIECT / "L3-descriptori" / "scripts" / "metrici.py"
        spec = importlib.util.spec_from_file_location("metrici", cale)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m


# ---------------------------------------------------------------------
# Distante
# ---------------------------------------------------------------------

def distante(Q: np.ndarray, X: np.ndarray, metrica: str) -> np.ndarray:
    """Distantele de la fiecare interogare (q x d) la tot catalogul (N x d).

    Intoarce o matrice q x N; valori mai mici = mai asemanator.
    """
    Q = np.atleast_2d(Q).astype(np.float32)
    if metrica == "l2":
        d = (Q ** 2).sum(1)[:, None] - 2 * Q @ X.T + (X ** 2).sum(1)[None, :]
        return np.sqrt(np.maximum(d, 0))
    if metrica == "cos":
        Qn = Q / (np.linalg.norm(Q, axis=1, keepdims=True) + 1e-12)
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
        return 1.0 - Qn @ Xn.T
    if metrica == "l1":
        return np.stack([np.abs(X - q).sum(1) for q in Q])
    if metrica == "chi2":
        return np.stack([((X - q) ** 2 / (X + q + 1e-10)).sum(1) * 0.5 for q in Q])
    raise ValueError(f"metrica necunoscuta: {metrica}")


def clasament(q_vec: np.ndarray, X: np.ndarray, ids: np.ndarray, metrica: str,
              k: int = 100, exclude: int | None = None) -> list[int]:
    """Primii k identificatori, in ordinea asemanarii. Exclude interogarea insasi."""
    d = distante(q_vec, X, metrica)[0]
    m = min(k + 1, len(d))
    cand = np.argpartition(d, m - 1)[:m]
    cand = cand[np.argsort(d[cand], kind="stable")]
    rez = [int(ids[i]) for i in cand if exclude is None or int(ids[i]) != exclude]
    return rez[:k]


# ---------------------------------------------------------------------
# Evaluarea pe setul din L3
# ---------------------------------------------------------------------

def evalueaza(clasamente: dict[str, list[int]], relevanta: dict[str, set[int]],
              k: int = 10) -> tuple[dict, list[dict]]:
    """clasamente: {id_interogare: [id_produs, ...]}.

    Intoarce (medii, pe_interogare). Produsele nejudecate se considera
    nerelevante: exact limita pooling-ului discutata in C3.
    """
    m = modul_metrici()
    pe_q = []
    for qid, lista in sorted(clasamente.items()):
        rel = relevanta.get(qid, set())
        etichete = [1 if x in rel else 0 for x in lista]
        R = len(rel)
        pe_q.append({
            "interogare": qid,
            "R": R,
            f"P@{k}": round(m.precizie_la_k(etichete, k), 4),
            f"R@{k}": round(m.rapel_la_k(etichete, k, R), 4),
            "AP": round(m.precizie_medie(etichete, R), 4),
        })
    # Interogarile fara niciun produs relevant cunoscut nu pot fi evaluate
    # (AP nedefinit): se exclud din medii, ca in TREC, si se raporteaza.
    valide = [r for r in pe_q if r["R"] > 0]
    n = max(len(valide), 1)
    medii = {
        f"P@{k}": round(sum(r[f"P@{k}"] for r in valide) / n, 4),
        f"R@{k}": round(sum(r[f"R@{k}"] for r in valide) / n, 4),
        "mAP": round(sum(r["AP"] for r in valide) / n, 4),
        "interogari": len(valide),
    }
    return medii, pe_q


def clasamente_pentru(X: np.ndarray, ids: np.ndarray, metrica: str,
                      interogari: list[dict], k: int = 100) -> dict[str, list[int]]:
    poz = {int(v): i for i, v in enumerate(ids)}
    rez = {}
    for q in interogari:
        idp = int(q["id_produs"])
        if idp not in poz:
            continue
        rez[q["id_interogare"]] = clasament(X[poz[idp]], X, ids, metrica, k, exclude=idp)
    return rez


# ---------------------------------------------------------------------
# Pagini HTML de vizualizare si etichetare (imagini incluse in pagina)
# ---------------------------------------------------------------------

def _img_b64(idp: int) -> str:
    cale = bdm.IMAGINI / f"{idp}.jpg"
    if not cale.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(cale.read_bytes()).decode()


def pagina_grila(titlu: str, interogare: int | str | None,
                 randuri: list[tuple[str, list[int]]], cale: Path,
                 nota: str = "") -> Path:
    """Scrie o pagina HTML cu una sau mai multe grile numerotate.

    interogare: id_produs (se afiseaza imaginea) sau text (se afiseaza textul).
    randuri: [(eticheta grilei, [id_produs, ...]), ...]
    """
    css = """
    body{font-family:system-ui,sans-serif;margin:16px;background:#fafafa;color:#222}
    h1{font-size:20px} h2{font-size:16px;margin:22px 0 8px}
    .q{display:flex;gap:16px;align-items:center;padding:12px;background:#fff;border:1px solid #ddd;border-radius:8px}
    .q img{height:200px} .q .t{font-size:22px;font-weight:600}
    .g{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
    .c{background:#fff;border:1px solid #ddd;border-radius:6px;padding:6px;text-align:center}
    .c img{height:150px;max-width:100%;object-fit:contain}
    .n{font-weight:700;font-size:15px} .id{color:#777;font-size:12px}
    .nota{color:#555;max-width:900px}
    """
    p = [f"<!doctype html><meta charset='utf-8'><title>{html.escape(titlu)}</title>",
         f"<style>{css}</style><h1>{html.escape(titlu)}</h1>"]
    if nota:
        p.append(f"<p class='nota'>{html.escape(nota)}</p>")
    if isinstance(interogare, int):
        p.append(f"<div class='q'><img src='{_img_b64(interogare)}'>"
                 f"<div><div class='t'>Interogarea</div><div class='id'>produs {interogare}</div></div></div>")
    elif interogare:
        p.append(f"<div class='q'><div class='t'>„{html.escape(str(interogare))}”</div></div>")
    for eticheta, lista in randuri:
        p.append(f"<h2>{html.escape(eticheta)}</h2><div class='g'>")
        for poz, idp in enumerate(lista, 1):
            p.append(f"<div class='c'><div class='n'>{poz}</div><img src='{_img_b64(idp)}'>"
                     f"<div class='id'>{idp}</div></div>")
        p.append("</div>")
    cale.parent.mkdir(parents=True, exist_ok=True)
    cale.write_text("\n".join(p), encoding="utf-8")
    return cale
