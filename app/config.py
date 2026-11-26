"""Конфигурация ATLANTA. Читается из окружения и .env без внешних зависимостей."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Владелец бота по умолчанию: арбитр, которому доступны админ-команды.
# Переопределяется переменной ADMIN_IDS.
DEFAULT_ADMIN_IDS = "976961244"


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


def _detect_public_url() -> str:
    """Адрес, который платформа хостинга сообщает через переменные окружения."""
    for name in (
        "APP_URL",
        "PUBLIC_DOMAIN",
        "DOMAIN",
        "RAILWAY_PUBLIC_DOMAIN",
        "RENDER_EXTERNAL_URL",
        "VERCEL_URL",
        "BOTHOST_DOMAIN",
    ):
        value = os.getenv(name, "").strip().rstrip("/")
        if not value:
            continue
        if value.startswith("http://"):
            value = f"https://{value[len('http://'):]}"
        elif not value.startswith("https://"):
            value = f"https://{value}"
        return value
    return ""


class Settings:
    def __init__(self) -> None:
        self.bot_token: str = os.getenv("BOT_TOKEN", "").strip()
        # Bothost подставляет токен и домен сам; username уточняется через getMe при старте.
        self.bot_username: str = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
        explicit_public_url = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
        self.public_url_explicit: bool = bool(explicit_public_url)
        self.public_url: str = explicit_public_url or _detect_public_url() or "http://127.0.0.1:8080"
        self._webapp_url: str = os.getenv("WEBAPP_URL", "").strip()
        self._market_url: str = os.getenv("MARKET_URL", "").strip()
        self.gram_receive_address: str = os.getenv("GRAM_RECEIVE_ADDRESS", "").strip()
        self.gram_receive_comment: str = os.getenv("GRAM_RECEIVE_COMMENT", "ATLANTA GRAM topup").strip()
        self.gift_receive_username: str = os.getenv("GIFT_RECEIVE_USERNAME", "").strip().lstrip("@")

        # Пополнение маркета: счёт в валюте Crypto Pay, зачисление в GRAM по курсу.
        self.topup_asset: str = os.getenv("TOPUP_ASSET", "TON").strip().upper() or "TON"
        try:
            self.gram_per_unit: float = float(os.getenv("GRAM_PER_UNIT") or os.getenv("GRAM_PER_TON") or "1000")
        except ValueError:
            self.gram_per_unit = 1000.0
        if self.gram_per_unit <= 0:
            self.gram_per_unit = 1000.0
        self.market_min_topup: float = float(os.getenv("MARKET_MIN_TOPUP", "10"))
        self.market_min_withdraw: float = float(os.getenv("MARKET_MIN_WITHDRAW", "10"))

        self.admin_ids: tuple[int, ...] = tuple(
            int(x)
            for x in os.getenv("ADMIN_IDS", DEFAULT_ADMIN_IDS).replace(";", ",").split(",")
            if x.strip().isdigit()
        )
        self.dev_mode: bool = _flag("DEV_MODE", "1")

        self.db_path: Path = Path(
            os.getenv("DB_PATH", str(Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))) / "kustos.db"))
        )
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
    def webapp_url(self) -> str:
        base = self._webapp_url or f"{self.public_url}/app/"
        return base if base.endswith("/") else f"{base}/"

    @property
    def market_url(self) -> str:
        base = self._market_url or f"{self.public_url}/market/"
        return base if base.endswith("/") else f"{base}/"

    @property
    def public_url_ready(self) -> bool:
        """Telegram открывает Mini App только по живому HTTPS-адресу."""
        return self.public_url.startswith("https://")

    def set_public_url(self, url: str) -> bool:
        """Подхватить публичный адрес из запроса, если PUBLIC_URL не задан вручную."""
        if self.public_url_explicit or self.public_url_ready:
            return False
        url = (url or "").strip().rstrip("/")
        if not url.startswith("https://") or url == self.public_url:
            return False
        self.public_url = url
        return True

    @property
    def is_production(self) -> bool:
        return not self.dev_mode


settings = Settings()
