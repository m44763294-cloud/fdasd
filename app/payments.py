"""Платёжные провайдеры: mock и реальный CryptoPay (@CryptoBot)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import aiohttp

from .config import settings
from .models import CURRENCIES, currency_or_raise
from .security import verify_payload

log = logging.getLogger("kustos.payments")


class PaymentError(Exception):
    pass


@dataclass
class Deposit:
    provider: str
    ref: str
    address: str | None
    memo: str | None
    uri: str | None
    pay_url: str | None
    amount: str
    currency: str
    expires_at: str


@dataclass
class PayoutResult:
    ok: bool
    ref: str
    status: str = "sent"


@dataclass
class PaymentEvent:
    deal_code: str
    ref: str
    amount: Decimal | None
    currency: str
    provider: str
    raw: dict


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _expiry() -> str:
    return _iso(_now() + timedelta(minutes=settings.payment_ttl_minutes))


def _mock_address(currency: str, code: str) -> str:
    if currency == "BTC":
        return "bc1q" + secrets.token_hex(19)
    if currency in {"ETH", "USDC"}:
        return "0x" + secrets.token_hex(20)
    if currency == "USDT":
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return "T" + "".join(secrets.choice(alphabet) for _ in range(33))
    if currency == "TON":
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        return "UQ" + "".join(secrets.choice(alphabet) for _ in range(46))
    return f"ATLANTA-{code}"


def _wallet_uri(currency: str, address: str, amount: str) -> str | None:
    if currency == "BTC":
        return f"bitcoin:{address}?amount={amount}"
    if currency == "ETH":
        return f"ethereum:{address}"
    if currency == "TON":
        try:
            nano = int(Decimal(amount) * Decimal(10**9))
            return f"ton://transfer/{address}?amount={nano}"
        except Exception:
            return f"ton://transfer/{address}"
    if currency == "USDT":
        return f"https://tronscan.org/#/address/{address}"
    return None


class MockProvider:
    """Тестовый провайдер: генерирует реквизиты, подтверждение — через вебхук."""

    name = "mock"

    async def create_deposit(self, deal: dict) -> Deposit:
        currency = deal["currency"]
        info = currency_or_raise(currency)
        address = _mock_address(currency, deal["code"])
        token = secrets.token_hex(8)
        return Deposit(
            provider=self.name,
            ref=f"mock_{deal['id']}_{token}",
            address=address,
            memo=deal["code"] if info.kind == "crypto" else "ATLANTA",
            uri=_wallet_uri(currency, address, deal["amount"]),
            pay_url=None,
            amount=deal["amount"],
            currency=currency,
            expires_at=_expiry(),
        )

    async def parse_webhook(self, headers: dict, raw: bytes, payload: dict) -> PaymentEvent | None:
        signature = headers.get("x-webhook-signature") or headers.get("X-Webhook-Signature") or ""
        if not verify_payload(raw, settings.webhook_secret, signature):
            raise PaymentError("Неверная подпись вебхука")
        if payload.get("event") != "payment.confirmed":
            return None
        code = str(payload.get("deal_code", "")).upper()
        if not code:
            raise PaymentError("В вебхуке нет deal_code")
        amount = payload.get("amount")
        return PaymentEvent(
            deal_code=code,
            ref=str(payload.get("ref", "")),
            amount=Decimal(str(amount)) if amount is not None else None,
            currency=str(payload.get("currency", "")).upper(),
            provider=self.name,
            raw=payload,
        )

    async def payout(self, user: dict, amount: str, currency: str, address: str) -> PayoutResult:
        return PayoutResult(ok=True, ref=f"mock_payout_{secrets.token_hex(8)}", status="sent")


class CryptoPayProvider:
    """Реальный приём крипты через CryptoPay API. Включается токеном и PAYMENT_PROVIDER=cryptopay."""

    name = "cryptopay"
    API = "https://pay.crypt.bot/api/"

    def __init__(self, token: str) -> None:
        self.token = token

    async def _call(self, method: str, payload: dict[str, Any] | None = None) -> dict:
        headers = {"Crypto-Pay-API-Token": self.token}
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.API + method, json=payload or {}, headers=headers) as resp:
                data = await resp.json(content_type=None)
        if not data.get("ok"):
            raise PaymentError(f"CryptoPay {method}: {data.get('error', 'unknown error')}")
        return data["result"]

    async def create_deposit(self, deal: dict) -> Deposit:
        asset = deal["currency"]
        if asset not in {"USDT", "TON", "BTC", "ETH", "USDC"}:
            raise PaymentError(f"CryptoPay не поддерживает {asset}")
        result = await self._call(
            "createInvoice",
            {
                "asset": asset,
                "amount": deal["amount"],
                "description": f"ATLANTA · {deal['code']} · {deal['title'][:80]}",
                "payload": deal["code"],
                "expires_in": settings.payment_ttl_minutes * 60,
                "allow_comments": False,
                "allow_anonymous": False,
            },
        )
        return Deposit(
            provider=self.name,
            ref=str(result["invoice_id"]),
            address=None,
            memo=None,
            uri=None,
            pay_url=result.get("mini_app_invoice_url") or result.get("bot_invoice_url"),
            amount=deal["amount"],
            currency=asset,
            expires_at=result.get("expiration_date") or _expiry(),
        )

    async def parse_webhook(self, headers: dict, raw: bytes, payload: dict) -> PaymentEvent | None:
        token = headers.get("crypto-pay-api-token") or headers.get("Crypto-Pay-API-Token") or ""
        if not hmac.compare_digest(token, self.token):
            raise PaymentError("Неверный токен вебхука CryptoPay")
        if payload.get("update_type") != "invoice_paid":
            return None
        invoice = payload.get("payload") or {}
        code = str(invoice.get("payload", "")).upper()
        invoice_id = invoice.get("invoice_id")
        if not code or invoice_id is None:
            raise PaymentError("Некорректный вебхук CryptoPay")

        # Перепроверяем статус счёта на стороне CryptoPay, не доверяем телу вебхука.
        verified = await self._call("getInvoices", {"invoice_ids": str(invoice_id), "count": 1})
        items = verified.get("items") or []
        if not items or items[0].get("status") != "paid":
            raise PaymentError("Счёт CryptoPay не оплачен")
        item = items[0]
        return PaymentEvent(
            deal_code=code,
            ref=str(invoice_id),
            amount=Decimal(str(item.get("paid_amount") or item.get("amount"))),
            currency=str(item.get("asset", "")).upper(),
            provider=self.name,
            raw=item,
        )

    async def payout(self, user: dict, amount: str, currency: str, address: str) -> PayoutResult:
        result = await self._call(
            "transfer",
            {
                "user_id": int(user["id"]),
                "asset": currency,
                "amount": amount,
                "spend_id": f"kustos_{user['id']}_{secrets.token_hex(6)}",
                "comment": "ATLANTA payout",
            },
        )
        return PayoutResult(ok=True, ref=str(result.get("transfer_id", "")), status="sent")


_provider: Any = None


def init_provider() -> None:
    global _provider
    if settings.payment_provider == "cryptopay" and settings.cryptopay_token:
        _provider = CryptoPayProvider(settings.cryptopay_token)
        log.info("Платёжный провайдер: CryptoPay")
    else:
        _provider = MockProvider()
        log.info("Платёжный провайдер: mock")


def get_provider(currency: str | None = None) -> Any:
    global _provider
    if _provider is None:
        init_provider()
    if currency and currency in CURRENCIES and CURRENCIES[currency].kind == "fiat":
        return MockProvider()
    return _provider


def webhook_payload_from_raw(raw: bytes) -> dict:
    try:
        data = json.loads(raw or b"{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise PaymentError("Некорректный JSON вебхука") from exc
