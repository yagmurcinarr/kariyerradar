"""Komut satırı: ilanları topla ve veritabanına yaz.

Kullanım:
    python -m scraper.run --source lever
    python -m scraper.run --source all
    python -m scraper.run --source greenhouse --dry-run   # DB'ye yazmadan dene
"""

import argparse
import logging
import sys

from scraper import db
from scraper.collectors import COLLECTORS
from scraper.models import JobPosting

logger = logging.getLogger("scraper")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="StajRadar ilan toplayıcı")
    parser.add_argument("--source", required=True, choices=[*COLLECTORS, "all"])
    parser.add_argument("--dry-run", action="store_true", help="Veritabanına yazma")
    parser.add_argument("-v", "--verbose", action="store_true", help="Ayrıntılı log")
    return parser.parse_args(argv)


def collect(source: str) -> list[JobPosting]:
    """Seçilen kaynak(lar)dan ilanları toplar."""
    names = list(COLLECTORS) if source == "all" else [source]
    postings: list[JobPosting] = []
    for name in names:
        postings.extend(COLLECTORS[name]().collect())
    return postings


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # httpx her isteği INFO'da loglar; kalabalık yapmasın
    logging.getLogger("httpx").setLevel(logging.INFO if args.verbose else logging.WARNING)

    postings = collect(args.source)
    logger.info("Toplam %d Türkiye ilanı toplandı", len(postings))

    if args.dry_run:
        for p in postings[:10]:
            logger.info("  %s | %s | %s", p.company, p.title, p.location_raw)
        return 0

    if not postings:
        logger.error("Hiç ilan toplanamadı")
        return 1

    with db.connect() as conn:  # blok hatasız biterse commit, hata olursa rollback
        db.ensure_schema(conn)
        result = db.upsert_postings(conn, postings)
    logger.info("Veritabanı: %d yeni, %d güncellendi", result.inserted, result.updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
