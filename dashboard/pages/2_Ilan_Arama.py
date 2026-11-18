"""İlan Arama: şehir, iş türü, beceri ve metin filtreleriyle ilan listesi."""

import streamlit as st
from filters import JOB_TYPE_LABELS, filter_jobs, skills_per_job
from queries import load_data_or_stop

jobs, job_skills = load_data_or_stop()

st.title("İlan Arama")

# --- Filtreler (tek satır) --------------------------------------------------------
col_city, col_type, col_skill = st.columns(3)
cities = col_city.multiselect(
    "Şehir",
    options=sorted(jobs["city"].unique()),
    placeholder="Tümü",
)
job_types = col_type.multiselect(
    "İş türü",
    options=list(JOB_TYPE_LABELS),
    format_func=JOB_TYPE_LABELS.get,
    placeholder="Tümü",
)
skills = col_skill.multiselect(
    "Beceriler",
    options=sorted(job_skills["skill_name"].unique()),
    placeholder="Tümü",
    help="Seçilen becerilerin hepsi ilanda geçmeli.",
)
col_query, col_remote = st.columns([3, 1], vertical_alignment="bottom")
query = col_query.text_input("Pozisyon veya firma ara", placeholder="ör. data, game, Trendyol")
remote_only = col_remote.checkbox("Sadece uzaktan")

# --- Sonuçlar ---------------------------------------------------------------------
results = filter_jobs(
    jobs,
    job_skills,
    cities=cities,
    job_types=job_types,
    skills=skills,
    query=query,
    remote_only=remote_only,
).sort_values("posted_date", ascending=False)

st.markdown(f"**{len(results)}** ilan bulundu.")

if results.empty:
    st.info("Bu filtrelerle eşleşen ilan yok. Filtrelerden birini kaldırmayı deneyin.")
else:
    skill_text = skills_per_job(job_skills)
    table = results.assign(
        job_type=results["job_type"].map(JOB_TYPE_LABELS),
        skills=results["job_id"].map(skill_text).fillna(""),
    )[["title", "company_name", "city", "job_type", "skills", "posted_date", "url"]]
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(table), 640),
        column_config={
            "title": st.column_config.TextColumn("Pozisyon", width="medium"),
            "company_name": "Firma",
            "city": "Şehir",
            "job_type": "Tür",
            "skills": st.column_config.TextColumn("Beceriler", width="large"),
            "posted_date": st.column_config.DateColumn("Yayın", format="DD.MM.YYYY"),
            "url": st.column_config.LinkColumn("İlan", display_text="Aç ↗"),
        },
    )
