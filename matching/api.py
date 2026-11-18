"""KariyerRadar CV eşleştirme API'si (FastAPI).

Çalıştırma:
    uvicorn matching.api:app --reload
    → http://127.0.0.1:8000/docs adresinde etkileşimli dokümantasyon

Örnek:
    curl -F "file=@cv.pdf" -F "top_k=5" http://127.0.0.1:8000/match
    curl -F "text=Python, SQL ve Power BI biliyorum" http://127.0.0.1:8000/match
"""

import logging
from collections.abc import Sequence
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from matching import retriever
from matching.cv_parser import MAX_PDF_BYTES, CVParseError, extract_text_from_pdf, normalize_text
from matching.embedder import E5Embedder, Embedder
from matching.llm_client import LLMClient, get_llm_client
from matching.retriever import JobMatch
from matching.service import MatchResponse, Searcher, match_cv
from scraper import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

JobType = Literal["staj", "yeni_mezun", "junior", "diger"]
MIN_CV_CHARS = 30


# --- Bağımlılıklar (testlerde app.dependency_overrides ile değiştirilir) -------------


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Model bir kez yüklenir ve tüm isteklerde paylaşılır."""
    return E5Embedder()


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    return get_llm_client()


def db_search(
    vector: list[float], text: str, k: int, city: str | None, job_types: Sequence[str] | None
) -> list[JobMatch]:
    """Her istek için kısa ömürlü bir bağlantıyla hibrit arama."""
    with db.connect() as conn:
        return retriever.search(conn, vector, text, k, city, job_types)


def get_searcher() -> Searcher:
    return db_search


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    # Modeli ilk istekte değil açılışta yükle → ilk kullanıcı beklemesin
    embedder = app.dependency_overrides.get(get_embedder, get_embedder)()
    embedder.embed_query("ısınma")
    yield


app = FastAPI(
    title="KariyerRadar API",
    description="CV'ye göre iş ilanı öneren ve eksik becerileri gösteren eşleştirme servisi.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health(llm: Annotated[LLMClient, Depends(get_llm)]) -> dict[str, str]:
    return {"status": "ok", "llm": llm.name}


@app.post("/match", response_model=MatchResponse)
async def match(
    embedder: Annotated[Embedder, Depends(get_embedder)],
    searcher: Annotated[Searcher, Depends(get_searcher)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    file: Annotated[UploadFile | None, File(description="CV (PDF)")] = None,
    text: Annotated[str | None, Form(description="CV düz metin (PDF yerine)")] = None,
    top_k: Annotated[int, Form(ge=1, le=50)] = 10,
    city: Annotated[str | None, Form(description="ör. İstanbul")] = None,
    job_type: Annotated[list[JobType] | None, Form()] = None,
) -> MatchResponse:
    """PDF ya da düz metin CV alır, en uygun ilanları döner. CV kaydedilmez."""
    cv_text = await read_cv(file, text)
    return match_cv(
        cv_text,
        embedder=embedder,
        searcher=searcher,
        llm=llm,
        top_k=top_k,
        city=city or None,
        job_types=job_type or None,
    )


async def read_cv(file: UploadFile | None, text: str | None) -> str:
    """CV metnini PDF'ten veya düz metinden alır; sadece bellekte tutar."""
    if file is not None and file.filename:
        data = await file.read(MAX_PDF_BYTES + 1)
        try:
            cv_text = extract_text_from_pdf(data)
        except CVParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif text:
        cv_text = normalize_text(text)
    else:
        raise HTTPException(status_code=422, detail="CV için 'file' (PDF) veya 'text' gönderin.")

    if len(cv_text) < MIN_CV_CHARS:
        raise HTTPException(status_code=422, detail="CV metni çok kısa.")
    return cv_text
