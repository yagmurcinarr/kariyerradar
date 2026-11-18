"""CV eşleştirme API testleri.

Model, veritabanı ve LLM sahte sürümlerle değiştirilir (dependency_overrides);
böylece testler hızlı, internetsiz ve deterministik çalışır.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from matching import api
from matching.cv_parser import CVParseError, extract_text_from_pdf
from matching.llm_client import NullLLMClient, get_llm_client
from matching.prompts import build_explanation_prompt, parse_explanations
from matching.retriever import JobMatch, rerank

CV_TEXT = "Yönetim Bilişim Sistemleri öğrencisiyim. Python, SQL ve Excel ile veri analizi yaptım."

JOBS = [
    JobMatch(1, "Data Analyst Intern", "Trendyol", "İstanbul", "staj", "https://x/1", 0.82,
             ("Python", "SQL", "Power BI")),
    JobMatch(2, "Game Developer", "Dream Games", "İstanbul", "junior", "https://x/2", 0.80,
             ("Unity", "C#")),
]  # fmt: skip


class FakeEmbedder:
    model_name = "fake"

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * 384

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]


class FakeLLM:
    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_json(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return {"explanations": [{"job_id": 1, "explanation": "Python ve SQL biliyorsun."}]}


def fake_searcher(vector, text, k, city, job_types):  # noqa: ANN001, ANN201
    from matching.skills import extract_skills

    pool = [j for j in JOBS if (not city or j.city == city)]
    pool = [j for j in pool if (not job_types or j.job_type in job_types)]
    return rerank(pool, extract_skills(text), k)


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(llm: FakeLLM) -> Iterator[TestClient]:
    api.app.dependency_overrides = {
        api.get_embedder: FakeEmbedder,
        api.get_searcher: lambda: fake_searcher,
        api.get_llm: lambda: llm,
    }
    with TestClient(api.app) as c:
        yield c
    api.app.dependency_overrides = {}


def make_pdf(text: str) -> bytes:
    """Tek sayfalık, metin içeren minimal bir PDF üretir (test için)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


# --- API -----------------------------------------------------------------------


def test_match_with_text_returns_skills_and_explanation(client: TestClient, llm: FakeLLM) -> None:
    response = client.post("/match", data={"text": CV_TEXT, "top_k": 5})
    assert response.status_code == 200
    body = response.json()

    assert {"Python", "SQL", "Excel"} <= set(body["cv_skills"])
    first = body["matches"][0]
    assert first["job_id"] == 1  # beceri örtüşmesi olan ilan üstte
    assert first["matching_skills"] == ["Python", "SQL"]
    assert first["missing_skills"] == ["Power BI"]
    assert first["explanation"] == "Python ve SQL biliyorsun."
    assert body["matches"][1]["explanation"] is None  # LLM bu ilan için yazmadı
    assert body["llm_used"] is True
    # Gizlilik: LLM'e CV metni değil sadece beceriler gider
    assert "Yönetim Bilişim" not in llm.prompts[0]


def test_match_with_pdf_and_filters(client: TestClient) -> None:
    pdf = make_pdf("Python SQL Excel veri analizi stajyer adayi")
    response = client.post(
        "/match",
        files={"file": ("cv.pdf", pdf, "application/pdf")},
        data={"job_type": ["junior"], "top_k": 3},
    )
    assert response.status_code == 200
    assert [m["job_id"] for m in response.json()["matches"]] == [2]


def test_match_without_llm_still_works(client: TestClient) -> None:
    api.app.dependency_overrides[api.get_llm] = NullLLMClient
    body = client.post("/match", data={"text": CV_TEXT}).json()
    assert body["llm_used"] is False
    assert body["matches"][0]["matching_skills"] == ["Python", "SQL"]
    assert all(m["explanation"] is None for m in body["matches"])


@pytest.mark.parametrize(
    ("data", "files"),
    [
        ({}, None),  # CV yok
        ({"text": "kısa"}, None),  # çok kısa
        ({"text": CV_TEXT, "top_k": 0}, None),  # geçersiz top_k
        ({}, {"file": ("cv.pdf", b"bu bir pdf degil", "application/pdf")}),  # bozuk PDF
    ],
)
def test_match_rejects_bad_input(client: TestClient, data: dict, files: dict | None) -> None:
    assert client.post("/match", data=data, files=files).status_code == 422


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "llm": "fake"}


# --- Yardımcı modüller --------------------------------------------------------------


def test_pdf_parser_reads_text_and_rejects_empty() -> None:
    assert "Python SQL" in extract_text_from_pdf(make_pdf("Python SQL"))
    with pytest.raises(CVParseError):
        extract_text_from_pdf(make_pdf(""))


def test_parse_explanations_skips_bad_items() -> None:
    payload = {"explanations": [{"job_id": "3", "explanation": " iyi "}, {"job_id": "x"}, {}]}
    assert parse_explanations(payload) == {3: "iyi"}
    assert parse_explanations(None) == {}


def test_prompt_contains_precomputed_skills() -> None:
    prompt = build_explanation_prompt({"SQL"}, rerank(JOBS[:1], {"SQL"}, k=1))
    assert "CV'deki beceriler: SQL" in prompt
    assert '"Power BI"' in prompt and '"job_id": 1' in prompt


def test_llm_client_falls_back_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "")
    assert isinstance(get_llm_client(), NullLLMClient)
