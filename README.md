# StajRadar

Türkiye'deki staj ve yeni mezun ilanlarını her gün toplayan veri hattı ve CV'ye göre ilan öneren yapay zekâ asistanı.

> 🚧 Geliştirme aşamasında. Ayrıntılı plan: [CLAUDE.md](CLAUDE.md)

## Hızlı başlangıç (lokal)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # POSTGRES_PASSWORD ve DATABASE_URL'i düzenleyin
docker compose up -d
pytest
```
