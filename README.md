# KariyerRadar

Türkiye'deki iş ilanlarını her gün toplayan veri hattı ve CV'ye göre ilan öneren yapay zekâ asistanı.
Öğrenci ve yeni mezunlar için staj, yeni mezun ve junior ilanlarına odaklanır.

[![CI](https://github.com/yagmurcinarr/kariyerradar/actions/workflows/ci.yml/badge.svg)](https://github.com/yagmurcinarr/kariyerradar/actions/workflows/ci.yml)
[![Günlük veri hattı](https://github.com/yagmurcinarr/kariyerradar/actions/workflows/daily_pipeline.yml/badge.svg)](https://github.com/yagmurcinarr/kariyerradar/actions/workflows/daily_pipeline.yml)

**🔗 Canlı demo:** https://kariyerradar-jyunakkgmtsje9pwbolycs.streamlit.app/

> Ayrıntılı plan ve mimari: [CLAUDE.md](CLAUDE.md)

## Hızlı başlangıç (lokal)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # POSTGRES_PASSWORD ve DATABASE_URL'i düzenleyin
docker compose up -d          # PostgreSQL + pgvector, host portu 5433
pytest
python -m scraper.run --source all   # ilanları topla → raw.job_postings
python -m pipeline.run_dbt build     # dbt: seed + modeller + testler → staging, marts
```

Dashboard:

```bash
streamlit run dashboard/app.py       # http://localhost:8501
```

| Sayfa | İçerik |
|---|---|
| Genel Bakış | Toplam / giriş seviyesi ilan sayısı, en yeni giriş seviyesi ilanlar |
| Trendler | En çok istenen 15 beceri, haftalık ilan sayısı, şehir ve iş türü dağılımı |
| İlan Arama | Şehir, iş türü, beceri ve metin filtreleri; ilana link |

## Veri modeli (dbt)

| Katman | Tablo | İçerik |
|---|---|---|
| staging | `stg_jobs` | Temizlenmiş ilanlar; şehir/ilçe ve iş türü (`staj`, `yeni_mezun`, `junior`, `diger`) |
| marts | `fct_job` | İlan olgu tablosu |
| marts | `dim_company` | Firma boyutu |
| marts | `dim_skill` | ~100 becerilik sözlük ([seeds/skills.csv](pipeline/seeds/skills.csv)) |
| marts | `bridge_job_skill` | İlan metninde geçen beceriler (regex, kelime sınırıyla) |

## Veri kaynakları

İlanlar, şirketlerin kullandığı ATS'lerin (Lever, Greenhouse, Workable) **herkese açık ilan
API'lerinden** toplanır. Bu API'ler ilanların dış sitelerde yayınlanması için tasarlanmıştır.
İlan sitelerinin `robots.txt` ve kullanım koşulları incelenmiş, otomatik toplamayı yasaklayan
siteler kullanılmamıştır. İlan metinlerindeki e-posta ve telefon numaraları kaydedilmeden önce
silinir. Şirket listesi: [scraper/companies.py](scraper/companies.py).
