"""
Functii comune pentru laboratoarele L2-L7.

Se importa din orice script de laborator astfel:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from comun import bdm

Toate setarile vin din variabilele de mediu ale containerului Jupyter
(aceleasi ca in L1), deci nu trebuie modificat nimic aici.
"""

from __future__ import annotations

import csv
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------
# Cai
# ---------------------------------------------------------------------

PROIECT = Path(os.environ.get("BDM_PROIECT", Path(__file__).resolve().parents[1]))
DATE = Path(os.environ.get("BDM_DATE", "/date"))
IMAGINI = DATE / "images"
# Fisierele precalculate publicate de profesor (descriptori, embeddings,
# interogari, relevanta). Se copiaza aici; nu se versioneaza.
ARTEFACTE = Path(os.environ.get("BDM_ARTEFACTE", PROIECT / "artefacte"))
# Tabelul de rezultate acumulat pe tot modulul: scheletul raportului.
REZULTATE = Path(os.environ.get("BDM_REZULTATE", PROIECT / "rezultate.csv"))

DSN = (
    f"host={os.environ.get('PGHOST', 'postgres')} "
    f"port={os.environ.get('PGPORT', '5432')} "
    f"user={os.environ.get('PGUSER', 'bdm')} "
    f"password={os.environ.get('PGPASSWORD', 'bdm')} "
    f"dbname={os.environ.get('PGDATABASE', 'bdm')}"
)
S3_BUCKET = os.environ.get("S3_BUCKET", "imagini")


# ---------------------------------------------------------------------
# Conexiuni
# ---------------------------------------------------------------------

def conectare(autocommit: bool = True):
    """Conexiune psycopg 3, cu tipul vector inregistrat daca exista extensia."""
    import psycopg

    conn = psycopg.connect(DSN, autocommit=autocommit)
    # Fara instructiuni pregatite pe server: altfel, dupa cateva executii,
    # PostgreSQL trece la un plan generic, care poate ocoli indexul HNSW si
    # ar falsifica masuratorile din L6.
    conn.prepare_threshold = None
    try:
        from pgvector.psycopg import register_vector
        register_vector(conn)
    except Exception:  # extensia nu e inca creata: L2-L5 nu au nevoie de ea
        pass
    return conn


def client_s3():
    import boto3
    from botocore.client import Config

    lipsa = [v for v in ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY")
             if not os.environ.get(v)]
    if lipsa:
        raise SystemExit(
            f"Lipsesc variabilele {', '.join(lipsa)}. Verifica .env si "
            "recreeaza containerul jupyter cu --force-recreate (vezi L1).")
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION", "garage"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def client_qdrant():
    from qdrant_client import QdrantClient

    url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    if url == ":memory:":  # folosit doar la testarea scripturilor
        return QdrantClient(":memory:")
    return QdrantClient(url=url, timeout=120)


# ---------------------------------------------------------------------
# Masurarea timpului
# ---------------------------------------------------------------------

def cronometreaza(functie, *args, **kwargs) -> tuple[float, object]:
    """Ruleaza functia o data; intoarce (milisecunde, rezultat)."""
    t0 = time.perf_counter()
    r = functie(*args, **kwargs)
    return (time.perf_counter() - t0) * 1000.0, r


def percentila(valori, p: float) -> float:
    return float(np.percentile(np.asarray(valori, dtype=float), p))


def rezumat_latente(ms) -> dict:
    """p50 si p95 (milisecunde). Media o dam doar ca sa vedeti cat minte."""
    ms = list(ms)
    return {
        "n": len(ms),
        "p50_ms": round(percentila(ms, 50), 3),
        "p95_ms": round(percentila(ms, 95), 3),
        "medie_ms": round(statistics.fmean(ms), 3),
        "max_ms": round(max(ms), 3),
    }


# ---------------------------------------------------------------------
# Artefacte precalculate
# ---------------------------------------------------------------------

def artefact(nume: str) -> Path:
    cale = ARTEFACTE / nume
    if not cale.exists():
        raise SystemExit(
            f"Lipseste {cale}.\nFisierul este publicat de profesor; copiaza-l in "
            f"{ARTEFACTE}/ (vezi sectiunea 'Inainte de laborator' din fisa).")
    return cale


def incarca_vectori(nume_fisier: str, cheie: str) -> tuple[np.ndarray, np.ndarray]:
    """Intoarce (ids, matrice) dintr-un .npz publicat (ex. L3_descriptori.npz)."""
    z = np.load(artefact(nume_fisier), allow_pickle=False)
    if cheie not in z.files:
        raise SystemExit(f"{nume_fisier} nu contine '{cheie}'. Chei: {z.files}")
    return z["ids"].astype(np.int64), np.ascontiguousarray(z[cheie], dtype=np.float32)


def citeste_csv(cale: Path) -> list[dict]:
    with open(cale, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scrie_csv(cale: Path, randuri: list[dict], coloane: list[str] | None = None) -> Path:
    cale.parent.mkdir(parents=True, exist_ok=True)
    coloane = coloane or (list(randuri[0].keys()) if randuri else [])
    with open(cale, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=coloane)
        w.writeheader()
        w.writerows(randuri)
    return cale


def incarca_interogari() -> list[dict]:
    """Cele 20 de interogari din L3: id_interogare, id_produs, tip_articol."""
    return citeste_csv(artefact("L3_interogari.csv"))


def incarca_relevanta(nume: str | None = None) -> dict[str, set[int]]:
    """{id_interogare: {id_produs relevante}}.

    Foloseste cea mai recenta versiune publicata: L5_relevanta.csv (dupa
    completarea pool-ului cu CLIP) daca exista, altfel L3_relevanta.csv.
    """
    if nume is None:
        nume = "L5_relevanta.csv" if (ARTEFACTE / "L5_relevanta.csv").exists() \
            else "L3_relevanta.csv"
    rel: dict[str, set[int]] = {}
    for r in citeste_csv(artefact(nume)):
        if str(r["relevant"]).strip() == "1":
            rel.setdefault(r["id_interogare"], set()).add(int(r["id_produs"]))
    return rel


def judecati(nume: str | None = None) -> dict[str, set[int]]:
    """{id_interogare: {id_produs judecate}}, relevante sau nu (pentru pooling)."""
    if nume is None:
        nume = "L5_relevanta.csv" if (ARTEFACTE / "L5_relevanta.csv").exists() \
            else "L3_relevanta.csv"
    j: dict[str, set[int]] = {}
    for r in citeste_csv(artefact(nume)):
        j.setdefault(r["id_interogare"], set()).add(int(r["id_produs"]))
    return j


# ---------------------------------------------------------------------
# Tabelul de rezultate al proiectului
# ---------------------------------------------------------------------

COLOANE_REZULTATE = ["data", "laborator", "experiment", "configuratie", "metrica", "valoare"]


def noteaza(laborator: str, experiment: str, configuratie: str, metrica: str,
            valoare) -> None:
    """Adauga un rand in rezultate.csv. Fiecare script il apeleaza singur.

    Fisierul se acumuleaza de la L2 la L7 si devine tabelul de rezultate
    din raportul de proiect. Nu-l stergeti intre laboratoare.
    """
    nou = not REZULTATE.exists()
    REZULTATE.parent.mkdir(parents=True, exist_ok=True)
    with open(REZULTATE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nou:
            w.writerow(COLOANE_REZULTATE)
        w.writerow([datetime.now().isoformat(timespec="seconds"), laborator,
                    experiment, configuratie, metrica, valoare])


def tabel(randuri: list[dict], coloane: list[str] | None = None) -> str:
    """Tabel text simplu, aliniat, pentru afisare in terminal."""
    if not randuri:
        return "(gol)"
    coloane = coloane or list(randuri[0].keys())
    s = [[str(r.get(c, "")) for c in coloane] for r in randuri]
    lat = [max(len(c), *(len(x[i]) for x in s)) for i, c in enumerate(coloane)]
    linii = ["  ".join(c.ljust(lat[i]) for i, c in enumerate(coloane)),
             "  ".join("-" * l for l in lat)]
    linii += ["  ".join(x[i].ljust(lat[i]) for i in range(len(coloane))) for x in s]
    return "\n".join(linii)
