"""Yeni veya metni değişmiş ilanların embedding'ini üretip ml.job_embeddings'e yazar.

Artımlıdır: her ilanın metninden bir hash tutulur; hash ve model aynıysa ilan atlanır.
Kullanım:
    python -m matching.embed_jobs            # sadece eksik/değişmiş ilanlar
    python -m matching.embed_jobs --all      # hepsini yeniden üret
"""

import argparse
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg

from matching.embedder import E5Embedder, Embedder, build_passage, to_pgvector
from scraper import db

log = logging.getLogger("matching.embed_jobs")

SCHEMA_SQL = Path(__file__).parent / "sql" / "001_ml_job_embeddings.sql"

UPSERT_SQL = """
INSERT INTO ml.job_embeddings (job_id, embedding, model_name, content_hash, created_at)
VALUES (%s, %s::vector, %s, %s, now())
ON CONFLICT (job_id) DO UPDATE SET
    embedding    = EXCLUDED.embedding,
    model_name   = EXCLUDED.model_name,
    content_hash = EXCLUDED.content_hash,
    created_at   = now()
"""


@dataclass(frozen=True)
class JobText:
    job_id: int
    text: str

    @property
    def content_hash(self) -> str:
        return hashlib.md5(self.text.encode("utf-8")).hexdigest()


def ensure_schema(conn: psycopg.Connection) -> None:
    """pgvector eklentisini, ml şemasını, tabloyu ve indeksi yoksa oluşturur."""
    db.ensure_schema(conn)  # FK için raw.job_postings önce var olmalı
    conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))


def load_jobs(conn: psycopg.Connection) -> list[JobText]:
    rows = conn.execute(
        "SELECT job_id, title, company_name, description FROM marts.fct_job ORDER BY job_id"
    ).fetchall()
    return [JobText(row[0], build_passage(*row[1:])) for row in rows]


def load_existing(conn: psycopg.Connection) -> dict[int, tuple[str, str]]:
    """job_id → (content_hash, model_name)"""
    rows = conn.execute("SELECT job_id, content_hash, model_name FROM ml.job_embeddings")
    return {job_id: (h, model) for job_id, h, model in rows}


def select_pending(
    jobs: list[JobText], existing: dict[int, tuple[str, str]], model_name: str
) -> list[JobText]:
    """Embedding'i olmayan, metni değişmiş ya da başka modelle üretilmiş ilanlar."""
    return [job for job in jobs if existing.get(job.job_id) != (job.content_hash, model_name)]


def delete_orphans(conn: psycopg.Connection) -> int:
    """Artık fct_job'da olmayan ilanların vektörlerini siler."""
    cur = conn.execute(
        "DELETE FROM ml.job_embeddings e "
        "WHERE NOT EXISTS (SELECT 1 FROM marts.fct_job f WHERE f.job_id = e.job_id)"
    )
    return cur.rowcount


def embed_and_store(
    conn: psycopg.Connection, jobs: list[JobText], embedder: Embedder, batch_size: int = 64
) -> int:
    """İlanları gruplar halinde embed edip yazar; her grup sonunda commit eder."""
    done = 0
    for start in range(0, len(jobs), batch_size):
        batch = jobs[start : start + batch_size]
        vectors = embedder.embed_passages([job.text for job in batch])
        with conn.cursor() as cur:
            cur.executemany(
                UPSERT_SQL,
                [
                    (job.job_id, to_pgvector(vec), embedder.model_name, job.content_hash)
                    for job, vec in zip(batch, vectors, strict=True)
                ],
            )
        conn.commit()
        done += len(batch)
        log.info("%d/%d ilan işlendi", done, len(jobs))
    return done


def run(conn: psycopg.Connection, embedder: Embedder, reembed_all: bool = False) -> int:
    ensure_schema(conn)
    jobs = load_jobs(conn)
    existing = {} if reembed_all else load_existing(conn)
    pending = select_pending(jobs, existing, embedder.model_name)
    log.info("%d ilan var, %d tanesi embed edilecek", len(jobs), len(pending))
    count = embed_and_store(conn, pending, embedder)
    removed = delete_orphans(conn)
    conn.commit()
    if removed:
        log.info("%d eski vektör silindi", removed)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="İlan embedding'lerini üret")
    parser.add_argument("--all", action="store_true", help="tüm ilanları yeniden embed et")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # model indirme isteklerini loglama

    started = time.perf_counter()
    with db.connect() as conn:
        count = run(conn, E5Embedder(), reembed_all=args.all)
    log.info("Bitti: %d ilan, %.1f sn", count, time.perf_counter() - started)


if __name__ == "__main__":
    main()
