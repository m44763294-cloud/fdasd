"""Ядро сервиса: сделки, статусы, деньги, аудит и уведомления."""

from __future__ import annotations

import html
import json
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .config import settings
from .db import db
from .i18n import lang_of, tr
from .models import (
    CATEGORIES,
    CURRENCIES,
    FINAL_STATUSES,
    STATUS_LABELS,
    STATUS_TONES,
    currency_or_raise,
    fmt_amount,
    fmt_usd,
    parse_amount,
    quantize,
    split_fee,
    usd_value,
)
from .notify import notifier
from .payments import PaymentError, get_provider
from .security import new_deal_code, new_id, new_token, normalize_code

log = logging.getLogger("kustos.escrow")


class EscrowError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def user_name(user: dict | None) -> str:
    if not user:
        return "Пользователь"
    name = (user.get("first_name") or "").strip()
    if name:
        return name
    if user.get("username"):
        return "@" + user["username"]
    return f"ID {user.get('id')}"


# --------------------------------------------------------------------------- users


async def upsert_user(tg_user: dict) -> dict:
    uid = int(tg_user["id"])
    now = iso()
    is_admin = 1 if uid in settings.admin_ids else 0
    username = (tg_user.get("username") or "").strip().lstrip("@") or None
    first_name = (tg_user.get("first_name") or "").strip() or "Пользователь"
    last_name = (tg_user.get("last_name") or "").strip() or None
    photo_url = tg_user.get("photo_url")
    lang = str(tg_user.get("language") or "").strip().lower()
    lang = lang if lang in {"ru", "en"} else ""
    # Один атомарный upsert: параллельные первые запросы не ловят UNIQUE constraint.
    await db.execute(
        """INSERT INTO users (id, username, first_name, last_name, photo_url, language, is_admin, created_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             username=excluded.username,
             first_name=excluded.first_name,
             last_name=excluded.last_name,
             photo_url=COALESCE(excluded.photo_url, users.photo_url),
             language=CASE WHEN ? <> '' THEN ? ELSE users.language END,
             is_admin=MAX(users.is_admin, excluded.is_admin),
             last_seen_at=excluded.last_seen_at""",
        (uid, username, first_name, last_name, photo_url, lang or "ru", is_admin, now, now, lang, lang),
    )
    return await get_user(uid)


async def set_language(uid: int, lang: str) -> None:
    value = "en" if lang_of(lang) == "en" else "ru"
    now = iso()
    await db.execute(
        """INSERT INTO users (id, first_name, language, created_at, last_seen_at)
           VALUES (?, '', ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET language=excluded.language, last_seen_at=excluded.last_seen_at""",
        (int(uid), value, now, now),
    )


def user_lang(user: dict | None) -> str:
    return lang_of((user or {}).get("language"))


async def get_user(uid: int) -> dict | None:
    return await db.fetchone("SELECT * FROM users WHERE id=?", (int(uid),))


async def get_setting(key: str, default: str = "") -> str:
    row = await db.fetchone("SELECT value FROM app_settings WHERE key=?", (key,))
    return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    await db.execute(
        """INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, value, iso()),
    )


async def find_user_by_username(username: str) -> dict | None:
    token = (username or "").strip().lstrip("@")
    if not token:
        return None
    return await db.fetchone("SELECT * FROM users WHERE username=? COLLATE NOCASE", (token,))


async def ensure_user(uid: int) -> dict:
    uid = int(uid)
    if uid <= 0:
        raise EscrowError("Неверный пользователь")
    now = iso()
    await db.execute(
        """INSERT INTO users (id, first_name, language, is_admin, is_chief, created_at, last_seen_at)
           VALUES (?, '', 'ru', 0, 0, ?, ?)
           ON CONFLICT(id) DO NOTHING""",
        (uid, now, now),
    )
    user = await get_user(uid)
    if not user:
        raise EscrowError("Не удалось найти пользователя")
    return user


async def privileged_ids() -> list[int]:
    rows = await db.fetchall("SELECT id FROM users WHERE is_admin=1 OR is_chief=1")
    return [int(row["id"]) for row in rows]


async def claim_chief(uid: int) -> dict:
    """Главного арбитра назначает владелец бота, либо первый вызвавший команду."""
    existing = await db.fetchone("SELECT id FROM users WHERE is_chief=1 LIMIT 1")
    if existing and int(uid) not in settings.admin_ids:
        raise EscrowError("Главный арбитр уже назначен", 403, "forbidden")
    await ensure_user(uid)
    await db.execute("UPDATE users SET is_chief=1, is_admin=1 WHERE id=?", (int(uid),))
    return await get_user(uid)


async def set_arbiter(chief: dict, uid: int, enabled: bool) -> dict:
    if not chief.get("is_chief"):
        raise EscrowError("Недостаточно прав", 403, "forbidden")
    await ensure_user(uid)
    await db.execute("UPDATE users SET is_admin=? WHERE id=?", (1 if enabled else 0, int(uid)))
    return await get_user(uid)


def public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user["id"],
        "name": user_name(user),
        "username": user.get("username"),
        "photo_url": user.get("photo_url"),
        "is_admin": bool(user.get("is_admin")),
        "is_chief": bool(user.get("is_chief")),
    }


async def _users_map(ids: set[int]) -> dict[int, dict]:
    ids = {int(i) for i in ids if i}
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    rows = await db.fetchall(f"SELECT * FROM users WHERE id IN ({marks})", list(ids))
    return {row["id"]: row for row in rows}


# --------------------------------------------------------------------------- deals


def _waiting_slot(deal: dict) -> str | None:
    """Кого ждёт сделка на этапе приглашения: покупателя или продавца."""
    if deal["status"] != "waiting_buyer":
        return None
    if deal.get("creator_role") == "buyer" and deal.get("seller_id") == deal.get("buyer_id"):
        return "seller"
    if not deal.get("buyer_id"):
        return "buyer"
    return None


def _status_hint(deal: dict, role: str) -> str:
    status = deal["status"]
    if status == "waiting_buyer":
        if _waiting_slot(deal) == "seller":
            if role == "buyer":
                return "Отправьте ссылку продавцу — он присоединится к сделке и передаст товар."
            return "Сделка ждёт продавца. Вы можете занять это место."
        if role == "seller":
            return "Отправьте ссылку покупателю — он присоединится к сделке."
        return "Сделка ждёт покупателя. Вы можете занять это место."
    if status == "waiting_payment":
        if role == "buyer":
            return "Оплатите счёт: деньги заблокируются и уйдут продавцу только после вашего подтверждения."
        if role == "seller":
            return "Ждём оплату покупателя. После зачисления средства будут под защитой."
        return "Покупатель уже присоединился и оплачивает сделку."
    if status == "funded":
        if role == "seller":
            return "Деньги под защитой. Передайте товар и отметьте это в сделке."
        if role == "buyer":
            return "Деньги заблокированы. Проверьте товар и подтвердите получение."
        return "Средства заблокированы до подтверждения покупателем."
    if status == "delivered":
        if role == "buyer":
            return "Продавец отметил передачу. Подтвердите получение, чтобы выплатить ему деньги."
        return "Ждём подтверждения покупателя."
    if status == "completed":
        return "Сделка завершена, средства выплачены продавцу."
    if status == "disputed":
        return "Спор передан арбитру. Решение будет принято по условиям сделки."
    if status == "cancelled":
        return "Сделка отменена. Средства не списывались."
    if status == "refunded":
        return "Арбитр вернул средства покупателю."
    return ""


def _actions(deal: dict, role: str, viewer: dict | None, lang: str = "ru") -> list[dict]:
    status = deal["status"]
    is_admin = bool(viewer and viewer.get("is_admin"))
    is_participant = role in {"seller", "buyer"}
    actions: list[dict] = []

    def add(key: str, label: str, style: str) -> None:
        actions.append({"key": key, "label": tr(label, lang), "style": style})

    waiting_slot = _waiting_slot(deal)
    if viewer and role == "guest" and waiting_slot:
        label = "Присоединиться как продавец" if waiting_slot == "seller" else "Присоединиться к сделке"
        add("join", label, "primary")

    if role == "buyer" and status == "waiting_payment":
        add("pay_balance", "Оплатить с баланса", "primary")
        add("pay", "Оплатить сделку", "ghost")
    if role == "seller" and status == "funded":
        add("deliver", "Товар передан", "primary")
    if role == "buyer" and status in {"funded", "delivered"}:
        add("confirm", "Подтвердить получение", "success")
    if is_participant and status in {"funded", "delivered"}:
        add("dispute", "Открыть спор", "danger-ghost")
    if is_participant and status in {"waiting_buyer", "waiting_payment"}:
        add("cancel", "Отменить сделку", "ghost")
    if is_admin and status == "disputed":
        add("resolve_release", "Выплатить продавцу", "success")
        add("resolve_refund", "Вернуть покупателю", "danger")
    return actions


def _payment_public(deal: dict) -> dict | None:
    if not (deal.get("deposit_address") or deal.get("pay_url")):
        return None
    expires = parse_iso(deal.get("invoice_expires_at"))
    expired = bool(expires and expires < utcnow())
    return {
        "provider": deal.get("payment_provider") or "mock",
        "address": deal.get("deposit_address"),
        "memo": deal.get("deposit_memo"),
        "uri": deal.get("deposit_uri"),
        "pay_url": deal.get("pay_url"),
        "amount": deal["amount"],
        "currency": deal["currency"],
        "expires_at": deal.get("invoice_expires_at"),
        "expired": expired,
    }


async def public_deal(deal: dict, viewer: dict | None) -> dict:
    viewer_id = int(viewer["id"]) if viewer else None
    lang = user_lang(viewer)
    role = "guest"
    buyer_created = deal.get("creator_role") == "buyer" and deal.get("seller_id") == deal.get("buyer_id")
    if buyer_created and viewer_id and viewer_id == deal.get("buyer_id"):
        role = "buyer"
    elif viewer_id == deal["seller_id"]:
        role = "seller"
    elif viewer_id and viewer_id == deal.get("buyer_id"):
        role = "buyer"

    users = await _users_map({deal["seller_id"], deal.get("buyer_id") or 0, deal.get("arbiter_id") or 0})
    seller = users.get(deal["seller_id"])
    buyer = users.get(deal.get("buyer_id") or 0)

    events = await db.fetchall("SELECT * FROM events WHERE deal_id=? ORDER BY id ASC", (deal["id"],))
    event_actors = await _users_map({e["actor_id"] for e in events if e.get("actor_id")})
    event_list = [
        {
            "kind": e["kind"],
            "text": tr(e["text"], lang),
            "actor": user_name(event_actors.get(e["actor_id"])) if e.get("actor_id") else None,
            "created_at": e["created_at"],
        }
        for e in events
    ]

    payment = None
    if role in {"buyer", "seller"} or (viewer and viewer.get("is_admin")):
        payment = _payment_public(deal)

    invite_link = f"https://t.me/{settings.bot_username}?start=deal_{deal['code']}"
    return {
        "code": deal["code"],
        "title": deal["title"],
        "description": deal["description"],
        "terms": deal["terms"],
        "category": deal["category"],
        "category_label": tr(CATEGORIES.get(deal["category"], "Другое"), lang),
        "amount": deal["amount"],
        "currency": deal["currency"],
        "amount_usd": usd_value(deal["amount"], deal["currency"]),
        "fee_percent": deal["fee_percent"],
        "fee_amount": deal["fee_amount"],
        "fee_usd": usd_value(deal["fee_amount"], deal["currency"]),
        "net_amount": deal["net_amount"],
        "status": deal["status"],
        "status_label": tr(STATUS_LABELS.get(deal["status"], deal["status"]), lang),
        "status_tone": STATUS_TONES.get(deal["status"], "neutral"),
        "seller": public_user(seller),
        "buyer": public_user(buyer),
        "role": role,
        "is_admin": bool(viewer and viewer.get("is_admin")),
        "invite_link": invite_link if role != "guest" else None,
        "invite_role": "seller" if _waiting_slot(deal) == "seller" else "buyer",
        "payment": payment,
        "deadline_at": deal.get("deadline_at"),
        "created_at": deal["created_at"],
        "updated_at": deal["updated_at"],
        "paid_at": deal.get("paid_at"),
        "delivered_at": deal.get("delivered_at"),
        "completed_at": deal.get("completed_at"),
        "dispute_reason": deal.get("dispute_reason"),
        "resolution": tr(deal.get("resolution") or "", lang) or None,
        "events": event_list,
        "actions": _actions(deal, role, viewer, lang),
        "next_step": tr(_status_hint(deal, role), lang),
        "webapp_url": f"{settings.webapp_url}?deal={deal['code']}",
    }


async def get_deal_raw(code: str) -> dict | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    return await db.fetchone("SELECT * FROM deals WHERE code=?", (normalized,))


async def get_deal(code: str, viewer: dict | None) -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    return await public_deal(deal, viewer)


async def list_deals(user: dict, status: str | None = None, limit: int = 50) -> list[dict]:
    uid = int(user["id"])
    sql = "SELECT * FROM deals WHERE (seller_id=? OR buyer_id=?)"
    params: list[Any] = [uid, uid]
    if status and status != "all":
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(min(max(limit, 1), 100))
    rows = await db.fetchall(sql, params)
    return [await public_deal(row, user) for row in rows]


async def create_deal(user: dict, data: dict) -> dict:
    creator = await upsert_user(user)
    creator_role = "buyer" if data.get("creator_role") == "buyer" else "seller"

    title = (data.get("title") or "").strip()
    if not (5 <= len(title) <= 120):
        raise EscrowError("Название сделки — от 5 до 120 символов")
    description = (data.get("description") or "").strip()
    terms = (data.get("terms") or "").strip()
    if len(description) > 1500:
        raise EscrowError("Описание — не длиннее 1500 символов")
    if len(terms) > 3000:
        raise EscrowError("Условия — не длиннее 3000 символов")

    currency = (data.get("currency") or "").upper()
    if currency not in CURRENCIES:
        raise EscrowError("Неизвестная валюта")
    info = currency_or_raise(currency)

    try:
        amount = parse_amount(data.get("amount"))
    except ValueError as exc:
        raise EscrowError(str(exc)) from exc
    if amount <= 0:
        raise EscrowError("Сумма должна быть больше нуля")
    amount = quantize(amount, currency)
    if amount < Decimal(info.min_amount):
        raise EscrowError(f"Минимальная сумма — {info.min_amount} {currency}")
    if usd_value(amount, currency) < 1:
        raise EscrowError("Минимальная сумма сделки — эквивалент 1 USD")

    try:
        fee, net, percent = split_fee(
            amount, currency, settings.fee_crypto, settings.fee_fiat, settings.min_fee_usd
        )
    except ValueError as exc:
        raise EscrowError(str(exc)) from exc

    category = data.get("category") if data.get("category") in CATEGORIES else "other"

    code = ""
    for _ in range(12):
        candidate = new_deal_code()
        if not await db.scalar("SELECT 1 FROM deals WHERE code=?", (candidate,)):
            code = candidate
            break
    if not code:
        raise EscrowError("Не удалось создать код сделки, попробуйте ещё раз", 500)

    now = utcnow()
    deal_id = new_id()
    async with db.tx() as conn:
        await conn.execute(
            """INSERT INTO deals (
                id, code, title, description, terms, category, amount, currency,
                fee_percent, fee_amount, net_amount, status, seller_id, buyer_id,
                creator_role, invite_token, deadline_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting_buyer', ?, ?, ?, ?, ?, ?, ?)""",
            (
                deal_id, code, title, description, terms, category, str(amount), currency,
                percent, str(fee), str(net), creator["id"],
                creator["id"] if creator_role == "buyer" else None,
                creator_role, new_token(12),
                None, iso(now), iso(now),
            ),
        )
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'created', ?, ?)",
            (deal_id, creator["id"], "Сделка создана", iso(now)),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal_id,))
    return await public_deal(deal, creator)


async def join_deal(user: dict, code: str) -> dict:
    joiner = await upsert_user(user)
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")

    waiting_slot = _waiting_slot(deal)
    if not waiting_slot:
        if joiner["id"] in {deal["seller_id"], deal.get("buyer_id")}:
            return await public_deal(deal, joiner)
        raise EscrowError("Место в сделке уже занято", 409, "already_joined")
    if joiner["id"] in {deal["seller_id"], deal.get("buyer_id")}:
        raise EscrowError("Нельзя присоединиться к собственной сделке", 409, "own_deal")

    seller_joins = waiting_slot == "seller"
    name = "Продавец" if seller_joins else "Покупатель"
    if seller_joins:
        sql = """UPDATE deals SET seller_id=?, status='waiting_payment', updated_at=?, version=version+1
                 WHERE id=? AND status='waiting_buyer' AND seller_id=buyer_id"""
    else:
        sql = """UPDATE deals SET buyer_id=?, status='waiting_payment', updated_at=?, version=version+1
                 WHERE id=? AND status='waiting_buyer' AND buyer_id IS NULL"""

    async with db.tx() as conn:
        cur = await conn.execute(sql, (joiner["id"], iso(), deal["id"]))
        if cur.rowcount == 0:
            raise EscrowError("Сделка уже занята", 409, "already_joined")
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'joined', ?, ?)",
            (deal["id"], joiner["id"], f"{name} присоединился к сделке", iso()),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    detail = (
        "Покупатель может оплатить счёт."
        if seller_joins
        else "Теперь он оплачивает счёт."
    )
    await notifier.deal_event(
        deal,
        f"{name} присоединился",
        f"{esc(user_name(joiner))} вошёл в сделку. {detail}",
        exclude=joiner["id"],
    )
    return await public_deal(deal, joiner)


async def ensure_deposit(user: dict, code: str) -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if deal.get("buyer_id") != user["id"]:
        raise EscrowError("Оплатить сделку может только покупатель", 403, "forbidden")
    if deal["status"] != "waiting_payment":
        raise EscrowError("Сделка не ожидает оплаты", 409, "wrong_status")

    existing_expiry = parse_iso(deal.get("invoice_expires_at"))
    if deal.get("payment_ref") and existing_expiry and existing_expiry > utcnow():
        return _payment_public(deal) or {}

    provider = get_provider(deal["currency"])
    try:
        deposit = await provider.create_deposit(deal)
    except PaymentError as exc:
        raise EscrowError(f"Платёжный провайдер недоступен: {exc}", 502, "payment_error") from exc

    async with db.tx() as conn:
        await conn.execute(
            """UPDATE deals SET payment_provider=?, payment_ref=?, deposit_address=?, deposit_memo=?,
               deposit_uri=?, pay_url=?, invoice_expires_at=?, updated_at=?, version=version+1
               WHERE id=?""",
            (
                deposit.provider, deposit.ref, deposit.address, deposit.memo,
                deposit.uri, deposit.pay_url, deposit.expires_at, iso(), deal["id"],
            ),
        )
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'invoice', ?, ?)",
            (deal["id"], user["id"], "Счёт на оплату сформирован", iso()),
        )
    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    return _payment_public(deal) or {}


async def mark_funded(code: str, ref: str, amount: Decimal | None, provider: str) -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if deal["status"] in {"funded", "delivered", "completed", "disputed"}:
        return deal
    if deal["status"] != "waiting_payment":
        raise EscrowError("Сделка не ожидает оплаты", 409, "wrong_status")

    if amount is not None and Decimal(amount) < Decimal(deal["amount"]):
        raise EscrowError(
            f"Оплачено меньше суммы сделки: {fmt_amount(amount, deal['currency'])}",
            409,
            "underpaid",
        )

    async with db.tx() as conn:
        cur = await conn.execute(
            """UPDATE deals SET status='funded', paid_at=?, payment_ref=COALESCE(?, payment_ref),
               payment_provider=COALESCE(?, payment_provider), updated_at=?, version=version+1
               WHERE id=? AND status='waiting_payment'""",
            (iso(), ref or None, provider or None, iso(), deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        await conn.execute(
            "INSERT INTO events (deal_id, kind, text, created_at) VALUES (?, 'funded', ?, ?)",
            (deal["id"], "Средства заблокированы под защитой ATLANTA", iso()),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    await notifier.deal_event(
        deal,
        "Деньги под защитой",
        "Покупатель оплатил сделку. Продавец может передавать товар, покупатель — подтверждать получение.",
    )
    return deal


async def pay_from_balance(user: dict, code: str) -> dict:
    """Оплатить сделку деньгами, уже лежащими на балансе ATLANTA."""
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if deal.get("buyer_id") != int(user["id"]):
        raise EscrowError("Оплатить сделку может только покупатель", 403, "forbidden")
    if deal["status"] != "waiting_payment":
        raise EscrowError("Сделка не ожидает оплаты", 409, "wrong_status")

    amount = Decimal(deal["amount"])
    currency = deal["currency"]
    wallet = await db.fetchone(
        "SELECT available FROM wallets WHERE user_id=? AND currency=?", (int(user["id"]), currency)
    )
    if not wallet or Decimal(wallet["available"]) < amount:
        raise EscrowError("Недостаточно средств на балансе", 409, "insufficient_funds")

    ref = f"balance-{new_id()[:12]}"
    async with db.tx() as conn:
        await _wallet_add(conn, int(user["id"]), currency, -amount)
        cur = await conn.execute(
            """UPDATE deals SET status='funded', paid_at=?, payment_provider='balance', payment_ref=?,
               updated_at=?, version=version+1
               WHERE id=? AND status='waiting_payment'""",
            (iso(), ref, iso(), deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        await _ledger(
            conn, int(user["id"]), deal["id"], currency, str(amount), "deal_payment", "Оплата сделки с баланса"
        )
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'funded', ?, ?)",
            (deal["id"], int(user["id"]), "Оплата списана с баланса и зачислена под защиту ATLANTA", iso()),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    await notifier.deal_event(
        deal,
        "Деньги под защитой",
        "Покупатель оплатил сделку с баланса. Продавец может передавать товар, покупатель — подтверждать получение.",
    )
    return await get_deal(code, user)


async def deliver(user: dict, code: str, note: str = "") -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if deal["seller_id"] != user["id"]:
        raise EscrowError("Отметить передачу может только продавец", 403, "forbidden")
    if deal["status"] != "funded":
        raise EscrowError("Передать товар можно только после оплаты", 409, "wrong_status")

    note = (note or "").strip()[:500]
    text = "Продавец отметил передачу товара"
    if note:
        text += f": {note}"
    async with db.tx() as conn:
        cur = await conn.execute(
            """UPDATE deals SET status='delivered', delivered_at=?, updated_at=?, version=version+1
               WHERE id=? AND status='funded'""",
            (iso(), iso(), deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'delivered', ?, ?)",
            (deal["id"], user["id"], text, iso()),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    await notifier.deal_event(
        deal,
        "Товар передан",
        "Проверьте товар. Деньги уйдут продавцу только после вашего подтверждения.",
        exclude=user["id"],
    )
    return await get_deal(code, user)


async def confirm(user: dict, code: str) -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if deal.get("buyer_id") != user["id"]:
        raise EscrowError("Подтвердить сделку может только покупатель", 403, "forbidden")
    if deal["status"] not in {"funded", "delivered"}:
        raise EscrowError("Сейчас подтверждение недоступно", 409, "wrong_status")

    now = iso()
    async with db.tx() as conn:
        cur = await conn.execute(
            """UPDATE deals SET status='completed', completed_at=?, updated_at=?, version=version+1
               WHERE id=? AND status IN ('funded','delivered')""",
            (now, now, deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        await _wallet_add(conn, deal["seller_id"], deal["currency"], Decimal(deal["net_amount"]))
        await _ledger(conn, deal["seller_id"], deal["id"], deal["currency"], deal["net_amount"], "release", "Выплата по сделке")
        await _ledger(conn, None, deal["id"], deal["currency"], deal["fee_amount"], "fee", "Комиссия ATLANTA")
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'completed', ?, ?)",
            (deal["id"], user["id"], "Покупатель подтвердил сделку · средства выплачены продавцу", now),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    await notifier.deal_event(
        deal,
        "Сделка завершена",
        f"Покупатель подтвердил получение. Продавцу выплачено {fmt_amount(deal['net_amount'], deal['currency'])}.",
    )
    return await get_deal(code, user)


async def cancel(user: dict, code: str, reason: str = "") -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if user["id"] not in {deal["seller_id"], deal.get("buyer_id")}:
        raise EscrowError("Отменить сделку может только участник", 403, "forbidden")
    if deal["status"] not in {"waiting_buyer", "waiting_payment"}:
        raise EscrowError("Оплаченную сделку нельзя просто отменить — откройте спор", 409, "wrong_status")

    reason = (reason or "").strip()[:500]
    text = "Сделка отменена"
    if reason:
        text += f": {reason}"
    async with db.tx() as conn:
        cur = await conn.execute(
            """UPDATE deals SET status='cancelled', updated_at=?, version=version+1
               WHERE id=? AND status IN ('waiting_buyer','waiting_payment')""",
            (iso(), deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'cancelled', ?, ?)",
            (deal["id"], user["id"], text, iso()),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    await notifier.deal_event(deal, "Сделка отменена", esc(reason or "Участник отменил сделку."), exclude=user["id"])
    return await get_deal(code, user)


async def dispute(user: dict, code: str, reason: str) -> dict:
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if user["id"] not in {deal["seller_id"], deal.get("buyer_id")}:
        raise EscrowError("Открыть спор может только участник", 403, "forbidden")
    if deal["status"] not in {"funded", "delivered"}:
        raise EscrowError("Спор можно открыть только по оплаченной сделке", 409, "wrong_status")

    reason = (reason or "").strip()
    if len(reason) < 10:
        raise EscrowError("Опишите проблему — минимум 10 символов")

    async with db.tx() as conn:
        cur = await conn.execute(
            """UPDATE deals SET status='disputed', dispute_reason=?, updated_at=?, version=version+1
               WHERE id=? AND status IN ('funded','delivered')""",
            (reason[:1000], iso(), deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, 'disputed', ?, ?)",
            (deal["id"], user["id"], f"Открыт спор: {reason[:300]}", iso()),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    await notifier.deal_event(
        deal,
        "Открыт спор",
        f"Причина: {esc(reason)}\n\nАрбитр изучит условия сделки и примет решение. Не выводите общение из чата сделки.",
    )
    await notifier.admin_alert(
        f"Спор по сделке <code>{deal['code']}</code>\n"
        f"Сумма: {fmt_amount(deal['amount'], deal['currency'])} ({fmt_usd(usd_value(deal['amount'], deal['currency']))})\n"
        f"Причина: {esc(reason)}",
        deal["code"],
    )
    return await get_deal(code, user)


async def resolve(admin: dict, code: str, outcome: str, note: str = "") -> dict:
    if not admin.get("is_admin"):
        raise EscrowError("Недостаточно прав", 403, "forbidden")
    if outcome not in {"release", "refund"}:
        raise EscrowError("Некорректное решение арбитра")
    deal = await get_deal_raw(code)
    if not deal:
        raise EscrowError("Сделка не найдена", 404, "not_found")
    if deal["status"] != "disputed":
        raise EscrowError("Сделка не находится в споре", 409, "wrong_status")

    note = (note or "").strip()[:500]
    now = iso()
    new_status = "completed" if outcome == "release" else "refunded"
    resolution = ("Выплата продавцу" if outcome == "release" else "Возврат покупателю") + (f": {note}" if note else "")

    async with db.tx() as conn:
        cur = await conn.execute(
            """UPDATE deals SET status=?, arbiter_id=?, resolution=?, completed_at=?, updated_at=?, version=version+1
               WHERE id=? AND status='disputed'""",
            (new_status, admin["id"], resolution, now, now, deal["id"]),
        )
        if cur.rowcount == 0:
            raise EscrowError("Статус сделки уже изменился", 409, "conflict")
        if outcome == "release":
            await _wallet_add(conn, deal["seller_id"], deal["currency"], Decimal(deal["net_amount"]))
            await _ledger(conn, deal["seller_id"], deal["id"], deal["currency"], deal["net_amount"], "release", "Решение арбитра")
            await _ledger(conn, None, deal["id"], deal["currency"], deal["fee_amount"], "fee", "Комиссия ATLANTA")
        else:
            if (deal.get("payment_provider") or "") == "balance" and deal.get("buyer_id"):
                await _wallet_add(
                    conn, int(deal["buyer_id"]), deal["currency"], Decimal(deal["amount"])
                )
            await _ledger(conn, deal.get("buyer_id"), deal["id"], deal["currency"], deal["amount"], "refund", "Решение арбитра")
        await conn.execute(
            "INSERT INTO events (deal_id, actor_id, kind, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (deal["id"], admin["id"], f"resolved_{outcome}", resolution, now),
        )

    deal = await db.fetchone("SELECT * FROM deals WHERE id=?", (deal["id"],))
    if outcome == "release":
        headline = "Арбитр завершил сделку"
        extra = f"Средства выплачены продавцу: {fmt_amount(deal['net_amount'], deal['currency'])}."
    else:
        headline = "Арбитр вернул средства"
        extra = f"Покупателю возвращено {fmt_amount(deal['amount'], deal['currency'])}."
    if note:
        extra += f"\nКомментарий: {esc(note)}"
    await notifier.deal_event(deal, headline, extra)
    return await get_deal(code, admin)


# --------------------------------------------------------------------------- money


async def _wallet_add(conn, user_id: int, currency: str, delta: Decimal) -> Decimal:
    cur = await conn.execute("SELECT available FROM wallets WHERE user_id=? AND currency=?", (user_id, currency))
    row = await cur.fetchone()
    current = Decimal(row["available"]) if row else Decimal(0)
    new_value = quantize(current + delta, currency)
    if new_value < 0:
        raise EscrowError("Недостаточно средств на балансе", 409, "insufficient_funds")
    await conn.execute(
        """INSERT INTO wallets (user_id, currency, available) VALUES (?, ?, ?)
           ON CONFLICT(user_id, currency) DO UPDATE SET available=excluded.available""",
        (user_id, currency, format(new_value, "f")),
    )
    return new_value


async def admin_credit(admin: dict, amount_raw: str, currency_raw: str, to_uid: int | None = None) -> dict:
    """Арбитр пополняет баланс себе или другому пользователю."""
    if not admin.get("is_admin"):
        raise EscrowError("Недостаточно прав", 403, "forbidden")
    currency = (currency_raw or "").upper()
    if currency not in CURRENCIES:
        raise EscrowError("Неизвестная валюта")
    try:
        amount = quantize(parse_amount(amount_raw), currency)
    except ValueError as exc:
        raise EscrowError(str(exc)) from exc
    if amount <= 0:
        raise EscrowError("Сумма должна быть больше нуля")

    uid = int(to_uid) if to_uid else int(admin["id"])
    target = await ensure_user(uid)
    uid = int(target["id"])
    note = "Начисление арбитром" if to_uid else "Пополнение арбитром"
    async with db.tx() as conn:
        available = await _wallet_add(conn, uid, currency, amount)
        await _ledger(conn, uid, None, currency, str(amount), "admin_credit", note)
    return {
        "user_id": uid,
        "currency": currency,
        "amount": format(amount, "f"),
        "available": format(available, "f"),
    }


async def give_balance(arbiter: dict, to_uid: int, amount_raw: str, currency_raw: str) -> dict:
    """Арбитр начисляет баланс другому пользователю."""
    return await admin_credit(arbiter, amount_raw, currency_raw, to_uid=to_uid)


async def _ledger(conn, user_id: int | None, deal_id: str | None, currency: str, amount: str, kind: str, note: str = "") -> None:
    await conn.execute(
        "INSERT INTO ledger (user_id, deal_id, currency, amount, kind, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, deal_id, currency, str(amount), kind, note, iso()),
    )


async def balances(user_id: int) -> dict:
    rows = await db.fetchall("SELECT * FROM wallets WHERE user_id=? ORDER BY currency", (user_id,))
    items = []
    total = 0.0
    for row in rows:
        available = Decimal(row["available"])
        if available <= 0:
            continue
        usd = usd_value(available, row["currency"])
        total += usd
        items.append(
            {
                "currency": row["currency"],
                "available": format(available, "f"),
                "pending": row["pending"],
                "usd": usd,
            }
        )
    return {"items": items, "total_usd": round(total, 2)}


WITHDRAW_REQUIRED_DEALS = 3


async def completed_deals_count(uid: int) -> int:
    return int(
        await db.scalar(
            "SELECT COUNT(*) FROM deals WHERE status='completed' AND (seller_id=? OR buyer_id=?)",
            (int(uid), int(uid)),
        )
        or 0
    )


async def withdraw_access(user: dict) -> dict:
    completed = await completed_deals_count(user["id"])
    return {"allowed": completed >= WITHDRAW_REQUIRED_DEALS, "completed": completed, "required": WITHDRAW_REQUIRED_DEALS}


async def withdraw(user: dict, currency: str, amount_raw: str, address: str) -> dict:
    if await completed_deals_count(user["id"]) < WITHDRAW_REQUIRED_DEALS:
        raise EscrowError("Вывод доступен после 3 успешных сделок", 403, "withdraw_locked")
    currency = (currency or "").upper()
    if currency not in CURRENCIES:
        raise EscrowError("Неизвестная валюта")
    address = (address or "").strip()
    if len(address) < 8:
        raise EscrowError("Укажите корректные реквизиты получателя")
    try:
        amount = quantize(parse_amount(amount_raw), currency)
    except ValueError as exc:
        raise EscrowError(str(exc)) from exc
    if amount <= 0:
        raise EscrowError("Сумма должна быть больше нуля")

    wallet = await db.fetchone("SELECT * FROM wallets WHERE user_id=? AND currency=?", (user["id"], currency))
    if not wallet or Decimal(wallet["available"]) < amount:
        raise EscrowError("Недостаточно средств", 409, "insufficient_funds")

    provider = get_provider(currency)
    try:
        result = await provider.payout(user, format(amount, "f"), currency, address)
    except PaymentError as exc:
        raise EscrowError(f"Вывод не выполнен: {exc}", 502, "payout_error") from exc

    payout_id = new_id()
    async with db.tx() as conn:
        await _wallet_add(conn, user["id"], currency, -amount)
        await conn.execute(
            "INSERT INTO payouts (id, user_id, currency, amount, address, status, provider_ref, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (payout_id, user["id"], currency, format(amount, "f"), address, result.status, result.ref, iso()),
        )
        await _ledger(conn, user["id"], None, currency, str(amount), "withdraw", tr("Вывод средств", user_lang(user)))

    await notifier.send(
        user["id"],
        f"<b>{tr('Вывод отправлен', user_lang(user))}</b>\n\n"
        f"{fmt_amount(amount, currency)} → {esc(address)}\n"
        f"{tr('Статус', user_lang(user))}: {result.status}",
    )
    return {"id": payout_id, "status": result.status, "ref": result.ref, "amount": format(amount, "f"), "currency": currency}


# --------------------------------------------------------------------------- aggregates


async def stats() -> dict:
    users_count = int(await db.scalar("SELECT COUNT(*) FROM users") or 0)
    deals_count = int(await db.scalar("SELECT COUNT(*) FROM deals") or 0)
    completed = int(await db.scalar("SELECT COUNT(*) FROM deals WHERE status='completed'") or 0)
    disputed = int(await db.scalar("SELECT COUNT(*) FROM deals WHERE status='disputed'") or 0)
    rows = await db.fetchall(
        "SELECT amount, currency, created_at, completed_at FROM deals WHERE status IN ('funded','delivered','completed','disputed')"
    )
    volume = sum(usd_value(row["amount"], row["currency"]) for row in rows)

    durations: list[float] = []
    for row in rows:
        if row["completed_at"]:
            start = parse_iso(row["created_at"])
            end = parse_iso(row["completed_at"])
            if start and end:
                durations.append((end - start).total_seconds() / 60)
    avg_minutes = int(sum(durations) / len(durations)) if durations else 0

    return {
        "users": users_count,
        "deals": deals_count,
        "completed": completed,
        "disputed": disputed,
        "volume_usd": round(volume, 2),
        "avg_minutes": avg_minutes,
        "fee_crypto": settings.fee_crypto,
        "fee_fiat": settings.fee_fiat,
    }


async def profile(user: dict) -> dict:
    uid = int(user["id"])
    row = await db.fetchone(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                  SUM(CASE WHEN status='disputed' THEN 1 ELSE 0 END) AS disputed
           FROM deals WHERE seller_id=? OR buyer_id=?""",
        (uid, uid),
    )
    volume_rows = await db.fetchall(
        "SELECT amount, currency FROM deals WHERE status='completed' AND (seller_id=? OR buyer_id=?)",
        (uid, uid),
    )
    volume = sum(usd_value(r["amount"], r["currency"]) for r in volume_rows)
    return {
        "user": public_user(user),
        "created_at": user["created_at"],
        "stats": {
            "deals": int(row["total"] or 0) if row else 0,
            "completed": int(row["completed"] or 0) if row else 0,
            "disputed": int(row["disputed"] or 0) if row else 0,
            "volume_usd": round(volume, 2),
        },
        "balances": await balances(uid),
    }


async def admin_disputes(admin: dict) -> list[dict]:
    if not admin.get("is_admin"):
        raise EscrowError("Недостаточно прав", 403, "forbidden")
    rows = await db.fetchall("SELECT * FROM deals WHERE status='disputed' ORDER BY updated_at ASC")
    return [await public_deal(row, admin) for row in rows]


async def admin_recent(admin: dict, limit: int = 20) -> list[dict]:
    if not admin.get("is_admin"):
        raise EscrowError("Недостаточно прав", 403, "forbidden")
    rows = await db.fetchall("SELECT * FROM deals ORDER BY updated_at DESC LIMIT ?", (min(limit, 50),))
    return [await public_deal(row, admin) for row in rows]
