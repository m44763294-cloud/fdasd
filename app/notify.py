"""Уведомления в Telegram. Без токена бота просто пишет в лог."""

from __future__ import annotations

import logging
from typing import Any

from .config import settings
from .i18n import tr

log = logging.getLogger("kustos.notify")


class Notifier:
    def __init__(self) -> None:
        self.bot: Any = None
        self.username: str = settings.bot_username

    def attach(self, bot: Any, username: str = "") -> None:
        self.bot = bot
        if username:
            self.username = username

    async def _lang(self, chat_id: int | str) -> str:
        """Язык получателя из базы; ошибки не должны ломать уведомление."""
        try:
            from .db import db

            row = await db.fetchone("SELECT language FROM users WHERE id=?", (int(chat_id),))
            return "en" if (row or {}).get("language") == "en" else "ru"
        except Exception:
            return "ru"

    def deal_keyboard(self, code: str, lang: str = "ru"):
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

        url = f"{settings.webapp_url}?deal={code}"
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=tr("Открыть сделку", lang), web_app=WebAppInfo(url=url))]]
        )

    async def send(self, chat_id: int | str, text: str, keyboard: Any = None) -> bool:
        if self.bot is None:
            log.info("NOTIFY %s: %s", chat_id, text.replace("\n", " | ")[:300])
            return False
        try:
            await self.bot.send_message(
                int(chat_id),
                text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return True
        except Exception as exc:  # пользователь мог заблокировать бота
            log.warning("Не удалось отправить сообщение %s: %s", chat_id, exc)
            return False

    async def deal_event(self, deal: dict, headline: str, extra: str = "", exclude: int | None = None) -> None:
        from .models import fmt_amount

        for uid in {deal.get("seller_id"), deal.get("buyer_id")}:
            if not uid or uid == exclude:
                continue
            lang = await self._lang(uid)
            text = (
                f"<b>{tr(headline, lang)}</b>\n\n"
                f"{tr('Сделка', lang)} <code>{deal['code']}</code> · {deal['title']}\n"
                f"{tr('Сумма', lang)}: <b>{fmt_amount(deal['amount'], deal['currency'])}</b>"
            )
            if extra:
                text += f"\n\n{tr(extra, lang)}"
            await self.send(uid, text, self.deal_keyboard(deal["code"], lang))

    async def admin_alert(self, text: str, code: str | None = None) -> None:
        for admin_id in settings.admin_ids:
            lang = await self._lang(admin_id)
            keyboard = self.deal_keyboard(code, lang) if code else None
            await self.send(admin_id, f"{tr('Арбитраж', lang)}\n\n{tr(text, lang)}", keyboard)


notifier = Notifier()
