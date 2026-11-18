"""Workable ATS'nin herkese açık kariyer sayfası widget API'si:
https://apply.workable.com/api/v1/widget/accounts/<slug>?details=true
"""

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from scraper.base import BaseCollector
from scraper.companies import CompanyBoard
from scraper.models import JobPosting
from scraper.text import clean_description

logger = logging.getLogger(__name__)

API_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


class WorkableCollector(BaseCollector):
    source = "workable"

    def fetch(self, board: CompanyBoard) -> Any:
        return self.get_json(API_URL.format(slug=board.slug), params={"details": "true"})

    def parse(self, payload: Any, board: CompanyBoard) -> list[JobPosting]:
        postings = []
        for item in payload.get("jobs", []):
            if not _is_turkey(item):
                continue
            try:
                postings.append(self._to_posting(item, board))
            except (KeyError, ValidationError) as exc:
                logger.warning("Workable ilanı atlandı (%s): %s", item.get("shortcode"), exc)
        return postings

    @staticmethod
    def _to_posting(item: dict[str, Any], board: CompanyBoard) -> JobPosting:
        location = ", ".join(p for p in (item.get("city"), item.get("state")) if p)
        published = item.get("published_on") or item.get("created_at")
        return JobPosting(
            source=WorkableCollector.source,
            source_job_id=item["shortcode"],
            url=item["url"],
            title=item["title"],
            company=board.name,
            location_raw=location or item.get("country"),
            job_type_raw=item.get("employment_type") or None,
            description=clean_description(item.get("description")),
            posted_at=(
                datetime.fromisoformat(published).replace(tzinfo=UTC) if published else None
            ),
        )


def _is_turkey(item: dict[str, Any]) -> bool:
    """İlanın lokasyonlarından biri Türkiye ise True."""
    codes = {loc.get("countryCode") for loc in item.get("locations") or []}
    return "TR" in codes or (item.get("country") or "").lower() in {"turkey", "türkiye"}
