-- Baze de date multimedia — L7
-- Cautarea hibrida intr-o singura interogare SQL, cu fuziune pe ranguri (RRF).
--
-- Partea vectoriala foloseste aici vectorul IMAGINII unui produs (cautare
-- „similare cu produsul X”), ca interogarea sa poata rula direct din psql.
-- In script (l7_hibrid.py) vectorul vine din TEXT, prin encoderul CLIP.
--
--   docker compose exec postgres psql -U bdm -d bdm \
--     -v produs=15970 -v text="'navy blue shirt'" -f /proiect/L7-hibrid/sql/02_hibrid_rrf.sql

\set k 60

WITH
vect AS (                                   -- lista 1: similaritate vizuala
    SELECT v.id_produs,
           row_number() OVER (ORDER BY v.emb <=> r.emb) AS rang
    FROM produs_vector v,
         (SELECT emb FROM produs_vector WHERE id_produs = :produs) r
    ORDER BY v.emb <=> r.emb
    LIMIT 50
),
txt AS (                                    -- lista 2: potrivire de text
    SELECT p.id_produs,
           row_number() OVER (ORDER BY ts_rank_cd(p.nume_tsv, q) DESC) AS rang
    FROM produs p, websearch_to_tsquery('english', :text) q
    WHERE p.nume_tsv @@ q
    ORDER BY ts_rank_cd(p.nume_tsv, q) DESC
    LIMIT 50
),
fuziune AS (                                -- RRF: suma de 1 / (k + rang)
    SELECT id_produs, sum(1.0 / (:k + rang)) AS scor_rrf,
           min(rang) FILTER (WHERE sursa = 'vect') AS rang_vect,
           min(rang) FILTER (WHERE sursa = 'text') AS rang_text
    FROM (SELECT id_produs, rang, 'vect' AS sursa FROM vect
          UNION ALL
          SELECT id_produs, rang, 'text' FROM txt) u
    GROUP BY id_produs
)
SELECT f.id_produs, p.nume, round(f.scor_rrf, 5) AS scor_rrf, f.rang_vect, f.rang_text
FROM fuziune f JOIN produs p USING (id_produs)
ORDER BY f.scor_rrf DESC
LIMIT 10;
