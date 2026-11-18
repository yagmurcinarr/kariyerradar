"""CV dosyasından düz metin çıkarma.

CV hiçbir zaman diske yazılmaz: PDF baytları bellekte okunur, metin döndürülür.
"""

import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PAGES = 5
MAX_CV_CHARS = 20_000


class CVParseError(ValueError):
    """CV okunamadığında (bozuk/şifreli/boş PDF, çok büyük dosya) fırlatılır."""


def normalize_text(text: str) -> str:
    """Fazla boşlukları ve boş satırları temizler, uzunluğu sınırlar."""
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()[:MAX_CV_CHARS]


def extract_text_from_pdf(data: bytes) -> str:
    """PDF baytlarından metni çıkarır (ilk MAX_PAGES sayfa)."""
    if len(data) > MAX_PDF_BYTES:
        raise CVParseError("PDF 5 MB'tan büyük olamaz.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise CVParseError("Şifreli PDF okunamıyor.")
        pages = [page.extract_text() or "" for page in reader.pages[:MAX_PAGES]]
    except PdfReadError as exc:
        raise CVParseError("PDF okunamadı; dosya bozuk olabilir.") from exc

    text = normalize_text("\n".join(pages))
    if not text:
        # Taranmış (resim) PDF'lerde metin katmanı yoktur
        raise CVParseError("PDF'te metin bulunamadı; taranmış bir belge olabilir.")
    return text
