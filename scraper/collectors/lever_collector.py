"""Lever ATS'nin herkese açık ilan API'si: https://api.lever.co/v0/postings/<slug>?mode=json"""

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from scraper.base import BaseCollector
from scraper.companies import CompanyBoard
from scraper.models import JobPosting
from scraper.text import clean_description

logger = logging.getLogger(__name__)

API_URL = "https://api.lever.co/v0/postings/{slug}"


class LeverCollector(BaseCollector):
    source = "lever"

    def fetch(self, board: CompanyBoard) -> Any:
        return self.get_json(API_URL.format(slug=board.slug), params={"mode": "json"})

    def parse(self, payload: Any, board: CompanyBoard) -> list[JobPosting]:
        postings = []
        for item in payload:
            if item.get("country") != "TR":  # Lever her ilana ISO ülke kodu verir
                continue
            try:
                postings.append(self._to_posting(item, board))
            except (KeyError, ValidationError) as exc:
                logger.warning("Lever ilanı atlandı (%s): %s", item.get("id"), exc)
        return postings

    @staticmethod
    def _to_posting(item: dict[str, Any], board: CompanyBoard) -> JobPosting:
        categories = item.get("categories") or {}
        locations = categories.get("allLocations") or [categories.get("location")]
        created_ms = item.get("createdAt")
        return JobPosting(
            source=LeverCollector.source,
            source_job_id=item["id"],
            url=item["hostedUrl"],
            title=item["text"],
            company=board.name,
            location_raw=" | ".join(loc for loc in locations if loc) or None,
            job_type_raw=categories.get("commitment"),
            description=clean_description(_full_description_html(item)),
            posted_at=datetime.fromtimestamp(created_ms / 1000, UTC) if created_ms else None,
        )


def _full_description_html(item: dict[str, Any]) -> str:
    """Lever açıklamayı parçalı verir: giriş + başlıklı listeler (ör. Requirements) + ek."""
    parts = [item.get("description") or ""]
    for section in item.get("lists") or []:
        parts.append(f"<h3>{section.get('text', '')}</h3><ul>{section.get('content', '')}</ul>")
    parts.append(item.get("additional") or "")
    return "\n".join(parts)
