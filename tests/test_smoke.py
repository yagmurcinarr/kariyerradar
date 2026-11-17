"""Aşama 0 duman testi: paketlerin import edilebildiğini doğrular."""

import importlib

import pytest


@pytest.mark.parametrize("module", ["scraper", "scraper.collectors", "matching"])
def test_packages_importable(module: str) -> None:
    """Proje paketleri hatasız import edilmeli."""
    assert importlib.import_module(module) is not None
