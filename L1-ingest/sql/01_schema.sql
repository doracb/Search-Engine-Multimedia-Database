-- Baze de date multimedia — L1
-- Schema de referinta. 
--
-- Rulare:
--   docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L1-ingest/sql/01_schema.sql

BEGIN;

DROP TABLE IF EXISTS ingest_eroare CASCADE;
DROP TABLE IF EXISTS imagine CASCADE;
DROP TABLE IF EXISTS produs CASCADE;

-- ---------------------------------------------------------------------
-- Datele structurate ale catalogului. Nimic media aici.
-- ---------------------------------------------------------------------
CREATE TABLE produs (
    id_produs           integer PRIMARY KEY,
    gen                 text,
    categorie_principala text,
    subcategorie        text,
    tip_articol         text,
    culoare_de_baza     text,
    sezon               text,
    an                  smallint,
    utilizare           text,
    nume                text NOT NULL,
    -- Atribute sintetice, deterministe pe id_produs: servesc filtrarea
    -- cu predicate din L6. Vezi pret_si_stoc() din ingest.py.
    pret                numeric(8,2),
    stoc                integer,
    creat_la            timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Continutul media: aici stau REFERINTA si metadatele, nu octetii.
-- Decizia asta e subiectul argumentului din T5 si al masuratorii din L2.
-- ---------------------------------------------------------------------
CREATE TABLE imagine (
    id                bigserial PRIMARY KEY,
    id_produs         integer NOT NULL
                      REFERENCES produs(id_produs) ON DELETE CASCADE,
    bucket            text NOT NULL,
    cheie_obiect      text NOT NULL,
    dimensiune_octeti bigint NOT NULL,
    latime            integer,
    inaltime          integer,
    format            text,
    mod_culoare       text,     -- RGB, CMYK, L... relevant abia in L3
    hash_sha256       char(64) NOT NULL,
    exif              jsonb,    -- de obicei gol: vezi intrebarea 7 din T4
    creat_la          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (bucket, cheie_obiect)
);

-- ---------------------------------------------------------------------
-- Jurnal de erori. Este jurnal, nu stare: se acumuleaza intre rulari.
-- ---------------------------------------------------------------------
CREATE TABLE ingest_eroare (
    id        bigserial PRIMARY KEY,
    etapa     text NOT NULL,      -- csv | imagine | s3 | bd
    tip       text NOT NULL,      -- rand_malformat | fisier_lipsa | ...
    mesaj     text,
    id_produs integer,
    creat_la  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_produs_categorie  ON produs (categorie_principala, subcategorie);
CREATE INDEX idx_produs_an         ON produs (an);
CREATE INDEX idx_imagine_produs    ON imagine (id_produs);
CREATE INDEX idx_imagine_hash      ON imagine (hash_sha256);
CREATE INDEX idx_eroare_tip        ON ingest_eroare (etapa, tip);

COMMIT;

\echo 'Schema creata.'
