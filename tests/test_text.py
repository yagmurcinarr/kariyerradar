"""scraper.text yardımcılarının birim testleri."""

import pytest

from scraper.text import REDACTED, fold_turkish, html_to_text, is_turkey_location, scrub_pii


def test_html_to_text_keeps_inline_tags_on_same_line() -> None:
    html = (
        "<p>Looking for a <strong>Data</strong> intern.</p>"
        "<ul><li><p>SQL</p></li><li>Excel</li></ul>"
    )
    assert html_to_text(html) == "Looking for a Data intern.\n\n- SQL\n- Excel"


def test_html_to_text_handles_empty() -> None:
    assert html_to_text(None) == ""
    assert html_to_text("") == ""


@pytest.mark.parametrize(
    "raw",
    [
        "ayse.yilmaz@ornek.com",
        "+90 532 123 45 67",
        "0(212) 123 45 67",
        "05321234567",
    ],
)
def test_scrub_pii_removes_contact_details(raw: str) -> None:
    assert scrub_pii(f"İletişim: {raw}.") == f"İletişim: {REDACTED}."


def test_scrub_pii_keeps_ordinary_numbers() -> None:
    text = "2026 yaz dönemi, 3 ay, 20 kişilik ekip"
    assert scrub_pii(text) == text


def test_fold_turkish() -> None:
    assert fold_turkish("İSTANBUL / Şişli, Çankaya, Iğdır") == "istanbul / sisli, cankaya, igdir"


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Istanbul / Maslak", True),
        ("Sarıyer, İstanbul", True),
        ("Denizli / Merkezefendi", True),
        ("Remote - Türkiye", True),
        ("Vancouver, Canada", False),  # "van" kelime sınırı sayesinde eşleşmemeli
        ("Riyadh", False),
        (None, False),
    ],
)
def test_is_turkey_location(location: str | None, expected: bool) -> None:
    assert is_turkey_location(location) is expected
