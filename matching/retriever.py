"""İlan arama: pgvector benzerliği + beceri örtüşmesiyle hibrit sıralama.

1. pgvector ile anlamca en yakın `candidates` ilan alınır (cosine).
2. Sorgudan (veya CV'den) beceriler çıkarılır; her ilanın becerileriyle örtüşmesi hesaplanır.
3. Nihai skor = vektör skoru (aday grubu içinde 0–1'e ölçeklenmiş) ve beceri örtüşmesinin
   ağırlıklı ortalaması. Sadece vektöre bakınca model metnin dilini/genel konusunu eşleştirip
   ilgisiz ilanları üste taşıyabiliyor; beceri örtüşmesi bunu düzeltir.

Kullanım:
    python -m matching.retriever "Python SQL veri analizi stajı Denizli" -k 10
    python -m matching.retriever "frontend react" --job-type staj junior
"""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass, replace

import psycopg

from matching.embedder import E5Embedder, to_pgvector
from matching.skills import extract_skills
from scraper import db

SKILL_WEIGHT = 0.5  # beceri örtüşmesinin nihai skordaki payı
DEFAULT_CANDIDATES = 100
# İlan tarafı oranında paydaya eklenir: tek beceri isteyen ilan, tek eşleşmeyle tam puan almasın
JOB_COVERAGE_SMOOTHING = 2
# Sorgu tarafı oranı en fazla bu kadar beceri üzerinden hesaplanır: 20+ beceri içeren bir CV,
# ilanın 5 becerisini karşılıyorsa bu zaten güçlü bir eşleşmedir.
QUERY_SKILL_CAP = 5

# <=> : cosine mesafe (0 = aynı yön). vector_score = 1 - mesafe.
# Filtreler boşsa (NULL) uygulanmaz.
SEARCH_SQL = """
SELECT f.job_id, f.title, f.company_name, f.city, f.job_type, f.url,
       1 - (e.embedding <=> %(vec)s::vector) AS vector_score,
       array(
           SELECT s.skill_name
           FROM marts.bridge_job_skill b
           JOIN marts.dim_skill s USING (skill_id)
           WHERE b.job_id = f.job_id
           ORDER BY s.skill_name
       ) AS skills
FROM ml.job_embeddings e
JOIN marts.fct_job f USING (job_id)
WHERE (%(city)s::text IS NULL OR f.city = %(city)s)
  AND (%(job_types)s::text[] IS NULL OR f.job_type = ANY(%(job_types)s))
ORDER BY e.embedding <=> %(vec)s::vector
LIMIT %(limit)s
"""


@dataclass(frozen=True)
class JobMatch:
    job_id: int
    title: str
    company: str
    city: str
    job_type: str
    url: str
    vector_score: float
    skills: tuple[str, ...] = ()
    matching_skills: tuple[str, ...] = ()
    missing_skills: tuple[str, ...] = ()
    score: float = 0.0  # nihai (hibrit) skor, 0–1


def rerank(
    candidates: list[JobMatch], query_skills: set[str], k: int, skill_weight: float = SKILL_WEIGHT
) -> list[JobMatch]:
    """Adayları hibrit skora göre sıralar; eşleşen/eksik becerileri doldurur.

    - matching_skills: sorguda (CV'de) VE ilanda olan beceriler
    - missing_skills:  ilanda olup sorguda (CV'de) OLMAYAN beceriler
    Sorguda hiç beceri yoksa sıralama sadece vektör skoruna göre yapılır.
    """
    if not candidates:
        return []
    scores = [c.vector_score for c in candidates]
    low, high = min(scores), max(scores)
    spread = high - low

    ranked = []
    for c in candidates:
        vec_norm = (c.vector_score - low) / spread if spread > 0 else 1.0
        job_skills = set(c.skills)
        matching = query_skills & job_skills
        if query_skills:
            overlap = skill_overlap(query_skills, job_skills)
            final = (1 - skill_weight) * vec_norm + skill_weight * overlap
        else:
            final = vec_norm
        ranked.append(
            replace(
                c,
                matching_skills=tuple(sorted(matching)),
                missing_skills=tuple(sorted(job_skills - query_skills)),
                score=round(final, 4),
            )
        )
    ranked.sort(key=lambda m: (-m.score, -m.vector_score))
    return ranked[:k]


def skill_overlap(query_skills: set[str], job_skills: set[str]) -> float:
    """Beceri örtüşmesi (0–1): iki yönlü oranın ortalaması.

    - sorgu tarafı: sorgudaki becerilerin ne kadarı ilanda var (kısa sorgularda belirleyici)
    - ilan tarafı: ilanın istediği becerilerin ne kadarını sorgu/CV karşılıyor
    Uzun CV'lerde sorgu tarafı payda QUERY_SKILL_CAP ile sınırlanır; yoksa 20+ beceri içeren
    bir CV için bu oran her ilanda düşük kalır ve sıralamayı yine sadece vektör belirler.
    """
    if not query_skills:
        return 0.0
    matching = len(query_skills & job_skills)
    query_side = min(1.0, matching / min(len(query_skills), QUERY_SKILL_CAP))
    job_side = matching / (len(job_skills) + JOB_COVERAGE_SMOOTHING)
    return (query_side + job_side) / 2


def fetch_candidates(
    conn: psycopg.Connection,
    query_vector: list[float],
    limit: int = DEFAULT_CANDIDATES,
    city: str | None = None,
    job_types: Sequence[str] | None = None,
) -> list[JobMatch]:
    """Vektöre en yakın `limit` ilan (sadece pgvector sıralaması)."""
    params = {
        "vec": to_pgvector(query_vector),
        "city": city,
        "job_types": list(job_types) if job_types else None,
        "limit": limit,
    }
    with conn.transaction():
        # Filtreli aramada HNSW'nin yeterince aday taraması için (varsayılan 40)
        conn.execute("SET LOCAL hnsw.ef_search = 200")
        rows = conn.execute(SEARCH_SQL, params).fetchall()
    return [JobMatch(*row[:6], vector_score=float(row[6]), skills=tuple(row[7])) for row in rows]


def search(
    conn: psycopg.Connection,
    query_vector: list[float],
    query_text: str = "",
    k: int = 10,
    city: str | None = None,
    job_types: Sequence[str] | None = None,
    candidates: int = DEFAULT_CANDIDATES,
) -> list[JobMatch]:
    """Hibrit arama: vektörle aday getir, sorgu metnindeki becerilerle yeniden sırala."""
    pool = fetch_candidates(conn, query_vector, max(candidates, k), city, job_types)
    return rerank(pool, extract_skills(query_text), k)


def main() -> None:
    parser = argparse.ArgumentParser(description="İlanlarda anlamsal arama")
    parser.add_argument("query", help="aranacak metin")
    parser.add_argument("-k", type=int, default=10, help="sonuç sayısı")
    parser.add_argument("--city", help="ör. İstanbul")
    parser.add_argument("--job-type", nargs="+", help="staj yeni_mezun junior diger")
    args = parser.parse_args()

    print(f"Sorgudaki beceriler: {', '.join(sorted(extract_skills(args.query))) or '-'}\n")
    vector = E5Embedder().embed_query(args.query)
    with db.connect() as conn:
        matches = search(conn, vector, args.query, args.k, args.city, args.job_type)
    for i, m in enumerate(matches, 1):
        print(
            f"{i:2}. {m.score:.2f} (vektör {m.vector_score:.3f})  {m.title} — {m.company} "
            f"({m.city}, {m.job_type})  eşleşen: {', '.join(m.matching_skills) or '-'}"
        )


if __name__ == "__main__":
    main()
