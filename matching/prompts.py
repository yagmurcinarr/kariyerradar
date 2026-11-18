"""LLM prompt şablonları.

LLM'e CV'nin kendisi gönderilmez; sadece CV'den çıkarılan beceri listesi ve ilan özetleri
gider. Böylece kişisel bilgiler (ad, telefon, adres) üçüncü taraf bir servise ulaşmaz.
Eşleşen/eksik beceriler önceden hesaplanmıştır; LLM sadece bunları açıklar, yeni beceri
uydurmaması istenir.
"""

import json

from matching.retriever import JobMatch

EXPLANATION_PROMPT = """\
Sen bir kariyer danışmanısın. Bir öğrencinin CV'si ile iş ilanları karşılaştırıldı.
Her ilan için öğrenciye hitap eden, 1-2 cümlelik kısa bir Türkçe açıklama yaz:
neden uygun olduğunu ve varsa eksik becerilerden en önemli 1-2 tanesini söyle.

Kurallar:
- Sadece aşağıda verilen bilgileri kullan; listede olmayan beceri veya bilgi uydurma.
- "Sen" diye hitap et, abartılı övgü kullanma.
- Cevabı şu JSON biçiminde ver:
  {{"explanations": [{{"job_id": <sayı>, "explanation": "<metin>"}}]}}

CV'deki beceriler: {cv_skills}

İlanlar:
{jobs}
"""

MAX_MISSING_IN_PROMPT = 8


def build_explanation_prompt(cv_skills: set[str], matches: list[JobMatch]) -> str:
    jobs = [
        {
            "job_id": m.job_id,
            "pozisyon": m.title,
            "firma": m.company,
            "tur": m.job_type,
            "eslesen_beceriler": list(m.matching_skills),
            "eksik_beceriler": list(m.missing_skills[:MAX_MISSING_IN_PROMPT]),
        }
        for m in matches
    ]
    return EXPLANATION_PROMPT.format(
        cv_skills=", ".join(sorted(cv_skills)) or "(belirlenemedi)",
        jobs=json.dumps(jobs, ensure_ascii=False, indent=1),
    )


def parse_explanations(payload: dict | None) -> dict[int, str]:
    """LLM cevabını job_id → açıklama sözlüğüne çevirir; bozuk kayıtları atlar."""
    if not isinstance(payload, dict):
        return {}
    result: dict[int, str] = {}
    for item in payload.get("explanations", []):
        try:
            job_id = int(item["job_id"])
            text = str(item["explanation"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if text:
            result[job_id] = text
    return result
