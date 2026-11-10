"""Read local MySQL settings without putting credentials in source code."""

from __future__ import annotations

import tomllib
from pathlib import Path

from sqlalchemy import URL, create_engine


PROJECT_DIR = Path(__file__).resolve().parent
MYSQL_SECRETS_PATH = PROJECT_DIR / ".streamlit" / "secrets.toml"
REQUIRED_MYSQL_SETTINGS = ("host", "port", "database", "username", "password")


def has_mysql_secrets() -> bool:
    """Return True only when a complete MySQL configuration is available."""
    if not MYSQL_SECRETS_PATH.is_file():
        return False

    try:
        with MYSQL_SECRETS_PATH.open("rb") as secrets_file:
            settings = tomllib.load(secrets_file).get("mysql", {})
    except (OSError, tomllib.TOMLDecodeError):
        return False

    return all(settings.get(key) for key in REQUIRED_MYSQL_SETTINGS)


def load_mysql_settings() -> dict:
    if not MYSQL_SECRETS_PATH.is_file():
        raise FileNotFoundError(
            f"MySQL settings not found at {MYSQL_SECRETS_PATH}. "
            "Copy .streamlit/secrets.toml.example to .streamlit/secrets.toml and fill it in."
        )

    with MYSQL_SECRETS_PATH.open("rb") as secrets_file:
        settings = tomllib.load(secrets_file).get("mysql", {})

    missing = [key for key in REQUIRED_MYSQL_SETTINGS if not settings.get(key)]
    if missing:
        raise ValueError(f"Missing MySQL settings in secrets.toml: {', '.join(missing)}")

    return settings


def create_mysql_engine():
    settings = load_mysql_settings()
    url = URL.create(
        "mysql+pymysql",
        username=settings["username"],
        password=settings["password"],
        host=settings["host"],
        port=int(settings["port"]),
        database=settings["database"],
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True)
