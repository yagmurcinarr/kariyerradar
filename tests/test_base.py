"""BaseCollector'ın retry ve rate-limit davranışı. httpx.MockTransport ile gerçek ağ kullanılmaz."""

from typing import Any

import httpx
import pytest

from scraper.base import USER_AGENT, BaseCollector, FetchError
from scraper.companies import CompanyBoard
from scraper.models import JobPosting


class DummyCollector(BaseCollector):
    """Testler için en basit somut collector."""

    source = "dummy"

    def fetch(self, board: CompanyBoard) -> Any:
        return self.get_json(f"https://example.test/{board.slug}")

    def parse(self, payload: Any, board: CompanyBoard) -> list[JobPosting]:
        return [
            JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                url="https://example.test/job",
                title=item["title"],
                company=board.name,
            )
            for item in payload
        ]


def make_collector(responses: list[httpx.Response], boards: list[CompanyBoard] | None = None):
    """Sırayla verilen yanıtları dönen sahte bir HTTP istemcisiyle collector kurar."""
    calls: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses.pop(0)

    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT}
    )
    collector = DummyCollector(
        boards=boards or [CompanyBoard("Örnek", "dummy", "ornek")],
        client=client,
        sleep=sleeps.append,  # gerçekten uyumak yerine bekleme sürelerini kaydet
    )
    return collector, calls, sleeps


def test_retries_transient_errors_then_succeeds() -> None:
    collector, calls, sleeps = make_collector(
        [httpx.Response(503), httpx.Response(429), httpx.Response(200, json=[{"id": 1}])]
    )
    assert collector.get_json("https://example.test/x") == [{"id": 1}]
    assert len(calls) == 3
    assert 2 in sleeps and 4 in sleeps  # üstel bekleme: 2 sn, 4 sn


def test_gives_up_after_max_retries() -> None:
    collector, calls, _ = make_collector([httpx.Response(500)] * 3)
    with pytest.raises(FetchError):
        collector.get_json("https://example.test/x")
    assert len(calls) == 3


def test_does_not_retry_client_errors() -> None:
    collector, calls, _ = make_collector([httpx.Response(404)])
    with pytest.raises(FetchError):
        collector.get_json("https://example.test/x")
    assert len(calls) == 1


def test_rate_limit_waits_between_requests() -> None:
    collector, _, sleeps = make_collector(
        [httpx.Response(200, json=[]), httpx.Response(200, json=[])]
    )
    collector.get_json("https://example.test/a")
    collector.get_json("https://example.test/b")
    assert len(sleeps) == 1 and 1.9 < sleeps[0] <= 3.0


def test_sends_descriptive_user_agent() -> None:
    collector, calls, _ = make_collector([httpx.Response(200, json=[])])
    collector.get_json("https://example.test/a")
    assert calls[0].headers["User-Agent"].startswith("KariyerRadar/")


def test_collect_skips_failing_board_and_continues() -> None:
    boards = [CompanyBoard("Bozuk", "dummy", "bozuk"), CompanyBoard("Sağlam", "dummy", "saglam")]
    collector, _, _ = make_collector(
        [httpx.Response(404), httpx.Response(200, json=[{"id": 7, "title": "Stajyer"}])],
        boards=boards,
    )
    postings = collector.collect()
    assert [(p.company, p.title) for p in postings] == [("Sağlam", "Stajyer")]
