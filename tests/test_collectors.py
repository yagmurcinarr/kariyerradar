"""Collector parse() testleri: kaydedilmiş örnek API yanıtlarıyla, ağa çıkmadan."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scraper.collectors.greenhouse_collector import GreenhouseCollector
from scraper.collectors.lever_collector import LeverCollector
from scraper.collectors.workable_collector import WorkableCollector
from scraper.companies import CompanyBoard
from scraper.text import REDACTED

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_lever_parse_keeps_only_turkey_and_builds_description() -> None:
    board = CompanyBoard("Örnek A.Ş.", "lever", "ornek")
    postings = LeverCollector(boards=[board]).parse(load("lever_postings.json"), board)

    assert len(postings) == 1  # Riyadh ilanı elendi
    p = postings[0]
    assert p.source == "lever"
    assert p.source_job_id == "11111111-aaaa-4bbb-8ccc-000000000001"
    assert p.title == "Data Analyst Intern"
    assert p.company == "Örnek A.Ş."
    assert p.location_raw == "Istanbul / Maslak"
    assert p.job_type_raw == "Intern"
    assert p.posted_at is not None and p.posted_at.year == 2026
    # HTML → düz metin; listeler başlığıyla birlikte
    assert "We are looking for a Data Analyst Intern to join our team." in p.description
    assert "Requirements\n\n- Good knowledge of SQL and Python\n- Familiarity with Power BI" in (
        p.description
    )
    # Kişisel veri temizlendi
    assert "ayse.yilmaz@ornek.com" not in p.description
    assert "532" not in p.description
    assert p.description.count(REDACTED) == 2


def test_greenhouse_parse_unescapes_content_and_checks_offices() -> None:
    board = CompanyBoard("Örnek Games", "greenhouse", "ornek")
    postings = GreenhouseCollector(boards=[board]).parse(load("greenhouse_jobs.json"), board)

    ids = [p.source_job_id for p in postings]
    assert ids == ["9000000001", "9000000002"]  # Vancouver elendi; Ankara ofisi yakalandı

    first = postings[0]
    assert first.location_raw == "Sarıyer, İstanbul"
    assert first.description == "About us\n\nWe build mobile games.\n\n- C# and Unity"
    assert first.posted_at == datetime.fromisoformat("2026-10-14T06:43:00-04:00")
    # first_published yoksa updated_at kullanılır
    assert postings[1].posted_at == datetime.fromisoformat("2026-10-01T10:00:00+00:00")


def test_workable_parse() -> None:
    board = CompanyBoard("Örnek Games", "workable", "ornek")
    postings = WorkableCollector(boards=[board]).parse(load("workable_account.json"), board)

    assert len(postings) == 1  # Vilnius elendi
    p = postings[0]
    assert p.source_job_id == "ABC123DEF4"
    assert p.location_raw == "Istanbul, İstanbul"
    assert p.job_type_raw == "Internship"
    assert p.description.startswith("We are hiring a Game Design Intern for our Levent office.")
    assert p.posted_at is not None and p.posted_at.tzinfo is not None
