"""Dashboard'un saf (Streamlit'ten bağımsız) veri mantığı: filtreleme ve özetler.

Sadece pandas kullanır; bu yüzden veritabanı ve arayüz olmadan birim test edilebilir.
Girdi tabloları:
    jobs:       job_id, title, company_name, city, is_remote, job_type, url, posted_date, ...
    job_skills: job_id, skill_name, category
"""

import unicodedata
from collections.abc import Iterable

import pandas as pd

JOB_TYPE_LABELS: dict[str, str] = {
    "staj": "Staj",
    "yeni_mezun": "Yeni mezun",
    "junior": "Junior",
    "diger": "Diğer",
}
ENTRY_LEVEL_TYPES: frozenset[str] = frozenset({"staj", "yeni_mezun", "junior"})


def fold_text(text: str) -> str:
    """Aramada Türkçe karakter ve büyük/küçük harf farkını yok sayar: 'İstanbul' → 'istanbul'."""
    text = text.replace("ı", "i").replace("İ", "i").casefold()
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def filter_jobs(
    jobs: pd.DataFrame,
    job_skills: pd.DataFrame,
    *,
    cities: Iterable[str] = (),
    job_types: Iterable[str] = (),
    skills: Iterable[str] = (),
    query: str = "",
    remote_only: bool = False,
) -> pd.DataFrame:
    """İlanları filtreler. Boş bırakılan filtre uygulanmaz.

    - cities / job_types: seçilenlerden HERHANGİ biri (VEYA)
    - skills: seçilen becerilerin HEPSİ ilanda geçmeli (VE)
    - query: başlık veya firma adında geçen metin (Türkçe karakter duyarsız)
    """
    mask = pd.Series(True, index=jobs.index)
    cities, job_types, skills = list(cities), list(job_types), list(skills)

    if cities:
        mask &= jobs["city"].isin(cities)
    if job_types:
        mask &= jobs["job_type"].isin(job_types)
    if remote_only:
        mask &= jobs["is_remote"].fillna(False).astype(bool)
    if query.strip():
        needle = fold_text(query.strip())
        haystack = (jobs["title"].fillna("") + " " + jobs["company_name"].fillna("")).map(fold_text)
        mask &= haystack.str.contains(needle, regex=False)
    if skills:
        wanted = set(skills)
        per_job = job_skills[job_skills["skill_name"].isin(wanted)].groupby("job_id")["skill_name"]
        matching_ids = per_job.nunique()
        matching_ids = matching_ids[matching_ids == len(wanted)].index
        mask &= jobs["job_id"].isin(matching_ids)

    return jobs[mask]


def entry_level(jobs: pd.DataFrame) -> pd.DataFrame:
    """Sadece giriş seviyesi (staj / yeni mezun / junior) ilanlar."""
    return jobs[jobs["job_type"].isin(ENTRY_LEVEL_TYPES)]


def top_skills(job_skills: pd.DataFrame, job_ids: Iterable[int], n: int = 15) -> pd.DataFrame:
    """Verilen ilanlarda en çok geçen n beceri: skill_name, job_count, share (ilan oranı)."""
    ids = set(job_ids)
    if not ids:
        return pd.DataFrame(columns=["skill_name", "job_count", "share"])
    subset = job_skills[job_skills["job_id"].isin(ids)]
    counts = (
        subset.groupby("skill_name")["job_id"]
        .nunique()
        .rename("job_count")
        .reset_index()
        .sort_values(["job_count", "skill_name"], ascending=[False, True])
        .head(n)
    )
    counts["share"] = counts["job_count"] / len(ids)
    return counts.reset_index(drop=True)


def _week_start(dates: pd.Series | pd.Timestamp) -> pd.Series | pd.Timestamp:
    """Tarihin içinde bulunduğu haftanın Pazartesi'si."""
    if isinstance(dates, pd.Timestamp):
        return dates.to_period("W-SUN").start_time
    return dates.dt.to_period("W-SUN").dt.start_time


def weekly_counts(
    jobs: pd.DataFrame, weeks: int | None = None, today: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Yayın tarihine göre haftalık ilan sayısı (hafta Pazartesi başlar); boş haftalar 0.

    weeks verilirse sadece bugünün haftası dahil son `weeks` hafta döner; böylece yıllardır
    açık birkaç ilan grafiği yıllara yaymaz.
    """
    empty = pd.DataFrame(columns=["week_start", "job_count"])
    if jobs.empty:
        return empty
    week_of = _week_start(pd.to_datetime(jobs["posted_date"]))

    if weeks is None:
        start, end = week_of.min(), week_of.max()
    else:
        end = _week_start(pd.Timestamp(today) if today is not None else pd.Timestamp.today())
        start = end - pd.Timedelta(weeks=weeks - 1)
        week_of = week_of[(week_of >= start) & (week_of <= end)]

    full_range = pd.date_range(start, end, freq="W-MON")
    counts = week_of.value_counts().reindex(full_range, fill_value=0)
    return pd.DataFrame({"week_start": full_range, "job_count": counts.to_numpy()})


def count_by(jobs: pd.DataFrame, column: str, label: str) -> pd.DataFrame:
    """Bir sütuna göre ilan sayısı, çoktan aza: <label>, job_count."""
    counts = jobs[column].value_counts().rename_axis(label).reset_index(name="job_count")
    return counts.sort_values(["job_count", label], ascending=[False, True]).reset_index(drop=True)


def skills_per_job(job_skills: pd.DataFrame) -> pd.Series:
    """job_id → 'Python, SQL, ...' (alfabetik)."""
    return job_skills.groupby("job_id")["skill_name"].agg(lambda s: ", ".join(sorted(set(s))))
