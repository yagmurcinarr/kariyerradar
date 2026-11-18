"""Kaynak adı → collector sınıfı eşlemesi (CLI bu sözlüğü kullanır)."""

from scraper.base import BaseCollector
from scraper.collectors.greenhouse_collector import GreenhouseCollector
from scraper.collectors.lever_collector import LeverCollector
from scraper.collectors.workable_collector import WorkableCollector

COLLECTORS: dict[str, type[BaseCollector]] = {
    cls.source: cls for cls in (LeverCollector, GreenhouseCollector, WorkableCollector)
}

__all__ = ["COLLECTORS"]
