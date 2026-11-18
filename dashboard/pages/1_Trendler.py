"""Trendler: en çok istenen beceriler, haftalık ilan sayısı, şehir ve iş türü dağılımı."""

import altair as alt
import streamlit as st
from charts import horizontal_bar, weekly_line
from filters import JOB_TYPE_LABELS, count_by, entry_level, top_skills, weekly_counts
from queries import load_data_or_stop

jobs, job_skills = load_data_or_stop()

st.title("Trendler")

# Filtre en üstte, tek satırda; aşağıdaki tüm grafiklere uygulanır.
scope = st.segmented_control(
    "İlan kapsamı",
    options=["Tüm ilanlar", "Giriş seviyesi"],
    default="Tüm ilanlar",
    help="Giriş seviyesi: staj, yeni mezun ve junior ilanları",
)
scoped = entry_level(jobs) if scope == "Giriş seviyesi" else jobs
st.caption(f"{len(scoped)} ilan üzerinden hesaplandı.")

if scoped.empty:
    st.info("Bu kapsamda ilan yok.")
    st.stop()

# --- En çok istenen beceriler -------------------------------------------------
st.subheader("En çok istenen 15 beceri")
skills = top_skills(job_skills, scoped["job_id"], n=15)
st.altair_chart(
    horizontal_bar(
        skills,
        category="skill_name",
        value="job_count",
        value_title="İlan sayısı",
        tooltip=[
            alt.Tooltip("skill_name:N", title="Beceri"),
            alt.Tooltip("job_count:Q", title="İlan"),
            alt.Tooltip("share:Q", title="İlanların", format=".0%"),
        ],
    ),
    width="stretch",
)
with st.expander("Tablo olarak göster"):
    st.dataframe(
        skills,
        hide_index=True,
        column_config={
            "skill_name": "Beceri",
            "job_count": "İlan sayısı",
            "share": st.column_config.NumberColumn("İlanların oranı", format="percent"),
        },
    )

# --- Haftalık ilan sayısı -------------------------------------------------------
st.subheader("Haftalık yayınlanan ilan sayısı")
st.altair_chart(weekly_line(weekly_counts(scoped)), width="stretch")
st.caption(
    "Yayın tarihi şirketin işe alım sisteminden gelir. Uzun süredir açık ilanlar da sayıldığı için "
    "eski haftalarda da ilan görünür; veri her gün toplandıkça grafik güncellenir."
)

# --- Şehir ve iş türü -----------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("Şehir dağılımı")
    cities = count_by(scoped, "city", "city")
    st.altair_chart(
        horizontal_bar(
            cities,
            category="city",
            value="job_count",
            value_title="İlan sayısı",
            tooltip=[
                alt.Tooltip("city:N", title="Şehir"),
                alt.Tooltip("job_count:Q", title="İlan"),
            ],
        ),
        width="stretch",
    )
with right:
    st.subheader("İş türü dağılımı")
    types = count_by(
        scoped.assign(job_type=scoped["job_type"].map(JOB_TYPE_LABELS)), "job_type", "job_type"
    )
    st.altair_chart(
        horizontal_bar(
            types,
            category="job_type",
            value="job_count",
            value_title="İlan sayısı",
            tooltip=[
                alt.Tooltip("job_type:N", title="Tür"),
                alt.Tooltip("job_count:Q", title="İlan"),
            ],
        ),
        width="stretch",
    )
