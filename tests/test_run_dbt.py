"""pipeline.run_dbt: DATABASE_URL → dbt ortam değişkenleri dönüşümü."""

import pytest

from pipeline.run_dbt import dbt_env_from_url


def test_parses_local_url() -> None:
    env = dbt_env_from_url("postgresql://stajradar:gizli@localhost:5433/stajradar")
    assert env == {
        "DBT_HOST": "localhost",
        "DBT_PORT": "5433",
        "DBT_USER": "stajradar",
        "DBT_PASSWORD": "gizli",
        "DBT_DBNAME": "stajradar",
    }


def test_parses_cloud_url_with_sslmode_and_encoded_password() -> None:
    env = dbt_env_from_url("postgres://u:p%40ss@ep-x.neon.tech/db?sslmode=require")
    assert env["DBT_PASSWORD"] == "p@ss"  # URL kodlaması çözülmeli
    assert env["DBT_PORT"] == "5432"  # port yoksa varsayılan
    assert env["DBT_SSLMODE"] == "require"


def test_rejects_non_postgres_url() -> None:
    with pytest.raises(ValueError):
        dbt_env_from_url("mysql://u:p@host/db")
