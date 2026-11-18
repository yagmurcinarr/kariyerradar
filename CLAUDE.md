# StajRadar — Proje Planı ve Mimari

> Bu dosya projenin ana rehberidir. Claude Code her oturumda bunu okur.
> Kural: Her aşamayı sırayla yap, bir aşama "Kabul kriterleri" sağlanmadan sonrakine geçme.

## 1. Proje Özeti

**StajRadar**, Türkiye'deki staj ve yeni mezun ilanlarını her gün otomatik toplayan,
temizleyen, analiz eden ve kullanıcının CV'sine göre en uygun ilanları öneren
uçtan uca bir veri ve yapay zekâ sistemidir.

İki parçadan oluşur:
1. **Veri hattı + dashboard (Data Engineering):** İlan toplama → veritabanı → dbt ile dönüşüm → Streamlit dashboard
2. **CV eşleştirme asistanı (ML Engineering / RAG):** Embedding + vektör arama + LLM ile açıklamalı öneri

Geliştirici: Merve — Pamukkale Üniversitesi YBS 4. sınıf. Geliştirme ortamı: macOS, VS Code, zsh terminal.
Komutları macOS'a göre ver (Homebrew, `python3`, `source .venv/bin/activate`). Proje CV/portföy amaçlıdır;
kod okunabilir, iyi belgelenmiş ve tekrar üretilebilir olmalıdır.

## 2. Genel Sistem Mimarisi

```
┌──────────────────────────────────────────────────────────────────────┐
│                         VERİ KAYNAKLARI                              │
│   İlan siteleri (robots.txt + kullanım koşullarına uygun olanlar)    │
└───────────────┬──────────────────────────────────────────────────────┘
                │  (GitHub Actions — günde 1 kez, cron)
                ▼
┌──────────────────────────┐
│  scraper/                │  Site başına bir "collector" sınıfı
│  - base.py (arayüz)      │  Rate limit, retry, User-Agent, loglama
│  - <site>_collector.py   │
└───────────────┬──────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PostgreSQL (+ pgvector)   — lokalde Docker, bulutta Neon/Supabase   │
│                                                                      │
│  raw.job_postings      ← ham veri (append-only, scraped_at ile)      │
│        │                                                             │
│        ▼  dbt                                                        │
│  staging.stg_jobs      ← temizlenmiş, standart şehir/tarih           │
│  marts.dim_company     ← firma boyutu                                │
│  marts.dim_skill       ← beceri sözlüğü                              │
│  marts.fct_job         ← ilan olgu tablosu                           │
│  marts.bridge_job_skill← ilan–beceri ilişkisi                        │
│  ml.job_embeddings     ← ilan vektörleri (pgvector)                  │
└───────┬──────────────────────────────────────┬───────────────────────┘
        │                                      │
        ▼                                      ▼
┌──────────────────────┐          ┌───────────────────────────────────┐
│ dashboard/ (Streamlit)│          │ matching/ (FastAPI)               │
│ - Beceri trendleri    │          │ POST /match  (CV PDF/metin)       │
│ - Şehir dağılımı      │◄────────►│  1. CV metnini çıkar              │
│ - İlan arama/filtre   │  HTTP    │  2. CV embedding'i üret           │
│ - "CV'ni yükle" sayfası│          │  3. pgvector ile top-k ilan       │
└──────────────────────┘          │  4. LLM ile eksik beceri analizi  │
                                  └───────────────────────────────────┘
```

### Teknoloji yığını

| Katman | Teknoloji | Not |
|---|---|---|
| Dil | Python 3.11+ | Bağımlılık yönetimi: `uv` veya `pip` + `requirements.txt` |
| Toplama | `httpx` / `requests`, `beautifulsoup4`, gerekirse `playwright` | |
| Veritabanı | PostgreSQL 16 + `pgvector` | Lokal: Docker. Bulut: Neon veya Supabase (ücretsiz, pgvector destekli) |
| Dönüşüm | `dbt-postgres` | staging → marts katmanları, testler |
| Orkestrasyon | GitHub Actions (cron) | Airflow opsiyonel, sonra |
| Embedding | `sentence-transformers` — `intfloat/multilingual-e5-small` | Türkçe destekli, CPU'da çalışır |
| LLM | Sağlayıcıdan bağımsız arayüz (`llm_client.py`) | Ücretsiz seçenek: Ollama (lokal) veya ücretsiz katmanlı bir API |
| API | FastAPI + Pydantic | |
| Arayüz | Streamlit | |
| Paketleme | Docker + docker-compose | |
| Kalite | `ruff`, `pytest`, `pre-commit` | |

## 3. Klasör Yapısı

```
stajradar/
├── CLAUDE.md                 # bu dosya
├── README.md                 # vitrin: problem, mimari, ekran görüntüleri, demo linki
├── .env.example              # DATABASE_URL, LLM_API_KEY vb. (gerçek .env commit edilmez)
├── docker-compose.yml        # postgres(pgvector), api, dashboard
├── requirements.txt
├── scraper/
│   ├── __init__.py
│   ├── base.py               # BaseCollector: fetch(), parse(), rate limit, retry
│   ├── models.py             # JobPosting dataclass / Pydantic modeli
│   ├── collectors/
│   │   └── <site>_collector.py
│   ├── db.py                 # raw tabloya upsert
│   └── run.py                # CLI: python -m scraper.run --source <site>
├── pipeline/                 # dbt projesi
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/stg_jobs.sql
│   │   └── marts/{dim_company,dim_skill,fct_job,bridge_job_skill}.sql
│   ├── seeds/skills.csv      # beceri sözlüğü (SQL, Python, SAP, Excel, Power BI ...)
│   └── tests/
├── matching/
│   ├── embed_jobs.py         # yeni ilanların embedding'ini üret, ml.job_embeddings'e yaz
│   ├── cv_parser.py          # PDF → metin (pypdf)
│   ├── retriever.py          # pgvector benzerlik araması
│   ├── llm_client.py         # sağlayıcıdan bağımsız LLM arayüzü
│   ├── prompts.py            # LLM prompt şablonları
│   └── api.py                # FastAPI uygulaması
├── dashboard/
│   ├── app.py
│   └── pages/
│       ├── 1_Trendler.py
│       ├── 2_Ilan_Arama.py
│       └── 3_CV_Eslestir.py
├── tests/
└── .github/workflows/
    ├── daily_pipeline.yml    # scrape → dbt run → embed
    └── ci.yml                # ruff + pytest
```

## 4. Veri Modeli

### raw.job_postings
| Kolon | Tip | Açıklama |
|---|---|---|
| id | bigserial PK | |
| source | text | site adı |
| source_job_id | text | sitedeki ilan kimliği |
| url | text | |
| title | text | |
| company | text | |
| location_raw | text | ham şehir/ilçe metni |
| job_type_raw | text | staj / yeni mezun / tam zamanlı ... |
| description | text | ilan metni |
| posted_at | timestamptz null | |
| scraped_at | timestamptz | |
| UNIQUE(source, source_job_id) | | tekrar eklemeyi engeller |

### ml.job_embeddings
| Kolon | Tip |
|---|---|
| job_id | FK → marts.fct_job |
| embedding | vector(384) |
| model_name | text |
| created_at | timestamptz |

## 5. Aşamalar (sırayla)

### Aşama 0 — Proje iskeleti
- Klasör yapısını, `requirements.txt`, `.env.example`, `.gitignore`, `docker-compose.yml` (sadece postgres+pgvector) oluştur.
- `ruff` ve `pytest` ayarla, `pre-commit` ekle.
- **Kabul kriterleri:** `docker compose up -d` ile veritabanı açılıyor; `pytest` boş da olsa çalışıyor.

### Aşama 1 — Veri toplama
- Kaynak seçmeden önce siteyi incele: `robots.txt` ve kullanım koşulları toplamaya izin veriyor mu? İzin vermeyen siteyi kullanma; Merve'ye sor.
- `BaseCollector`: istekler arası en az 2–3 sn bekleme, 3 deneme ile retry, açıklayıcı User-Agent, loglama.
- Kişisel veri (ilan verenin adı, telefonu, e-postası) toplama.
- İlk aşamada **1 kaynak**, sonra ikinci kaynak eklenebilir.
- `raw.job_postings` tablosuna upsert.
- **Kabul kriterleri:** `python -m scraper.run --source <site>` çalışınca en az 50 ilan tabloya yazılıyor; ikinci çalıştırmada tekrar kayıt oluşmuyor; parse fonksiyonu için kaydedilmiş örnek HTML ile en az 1 test var.

### Aşama 2 — dbt dönüşümleri
- `stg_jobs`: boşlukları temizle, şehir adlarını standartlaştır (ör. "Denizli / Merkezefendi" → şehir=Denizli, ilçe=Merkezefendi), iş türünü `staj | yeni_mezun | junior | diger` olarak sınıflandır (junior: giriş seviyesi odağı için eklendi).
- `seeds/skills.csv`: ~80 beceri ve eş anlamlıları (ör. `power bi, powerbi`).
- `bridge_job_skill`: ilan metninde geçen becerileri eşle (önce basit anahtar kelime eşleme; regex ile kelime sınırı kullan).
- dbt testleri: `unique`, `not_null`, `relationships`.
- **Kabul kriterleri:** `dbt run && dbt test` hatasız; her ilanın şehir ve iş türü dolu.

### Aşama 3 — Otomasyon
- `daily_pipeline.yml`: her gün 06:00 (UTC+3) → scrape → `dbt run` → `dbt test`.
- Veritabanı bağlantısı GitHub Secrets'tan (`DATABASE_URL`). Bulut DB: Neon veya Supabase.
- **Kabul kriterleri:** Workflow elle tetiklenince yeşil bitiyor; yeni ilanlar bulut DB'de görünüyor.

### Aşama 4 — Dashboard
- Sayfa 1 "Trendler": en çok istenen 15 beceri (bar), haftalık ilan sayısı (çizgi), şehir dağılımı.
- Sayfa 2 "İlan Arama": şehir, iş türü, beceri filtreleri; ilana link.
- Sorgular `marts` tablolarından; `st.cache_data` ile önbellek.
- **Kabul kriterleri:** `streamlit run dashboard/app.py` lokal çalışıyor; filtreler doğru sonuç veriyor.
- ➜ Bu noktada **Proje 1 tamam**: README'ye ekran görüntüsü ekle, Streamlit Cloud'a deploy et.

### Aşama 5 — Embedding ve vektör arama
- `CREATE EXTENSION vector;` ve `ml.job_embeddings` tablosu.
- `embed_jobs.py`: sadece embedding'i olmayan ilanları işle (artımlı). e5 modeli için metne `"passage: "` öneki, sorguya `"query: "` öneki ekle.
- Metin: `title + company + description` (çok uzunsa kırp).
- HNSW veya IVFFlat indeks, cosine mesafe.
- Günlük workflow'a `embed_jobs` adımını ekle.
- **Kabul kriterleri:** "Python SQL veri analizi stajı Denizli" sorgusu mantıklı ilk 10 sonucu döndürüyor.

### Aşama 6 — CV eşleştirme API (RAG)
- `POST /match`: PDF ya da düz metin CV alır, `top_k` parametresi (varsayılan 10), opsiyonel `city` ve `job_type` filtreleri.
- Akış: CV metni → embedding → pgvector top-k → her ilan için CV ile ilan becerilerini karşılaştır → LLM'e kısa bağlam ver → JSON çıktı:
  ```json
  {"matches": [{"job_id": 1, "title": "...", "company": "...", "url": "...",
                "score": 0.82, "matching_skills": ["SQL"], "missing_skills": ["Power BI"],
                "explanation": "kısa Türkçe açıklama"}]}
  ```
- Eşleşen/eksik becerileri **önce deterministik olarak** (beceri sözlüğüyle) hesapla; LLM yalnızca kısa açıklamayı yazsın. Böylece halüsinasyon azalır ve LLM olmadan da çalışır.
- `llm_client.py` sağlayıcıdan bağımsız olsun; anahtar `.env`'den. LLM erişilemezse açıklamasız sonuç dön.
- CV verisini diske ya da veritabanına **kaydetme**; sadece istek süresince bellekte tut.
- **Kabul kriterleri:** Örnek bir CV ile `/match` 5 sn altında anlamlı sonuç dönüyor; `pytest` ile API için en az 2 test.

### Aşama 7 — Arayüz entegrasyonu ve yayın
- Dashboard'a "CV Eşleştir" sayfası: PDF yükle → API'yi çağır → kartlar halinde sonuçlar, eksik beceriler vurgulu.
- `docker-compose.yml`'a `api` ve `dashboard` servislerini ekle.
- Deploy: dashboard → Streamlit Cloud veya Hugging Face Spaces; API → Hugging Face Spaces (Docker) veya Render ücretsiz katman.
- **Kabul kriterleri:** Canlı linkten uçtan uca çalışıyor.

### Aşama 8 — Vitrin (README)
- Problem tanımı (1 paragraf), mimari diyagram, ekran görüntüleri / GIF, kurulum adımları, sayılarla sonuçlar (toplam ilan sayısı, günlük işlenen ilan, ortalama yanıt süresi), gelecek planı.
- **Kabul kriterleri:** Projeyi hiç görmemiş biri README'yi okuyup 10 dakikada lokalde çalıştırabiliyor.

## 6. Kodlama Kuralları
- Kod ve değişken isimleri İngilizce; yorumlar ve README Türkçe olabilir.
- Gizli bilgiler (şifre, API anahtarı) asla koda yazılmaz, `.env` kullanılır, `.env` commit edilmez.
- Her modülde type hint ve kısa docstring.
- Fonksiyonlar küçük ve test edilebilir; ağ isteği yapan kod, parse eden koddan ayrı.
- Her aşama sonunda: `ruff check .`, `pytest` ve anlamlı bir git commit mesajı.
- Değişiklik yapmadan önce planı kısaca anlat, büyük kararlarda (kütüphane, kaynak site, bulut servisi) Merve'ye sor.

## 7. CV Hedef Maddesi
> Türkiye'deki staj ilanlarını her gün otomatik toplayan uçtan uca veri hattı (Python, PostgreSQL, dbt, GitHub Actions) ve CV'ye göre ilan önerip eksik becerileri açıklayan RAG tabanlı yapay zekâ asistanı (pgvector, FastAPI, Streamlit) geliştirdim. [X] ilan işlendi — canlı demo: [link]

---

## 8. Başlangıç Prompt'u (Claude Code'a ilk mesaj olarak yapıştır)

```
Merhaba! Bu repoda "StajRadar" projesini geliştireceğiz. Proje planı ve mimarisi
CLAUDE.md dosyasında. Lütfen önce CLAUDE.md'yi baştan sona oku.

Şimdi sadece "Aşama 0 — Proje iskeleti"ni yap:
1. Klasör yapısını oluştur (boş modüller __init__.py ile).
2. requirements.txt, .env.example, .gitignore, docker-compose.yml (postgres + pgvector),
   ruff ve pytest ayarlarını ekle.
3. Bana lokalde nasıl çalıştıracağımı adım adım anlat (macOS kullanıyorum; Homebrew, Python 3.11+
   ve Docker Desktop kurulu değilse kurulumlarını da söyle. Apple Silicon/Intel farkı varsa belirt).

Kurallar:
- Her adımdan önce ne yapacağını kısaca söyle.
- Aşama 0'ın kabul kriterlerini sağladığımızda dur ve bana özet ver; Aşama 1'e ben onay verince geç.
- Ben YBS öğrencisiyim, C# biliyorum, Python'da orta seviyedeyim: yazdığın kodu kısaca açıkla
  ki mülakatta anlatabileyim.
```

### Sonraki aşamalar için kısa prompt şablonu
```
CLAUDE.md'deki "Aşama N — <ad>"ı yapalım. Önce planını madde madde yaz, ben onaylayınca kodla.
Bitince kabul kriterlerini tek tek kontrol et, testleri çalıştır ve bana neyi neden yaptığını özetle.
```
