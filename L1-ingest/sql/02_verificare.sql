-- Baze de date multimedia — L1
-- Interogari de verificare si de analiza a calitatii datelor.
-- Studentii CITESC rezultatele si raspund la intrebarile din T4.
--
--   docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L1-ingest/sql/02_verificare.sql

\echo ''
\echo '=== 1. Cate produse si cate imagini au intrat ==='
SELECT
    (SELECT count(*) FROM produs)  AS produse,
    (SELECT count(*) FROM imagine) AS imagini,
    (SELECT count(*) FROM produs p
      WHERE NOT EXISTS (SELECT 1 FROM imagine i WHERE i.id_produs = p.id_produs))
        AS produse_fara_imagine;

\echo ''
\echo '=== 2. Distributia pe categorii ==='
SELECT categorie_principala,
       count(*) AS produse,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS procent
FROM produs
GROUP BY categorie_principala
ORDER BY produse DESC;

\echo ''
\echo '=== 3. Erori de ingest, pe tipuri ==='
SELECT etapa, tip, count(*) AS aparitii
FROM ingest_eroare
GROUP BY etapa, tip
ORDER BY aparitii DESC;

\echo ''
\echo '=== 4. Acoperirea metadatelor descriptive (procent NULL) ==='
SELECT
    round(100.0 * count(*) FILTER (WHERE gen IS NULL)             / count(*), 1) AS gen,
    round(100.0 * count(*) FILTER (WHERE sezon IS NULL)           / count(*), 1) AS sezon,
    round(100.0 * count(*) FILTER (WHERE an IS NULL)              / count(*), 1) AS an,
    round(100.0 * count(*) FILTER (WHERE utilizare IS NULL)       / count(*), 1) AS utilizare,
    round(100.0 * count(*) FILTER (WHERE culoare_de_baza IS NULL) / count(*), 1) AS culoare
FROM produs;

\echo ''
\echo '=== 5. Metadate tehnice: dimensiuni, formate, moduri de culoare ==='
SELECT format,
       mod_culoare,
       count(*) AS imagini,
       min(latime) || 'x' || min(inaltime) AS minim,
       max(latime) || 'x' || max(inaltime) AS maxim,
       pg_size_pretty(avg(dimensiune_octeti)::bigint) AS dimensiune_medie
FROM imagine
GROUP BY format, mod_culoare
ORDER BY imagini DESC;

\echo ''
\echo '=== 6. Acoperirea EXIF ==='
SELECT count(*) FILTER (WHERE exif IS NOT NULL AND exif <> '{}'::jsonb) AS cu_exif,
       count(*)                                                          AS total,
       round(100.0 * count(*) FILTER (WHERE exif IS NOT NULL AND exif <> '{}'::jsonb)
             / count(*), 2)                                              AS procent
FROM imagine;

\echo ''
\echo '=== 7. Duplicate exacte de continut (acelasi SHA-256) ==='
SELECT hash_sha256, count(*) AS aparitii
FROM imagine
GROUP BY hash_sha256
HAVING count(*) > 1
ORDER BY aparitii DESC
LIMIT 10;

\echo ''
\echo '=== 8. Dimensiunea pe obiecte a bazei (punct de plecare pentru L2) ==='
SELECT relname AS obiect,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS dimensiune
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC;

\echo ''
\echo '=== 9. Atribute sintetice (se folosesc in L6) ==='
SELECT round(min(pret), 2) AS pret_min,
       round(avg(pret), 2) AS pret_mediu,
       round(max(pret), 2) AS pret_max,
       count(*) FILTER (WHERE stoc = 0) AS produse_epuizate
FROM produs;
