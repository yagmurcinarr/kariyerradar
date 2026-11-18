"""Genel Bakış: temel sayılar ve en yeni giriş seviyesi ilanlar."""

from zoneinfo import ZoneInfo

import streamlit as st
from filters import JOB_TYPE_LABELS, entry_level
from queries import load_data_or_stop

jobs, job_skills = load_data_or_stop()
entry = entry_level(jobs)

st.title("📡 KariyerRadar")
st.markdown(
    "Türkiye'deki iş ilanlarını her gün otomatik toplayan ve analiz eden bir veri hattı. "
    "Öğrenci ve yeni mezunlar için **staj, yeni mezun ve junior** ilanlarına odaklanır."
)

last_update = jobs["scraped_at"].max().astimezone(ZoneInfo("Europe/Istanbul"))
col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam ilan", f"{len(jobs):,}".replace(",", "."))
col2.metric("Giriş seviyesi ilan", len(entry), help="Staj + yeni mezun + junior")
col3.metric("Firma", jobs["company_name"].nunique())
col4.metric(
    "Son güncelleme",
    last_update.strftime("%d.%m %H:%M"),
    help=f"{last_update:%d.%m.%Y %H:%M} (Türkiye saati)",
)

st.subheader("En yeni giriş seviyesi ilanlar")
if entry.empty:
    st.info("Şu anda giriş seviyesi ilan yok.")
else:
    latest = entry.sort_values("posted_date", ascending=False).head(10)
    st.dataframe(
        latest.assign(job_type=latest["job_type"].map(JOB_TYPE_LABELS))[
            ["title", "company_name", "city", "job_type", "posted_date", "url"]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "title": "Pozisyon",
            "company_name": "Firma",
            "city": "Şehir",
            "job_type": "Tür",
            "posted_date": st.column_config.DateColumn("Yayın", format="DD.MM.YYYY"),
            "url": st.column_config.LinkColumn("İlan", display_text="Aç ↗"),
        },
    )

with st.expander("Veriler nereden geliyor?"):
    st.markdown(
        "İlanlar, şirketlerin kullandığı işe alım sistemlerinin (Lever, Greenhouse, Workable) "
        "**herkese açık ilan API'lerinden** her sabah 06:00'da toplanır, dbt ile temizlenir ve "
        "beceriler ilan metninden çıkarılır. Otomatik toplamayı yasaklayan siteler kullanılmaz; "
        "ilan metinlerindeki e-posta ve telefon numaraları kaydedilmeden silinir.\n\n"
        "Kaynak kod: [github.com/yagmurcinarr/kariyerradar]"
        "(https://github.com/yagmurcinarr/kariyerradar)"
    )
