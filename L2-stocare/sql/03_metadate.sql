-- Baze de date multimedia — L2, T7
-- Metadatele din L1 (coloana imagine.exif, JSONB) interogate si indexate.
-- Rulati interogarile UNA CATE UNA, din DBeaver/pgAdmin sau psql, si notati
-- rezultatele in fisa. Nu rulati fisierul intreg dintr-o data.
--
--   docker compose exec postgres psql -U bdm -d bdm

-- 1. Ce chei apar si cat de des? (ingestul din L1 a tradus etichetele EXIF
--    numerice in nume: 271 -> Make, 272 -> Model, 306 -> DateTime ...)
SELECT k AS cheie, count(*) AS aparitii
FROM imagine, jsonb_object_keys(exif) AS k
GROUP BY k ORDER BY aparitii DESC LIMIT 15;

-- 2. Valorile cele mai frecvente pentru o cheie aleasa de voi din (1).
--    Inlocuiti 'Make' cu cheia aleasa.
SELECT exif ->> 'Make' AS valoare, count(*) AS n
FROM imagine
WHERE exif ? 'Make'
GROUP BY 1 ORDER BY n DESC LIMIT 10;

-- 3. Cautare prin incluziune (@>). Inlocuiti perechea cu una din (2).
EXPLAIN (ANALYZE, BUFFERS)
SELECT id_produs FROM imagine
WHERE exif @> '{"Make": "Canon"}';

-- 4. Indexul GIN pentru JSONB (operatorul @>)
CREATE INDEX IF NOT EXISTS idx_imagine_exif ON imagine USING gin (exif jsonb_path_ops);
ANALYZE imagine;

-- 5. Aceeasi interogare ca la (3). Ce s-a schimbat in plan si in timp?
EXPLAIN (ANALYZE, BUFFERS)
SELECT id_produs FROM imagine
WHERE exif @> '{"Make": "Canon"}';

-- 6. Metadate tehnice + descriptive in aceeasi interogare:
--    produsele din categoria X ale caror fotografii au fost facute cu aparatul Y.
--    Scrieti-o voi (o singura interogare, cu JOIN intre produs si imagine).

-- 7. Cat ocupa indexul fata de tabel?
SELECT pg_size_pretty(pg_relation_size('idx_imagine_exif')) AS index_gin,
       pg_size_pretty(pg_relation_size('imagine'))          AS tabel;
