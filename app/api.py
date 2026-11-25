"""HTTP API ATLANTA."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import escrow, payments
from .config import settings
from .i18n import LANGS, tr
from .models import CATEGORIES, public_currencies
from .security import verify_init_data

log = logging.getLogger("kustos.api")
router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- auth


async def current_user(request: Request) -> dict:
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    auth = request.headers.get("Authorization", "").strip()
    lang = (request.headers.get("X-Lang") or request.query_params.get("lang") or "").strip().lower()
    lang = lang if lang in {"ru", "en"} else ""
    if not init_data and auth.lower().startswith("tma "):
        init_data = auth[4:].strip()

    tg_user: dict | None = None
    if init_data:
        if not settings.bot_token:
            raise HTTPException(status_code=401, detail=tr("Бот не настроен: проверка Telegram недоступна", lang))
        verified = verify_init_data(init_data, settings.bot_token)
        if not verified:
            raise HTTPException(status_code=401, detail=tr("Подпись Telegram недействительна", lang))
        tg_user = verified.get("user")
        if not isinstance(tg_user, dict) or not tg_user.get("id"):
            raise HTTPException(status_code=401, detail=tr("В данных Telegram нет пользователя", lang))

    if tg_user is None and settings.dev_mode:
        dev_id = request.headers.get("X-Dev-User", "777000").strip()
        try:
            uid = int(dev_id)
        except ValueError:
            uid = 777000
        tg_user = {
            "id": uid,
            "first_name": unquote(request.headers.get("X-Dev-Name", "Демо")).strip() or "Демо",
            "username": request.headers.get("X-Dev-Username", "dev"),
            "language": lang,
        }

    if tg_user is None:
        raise HTTPException(status_code=401, detail=tr("Откройте приложение внутри Telegram", lang))

    if lang:
        tg_user["language"] = lang
    return await escrow.upsert_user(tg_user)


# --------------------------------------------------------------------------- schemas


class DealCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    terms: str = ""
    category: str = "other"
    amount: str
    currency: str
    creator_role: str = "seller"


class NoteIn(BaseModel):
    note: str = ""


class ReasonIn(BaseModel):
    reason: str = ""


class ResolveIn(BaseModel):
    outcome: str
    note: str = ""


class WithdrawIn(BaseModel):
    currency: str
    amount: str
    address: str


class CreditIn(BaseModel):
    currency: str
    amount: str


# --------------------------------------------------------------------------- public


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "atlanta-otc"}


@router.get("/config")
async def config() -> dict:
    gram_receive_address = await escrow.get_setting("gram_receive_address", settings.gram_receive_address)
    gram_receive_comment = await escrow.get_setting("gram_receive_comment", settings.gram_receive_comment)
    return {
        "brand": settings.brand,
        "tagline": settings.tagline,
        "bot_username": settings.bot_username,
        "bot_link": f"https://t.me/{settings.bot_username}",
        "support": settings.support_username,
        "languages": [{"code": code, "label": code.upper()} for code in LANGS],
        "currencies": public_currencies(),
        "categories": [{"key": k, "label": v} for k, v in CATEGORIES.items()],
        "fees": {"crypto": settings.fee_crypto, "fiat": settings.fee_fiat, "min_usd": settings.min_fee_usd},
        "payment_provider": settings.payment_provider,
        "gram_receive_address": gram_receive_address,
        "gram_receive_comment": gram_receive_comment,
    }


@router.get("/market/config")
async def market_config() -> dict:
    gram_receive_address = await escrow.get_setting("gram_receive_address", settings.gram_receive_address)
    gram_receive_comment = await escrow.get_setting("gram_receive_comment", settings.gram_receive_comment)
    gift_receive_username = await escrow.get_setting("gift_receive_username", settings.gift_receive_username)
    return {
        "brand": settings.brand,
        "gram_receive_address": gram_receive_address,
        "gram_receive_comment": gram_receive_comment,
        "gift_receive_username": gift_receive_username,
        "bot_username": settings.bot_username,
    }


@router.get("/stats")
async def stats() -> dict:
    return await escrow.stats()


# --------------------------------------------------------------------------- me


@router.get("/me")
async def me(request: Request) -> dict:
    user = await current_user(request)
    data = await escrow.profile(user)
    data["is_admin"] = bool(user.get("is_admin"))
    return data


@router.get("/deals")
async def deals(request: Request, status: str | None = None) -> dict:
    user = await current_user(request)
    items = await escrow.list_deals(user, status)
    return {"items": items}


@router.post("/deals")
async def create_deal(request: Request, payload: DealCreateIn) -> dict:
    user = await current_user(request)
    return await escrow.create_deal(user, payload.model_dump())


@router.get("/deals/{code}")
async def deal_detail(request: Request, code: str) -> dict:
    user = await current_user(request)
    return await escrow.get_deal(code, user)


@router.post("/deals/{code}/join")
async def join_deal(request: Request, code: str) -> dict:
    user = await current_user(request)
    return await escrow.join_deal(user, code)


@router.post("/deals/{code}/pay")
async def pay_deal(request: Request, code: str) -> dict:
    user = await current_user(request)
    payment = await escrow.ensure_deposit(user, code)
    return {"payment": payment}


@router.post("/deals/{code}/pay-balance")
async def pay_balance(request: Request, code: str) -> dict:
    user = await current_user(request)
    return await escrow.pay_from_balance(user, code)


@router.post("/deals/{code}/deliver")
async def deliver(request: Request, code: str, payload: NoteIn | None = None) -> dict:
    user = await current_user(request)
    return await escrow.deliver(user, code, (payload.note if payload else ""))


@router.post("/deals/{code}/confirm")
async def confirm(request: Request, code: str) -> dict:
    user = await current_user(request)
    return await escrow.confirm(user, code)


@router.post("/deals/{code}/cancel")
async def cancel(request: Request, code: str, payload: ReasonIn | None = None) -> dict:
    user = await current_user(request)
    return await escrow.cancel(user, code, (payload.reason if payload else ""))


@router.post("/deals/{code}/dispute")
async def dispute(request: Request, code: str, payload: ReasonIn) -> dict:
    user = await current_user(request)
    return await escrow.dispute(user, code, payload.reason)


@router.post("/deals/{code}/resolve")
async def resolve(request: Request, code: str, payload: ResolveIn) -> dict:
    user = await current_user(request)
    return await escrow.resolve(user, code, payload.outcome, payload.note)


# --------------------------------------------------------------------------- wallet


@router.get("/wallet/withdraw-access")
async def withdraw_access(request: Request) -> dict:
    user = await current_user(request)
    return await escrow.withdraw_access(user)


@router.post("/wallet/withdraw")
async def withdraw(request: Request, payload: WithdrawIn) -> dict:
    user = await current_user(request)
    return await escrow.withdraw(user, payload.currency, payload.amount, payload.address)


# --------------------------------------------------------------------------- admin


@router.get("/admin/disputes")
async def admin_disputes(request: Request) -> dict:
    user = await current_user(request)
    return {"items": await escrow.admin_disputes(user)}


@router.get("/admin/deals")
async def admin_deals(request: Request) -> dict:
    user = await current_user(request)
    return {"items": await escrow.admin_recent(user)}


@router.post("/admin/credit")
async def admin_credit(request: Request, payload: CreditIn) -> dict:
    user = await current_user(request)
    return await escrow.admin_credit(user, payload.amount, payload.currency)


# --------------------------------------------------------------------------- webhook


@router.post("/payments/webhook")
async def payment_webhook(request: Request) -> dict:
    raw = await request.body()
    try:
        payload = payments.webhook_payload_from_raw(raw)
        provider = payments.get_provider()
        event = await provider.parse_webhook(dict(request.headers), raw, payload)
        if event is None:
            return {"ok": True, "ignored": True}
        deal = await escrow.mark_funded(event.deal_code, event.ref, event.amount, event.provider)
        return {"ok": True, "deal": deal["code"], "status": deal["status"]}
    except payments.PaymentError as exc:
        log.warning("Вебхук отклонён: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
