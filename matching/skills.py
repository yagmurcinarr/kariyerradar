"""Metinden beceri çıkarma (Python tarafı).

dbt'deki bridge_job_skill modeliyle aynı sözlüğü (pipeline/seeds/skills.csv) ve aynı kuralları
kullanır; böylece CV'den çıkan beceriler ilanlardan çıkanlarla birebir karşılaştırılabilir:
    - kelime sınırı: "sql" → "MySQL" içinde, "java" → "JavaScript" içinde eşleşmez
    - case_sensitive=true becerilerde büyük/küçük harf korunur ("Excel" evet, "excel at" hayır)
    - diğerlerinde Türkçe karakter ve büyük/küçük harf farkı yok sayılır
"""

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from scraper.text import fold_turkish

SKILLS_CSV = Path(__file__).resolve().parent.parent / "pipeline" / "seeds" / "skills.csv"

# Sınırda harf/rakam ve + # olmamalı (SQL modelindeki desenle aynı)
_BOUNDARY_LEFT = r"(?:^|(?<=[^A-Za-z0-9+#]))"
_BOUNDARY_RIGHT = r"(?=$|[^A-Za-z0-9+#])"


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    category: str
    pattern: re.Pattern[str]
    case_sensitive: bool


def _compile(aliases: list[str], case_sensitive: bool) -> re.Pattern[str]:
    words = [a if case_sensitive else fold_turkish(a) for a in aliases]
    alternation = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(f"{_BOUNDARY_LEFT}(?:{alternation}){_BOUNDARY_RIGHT}")


@lru_cache(maxsize=1)
def load_skills(path: Path = SKILLS_CSV) -> tuple[Skill, ...]:
    """Beceri sözlüğünü bir kez okuyup derlenmiş regex'lerle döner."""
    skills = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            aliases = [a.strip() for a in row["aliases"].split("|") if a.strip()]
            if not aliases:
                continue
            case_sensitive = row["case_sensitive"].strip().lower() == "true"
            skills.append(
                Skill(
                    skill_id=row["skill_id"],
                    name=row["skill_name"],
                    category=row["category"],
                    pattern=_compile(aliases, case_sensitive),
                    case_sensitive=case_sensitive,
                )
            )
    return tuple(skills)


def extract_skills(text: str) -> set[str]:
    """Metinde geçen becerilerin adları: {'Python', 'SQL', ...}"""
    folded = fold_turkish(text)
    return {s.name for s in load_skills() if s.pattern.search(text if s.case_sensitive else folded)}
