"""CV eşleştirme iş mantığı (FastAPI'den bağımsız, test edilebilir).

Akış:
    CV metni → beceriler (sözlükle) + embedding → hibrit arama (top-k ilan)
    → eşleşen/eksik beceriler (deterministik) → LLM ile kısa açıklama (opsiyonel)
"""

import logging
import time
from collections.abc import Callable, Sequence

from pydantic import BaseModel, Field

from matching.embedder import Embedder
from matching.llm_client import LLMClient
from matching.prompts import build_explanation_prompt, parse_explanations
from matching.retriever import JobMatch
from matching.skills import extract_skills

log = logging.getLogger(__name__)

# (vektör, sorgu metni, k, şehir, iş türleri) → ilanlar. Testte sahte sürümü verilir.
Searcher = Callable[[list[float], str, int, str | None, Sequence[str] | None], list[JobMatch]]


class MatchItem(BaseModel):
    job_id: int
    title: str
    company: str
    city: str
    job_type: str
    url: str
    score: float = Field(description="0–1 arası hibrit uygunluk skoru")
    matching_skills: list[str]
    missing_skills: list[str]
    explanation: str | None = None


class MatchResponse(BaseModel):
    cv_skills: list[str] = Field(description="CV'de bulunan beceriler")
    matches: list[MatchItem]
    llm_used: bool = Field(description="Açıklamalar LLM ile üretildiyse true")
    elapsed_ms: int


def match_cv(
    cv_text: str,
    *,
    embedder: Embedder,
    searcher: Searcher,
    llm: LLMClient,
    top_k: int = 10,
    city: str | None = None,
    job_types: Sequence[str] | None = None,
) -> MatchResponse:
    """CV metnine en uygun ilanları açıklamalarıyla döner. CV hiçbir yere kaydedilmez."""
    started = time.perf_counter()
    cv_skills = extract_skills(cv_text)
    vector = embedder.embed_query(cv_text)
    matches = searcher(vector, cv_text, top_k, city, job_types)

    explanations: dict[int, str] = {}
    if matches:
        payload = llm.generate_json(build_explanation_prompt(cv_skills, matches))
        explanations = parse_explanations(payload)

    items = [
        MatchItem(
            job_id=m.job_id,
            title=m.title,
            company=m.company,
            city=m.city,
            job_type=m.job_type,
            url=m.url,
            score=m.score,
            matching_skills=list(m.matching_skills),
            missing_skills=list(m.missing_skills),
            explanation=explanations.get(m.job_id),
        )
        for m in matches
    ]
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log.info("match: %d ilan, llm=%s, %d ms", len(items), bool(explanations), elapsed_ms)
    return MatchResponse(
        cv_skills=sorted(cv_skills),
        matches=items,
        llm_used=bool(explanations),
        elapsed_ms=elapsed_ms,
    )
