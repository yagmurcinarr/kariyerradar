"""Metin → vektör dönüşümü.

e5 modelleri iki tür girdiyi ayırt etmek için önek ister:
    - belgeler (ilanlar): "passage: ..."
    - aramalar (CV / sorgu): "query: ..."
Önek unutulursa benzerlik skorları belirgin biçimde kötüleşir.

Model ağır olduğu için (torch) içe aktarma ilk kullanımda yapılır; böylece testler ve
dashboard sentence-transformers kurulu olmadan da bu modülü import edebilir.
"""

from functools import cached_property
from typing import Protocol

MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
MAX_PASSAGE_CHARS = 2000  # model zaten 512 token'da keser; uzun metni baştan kırpıyoruz


class Embedder(Protocol):
    """Embedding üreten her sınıfın uyması gereken arayüz (testte sahte sürüm kullanılır)."""

    model_name: str

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def build_passage(title: str, company: str | None, description: str | None) -> str:
    """İlanın embed edilecek metni: başlık + firma + açıklama (kırpılmış)."""
    parts = [title.strip(), (company or "").strip(), (description or "").strip()]
    text = "\n".join(p for p in parts if p)
    return text[:MAX_PASSAGE_CHARS]


class E5Embedder:
    """sentence-transformers ile multilingual-e5-small (CPU'da çalışır)."""

    def __init__(self, model_name: str = MODEL_NAME, batch_size: int = 32) -> None:
        self.model_name = model_name
        self.batch_size = batch_size

    @cached_property
    def _model(self):  # noqa: ANN202 - tip, opsiyonel bağımlılıktan geliyor
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.model_name, device="cpu")

    def _encode(self, texts: list[str]) -> list[list[float]]:
        # normalize_embeddings=True → vektör uzunluğu 1; cosine benzerliği = iç çarpım
        vectors = self._model.encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"query: {text}"])[0]


def to_pgvector(vector: list[float]) -> str:
    """Python listesini pgvector metin biçimine çevirir: [0.1,0.2,...] (ek paket gerekmez)."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"
