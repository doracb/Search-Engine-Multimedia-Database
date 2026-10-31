#!/usr/bin/env python3
"""
Baze de date multimedia — L1
Ingest: catalog CSV -> PostgreSQL, fisiere imagine -> object storage (S3).

Set de date asteptat (Fashion Product Images, Kaggle):
    /date/styles.csv
    /date/images/{id}.jpg

Rulare:
    docker compose exec jupyter python /home/jovyan/proiect/L1-ingest/scripts/ingest.py --limit 20000

Scriptul este idempotent: rulat de doua ori, nu creeaza duplicate.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import boto3
import pandas as pd
import psycopg
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import ExifTags, Image, UnidentifiedImageError
from psycopg.types.json import Jsonb
from tqdm import tqdm

Image.MAX_IMAGE_PIXELS = 200_000_000  # protectie decompression bomb


# ---------------------------------------------------------------------
# Configurare, din variabile de mediu
# ---------------------------------------------------------------------

DSN = (
    f"host={os.environ.get('PGHOST', 'postgres')} "
    f"port={os.environ.get('PGPORT', '5432')} "
    f"user={os.environ.get('PGUSER', 'bdm')} "
    f"password={os.environ.get('PGPASSWORD', 'bdm')} "
    f"dbname={os.environ.get('PGDATABASE', 'bdm')}"
)

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_REGION = os.environ.get("S3_REGION", "garage")
S3_BUCKET = os.environ.get("S3_BUCKET", "imagini")

COLOANE = {
    "id": "id_produs",
    "gender": "gen",
    "masterCategory": "categorie_principala",
    "subCategory": "subcategorie",
    "articleType": "tip_articol",
    "baseColour": "culoare_de_baza",
    "season": "sezon",
    "year": "an",
    "usage": "utilizare",
    "productDisplayName": "nume",
}


@dataclass
class Statistici:
    randuri_csv: int = 0
    randuri_malformate: int = 0
    produse_inserate: int = 0
    imagini_incarcate: int = 0
    sarite_existente: int = 0
    erori: Counter = field(default_factory=Counter)

    def eroare(self, tip: str) -> None:
        self.erori[tip] += 1


# ---------------------------------------------------------------------
# Functii pure: se pot testa separat
# ---------------------------------------------------------------------

def pret_si_stoc(id_produs: int, categorie: str | None) -> tuple[float, int]:
    """Atribute sintetice, DETERMINISTE pe id_produs.

    Determinismul conteaza: in L6 comparam rezultate intre studenti, deci
    toata grupa trebuie sa obtina aceleasi valori. Nu inlocui cu random
    nesemintat.
    """
    r = random.Random(id_produs)
    baza = {
        "Apparel": (80, 450),
        "Footwear": (120, 600),
        "Accessories": (30, 250),
        "Personal Care": (15, 120),
    }.get(categorie or "", (25, 300))
    pret = round(r.uniform(*baza), 2)
    stoc = 0 if r.random() < 0.12 else r.randint(1, 80)
    return pret, stoc


def citeste_catalog(cale: Path, limita: int | None) -> tuple[pd.DataFrame, int]:
    """Citeste styles.csv, tolerand randurile malformate.

    Fisierul contine virgule neescapate in productDisplayName. Le numaram,
    nu le ascundem.
    """
    rele = 0

    def numara(_linie):
        nonlocal rele
        rele += 1
        return None

    df = pd.read_csv(cale, on_bad_lines=numara, engine="python")
    df = df.rename(columns=COLOANE)
    df = df[[c for c in COLOANE.values() if c in df.columns]]
    df = df.dropna(subset=["id_produs", "nume"])
    df["id_produs"] = df["id_produs"].astype(int)
    df["an"] = pd.to_numeric(df["an"], errors="coerce").astype("Int64")
    if limita:
        df = df.head(limita)
    return df, rele


def curata(text: str) -> str:
    """PostgreSQL nu accepta \\u0000 in jsonb. Aparatele foto scriu
    octeti nuli la finalul sirurilor EXIF de lungime fixa."""
    return text.replace("\x00", "").strip()


def analizeaza_imagine(cale: Path) -> dict:
    """Metadate tehnice + hash de continut. Ridica exceptie daca e corupta."""
    octeti = cale.read_bytes()
    with Image.open(io.BytesIO(octeti)) as im:
        im.verify()                      # detecteaza fisierele trunchiate
    with Image.open(io.BytesIO(octeti)) as im:
        exif = {}
        brut = getattr(im, "_getexif", lambda: None)()
        if brut:
            exif = {
                curata(ExifTags.TAGS.get(k, str(k))): curata(str(v))[:200]
                for k, v in brut.items()
            }
        return {
            "octeti": octeti,
            "dimensiune": len(octeti),
            "latime": im.width,
            "inaltime": im.height,
            "format": im.format,
            "mod_culoare": im.mode,
            "sha256": hashlib.sha256(octeti).hexdigest(),
            "exif": exif,
        }


# ---------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------

def client_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        # Garage, ca majoritatea implementarilor locale, cere path-style.
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def jurnal(cur, etapa: str, tip: str, mesaj: str, id_produs: int | None = None) -> None:
    cur.execute(
        "INSERT INTO ingest_eroare (etapa, tip, mesaj, id_produs) VALUES (%s,%s,%s,%s)",
        (etapa, tip, mesaj[:500], id_produs),
    )


def ruleaza(args) -> Statistici:
    st = Statistici()
    date = Path(args.data_dir)
    s3 = client_s3()

    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except ClientError as exc:
        print(f"Bucket-ul '{S3_BUCKET}' nu e accesibil: {exc}", file=sys.stderr)
        sys.exit(2)

    df, st.randuri_malformate = citeste_catalog(date / "styles.csv", args.limit)
    st.randuri_csv = len(df)

    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        if st.randuri_malformate:
            jurnal(cur, "csv", "rand_malformat",
                   f"{st.randuri_malformate} randuri respinse la parsare")
            conn.commit()

        for i, rand in enumerate(tqdm(df.to_dict("records"), desc="ingest")):
            idp = rand["id_produs"]
            try:
                # Fiecare produs in savepoint propriu: o imagine corupta la
                # produsul 300 nu trebuie sa anuleze lotul de 500.
                with conn.transaction():
                    pret, stoc = pret_si_stoc(idp, rand.get("categorie_principala"))
                    cur.execute(
                        """INSERT INTO produs (id_produs, gen, categorie_principala,
                               subcategorie, tip_articol, culoare_de_baza, sezon, an,
                               utilizare, nume, pret, stoc)
                           VALUES (%(id_produs)s, %(gen)s, %(categorie_principala)s,
                               %(subcategorie)s, %(tip_articol)s, %(culoare_de_baza)s,
                               %(sezon)s, %(an)s, %(utilizare)s, %(nume)s, %(pret)s, %(stoc)s)
                           ON CONFLICT (id_produs) DO NOTHING""",
                        {**{k: rand.get(k) for k in COLOANE.values()},
                         "an": None if pd.isna(rand.get("an")) else int(rand["an"]),
                         "pret": pret, "stoc": stoc},
                    )
                    inserat = cur.rowcount == 1

                    fisier = date / "images" / f"{idp}.jpg"
                    if not fisier.exists():
                        jurnal(cur, "imagine", "fisier_lipsa", str(fisier), idp)
                        st.eroare("fisier_lipsa")
                    else:
                        info = analizeaza_imagine(fisier)
                        cheie = f"produse/{idp % 100:02d}/{idp}.jpg"
                        s3.put_object(Bucket=S3_BUCKET, Key=cheie,
                                      Body=info["octeti"], ContentType="image/jpeg")
                        cur.execute(
                            """INSERT INTO imagine (id_produs, bucket, cheie_obiect,
                                   dimensiune_octeti, latime, inaltime, format,
                                   mod_culoare, hash_sha256, exif)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT (bucket, cheie_obiect) DO NOTHING""",
                            (idp, S3_BUCKET, cheie, info["dimensiune"], info["latime"],
                             info["inaltime"], info["format"], info["mod_culoare"],
                             info["sha256"], Jsonb(info["exif"])),
                        )
                        if cur.rowcount == 1:
                            st.imagini_incarcate += 1

                    if inserat:
                        st.produse_inserate += 1
                    else:
                        st.sarite_existente += 1

            except (UnidentifiedImageError, OSError) as exc:
                with conn.cursor() as c2:
                    jurnal(c2, "imagine", "fisier_corupt", str(exc), idp)
                conn.commit()
                st.eroare("fisier_corupt")
            except ClientError as exc:
                with conn.cursor() as c2:
                    jurnal(c2, "s3", "incarcare_esuata", str(exc), idp)
                conn.commit()
                st.eroare("incarcare_esuata")

            if (i + 1) % args.batch_size == 0:
                conn.commit()

        conn.commit()
        cur.close()
    return st


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest catalog multimedia (L1)")
    p.add_argument("--data-dir", default="/date")
    p.add_argument("--limit", type=int, default=20000, help="0 = tot setul")
    p.add_argument("--batch-size", type=int, default=500)
    args = p.parse_args()
    if args.limit == 0:
        args.limit = None

    t0 = time.time()
    st = ruleaza(args)
    durata = time.time() - t0

    print("\n" + "=" * 58)
    print("REZULTAT INGEST")
    print("=" * 58)
    print(f"  randuri CSV valide     : {st.randuri_csv}")
    print(f"  randuri malformate     : {st.randuri_malformate}")
    print(f"  produse inserate       : {st.produse_inserate}")
    print(f"  imagini incarcate      : {st.imagini_incarcate}")
    print(f"  sarite (deja existente): {st.sarite_existente}")
    if st.erori:
        print("  erori:")
        for tip, n in st.erori.most_common():
            print(f"      {tip:.<24} {n}")
    else:
        print("  erori                  : 0")
    print(f"  durata                 : {durata:.1f} s")
    print("=" * 58)
    print("\nUrmatorul pas:")
    print("  docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L1-ingest/sql/02_verificare.sql")


if __name__ == "__main__":
    main()
