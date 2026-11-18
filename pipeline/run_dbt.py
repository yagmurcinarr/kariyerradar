"""dbt'yi .env'deki DATABASE_URL ile çalıştıran ince sarmalayıcı.

Neden: Projede tek bağlantı ayarı (DATABASE_URL) olsun; dbt ise host/port/user'ı ayrı ister.
Kullanım (proje kökünden):
    python -m pipeline.run_dbt seed
    python -m pipeline.run_dbt build      # seed + run + test, bağımlılık sırasıyla
"""

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent


def dbt_env_from_url(url: str) -> dict[str, str]:
    """postgresql://user:pass@host:port/db?sslmode=... → dbt'nin beklediği DBT_* değişkenleri."""
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"PostgreSQL adresi bekleniyordu, gelen: {parsed.scheme}://")
    env = {
        "DBT_HOST": parsed.hostname or "localhost",
        "DBT_PORT": str(parsed.port or 5432),
        "DBT_USER": unquote(parsed.username or ""),
        "DBT_PASSWORD": unquote(parsed.password or ""),
        "DBT_DBNAME": parsed.path.lstrip("/"),
    }
    sslmode = parse_qs(parsed.query).get("sslmode")
    if sslmode:
        env["DBT_SSLMODE"] = sslmode[0]
    return env


def main(argv: list[str] | None = None) -> int:
    from dbt.cli.main import dbtRunner  # ağır import; sadece gerçekten çalışırken yükle

    load_dotenv(PROJECT_DIR.parent / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL tanımlı değil (.env dosyasına bakın).", file=sys.stderr)
        return 1
    os.environ.update(dbt_env_from_url(url))

    args = list(sys.argv[1:] if argv is None else argv)
    args += ["--project-dir", str(PROJECT_DIR), "--profiles-dir", str(PROJECT_DIR)]
    result = dbtRunner().invoke(args)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
