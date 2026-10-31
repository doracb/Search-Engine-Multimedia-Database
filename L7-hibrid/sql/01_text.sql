-- Baze de date multimedia — L7
-- Indexul de text complet pe numele produselor (pentru partea „text” a cautarii hibride).
--
--   docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L7-hibrid/sql/01_text.sql

ALTER TABLE produs DROP COLUMN IF EXISTS nume_tsv;

-- Coloana generata: PostgreSQL o tine la zi singur la fiecare INSERT/UPDATE.
-- Configuratia 'english': numele produselor sunt in engleza; „shoes” si „shoe”
-- devin acelasi termen. Marcile („Puma”, „Fastrack”) raman neschimbate.
ALTER TABLE produs ADD COLUMN nume_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(nume, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_produs_nume_tsv ON produs USING gin (nume_tsv);
ANALYZE produs;

\echo ''
\echo '=== Verificare: cele mai frecvente cuvinte din nume (primele = marci si tipuri) ==='
SELECT word AS termen, ndoc AS produse
FROM ts_stat('SELECT nume_tsv FROM produs')
ORDER BY ndoc DESC LIMIT 25;

\echo ''
\echo '=== Exemplu: cautare dupa text ==='
SELECT id_produs, nume, ts_rank_cd(nume_tsv, q) AS scor
FROM produs, websearch_to_tsquery('english', 'puma black shoes') AS q
WHERE nume_tsv @@ q
ORDER BY scor DESC LIMIT 5;
