# StajRadar

Türkiye'deki staj ve yeni mezun ilanlarını her gün toplayan veri hattı ve CV'ye göre ilan öneren yapay zekâ asistanı.

> 🚧 Geliştirme aşamasında. Ayrıntılı plan: [CLAUDE.md](CLAUDE.md)

## Hızlı başlangıç (lokal)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # POSTGRES_PASSWORD ve DATABASE_URL'i düzenleyin
docker compose up -d          # PostgreSQL + pgvector, host portu 5433
pytest
python -m scraper.run --source all   # ilanları topla → raw.job_postings
```

## Veri kaynakları

İlanlar, şirketlerin kullandığı ATS'lerin (Lever, Greenhouse, Workable) **herkese açık ilan
API'lerinden** toplanır. Bu API'ler ilanların dış sitelerde yayınlanması için tasarlanmıştır.
İlan sitelerinin `robots.txt` ve kullanım koşulları incelenmiş, otomatik toplamayı yasaklayan
siteler kullanılmamıştır. İlan metinlerindeki e-posta ve telefon numaraları kaydedilmeden önce
silinir. Şirket listesi: [scraper/companies.py](scraper/companies.py).
