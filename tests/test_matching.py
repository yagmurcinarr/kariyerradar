"""Embedding ve vektör arama testleri.

Gerçek model yerine sahte bir embedder kullanılır (torch gerekmez, hızlı ve deterministik).
Veritabanı testleri transaction içinde çalışır ve rollback edilir.
"""

import psycopg
import pytest

from matching import embed_jobs, retriever
from matching.embed_jobs import JobText, select_pending
from matching.embedder import EMBEDDING_DIM, MAX_PASSAGE_CHARS, build_passage, to_pgvector
from matching.retriever import JobMatch, rerank
from matching.skills import extract_skills
from scraper import db


def one_hot(i: int) -> list[float]:
    """i. boyutu 1 olan birim vektör: farklı i'ler birbirine dik (benzerlik 0)."""
    vec = [0.0] * EMBEDDING_DIM
    vec[i] = 1.0
    return vec


class FakeEmbedder:
    """Metinde geçen anahtar kelimeye göre sabit bir yön döndürür."""

    model_name = "fake-model"
    KEYWORDS = ("python", "unity", "muhasebe")

    def __init__(self) -> None:
        self.calls = 0

    def _vec(self, text: str) -> list[float]:
        text = text.lower()
        for i, word in enumerate(self.KEYWORDS):
            if word in text:
                return one_hot(i)
        return one_hot(len(self.KEYWORDS))

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.calls += len(texts)
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


# --- Saf fonksiyonlar ----------------------------------------------------------


def test_build_passage_joins_and_truncates() -> None:
    assert build_passage(" Veri Analisti ", "Trendyol", None) == "Veri Analisti\nTrendyol"
    assert len(build_passage("Başlık", "Firma", "x" * 5000)) == MAX_PASSAGE_CHARS


def test_to_pgvector_format() -> None:
    assert to_pgvector([0.5, -1.0, 0.0]) == "[0.5,-1,0]"


def test_select_pending_skips_unchanged() -> None:
    a, b, c = JobText(1, "aynı"), JobText(2, "yeni"), JobText(3, "değişti")
    existing = {
        1: (a.content_hash, "m"),  # değişmemiş → atla
        3: ("eski-hash", "m"),  # metin değişmiş → yeniden
    }
    assert select_pending([a, b, c], existing, "m") == [b, c]
    # Model değişirse hepsi yeniden üretilir
    assert select_pending([a], existing, "baska-model") == [a]


def test_extract_skills_uses_word_boundaries_and_turkish_folding() -> None:
    found = extract_skills("Python ve SQL ile VERİ ANALİZİ yaptım")
    assert found >= {"Python", "SQL", "Veri Analizi"}
    assert "SQL" not in extract_skills("MySQL deneyimi")  # kelime sınırı
    assert "Java" not in extract_skills("JavaScript biliyorum")
    assert "Excel" not in extract_skills("We excel at teamwork")  # case_sensitive beceri


def job(job_id: int, vector_score: float, skills: tuple[str, ...]) -> JobMatch:
    return JobMatch(job_id, "t", "c", "İstanbul", "staj", "u", vector_score, skills)


def test_rerank_combines_vector_and_skill_overlap() -> None:
    candidates = [
        job(1, 0.83, ()),  # vektörde en yakın ama becerisi yok
        job(2, 0.82, ("Python", "SQL", "Tableau")),
        job(3, 0.80, ("Python",)),
    ]
    result = rerank(candidates, {"Python", "SQL"}, k=3)
    assert [m.job_id for m in result] == [2, 1, 3]
    assert result[0].matching_skills == ("Python", "SQL")
    assert result[0].missing_skills == ("Tableau",)


def test_rerank_without_query_skills_keeps_vector_order() -> None:
    candidates = [job(1, 0.70, ("SQL",)), job(2, 0.90, ())]
    assert [m.job_id for m in rerank(candidates, set(), k=2)] == [2, 1]
    assert rerank([], {"SQL"}, k=5) == []


# --- Veritabanı ------------------------------------------------------------------


@pytest.fixture
def conn():
    try:
        connection = db.connect()
    except (RuntimeError, psycopg.OperationalError) as exc:
        pytest.skip(f"Veritabanına bağlanılamadı: {exc}")
    try:
        embed_jobs.ensure_schema(connection)
        # CI'da dbt çalışmadığı için fct_job yoksa test içinde geçici olarak oluştur
        connection.execute("CREATE SCHEMA IF NOT EXISTS marts")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS marts.fct_job (job_id bigint, title text, "
            "company_name text, city text, job_type text, url text, description text)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS marts.dim_skill (skill_id text, skill_name text)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS marts.bridge_job_skill (job_id bigint, skill_id text)"
        )
        connection.execute("DELETE FROM marts.fct_job")  # rollback ile geri gelir
        yield connection
    finally:
        connection.rollback()
        connection.close()


def add_job(conn: psycopg.Connection, title: str, city: str, job_type: str) -> int:
    job_id = conn.execute(
        "INSERT INTO raw.job_postings (source, source_job_id, url, title, company) "
        "VALUES ('pytest', %s, 'https://example.test', %s, 'Örnek') RETURNING id",
        (title, title),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO marts.fct_job (job_id, title, company_name, city, job_type, url, description) "
        "VALUES (%s, %s, 'Örnek', %s, %s, 'https://example.test', '')",
        (job_id, title, city, job_type),
    )
    return job_id


@pytest.mark.integration
def test_embed_is_incremental_and_search_ranks(conn: psycopg.Connection, monkeypatch) -> None:
    monkeypatch.setattr(conn, "commit", lambda: None)  # testte commit etme; rollback edilecek
    py = add_job(conn, "Python Geliştirici Stajyer", "Denizli", "staj")
    unity = add_job(conn, "Unity Oyun Geliştirici", "İstanbul", "junior")
    acc = add_job(conn, "Muhasebe Uzmanı", "Denizli", "diger")

    embedder = FakeEmbedder()
    assert embed_jobs.run(conn, embedder) == 3
    assert embed_jobs.run(conn, embedder) == 0  # ikinci çalıştırma: değişen yok
    assert embedder.calls == 3

    query = embedder.embed_query("python bilen stajyer")
    results = retriever.search(conn, query, k=3)
    assert results[0].job_id == py
    assert results[0].score == pytest.approx(1.0)

    filtered = retriever.search(conn, query, k=3, city="Denizli", job_types=["diger"])
    assert [r.job_id for r in filtered] == [acc]
    assert unity not in [r.job_id for r in retriever.search(conn, query, city="Denizli")]
