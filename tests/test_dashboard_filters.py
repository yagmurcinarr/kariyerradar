"""Dashboard filtre ve özet fonksiyonlarının testleri (veritabanı ve Streamlit olmadan)."""

import pandas as pd
import pytest

from dashboard.filters import (
    count_by,
    entry_level,
    filter_jobs,
    fold_text,
    skills_per_job,
    top_skills,
    weekly_counts,
)


@pytest.fixture
def jobs() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "job_id": [1, 2, 3, 4],
            "title": [
                "Data Analyst Intern",
                "Backend Engineer",
                "Junior Game Developer",
                "İK Uzmanı",
            ],
            "company_name": ["Trendyol", "Insider", "Dream Games", "Örnek A.Ş."],
            "city": ["İstanbul", "Ankara", "İstanbul", "İzmir"],
            "is_remote": [False, True, False, None],
            "job_type": ["staj", "diger", "junior", "diger"],
            "posted_date": pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-17", "2026-11-18"]),
        }
    )


@pytest.fixture
def job_skills() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "job_id": [1, 1, 2, 2, 3],
            "skill_name": ["SQL", "Python", "Python", "Go", "Unity"],
        }
    )


def ids(df: pd.DataFrame) -> list[int]:
    return sorted(df["job_id"].tolist())


def test_no_filters_returns_all(jobs, job_skills) -> None:
    assert ids(filter_jobs(jobs, job_skills)) == [1, 2, 3, 4]


def test_city_and_type_filters(jobs, job_skills) -> None:
    assert ids(filter_jobs(jobs, job_skills, cities=["İstanbul"])) == [1, 3]
    assert ids(filter_jobs(jobs, job_skills, cities=["İstanbul"], job_types=["staj"])) == [1]
    assert ids(filter_jobs(jobs, job_skills, job_types=["staj", "junior"])) == [1, 3]


def test_skills_filter_requires_all_selected(jobs, job_skills) -> None:
    assert ids(filter_jobs(jobs, job_skills, skills=["Python"])) == [1, 2]
    assert ids(filter_jobs(jobs, job_skills, skills=["Python", "SQL"])) == [1]
    assert ids(filter_jobs(jobs, job_skills, skills=["SQL", "Unity"])) == []


def test_query_is_turkish_and_case_insensitive(jobs, job_skills) -> None:
    assert ids(filter_jobs(jobs, job_skills, query="TRENDYOL")) == [1]
    assert ids(filter_jobs(jobs, job_skills, query="ik uzmani")) == [4]
    assert ids(filter_jobs(jobs, job_skills, query="ornek")) == [4]


def test_remote_only_treats_missing_as_false(jobs, job_skills) -> None:
    assert ids(filter_jobs(jobs, job_skills, remote_only=True)) == [2]


def test_entry_level(jobs) -> None:
    assert ids(entry_level(jobs)) == [1, 3]


def test_top_skills_counts_and_share(job_skills) -> None:
    result = top_skills(job_skills, job_ids=[1, 2, 3, 4], n=2)
    assert result["skill_name"].tolist() == ["Python", "Go"]  # eşitlikte alfabetik
    assert result["job_count"].tolist() == [2, 1]
    assert result["share"].tolist() == [0.5, 0.25]


def test_top_skills_empty() -> None:
    assert top_skills(pd.DataFrame(columns=["job_id", "skill_name"]), job_ids=[]).empty


def test_weekly_counts_fills_empty_weeks(jobs) -> None:
    result = weekly_counts(jobs)
    assert result["week_start"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-11-02",  # Pazartesi; 2 ve 3 Kasım aynı hafta
        "2026-11-09",  # ilan yok → 0
        "2026-11-16",  # 17 ve 18 Kasım
    ]
    assert result["job_count"].tolist() == [2, 0, 2]


def test_weekly_counts_last_n_weeks_window(jobs) -> None:
    old = pd.DataFrame({"posted_date": pd.to_datetime(["2017-07-01"])})
    data = pd.concat([jobs[["posted_date"]], old], ignore_index=True)
    result = weekly_counts(data, weeks=2, today=pd.Timestamp("2026-11-18"))
    # Sadece 9 ve 16 Kasım haftaları; 2017 ve 2 Kasım haftası pencere dışında
    assert result["week_start"].dt.strftime("%Y-%m-%d").tolist() == ["2026-11-09", "2026-11-16"]
    assert result["job_count"].tolist() == [0, 2]


def test_count_by(jobs) -> None:
    result = count_by(jobs, "city", "city")
    assert result.iloc[0].to_dict() == {"city": "İstanbul", "job_count": 2}


def test_skills_per_job(job_skills) -> None:
    assert skills_per_job(job_skills).to_dict() == {1: "Python, SQL", 2: "Go, Python", 3: "Unity"}


def test_fold_text() -> None:
    assert fold_text("İK UZMANI Şişli") == "ik uzmani sisli"
