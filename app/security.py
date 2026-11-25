"""Подпись initData Telegram WebApp, токены и вебхук-подписи."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
import time
from urllib.parse import parse_qsl

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def verify_init_data(init_data: str, bot_token: str, max_age: int = 86_400) -> dict | None:
    """Проверяет подпись Telegram.WebApp.initData. Возвращает разобранные данные."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        return None

    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        return None
    if max_age > 0 and (time.time() - auth_date) > max_age:
        return None

    user_raw = pairs.get("user")
    if user_raw:
        try:
            pairs["user"] = json.loads(user_raw)
        except json.JSONDecodeError:
            return None
    return pairs


def sign_payload(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def verify_payload(raw: bytes, secret: str, signature: str) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign_payload(raw, secret), signature)


def new_deal_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(6))
    return f"KST-{body}"


def new_token(length: int = 16) -> str:
    return secrets.token_urlsafe(length)


def new_id() -> str:
    return secrets.token_hex(8)


def normalize_code(raw: str) -> str:
    """Принимает KST-ABC123, kstabc123 или ссылку — возвращает код в верхнем регистре."""
    text = (raw or "").strip().upper()
    for prefix in ("HTTPS://T.ME/", "HTTP://T.ME/", "T.ME/"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if "?START=DEAL_" in text:
        text = text.split("?START=DEAL_", 1)[1]
    text = text.replace("DEAL_", "").replace("KST", "").strip("-_ ")
    if not text:
        return ""
    return f"KST-{text}"[:20]
