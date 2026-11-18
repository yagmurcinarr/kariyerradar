"""Upsert entegrasyon testi. Gerçek PostgreSQL gerekir; erişilemezse atlanır.

Test bir transaction içinde çalışır ve sonunda rollback edilir → tabloda iz bırakmaz.
"""

import psycopg
import pytest

from scraper import db
from scraper.models import JobPosting

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    try:
        connection = db.connect()
    except (RuntimeError, psycopg.OperationalError) as exc:
        pytest.skip(f"Veritabanına bağlanılamadı: {exc}")
    try:
        db.ensure_schema(connection)
        yield connection
    finally:
        connection.rollback()
        connection.close()


def make_posting(job_id: str, title: str = "Veri Analisti Stajyeri") -> JobPosting:
    return JobPosting(
        source="pytest",
        source_job_id=job_id,
        url=f"https://example.test/{job_id}",
        title=title,
        company="Örnek A.Ş.",
    )


def count_rows(conn: psycopg.Connection) -> int:
    sql = "SELECT count(*) FROM raw.job_postings WHERE source = 'pytest'"
    return conn.execute(sql).fetchone()[0]


def test_upsert_is_idempotent(conn: psycopg.Connection) -> None:
    postings = [make_posting("1"), make_posting("2")]

    first = db.upsert_postings(conn, postings)
    assert (first.inserted, first.updated) == (2, 0)

    second = db.upsert_postings(conn, postings)  # aynı ilanlar tekrar
    assert (second.inserted, second.updated) == (0, 2)
    assert count_rows(conn) == 2  # tekrar kayıt oluşmadı


def test_upsert_updates_changed_fields(conn: psycopg.Connection) -> None:
    db.upsert_postings(conn, [make_posting("1", title="Eski Başlık")])
    db.upsert_postings(conn, [make_posting("1", title="Yeni Başlık")])
    title = conn.execute(
        "SELECT title FROM raw.job_postings WHERE source = 'pytest' AND source_job_id = '1'"
    ).fetchone()[0]
    assert title == "Yeni Başlık"
