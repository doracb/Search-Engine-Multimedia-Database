-- Baze de date multimedia — L6
-- Embeddings CLIP in PostgreSQL, cu pgvector.
--
--   docker compose exec -T postgres psql -U bdm -d bdm -f /proiect/L6-vectoriale/sql/01_vectori.sql

CREATE EXTENSION IF NOT EXISTS vector;

SELECT extversion AS versiune_pgvector FROM pg_extension WHERE extname = 'vector';
-- Experimentul 2 are nevoie de hnsw.iterative_scan, disponibil din pgvector 0.8.0.

BEGIN;

DROP TABLE IF EXISTS produs_vector;

-- Atributele de filtrare sunt COPIATE din produs (denormalizare deliberata):
-- filtrul si vectorul stau in acelasi rand, ca planificatorul sa le poata
-- combina intr-o singura parcurgere a indexului HNSW (C6, partea 03).
-- Pretul de platit: doua copii de sincronizat. Intrebarea 7 din fisa.
CREATE TABLE produs_vector (
    id_produs        integer PRIMARY KEY
                     REFERENCES produs(id_produs) ON DELETE CASCADE,
    tip_articol      text,
    culoare_de_baza  text,
    pret             numeric(8,2),
    stoc             integer,
    model_versiune   text NOT NULL,          -- un model nou = vectori incompatibili (C5)
    emb              vector(512) NOT NULL
);

COMMIT;

-- Indexul HNSW NU se creeaza aici: il construieste l6_incarca.py, ca sa-i
-- masoare timpul. Pentru referinta, comanda este:
--   CREATE INDEX idx_produs_vector_hnsw ON produs_vector
--       USING hnsw (emb vector_cosine_ops) WITH (m = 16, ef_construction = 64);

\echo 'Tabelul produs_vector a fost creat.'
