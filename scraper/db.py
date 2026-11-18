"""PostgreSQL erişimi: bağlantı, şema kurulumu ve `raw.job_postings` tablosuna upsert."""

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from scraper.models import JobPosting

SCHEMA_SQL = Path(__file__).parent / "sql" / "001_raw_job_postings.sql"

# ON CONFLICT: (source, source_job_id) zaten varsa yeni satır açma, mevcut satırı güncelle.
# RETURNING (xmax = 0): PostgreSQL'de yeni eklenen satırda xmax 0'dır;
# böylece satırın eklendiğini mi güncellendiğini mi anlarız.
UPSERT_SQL = """
INSERT INTO raw.job_postings
    (source, source_job_id, url, title, company, location_raw,
     job_type_raw, description, posted_at, scraped_at)
VALUES
    (%(source)s, %(source_job_id)s, %(url)s, %(title)s, %(company)s, %(location_raw)s,
     %(job_type_raw)s, %(description)s, %(posted_at)s, %(scraped_at)s)
ON CONFLICT (source, source_job_id) DO UPDATE SET
    url          = EXCLUDED.url,
    title        = EXCLUDED.title,
    company      = EXCLUDED.company,
    location_raw = EXCLUDED.location_raw,
    job_type_raw = EXCLUDED.job_type_raw,
    description  = EXCLUDED.description,
    posted_at    = EXCLUDED.posted_at,
    scraped_at   = EXCLUDED.scraped_at   -- "en son ne zaman görüldü"
RETURNING (xmax = 0) AS inserted
"""


@dataclass
class UpsertResult:
    inserted: int = 0
    updated: int = 0


def get_database_url() -> str:
    """DATABASE_URL'i ortamdan (veya .env dosyasından) okur."""
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL tanımlı değil. .env.example'ı .env olarak kopyalayın.")
    return url


def connect(url: str | None = None) -> psycopg.Connection:
    """Yeni bir veritabanı bağlantısı açar."""
    return psycopg.connect(url or get_database_url())


def ensure_schema(conn: psycopg.Connection) -> None:
    """raw şemasını ve tabloyu yoksa oluşturur."""
    conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))


def upsert_postings(conn: psycopg.Connection, postings: list[JobPosting]) -> UpsertResult:
    """İlanları tabloya yazar. Commit'i çağıran yapar (testlerde rollback edebilmek için)."""
    result = UpsertResult()
    with conn.cursor() as cur:
        for posting in postings:
            cur.execute(UPSERT_SQL, posting.model_dump())
            (inserted,) = cur.fetchone()
            if inserted:
                result.inserted += 1
            else:
                result.updated += 1
    return result
