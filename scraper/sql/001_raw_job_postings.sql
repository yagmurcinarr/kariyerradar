-- Ham ilan tablosu (CLAUDE.md §4). Tekrar çalıştırılabilir (IF NOT EXISTS).
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.job_postings (
    id            bigserial PRIMARY KEY,
    source        text        NOT NULL,
    source_job_id text        NOT NULL,
    url           text        NOT NULL,
    title         text        NOT NULL,
    company       text        NOT NULL,
    location_raw  text,
    job_type_raw  text,
    description   text,
    posted_at     timestamptz,
    scraped_at    timestamptz NOT NULL DEFAULT now(),
    -- Aynı kaynaktaki aynı ilan ikinci kez eklenemez → upsert bu kısıta dayanır
    CONSTRAINT uq_job_postings_source_job UNIQUE (source, source_job_id)
);
