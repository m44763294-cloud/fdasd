"""Конфигурация ATLANTA. Читается из окружения и .env без внешних зависимостей."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_env()


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        self.bot_token: str = os.getenv("BOT_TOKEN", "").strip()
        self.bot_username: str = os.getenv("BOT_USERNAME", "atlantaotcbot").strip().lstrip("@")
        self.public_url: str = os.getenv("PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
        self.webapp_url: str = (
            os.getenv("WEBAPP_URL", "").strip() or f"{self.public_url}/app/"
        )
        if not self.webapp_url.endswith("/"):
            self.webapp_url += "/"
        self.market_url: str = os.getenv("MARKET_URL", "").strip() or f"{self.public_url}/market/"
        self.gram_receive_address: str = os.getenv("GRAM_RECEIVE_ADDRESS", "").strip()
        self.gram_receive_comment: str = os.getenv("GRAM_RECEIVE_COMMENT", "ATLANTA GRAM topup").strip()
        self.gift_receive_username: str = os.getenv("GIFT_RECEIVE_USERNAME", "").strip().lstrip("@")

        self.admin_ids: tuple[int, ...] = tuple(
            int(x) for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip().isdigit()
        )
        self.dev_mode: bool = _flag("DEV_MODE", "1")

        self.db_path: Path = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "kustos.db")))
        self.web_dir: Path = BASE_DIR / "web"

        self.payment_provider: str = os.getenv("PAYMENT_PROVIDER", "mock").strip().lower()
        self.cryptopay_token: str = os.getenv("CRYPTOPAY_TOKEN", "").strip()
        self.webhook_secret: str = os.getenv("PAYMENT_WEBHOOK_SECRET", "dev-webhook-secret").strip()
        self.payment_ttl_minutes: int = int(os.getenv("PAYMENT_TTL_MINUTES", "45"))

        self.fee_crypto: float = float(os.getenv("FEE_CRYPTO", "1.5"))
        self.fee_fiat: float = float(os.getenv("FEE_FIAT", "2.5"))
        self.min_fee_usd: float = float(os.getenv("MIN_FEE_USD", "0.30"))

        self.brand: str = "ATLANTA"
        self.tagline: str = "Сделки под контролем"
        self.support_username: str = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")

    @property
    def is_production(self) -> bool:
        return not self.dev_mode


settings = Settings()
