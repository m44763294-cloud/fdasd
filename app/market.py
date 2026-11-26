"""ATLANTA Market: каталог, кошелёк GRAM, заказы и пополнение через Crypto Pay.

Маркет работает на том же FastAPI-сервере, что и OTC-приложение: Telegram initData
проверяется один раз, баланс и заказы хранятся в SQLite, счёт на пополнение
выставляется в валюте Crypto Pay и зачисляется в GRAM по курсу GRAM_PER_UNIT.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import payments
from .auth import current_user
from .config import settings
from .db import db
from .escrow import EscrowError
from .notify import notifier
from .security import new_id

log = logging.getLogger("kustos.market")
router = APIRouter(prefix="/api/market")

MARKET_DIR = settings.web_dir / "market"
CENT = Decimal("0.01")

TERMS: dict[int, tuple[Decimal, str]] = {
    1: (Decimal("1"), "1 месяц"),
    3: (Decimal("0.95"), "3 месяца"),
    6: (Decimal("0.90"), "6 месяцев"),
}
STATUS_LABELS = {
    "paid": "оплачен · ожидает выдачи",
    "fulfilled": "выдан",
    "cancelled": "отменён",
    "refunded": "возврат",
}
PAYOUT_STATUSES = {"paid", "rejected"}


# --------------------------------------------------------------------------- catalog


def _load_lots() -> dict[str, dict]:
    path = MARKET_DIR / "market-data.js"
    try:
        raw = path.read_text(encoding="utf-8")
        start = raw.index("window.ATLANTA_MARKET")
        start = raw.index("=", start) + 1
        end = raw.rindex(";")
        items = json.loads(raw[start:end].strip())
    except (OSError, ValueError, json.JSONDecodeError):
        log.exception("Не удалось загрузить каталог маркета: %s", path)
        return {}
    return {str(item.get("id")): item for item in items if item.get("id")}


def _load_numbers() -> dict[str, dict]:
    path = MARKET_DIR / "numbers.json"
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        log.exception("Не удалось загрузить номера маркета: %s", path)
        return {}
    return {str(item.get("num")): item for item in items if item.get("num")}


LOTS = _load_lots()
NUMBERS = _load_numbers()
log.info("Маркет: %s лотов, %s номеров", len(LOTS), len(NUMBERS))


# --------------------------------------------------------------------------- helpers


def _money(value: Decimal | float | str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise EscrowError("Некорректная сумма") from exc


def _float(value: Decimal | str) -> float:
    return float(Decimal(str(value)))


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _date_label(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return (value or "")[:10]


def _public_user(user: dict) -> dict:
    return {
        "id": user.get("id"),
        "first_name": user.get("first_name") or "Пользователь",
        "last_name": user.get("last_name") or "",
        "username": user.get("username") or "",
        "photo_url": user.get("photo_url") or "",
    }


def _public_order(row: dict) -> dict:
    months = int(row.get("months") or 1)
    return {
        "id": row["id"],
        "type": row["type"],
        "mode": row["mode"],
        "title": row["title"],
        "subtitle": row["subtitle"],
        "amount": row["amount"],
        "currency": row["currency"],
        "months": months,
        "term_label": TERMS.get(months, (Decimal("1"), ""))[1],
        "gift_id": row.get("gift_id"),
        "number": row.get("number"),
        "anonymous": bool(row.get("anonymous")),
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "created_at": row["created_at"],
    }


async def _wallet_state(user_id: int) -> tuple[Decimal, Decimal]:
    row = await db.fetchone("SELECT available, pending FROM market_wallets WHERE user_id=?", (user_id,))
    if not row:
        return Decimal("0"), Decimal("0")
    return Decimal(row["available"]), Decimal(row["pending"])


async def _wallet_add(
    conn,
    user_id: int,
    delta: Decimal,
    kind: str,
    note: str,
    ref: str | None = None,
    pending_delta: Decimal = Decimal("0"),
) -> Decimal:
    """Изменить доступный и зарезервированный баланс в одной транзакции."""
    await conn.execute("INSERT OR IGNORE INTO market_wallets (user_id) VALUES (?)", (user_id,))
    cur = await conn.execute(
        "SELECT available, pending FROM market_wallets WHERE user_id=?", (user_id,)
    )
    row = await cur.fetchone()
    available = Decimal(row["available"]) + delta
    pending = Decimal(row["pending"]) + pending_delta
    if available < 0:
        raise EscrowError("Недостаточно GRAM на балансе", 409, "insufficient_funds")
    if pending < 0:
        pending = Decimal("0")
    await conn.execute(
        "UPDATE market_wallets SET available=?, pending=? WHERE user_id=?",
        (format(available, "f"), format(pending, "f"), user_id),
    )
    if delta != 0:
        await conn.execute(
            "INSERT INTO market_ledger (user_id, amount, kind, note, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, format(delta, "f"), kind, note, ref, _stamp()),
        )
    return available


async def _quote(payload: "OrderIn") -> dict:
    """Посчитать цену на сервере. Клиент не может подменить сумму заказа."""
    if payload.type == "gift":
        lot = LOTS.get(str(payload.giftId or ""))
        if not lot:
            raise EscrowError("Подарок не найден — обнови каталог", 404, "lot_not_found")
        name = str(lot.get("name") or "Подарок")
        subtitle = str(lot.get("model") or "")
        gift_id = str(lot["id"])
        number = str(lot.get("num") or "")
        anonymous = False
        months = int(payload.months or 1)
        if payload.mode == "rent":
            if months not in TERMS:
                raise EscrowError("Некорректный срок аренды")
            discount, label = TERMS[months]
            amount = _money(Decimal(str(lot.get("rent") or 0)) * months * discount)
        else:
            months = 1
            label = TERMS[1][1]
            amount = _money(lot.get("price") or 0)
    else:
        number_raw = str(payload.number or "").strip()
        item = NUMBERS.get(number_raw)
        if not item:
            raise EscrowError("Номер не найден — обнови каталог", 404, "number_not_found")
        name = "Анонимный номер +888"
        subtitle = str(item.get("tag") or "Fragment · +888")
        gift_id = None
        number = number_raw
        anonymous = True
        months = int(payload.months or 1)
        if payload.mode == "rent":
            if months not in TERMS:
                raise EscrowError("Некорректный срок аренды")
            discount, label = TERMS[months]
            amount = _money(Decimal(str(item.get("rent") or 0)) * months * discount)
        else:
            months = 1
            label = TERMS[1][1]
            amount = _money(item.get("price") or 0)

    if amount <= 0:
        raise EscrowError("Некорректная цена заказа", 400, "bad_price")
    return {
        "title": name,
        "subtitle": subtitle,
        "amount": amount,
        "months": months,
        "term_label": label,
        "gift_id": gift_id,
        "number": number,
        "anonymous": anonymous,
    }


def _require_admin(user: dict) -> None:
    if not user.get("is_admin"):
        raise EscrowError("Недостаточно прав", 403, "forbidden")


# --------------------------------------------------------------------------- schemas


class TopupIn(BaseModel):
    amount: float = Field(gt=0, le=100_000)


class OrderIn(BaseModel):
    type: Literal["gift", "number"]
    mode: Literal["buy", "rent"]
    giftId: str | None = None
    number: str | None = None
    months: int = 1


class WithdrawIn(BaseModel):
    amount: float = Field(gt=0)
    address: str = Field(min_length=4, max_length=160)


class PayoutActionIn(BaseModel):
    status: Literal["paid", "rejected"]


# --------------------------------------------------------------------------- endpoints


@router.get("/me")
async def market_me(request: Request) -> dict:
    user = await current_user(request)
    uid = int(user["id"])
    available, pending = await _wallet_state(uid)
    rows = await db.fetchall(
        "SELECT amount, kind, note, created_at FROM market_ledger WHERE user_id=? ORDER BY id DESC LIMIT 24",
        (uid,),
    )
    ops = []
    for row in rows:
        amount = Decimal(row["amount"])
        ops.append(
            {
                "type": "in" if amount > 0 else "out",
                "title": row["note"] or row["kind"],
                "amount": _float(abs(amount)),
                "date": _date_label(row["created_at"]),
            }
        )
    orders = await db.fetchall(
        "SELECT * FROM market_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 40",
        (uid,),
    )
    return {
        "user": _public_user(user),
        "balance": _float(available),
        "pending": _float(pending),
        "ops": ops,
        "orders": [_public_order(row) for row in orders],
    }


@router.post("/topup")
async def market_topup(request: Request, payload: TopupIn) -> dict:
    user = await current_user(request)
    amount = _money(payload.amount)
    if amount < _money(settings.market_min_topup):
        raise EscrowError(f"Минимальное пополнение — {settings.market_min_topup:g} GRAM")
    if amount > _money(100_000):
        raise EscrowError("Слишком большая сумма пополнения")

    provider = payments.get_provider()
    if not isinstance(provider, payments.CryptoPayProvider):
        raise EscrowError(
            "Пополнение временно недоступно: Crypto Pay не настроен",
            503,
            "topup_unavailable",
        )

    asset = settings.topup_asset
    if asset not in {"USDT", "TON", "BTC", "ETH", "USDC"}:
        raise EscrowError(f"Crypto Pay не поддерживает {asset}", 503, "topup_unavailable")

    units = (amount / Decimal(str(settings.gram_per_unit))).quantize(Decimal("0.000001"))
    if units <= 0:
        raise EscrowError("Сумма слишком мала для счёта")

    try:
        invoice = await provider.create_market_invoice(
            asset=asset,
            amount=format(units, "f"),
            description=f"ATLANTA Market · {amount:g} GRAM",
            payload=f"market:{user['id']}:{secrets.token_hex(6)}",
            expires_in=max(600, settings.payment_ttl_minutes * 60),
        )
    except payments.PaymentError as exc:
        log.warning("Crypto Pay не создал счёт: %s", exc)
        raise EscrowError(f"Не удалось создать счёт: {exc}", 502, "topup_failed") from exc

    invoice_id = str(invoice["invoice_id"])
    pay_url = invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url")
    mini_app_url = invoice.get("mini_app_invoice_url") or invoice.get("bot_invoice_url")
    await db.execute(
        """INSERT INTO market_invoices (id, user_id, gram, asset, units, status, pay_url, mini_app_url, created_at)
           VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
        (invoice_id, int(user["id"]), format(amount, "f"), asset, format(units, "f"), pay_url, mini_app_url, _stamp()),
    )
    return {
        "invoiceId": invoice_id,
        "payUrl": pay_url,
        "miniAppUrl": mini_app_url,
        "amount": _float(amount),
        "currency": "GRAM",
        "asset": asset,
        "units": _float(units),
    }


@router.get("/topup/{invoice_id}")
async def market_topup_status(request: Request, invoice_id: str) -> dict:
    user = await current_user(request)
    row = await db.fetchone(
        "SELECT id, gram, status FROM market_invoices WHERE id=? AND user_id=?",
        (invoice_id, int(user["id"])),
    )
    if not row:
        raise EscrowError("Счёт не найден", 404, "invoice_not_found")
    return {"invoiceId": row["id"], "amount": _float(row["gram"]), "status": row["status"]}


@router.post("/crypto/webhook")
async def market_crypto_webhook(request: Request) -> dict:
    """Вебхук Crypto Pay. Подпись проверяется по сырому телу, статус — в API."""
    if not settings.cryptopay_token:
        raise HTTPException(status_code=503, detail="Crypto Pay не настроен")
    raw = await request.body()
    signature = request.headers.get("crypto-pay-api-signature", "")
    secret = hashlib.sha256(settings.cryptopay_token.encode()).digest()
    calculated = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(calculated, signature):
        raise HTTPException(status_code=401, detail="Неверная подпись вебхука")

    try:
        update = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Некорректный JSON") from exc

    if update.get("update_type") != "invoice_paid":
        return {"ok": True, "ignored": True}

    invoice = update.get("payload") or {}
    invoice_id = str(invoice.get("invoice_id") or "")
    row = await db.fetchone("SELECT * FROM market_invoices WHERE id=?", (invoice_id,))
    if not row:
        return {"ok": True, "ignored": "unknown_invoice"}
    if row["status"] == "paid":
        return {"ok": True, "ignored": "already_paid"}

    provider = payments.get_provider()
    if not isinstance(provider, payments.CryptoPayProvider):
        raise HTTPException(status_code=503, detail="Crypto Pay не настроен")
    try:
        verified = await provider.get_invoice(invoice_id)
    except payments.PaymentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not verified or verified.get("status") != "paid":
        raise HTTPException(status_code=400, detail="Счёт не оплачен")

    gram = Decimal(row["gram"])
    async with db.tx() as conn:
        cur = await conn.execute("SELECT status FROM market_invoices WHERE id=?", (invoice_id,))
        current = await cur.fetchone()
        if not current or current["status"] == "paid":
            return {"ok": True, "ignored": "already_paid"}
        await conn.execute(
            "UPDATE market_invoices SET status='paid', paid_at=? WHERE id=?", (_stamp(), invoice_id)
        )
        await _wallet_add(
            conn,
            int(row["user_id"]),
            gram,
            "topup",
            "Пополнение GRAM",
            invoice_id,
        )

    await notifier.send(
        int(row["user_id"]),
        f"<b>Баланс пополнен</b>\n\n+{gram.normalize():f} GRAM\n<i>ATLANTA Market</i>",
    )
    return {"ok": True, "invoice": invoice_id, "credited": _float(gram)}


@router.get("/orders")
async def market_orders(request: Request) -> dict:
    user = await current_user(request)
    rows = await db.fetchall(
        "SELECT * FROM market_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 40",
        (int(user["id"]),),
    )
    return {"items": [_public_order(row) for row in rows]}


@router.post("/orders")
async def market_create_order(request: Request, payload: OrderIn) -> dict:
    user = await current_user(request)
    uid = int(user["id"])
    quote = await _quote(payload)
    amount: Decimal = quote["amount"]
    order_id = f"mkt_{new_id()}"

    async with db.tx() as conn:
        available = await _wallet_add(
            conn,
            uid,
            -amount,
            "purchase",
            f"Покупка: {quote['title']}" if payload.mode == "buy" else f"Аренда: {quote['title']}",
            order_id,
        )
        await conn.execute(
            """INSERT INTO market_orders
               (id, user_id, type, mode, title, subtitle, amount, currency, months, gift_id, number,
                anonymous, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'GRAM', ?, ?, ?, ?, 'paid', ?, ?)""",
            (
                order_id,
                uid,
                payload.type,
                payload.mode,
                quote["title"],
                quote["subtitle"],
                format(amount, "f"),
                quote["months"],
                quote["gift_id"],
                quote["number"],
                1 if quote["anonymous"] else 0,
                _stamp(),
                _stamp(),
            ),
        )

    row = await db.fetchone("SELECT * FROM market_orders WHERE id=?", (order_id,))
    await notifier.send(
        uid,
        f"<b>Заказ оплачен</b>\n\n{quote['title']} · {amount:g} GRAM\n"
        f"<i>{'Аренда' if payload.mode == 'rent' else 'Покупка'} · ожидает выдачи</i>",
    )
    return {"order": _public_order(row), "balance": _float(available)}


@router.post("/withdraw")
async def market_withdraw(request: Request, payload: WithdrawIn) -> dict:
    user = await current_user(request)
    uid = int(user["id"])
    amount = _money(payload.amount)
    if amount < _money(settings.market_min_withdraw):
        raise EscrowError(f"Минимальный вывод — {settings.market_min_withdraw:g} GRAM")
    address = payload.address.strip()
    if len(address) < 4:
        raise EscrowError("Укажи адрес кошелька или @username")

    available, _ = await _wallet_state(uid)
    if available < amount:
        raise EscrowError("Недостаточно GRAM на балансе", 409, "insufficient_funds")

    payout_id = f"wdr_{new_id()}"
    async with db.tx() as conn:
        await _wallet_add(
            conn,
            uid,
            -amount,
            "withdraw",
            "Заявка на вывод GRAM",
            payout_id,
            pending_delta=amount,
        )
        await conn.execute(
            """INSERT INTO market_payouts (id, user_id, amount, address, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (payout_id, uid, format(amount, "f"), address, _stamp()),
        )

    await notifier.send(
        uid,
        f"<b>Заявка на вывод создана</b>\n\n−{amount:g} GRAM\n"
        f"<i>Выплата вручную, до 24 часов</i>",
    )
    return {"id": payout_id, "amount": _float(amount), "status": "pending", "balance": _float(available - amount)}


# --------------------------------------------------------------------------- admin


async def admin_pending_orders(admin: dict) -> list[dict]:
    _require_admin(admin)
    rows = await db.fetchall(
        "SELECT * FROM market_orders WHERE status='paid' ORDER BY created_at ASC LIMIT 100"
    )
    return [_public_order(row) for row in rows]


async def admin_fulfill_order(admin: dict, order_id: str) -> dict:
    _require_admin(admin)
    row = await db.fetchone("SELECT * FROM market_orders WHERE id=?", (order_id,))
    if not row:
        raise EscrowError("Заказ не найден", 404, "order_not_found")
    if row["status"] != "paid":
        raise EscrowError("Заказ уже обработан")
    await db.execute(
        "UPDATE market_orders SET status='fulfilled', updated_at=? WHERE id=?", (_stamp(), order_id)
    )
    await notifier.send(
        int(row["user_id"]),
        f"<b>Заказ выдан</b>\n\n{row['title']} · {row['amount']} GRAM\n<i>ATLANTA Market</i>",
    )
    return _public_order(await db.fetchone("SELECT * FROM market_orders WHERE id=?", (order_id,)))


async def admin_refund_order(admin: dict, order_id: str) -> dict:
    """Вернуть GRAM за оплаченный, но не выданный заказ."""
    _require_admin(admin)
    row = await db.fetchone("SELECT * FROM market_orders WHERE id=?", (order_id,))
    if not row:
        raise EscrowError("Заказ не найден", 404, "order_not_found")
    if row["status"] != "paid":
        raise EscrowError("Заказ уже обработан")
    amount = Decimal(row["amount"])
    async with db.tx() as conn:
        cur = await conn.execute("SELECT status FROM market_orders WHERE id=?", (order_id,))
        current = await cur.fetchone()
        if not current or current["status"] != "paid":
            raise EscrowError("Заказ уже обработан")
        await conn.execute(
            "UPDATE market_orders SET status='refunded', updated_at=? WHERE id=?", (_stamp(), order_id)
        )
        await _wallet_add(
            conn,
            int(row["user_id"]),
            amount,
            "refund",
            f"Возврат: {row['title']}",
            order_id,
        )
    await notifier.send(
        int(row["user_id"]),
        f"<b>Возврат по заказу</b>\n\n{row['title']} · +{amount:g} GRAM\n<i>ATLANTA Market</i>",
    )
    return _public_order(await db.fetchone("SELECT * FROM market_orders WHERE id=?", (order_id,)))


async def admin_pending_payouts(admin: dict) -> list[dict]:
    _require_admin(admin)
    rows = await db.fetchall(
        "SELECT * FROM market_payouts WHERE status='pending' ORDER BY created_at ASC LIMIT 100"
    )
    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "amount": row["amount"],
            "address": row["address"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


async def admin_set_payout(admin: dict, payout_id: str, status: str) -> dict:
    _require_admin(admin)
    if status not in PAYOUT_STATUSES:
        raise EscrowError("Некорректный статус выплаты")
    row = await db.fetchone("SELECT * FROM market_payouts WHERE id=?", (payout_id,))
    if not row:
        raise EscrowError("Заявка не найдена", 404, "payout_not_found")
    if row["status"] != "pending":
        raise EscrowError("Заявка уже обработана")

    amount = Decimal(row["amount"])
    async with db.tx() as conn:
        if status == "paid":
            await _wallet_add(
                conn, int(row["user_id"]), Decimal("0"), "payout", "Вывод выплачен", payout_id,
                pending_delta=-amount,
            )
        else:
            await _wallet_add(
                conn, int(row["user_id"]), amount, "refund", "Возврат вывода", payout_id,
                pending_delta=-amount,
            )
        await conn.execute(
            "UPDATE market_payouts SET status=?, paid_at=? WHERE id=?", (status, _stamp(), payout_id)
        )

    text = "Вывод выплачен" if status == "paid" else "Вывод отклонён, GRAM возвращены на баланс"
    await notifier.send(int(row["user_id"]), f"<b>{text}</b>\n\n{amount:g} GRAM")
    return {"id": payout_id, "status": status}


@router.get("/admin/orders")
async def market_admin_orders(request: Request) -> dict:
    user = await current_user(request)
    return {"items": await admin_pending_orders(user)}


@router.post("/admin/orders/{order_id}/fulfill")
async def market_admin_fulfill(request: Request, order_id: str) -> dict:
    user = await current_user(request)
    return await admin_fulfill_order(user, order_id)


@router.post("/admin/orders/{order_id}/refund")
async def market_admin_refund(request: Request, order_id: str) -> dict:
    user = await current_user(request)
    return await admin_refund_order(user, order_id)


@router.get("/admin/payouts")
async def market_admin_payouts(request: Request) -> dict:
    user = await current_user(request)
    return {"items": await admin_pending_payouts(user)}


@router.post("/admin/payouts/{payout_id}")
async def market_admin_payout(request: Request, payout_id: str, payload: PayoutActionIn) -> dict:
    user = await current_user(request)
    return await admin_set_payout(user, payout_id, payload.status)
