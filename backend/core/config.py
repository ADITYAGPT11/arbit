"""Application configuration — API keys and broker settings only. No database."""

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env')


class Settings:
    """Lightweight settings. No database — purely API-driven."""

    # Angel One platform-level (for publisher-login)
    ANGEL_API_KEY: str = os.environ.get("ARBIT_ANGEL_API_KEY", "").strip()
    ANGEL_API_SECRET: str = os.environ.get("ARBIT_ANGEL_API_SECRET", "").strip()
    ANGEL_REDIRECT_URL: str = os.environ.get("ARBIT_ANGEL_REDIRECT_URL", "").strip()

    # Angel One personal credentials (for system auto-login)
    ANGEL_CLIENT_ID: str = os.environ.get("ANGEL_CLIENT_ID", "").strip()
    ANGEL_MPIN: str = os.environ.get("ANGEL_MPIN", "").strip()
    ANGEL_TOTP_SECRET: str = os.environ.get("ANGEL_TOTP_SECRET", "").strip()

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    # Redis (future, for caching)
    REDIS_URL: str | None = os.environ.get("REDIS_URL")


settings = Settings()


def get_settings() -> Settings:
    return settings
