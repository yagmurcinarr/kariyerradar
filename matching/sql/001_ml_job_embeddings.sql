-- İlan vektörleri (CLAUDE.md §4). Tekrar çalıştırılabilir (IF NOT EXISTS).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ml;

-- job_id, raw.job_postings.id'ye bağlıdır (marts.fct_job.job_id ile aynı değer).
-- marts.fct_job'a FK verilmez: dbt her çalıştırmada o tabloyu yeniden oluşturur.
CREATE TABLE IF NOT EXISTS ml.job_embeddings (
    job_id       bigint PRIMARY KEY REFERENCES raw.job_postings (id) ON DELETE CASCADE,
    embedding    vector(384) NOT NULL,
    model_name   text        NOT NULL,
    content_hash text        NOT NULL,  -- metin değişince yeniden embed etmek için
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Cosine mesafe için HNSW indeksi (embedding'ler normalize; <=> operatörü kullanılır)
CREATE INDEX IF NOT EXISTS ix_job_embeddings_hnsw
    ON ml.job_embeddings USING hnsw (embedding vector_cosine_ops);
