-- Baze de date multimedia — L2
-- Varianta A: aceleasi imagini, stocate IN baza, ca BYTEA.
-- Varianta B foloseste bucket-ul din L1 (Garage); nu are nevoie de tabel nou,
-- doar de un prefix separat: l2/.
--
-- Rulare:
--   docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L2-stocare/sql/01_bytea.sql

BEGIN;

DROP TABLE IF EXISTS imagine_bytea;

CREATE TABLE imagine_bytea (
    id_produs         integer PRIMARY KEY
                      REFERENCES produs(id_produs) ON DELETE CASCADE,
    continut          bytea   NOT NULL,
    dimensiune_octeti integer NOT NULL,
    creat_la          timestamptz NOT NULL DEFAULT now()
);

-- Strategia implicita pentru bytea este EXTENDED: PostgreSQL incearca intai
-- sa comprime valoarea (pglz sau lz4), apoi o muta in tabela TOAST.
-- Intrebarea 3 din T3 va cere sa o comparati cu EXTERNAL (fara compresie):
--   ALTER TABLE imagine_bytea ALTER COLUMN continut SET STORAGE EXTERNAL;

COMMIT;

\echo 'Tabelul imagine_bytea a fost creat.'
