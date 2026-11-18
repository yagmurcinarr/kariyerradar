"""Sağlayıcıdan bağımsız LLM arayüzü.

Uygulama sadece `LLMClient.generate_json(prompt)` çağırır; hangi sağlayıcının kullanılacağı
.env'deki LLM_PROVIDER ile seçilir. Yeni bir sağlayıcı eklemek için aynı metodu uygulayan
bir sınıf yazıp `get_llm_client`'a eklemek yeterli.

LLM isteğe bağlıdır: anahtar yoksa ya da istek başarısız olursa `None` döner ve API
açıklamasız sonuç verir (eşleşen/eksik beceriler zaten LLM'siz hesaplanır).
"""

import json
import logging
import os
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv

log = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMClient(Protocol):
    name: str

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        """Prompt'a JSON nesnesiyle cevap üretir; başarısızsa None."""
        ...


class NullLLMClient:
    """LLM kapalıyken kullanılır: hiçbir istek atmaz."""

    name = "none"

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        return None


class GeminiClient:
    """Google Gemini REST API (ek SDK gerekmez, httpx ile)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, timeout: float = 15.0):
        self._api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=timeout)

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",  # model geçerli JSON döndürsün
                "temperature": 0.3,
                # Kısa açıklamalar için "düşünme" adımına gerek yok; yanıt süresini kısaltır
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        try:
            response = self._client.post(
                GEMINI_URL.format(model=self.model),
                headers={"x-goog-api-key": self._api_key},  # anahtar URL'de değil, başlıkta
                json=body,
            )
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            # Anahtarı içerebilecek ayrıntıları loglamamak için sadece hata türü
            log.warning("Gemini isteği başarısız: %s", type(exc).__name__)
            return None


def get_llm_client() -> LLMClient:
    """.env'deki ayarlara göre LLM istemcisini oluşturur."""
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "none").strip().lower()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    if provider == "gemini" and api_key:
        return GeminiClient(api_key, model or DEFAULT_GEMINI_MODEL)
    if provider not in ("none", ""):
        log.warning("LLM_PROVIDER=%s için anahtar yok veya desteklenmiyor; LLM kapalı", provider)
    return NullLLMClient()
