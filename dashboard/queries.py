"""Veritabanından okuma. Sorgular sadece `marts` katmanına gider; sonuçlar 1 saat önbelleklenir.

Bağlantı adresi sırasıyla: Streamlit Cloud secrets → ortam değişkeni → proje kökündeki .env
"""

import os
from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

JOBS_SQL = """
select job_id, title, company_name, city, district, is_remote, job_type,
       url, posted_date, scraped_at
from marts.fct_job
"""

JOB_SKILLS_SQL = """
select b.job_id, s.skill_name, s.category
from marts.bridge_job_skill as b
join marts.dim_skill as s using (skill_id)
"""


def get_database_url() -> str | None:
    """Bağlantı adresini bulur; yoksa None."""
    try:
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"])
    except Exception:  # secrets.toml hiç yoksa Streamlit hata fırlatır; lokalde normal
        pass
    load_dotenv(ENV_FILE)
    return os.getenv("DATABASE_URL")


def _read(sql: str) -> pd.DataFrame:
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL tanımlı değil.")
    with psycopg.connect(url, connect_timeout=15) as conn:
        cursor = conn.execute(sql)
        columns = [col.name for col in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columns)


@st.cache_data(ttl=3600, show_spinner="İlanlar yükleniyor…")
def load_jobs() -> pd.DataFrame:
    """Tüm ilanlar (fct_job)."""
    jobs = _read(JOBS_SQL)
    jobs["posted_date"] = pd.to_datetime(jobs["posted_date"])
    return jobs


@st.cache_data(ttl=3600, show_spinner=False)
def load_job_skills() -> pd.DataFrame:
    """İlan–beceri eşleşmeleri."""
    return _read(JOB_SKILLS_SQL)


def load_data_or_stop() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Verileri yükler; veritabanına ulaşılamazsa anlaşılır bir hata gösterip sayfayı durdurur."""
    try:
        return load_jobs(), load_job_skills()
    except Exception as exc:
        st.error(
            "Veritabanına bağlanılamadı. Lokalde `docker compose up -d` çalıştırdığınızdan ve "
            "`.env` içinde `DATABASE_URL` olduğundan emin olun.\n\n"
            f"Ayrıntı: `{type(exc).__name__}`"
        )
        st.stop()
