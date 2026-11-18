"""Greenhouse ATS'nin herkese açık Job Board API'si:
https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true
"""

import html
import logging
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from scraper.base import BaseCollector
from scraper.companies import CompanyBoard
from scraper.models import JobPosting
from scraper.text import clean_description, is_turkey_location

logger = logging.getLogger(__name__)

API_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseCollector(BaseCollector):
    source = "greenhouse"

    def fetch(self, board: CompanyBoard) -> Any:
        # content=true → ilan açıklamaları da gelir (tek istekte tüm pano)
        return self.get_json(API_URL.format(slug=board.slug), params={"content": "true"})

    def parse(self, payload: Any, board: CompanyBoard) -> list[JobPosting]:
        postings = []
        for item in payload.get("jobs", []):
            location = (item.get("location") or {}).get("name")
            offices = [o.get("location") or o.get("name") for o in item.get("offices") or []]
            # Greenhouse'ta ülke kodu yok; lokasyon ve ofis metinlerinde Türkiye şehri arıyoruz.
            if not any(is_turkey_location(text) for text in [location, *offices]):
                continue
            try:
                postings.append(self._to_posting(item, board, location))
            except (KeyError, ValidationError) as exc:
                logger.warning("Greenhouse ilanı atlandı (%s): %s", item.get("id"), exc)
        return postings

    @staticmethod
    def _to_posting(item: dict[str, Any], board: CompanyBoard, location: str | None) -> JobPosting:
        published = item.get("first_published") or item.get("updated_at")
        return JobPosting(
            source=GreenhouseCollector.source,
            source_job_id=str(item["id"]),
            url=item["absolute_url"],
            title=item["title"],
            company=board.name,
            location_raw=location,
            job_type_raw=None,  # Greenhouse çalışma türünü standart bir alanda vermiyor
            # İçerik çift kodlanmış gelir (&lt;p&gt;) → önce html.unescape, sonra HTML → metin
            description=clean_description(html.unescape(item.get("content") or "")),
            posted_at=datetime.fromisoformat(published) if published else None,
        )
