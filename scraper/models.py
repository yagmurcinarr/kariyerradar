"""Toplanan ilanların ortak veri modeli.

Alanlar `raw.job_postings` tablosuyla birebir aynıdır (bkz. CLAUDE.md §4).
Her collector, kaynağı ne olursa olsun çıktısını bu modele dönüştürür.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JobPosting(BaseModel):
    """Tek bir ilan. Pydantic, alan tiplerini oluşturma anında doğrular."""

    # Metinlerdeki baş/son boşlukları kırp; nesne oluşturulduktan sonra değiştirilemesin.
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    source: str = Field(min_length=1, description="Kaynak adı, ör. 'lever'")
    source_job_id: str = Field(min_length=1, description="Kaynaktaki ilan kimliği")
    url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location_raw: str | None = None
    job_type_raw: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    scraped_at: datetime = Field(default_factory=_utc_now)
