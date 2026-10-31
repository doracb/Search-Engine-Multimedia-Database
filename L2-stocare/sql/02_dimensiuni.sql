-- Baze de date multimedia — L2
-- Cat ocupa varianta A in baza si unde anume.
--
--   docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L2-stocare/sql/02_dimensiuni.sql

\echo ''
\echo '=== 1. Tabelul imagine_bytea: tabela principala, TOAST, indecsi ==='
SELECT
    pg_size_pretty(pg_relation_size('imagine_bytea'))                AS tabela_principala,
    pg_size_pretty(pg_relation_size(c.reltoastrelid))                AS tabela_toast,
    pg_size_pretty(pg_indexes_size('imagine_bytea'))                 AS indecsi,
    pg_size_pretty(pg_total_relation_size('imagine_bytea'))          AS total,
    pg_total_relation_size('imagine_bytea')                          AS total_octeti
FROM pg_class c
WHERE c.relname = 'imagine_bytea';

\echo ''
\echo '=== 2. Brut fata de stocat: a comprimat PostgreSQL ceva? ==='
-- octet_length = lungimea logica; pg_column_size = cat ocupa efectiv valoarea
SELECT
    count(*)                                        AS imagini,
    pg_size_pretty(sum(octet_length(continut)))     AS brut,
    pg_size_pretty(sum(pg_column_size(continut)))   AS stocat,
    round(sum(pg_column_size(continut))::numeric
          / nullif(sum(octet_length(continut)), 0), 4) AS raport_stocat_brut
FROM imagine_bytea;

\echo ''
\echo '=== 3. Strategia de stocare a coloanei continut ==='
SELECT attname,
       CASE attstorage WHEN 'p' THEN 'PLAIN' WHEN 'e' THEN 'EXTERNAL'
                       WHEN 'm' THEN 'MAIN'  WHEN 'x' THEN 'EXTENDED' END AS strategie
FROM pg_attribute
WHERE attrelid = 'imagine_bytea'::regclass AND attname = 'continut';

\echo ''
\echo '=== 4. Pentru comparatie: tabelul imagine din L1 (doar referinte) ==='
SELECT pg_size_pretty(pg_total_relation_size('imagine')) AS total_imagine,
       (SELECT count(*) FROM imagine)                     AS randuri;

\echo ''
\echo '=== 5. Toata baza ==='
SELECT pg_size_pretty(pg_database_size(current_database())) AS baza_bdm;
