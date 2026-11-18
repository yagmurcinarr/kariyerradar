"""Tüm collector'ların ortak atası: nazik HTTP istemcisi (rate limit + retry) ve şablon akış.

Tasarım: ağ isteği yapan `fetch()` ile veriyi dönüştüren `parse()` ayrıdır.
Böylece `parse()` kaydedilmiş örnek yanıtlarla, internete çıkmadan test edilebilir.
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

import httpx

from scraper.companies import CompanyBoard, boards_for
from scraper.models import JobPosting

logger = logging.getLogger(__name__)

USER_AGENT = "KariyerRadar/0.1 (ogrenci portfolyo projesi; Turkiye is ilani analizi)"

# Bu durum kodları geçicidir; tekrar denemeye değer. 404 gibi diğer hatalar denenmez.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """Tüm denemelere rağmen veri alınamadığında fırlatılır."""


class BaseCollector(ABC):
    """Kaynak başına bir alt sınıf yazılır; alt sınıf `source`, `fetch` ve `parse`'ı tanımlar."""

    source: ClassVar[str]

    def __init__(
        self,
        boards: list[CompanyBoard] | None = None,
        client: httpx.Client | None = None,
        min_delay: float = 2.0,
        max_delay: float = 3.0,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # Testlerde sahte client ve "uyumayan" sleep verilebilsin diye dışarıdan alınıyor
        # (C#'taki constructor injection gibi).
        self.boards = boards if boards is not None else boards_for(self.source)
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self._sleep = sleep
        self._last_request_at: float | None = None

    # ---- HTTP katmanı -------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Bir önceki istekten bu yana en az 2–3 sn (rastgele) geçmesini bekler."""
        if self._last_request_at is None:
            return
        delay = random.uniform(self.min_delay, self.max_delay)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay:
            self._sleep(delay - elapsed)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET isteği atar, JSON döndürür. Geçici hatalarda üstel bekleme ile tekrar dener."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._wait_for_rate_limit()
            self._last_request_at = time.monotonic()
            try:
                response = self.client.get(url, params=params)
                if response.status_code in RETRYABLE_STATUS:
                    raise httpx.HTTPStatusError(
                        f"geçici hata {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()  # 404 vb. → hemen hata, tekrar deneme yok
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in RETRYABLE_STATUS:
                    raise FetchError(f"{url} → HTTP {exc.response.status_code}") from exc
                last_error = exc
            except httpx.TransportError as exc:  # bağlantı koptu, zaman aşımı vb.
                last_error = exc

            if attempt < self.max_retries:
                backoff = 2**attempt  # 2 sn, 4 sn ...
                logger.warning(
                    "%s deneme %d/%d başarısız (%s); %d sn sonra tekrar",
                    url,
                    attempt,
                    self.max_retries,
                    last_error,
                    backoff,
                )
                self._sleep(backoff)

        raise FetchError(f"{url} {self.max_retries} denemede alınamadı: {last_error}")

    # ---- Alt sınıfların dolduracağı kısım ------------------------------

    @abstractmethod
    def fetch(self, board: CompanyBoard) -> Any:
        """Bir şirket panosunun ham API yanıtını getirir (ağ erişimi burada)."""

    @abstractmethod
    def parse(self, payload: Any, board: CompanyBoard) -> list[JobPosting]:
        """Ham yanıtı JobPosting listesine çevirir; sadece Türkiye ilanlarını döndürür (ağsız)."""

    # ---- Şablon akış --------------------------------------------------

    def collect(self) -> list[JobPosting]:
        """Tüm panoları gezer. Bir pano hata verirse loglanır, diğerlerine devam edilir."""
        postings: list[JobPosting] = []
        for board in self.boards:
            try:
                payload = self.fetch(board)
                found = self.parse(payload, board)
            except Exception:
                logger.exception("[%s] %s panosu işlenemedi", self.source, board.slug)
                continue
            logger.info("[%s] %s: %d Türkiye ilanı", self.source, board.name, len(found))
            postings.extend(found)
        return postings
