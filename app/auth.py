"""Проверка Telegram Mini App initData и получение пользователя."""

from __future__ import annotations

from urllib.parse import unquote

from fastapi import HTTPException, Request

from . import escrow
from .config import settings
from .i18n import tr
from .security import verify_init_data


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
            raise HTTPException(
                status_code=401,
                detail=tr("Бот не настроен: проверка Telegram недоступна", lang),
            )
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
