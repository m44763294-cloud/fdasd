"""Telegram-бот ATLANTA: меню, создание сделок, вход по ссылке, арбитраж."""

from __future__ import annotations

import asyncio
import html
import logging
import os
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    CallbackQuery,
    FSInputFile,
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import escrow, market
from .config import settings
from .i18n import tr
from .models import CURRENCIES, fmt_amount, fmt_usd, parse_amount, quantize, split_fee, usd_value
from .notify import notifier
from .security import normalize_code

log = logging.getLogger("kustos.bot")
router = Router()

PREVIEW_IMAGE = Path(__file__).resolve().parent.parent / "preview_welcome.png"


def T(lang: str, ru: str, en: str) -> str:
    """Выбрать язык для строк с подстановками."""
    return en if lang == "en" else ru


async def lang_of(uid: int) -> str:
    return escrow.user_lang(await escrow.get_user(uid))


class CreateDeal(StatesGroup):
    currency = State()
    title = State()
    amount = State()
    terms = State()
    confirm = State()


class EnterCode(StatesGroup):
    code = State()


def tg_user(user, lang: str = "ru") -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name or "Пользователь",
        "last_name": user.last_name,
        "username": user.username,
        "language": lang,
    }


def webapp_url(query: str = "") -> str:
    base = settings.webapp_url
    return f"{base}?{query}" if query else base


def welcome_menu(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=tr("Открыть OTC", lang), web_app=WebAppInfo(url=webapp_url())),
        InlineKeyboardButton(
            text=tr("Открыть маркетплейс", lang), web_app=WebAppInfo(url=settings.market_url)
        ),
    )
    return builder.as_markup()


def main_menu(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=tr("Открыть приложение", lang), web_app=WebAppInfo(url=webapp_url())),
        InlineKeyboardButton(text=tr("Мои сделки", lang), web_app=WebAppInfo(url=webapp_url("tab=deals"))),
    )
    builder.row(
        InlineKeyboardButton(text=tr("Маркет подарков", lang), web_app=WebAppInfo(url=settings.market_url)),
    )
    builder.row(
        InlineKeyboardButton(text=tr("Создать сделку", lang), callback_data="create"),
        InlineKeyboardButton(text=tr("Войти по коду", lang), callback_data="enter_code"),
    )
    builder.row(
        InlineKeyboardButton(text=tr("Как это работает", lang), callback_data="how"),
        InlineKeyboardButton(text=tr("Язык", lang), callback_data="lang"),
    )
    return builder.as_markup()


def language_menu(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
    )
    builder.row(InlineKeyboardButton(text=T(lang, "← Назад", "← Back"), callback_data="menu"))
    return builder.as_markup()


def start_language_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Русский", callback_data="startlang:ru"),
        InlineKeyboardButton(text="English", callback_data="startlang:en"),
    )
    return builder.as_markup()


async def _await_public_url(timeout: float = 3.0) -> None:
    """Даёт приложению шанс узнать домен из первого HTTP-запроса прокси."""
    if settings.public_url_ready or settings.public_url_explicit:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not settings.public_url_ready and loop.time() < deadline:
        await asyncio.sleep(0.25)


async def send_welcome(target, lang: str) -> None:
    await _await_public_url()
    fee = f"{settings.fee_fiat:g}"
    welcome = T(
        lang,
        "Добро пожаловать 👋\n\n"
        "<blockquote>Atlanta Market — Мы специализированный сервис по обеспечению "
        "безопасности внебиржевых сделок. Удобный и быстрый вывод средств.</blockquote>\n\n"
        f"<blockquote>Комиссия сервиса: {fee.replace('.', ',')}%\n"
        "Режим работы: 24/7</blockquote>",
        "Welcome 👋\n\n"
        "<blockquote>Atlanta Market — We are a specialized service for secure "
        "over-the-counter deals. Fast and convenient withdrawals.</blockquote>\n\n"
        f"<blockquote>Service fee: {fee}%\n"
        "Working hours: 24/7</blockquote>",
    )
    markup = welcome_menu(lang)
    if PREVIEW_IMAGE.is_file():
        try:
            await target.answer_photo(
                photo=FSInputFile(PREVIEW_IMAGE),
                caption=welcome,
                reply_markup=markup,
            )
            return
        except Exception:
            log.warning("Не удалось отправить превью, отправляем текст", exc_info=True)
    await target.answer(welcome, reply_markup=markup)


def deal_keyboard(deal: dict, viewer_id: int | None, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=tr("Открыть сделку", lang), web_app=WebAppInfo(url=deal["webapp_url"])))
    if deal["role"] == "buyer" and deal["status"] == "waiting_payment":
        builder.row(
            InlineKeyboardButton(
                text=tr("Оплатить с баланса", lang), callback_data=f"paybal:{deal['code']}"
            )
        )
    if deal["role"] == "guest" and deal["status"] == "waiting_buyer":
        label = (
            "Присоединиться как продавец"
            if deal.get("invite_role") == "seller"
            else "Присоединиться"
        )
        builder.row(InlineKeyboardButton(text=tr(label, lang), callback_data=f"join:{deal['code']}"))
    if deal["role"] in {"seller", "buyer"} and deal["status"] == "waiting_buyer":
        invite = deal["invite_link"] or ""
        builder.row(
            InlineKeyboardButton(text=tr("Скопировать ссылку", lang), copy_text=CopyTextButton(text=invite)),
            InlineKeyboardButton(
                text=tr("Поделиться", lang),
                url=f"https://t.me/share/url?url={quote(invite)}&text={quote(T(lang, 'Сделка в ATLANTA: ', 'Deal on ATLANTA: ') + deal['title'])}",
            ),
        )
    return builder.as_markup()


def deal_text(deal: dict, lang: str = "ru") -> str:
    lines = [
        f"<b>{html.escape(deal['title'])}</b>",
        f"<code>{deal['code']}</code> · {deal['status_label']}",
        "",
        f"{tr('Сумма', lang)}: <b>{fmt_amount(deal['amount'], deal['currency'])}</b> "
        f"<i>(≈ {fmt_usd(deal['amount_usd'])})</i>",
    ]
    if deal.get("fee_amount"):
        lines.append(
            f"{tr('Комиссия', lang)}: {fmt_amount(deal['fee_amount'], deal['currency'])} · {deal['fee_percent']:g}%"
        )
    if deal.get("buyer"):
        lines.append(f"{tr('Покупатель', lang)}: {html.escape(deal['buyer']['name'])}")
    if deal.get("seller"):
        lines.append(f"{tr('Продавец', lang)}: {html.escape(deal['seller']['name'])}")
    lines += ["", f"<i>{html.escape(deal['next_step'])}</i>"]
    if deal["role"] in {"seller", "buyer"} and deal["status"] == "waiting_buyer" and deal.get("invite_link"):
        seller_link = deal.get("invite_role") == "seller"
        label = T(lang, "Ссылка для продавца:", "Seller link:") if seller_link else T(lang, "Ссылка для покупателя:", "Buyer link:")
        lines += ["", f"{label}\n<code>{deal['invite_link']}</code>"]
    return "\n".join(lines)


async def show_deal(message: Message, code: str, user, lang: str) -> None:
    viewer = await escrow.get_user(user.id)
    deal = await escrow.get_deal(code, viewer)
    await message.answer(deal_text(deal, lang), reply_markup=deal_keyboard(deal, user.id, lang))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    lang = await lang_of(message.from_user.id)
    payload = (command.args or "").strip()
    if payload.startswith("deal_"):
        code = payload[5:]
        try:
            deal = await escrow.join_deal(tg_user(message.from_user, lang), code)
        except escrow.EscrowError as exc:
            await message.answer(f"{html.escape(tr(exc.message, lang))}")
            try:
                await show_deal(message, code, message.from_user, lang)
            except escrow.EscrowError:
                pass
            return
        next_step = (
            "Следующий шаг — дождаться оплаты покупателя. После неё деньги окажутся под защитой."
            if deal["role"] == "seller"
            else "Следующий шаг — оплатить счёт в приложении. Деньги будут заблокированы до вашего подтверждения."
        )
        text = (
            f"<b>{tr('Вы в сделке', lang)}</b>\n\n" + deal_text(deal, lang) +
            f"\n\n{tr(next_step, lang)}"
        )
        await message.answer(text, reply_markup=deal_keyboard(deal, message.from_user.id, lang))
        return

    await message.answer("Выберите язык / Choose language", reply_markup=start_language_menu())


@router.callback_query(F.data.startswith("startlang:"))
async def cb_start_language(callback: CallbackQuery) -> None:
    lang = "en" if callback.data.split(":", 1)[1] == "en" else "ru"
    await escrow.set_language(callback.from_user.id, lang)
    await callback.answer("Language set to English" if lang == "en" else "Язык: русский")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await send_welcome(callback.message, lang)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    text = T(
        lang,
        "<b>Как это работает</b>\n\n"
        "<b>Оплата под защитой</b>\n<blockquote><b>Деньги не уходят продавцу.</b></blockquote>\n\n"
        "<b>Передача</b>\n<blockquote><b>Продавец фиксирует факт передачи, для решения возможных споров.</b></blockquote>\n\n"
        "<b>Выплата</b>\n<blockquote><b>После подтверждения покупателем или арбитром.</b></blockquote>\n\n"
        f"Комиссия: <b>{settings.fee_crypto:g}%</b> в крипте, <b>{settings.fee_fiat:g}%</b> в фиате. "
        "Удерживается только при успешной сделке.",
        "<b>How it works</b>\n\n"
        "<b>Payment protected</b>\n<blockquote><b>Funds don't go to the seller.</b></blockquote>\n\n"
        "<b>Delivery</b>\n<blockquote><b>The seller records the delivery to help resolve possible disputes.</b></blockquote>\n\n"
        "<b>Payout</b>\n<blockquote><b>After confirmation by the buyer or an arbitrator.</b></blockquote>\n\n"
        f"Fee: <b>{settings.fee_crypto:g}%</b> for crypto, <b>{settings.fee_fiat:g}%</b> for fiat. "
        "Charged only on a successful deal.",
    )
    await message.answer(text, reply_markup=main_menu(lang))


@router.message(Command("market"))
async def cmd_market(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=tr("Открыть маркет", lang), web_app=WebAppInfo(url=settings.market_url))
    )
    await message.answer(
        T(
            lang,
            "<b>ATLANTA Market</b>\n\n"
            "Подарки, аренда и анонимные номера +888.\n"
            "Баланс в GRAM, пополнение через @CryptoBot.",
            "<b>ATLANTA Market</b>\n\n"
            "Gifts, rent and anonymous +888 numbers.\n"
            "GRAM balance, top-up via @CryptoBot.",
        ),
        reply_markup=builder.as_markup(),
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    await message.answer(f"{tr('Ваш Telegram ID:', lang)} <code>{message.from_user.id}</code>")


@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    await message.answer(
        T(lang, "Выберите язык интерфейса:", "Choose the interface language:"),
        reply_markup=language_menu(lang),
    )


@router.message(Command("deals"))
async def cmd_deals(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=tr("Открыть мои сделки", lang), web_app=WebAppInfo(url=webapp_url("tab=deals"))))
    await message.answer(tr("Все сделки — в приложении:", lang), reply_markup=builder.as_markup())


@router.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext) -> None:
    await start_create(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    await state.clear()
    await message.answer(tr("Ок, отменил. Возвращайтесь, когда будете готовы.", lang), reply_markup=main_menu(lang))


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(T(lang, "Главное меню ATLANTA:", "ATLANTA main menu:"), reply_markup=main_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "lang")
async def cb_language(callback: CallbackQuery) -> None:
    lang = await lang_of(callback.from_user.id)
    await callback.message.edit_text(
        T(lang, "Выберите язык интерфейса:", "Choose the interface language:"),
        reply_markup=language_menu(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(callback: CallbackQuery) -> None:
    value = callback.data.split(":", 1)[1]
    lang = "en" if value == "en" else "ru"
    await escrow.set_language(callback.from_user.id, lang)
    await callback.answer("Language set to English" if lang == "en" else "Язык: русский")
    text = T(
        lang,
        "<b>ATLANTA</b> — сделки под контролем\n\nВыберите действие:",
        "<b>ATLANTA</b> — deals under control\n\nChoose an action:",
    )
    await callback.message.edit_text(text, reply_markup=main_menu(lang))


@router.callback_query(F.data == "how")
async def cb_how(callback: CallbackQuery) -> None:
    lang = await lang_of(callback.from_user.id)
    text = T(
        lang,
        "<b>Как это работает</b>\n\n"
        "<b>Оплата под защитой</b>\n<blockquote><b>Деньги не уходят продавцу.</b></blockquote>\n\n"
        "<b>Передача</b>\n<blockquote><b>Продавец фиксирует факт передачи, для решения возможных споров.</b></blockquote>\n\n"
        "<b>Выплата</b>\n<blockquote><b>После подтверждения покупателем или арбитром.</b></blockquote>",
        "<b>How it works</b>\n\n"
        "<b>Payment protected</b>\n<blockquote><b>Funds don't go to the seller.</b></blockquote>\n\n"
        "<b>Delivery</b>\n<blockquote><b>The seller records the delivery to help resolve possible disputes.</b></blockquote>\n\n"
        "<b>Payout</b>\n<blockquote><b>After confirmation by the buyer or an arbitrator.</b></blockquote>",
    )
    await callback.message.answer(text, reply_markup=main_menu(lang))
    await callback.answer()


# --------------------------------------------------------------------------- create flow


async def start_create(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    await state.set_state(CreateDeal.currency)
    await state.update_data(lang=lang)
    builder = InlineKeyboardBuilder()
    for info in CURRENCIES.values():
        builder.button(text=info.code, callback_data=f"cur:{info.code}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=tr("Отмена", lang), callback_data="create_cancel"))
    await message.answer(tr("Выберите валюту сделки:", lang), reply_markup=builder.as_markup())


@router.callback_query(F.data == "create")
async def cb_create(callback: CallbackQuery, state: FSMContext) -> None:
    await start_create(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "create_cancel")
async def cb_create_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(tr("Создание сделки отменено.", lang), reply_markup=main_menu(lang))
    await callback.answer()


@router.callback_query(CreateDeal.currency, F.data.startswith("cur:"))
async def cb_currency(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    if code not in CURRENCIES:
        await callback.answer(tr("Неизвестная валюта", lang), show_alert=True)
        return
    await state.update_data(currency=code)
    await state.set_state(CreateDeal.title)
    info = CURRENCIES[code]
    await callback.message.edit_text(
        T(lang, f"Валюта: <b>{code}</b> · {info.network}\n\n", f"Currency: <b>{code}</b> · {info.network}\n\n")
        + T(
            lang,
            "Как назовём сделку?\n<i>Например: «Аккаунт Steam с 50 играми»</i>",
            "What should we call the deal?\n<i>e.g. “Steam account with 50 games”</i>",
        )
    )
    await callback.answer()


@router.message(CreateDeal.title)
async def step_title(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    title = (message.text or "").strip()
    if not (5 <= len(title) <= 120):
        await message.answer(tr("Название — от 5 до 120 символов. Попробуйте ещё раз.", lang))
        return
    await state.update_data(title=title)
    await state.set_state(CreateDeal.amount)
    data = await state.get_data()
    info = CURRENCIES[data["currency"]]
    await message.answer(
        T(lang, f"Сумма в <b>{info.code}</b>.\n", f"Amount in <b>{info.code}</b>.\n")
        + T(
            lang,
            f"Минимум: {info.min_amount} {info.code}. Введите число, например: <code>150</code>",
            f"Minimum: {info.min_amount} {info.code}. Enter a number, e.g. <code>150</code>",
        )
    )


@router.message(CreateDeal.amount)
async def step_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = await lang_of(message.from_user.id)
    currency = data["currency"]
    info = CURRENCIES[currency]
    try:
        amount = quantize(parse_amount(message.text or ""), currency)
    except ValueError:
        await message.answer(
            T(
                lang,
                "Не понял сумму. Введите число, например: <code>150</code> или <code>0.025</code>",
                "Couldn't read the amount. Enter a number, e.g. <code>150</code> or <code>0.025</code>",
            )
        )
        return
    if amount < Decimal(info.min_amount):
        await message.answer(
            T(lang, "Минимальная сумма — ", "Minimum amount — ") + f"{info.min_amount} {currency}."
        )
        return
    if usd_value(amount, currency) < 1:
        await message.answer(tr("Минимальная сумма сделки — эквивалент 1 USD", lang))
        return

    fee, net, percent = split_fee(amount, currency, settings.fee_crypto, settings.fee_fiat, settings.min_fee_usd)
    await state.update_data(amount=format(amount, "f"))
    await state.set_state(CreateDeal.terms)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=tr("Пропустить", lang), callback_data="terms:skip"))
    await message.answer(
        T(lang, "Условия сделки\n\n", "Deal terms\n\n")
        + f"{tr('Сумма', lang)}: <b>{fmt_amount(amount, currency)}</b>\n"
        + f"{T(lang, f'Комиссия {percent:g}%: ', f'Fee {percent:g}%: ')}"
        + f"{fmt_amount(fee, currency)} · {T(lang, 'продавец получит ', 'seller gets ')}{fmt_amount(net, currency)}\n\n"
        + T(
            lang,
            "Опишите условия: что именно передаётся и что считается выполнением.\n\n"
            "Отправьте текст или нажмите «Пропустить».",
            "Describe the terms: what is delivered and what counts as completion.\n\n"
            "Send the text or tap “Skip”.",
        ),
        reply_markup=builder.as_markup(),
    )


@router.message(CreateDeal.terms)
async def step_terms(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    terms = (message.text or "").strip()
    if len(terms) > 3000:
        await message.answer(tr("Слишком длинно, максимум 3000 символов.", lang))
        return
    await state.update_data(terms=terms)
    await preview_deal(message, state, lang=lang)


@router.callback_query(CreateDeal.terms, F.data == "terms:skip")
async def cb_terms_skip(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(callback.from_user.id)
    await state.update_data(terms="")
    await preview_deal(callback.message, state, edit=True, lang=lang)
    await callback.answer()


async def preview_deal(message: Message, state: FSMContext, edit: bool = False, lang: str = "ru") -> None:
    data = await state.get_data()
    currency = data["currency"]
    amount = Decimal(data["amount"])
    fee, net, percent = split_fee(amount, currency, settings.fee_crypto, settings.fee_fiat, settings.min_fee_usd)
    text = (
        f"{tr('🧾 Проверьте сделку', lang)}\n\n"
        f"<b>{html.escape(data['title'])}</b>\n"
        f"{tr('Сумма', lang)}: <b>{fmt_amount(amount, currency)}</b> ≈ {fmt_usd(usd_value(amount, currency))}\n"
        f"{T(lang, f'Комиссия {percent:g}%: ', f'Fee {percent:g}%: ')}{fmt_amount(fee, currency)}\n"
        f"{T(lang, 'Продавец получит: ', 'Seller receives: ')}<b>{fmt_amount(net, currency)}</b>"
    )
    if data.get("terms"):
        text += f"\n<b>{tr('Условия', lang)}</b>\n{html.escape(data['terms'][:700])}"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=tr("Создать сделку", lang), callback_data="create:yes"))
    builder.row(
        InlineKeyboardButton(text=tr("Заново", lang), callback_data="create"),
        InlineKeyboardButton(text=tr("Отмена", lang), callback_data="create_cancel"),
    )
    await state.set_state(CreateDeal.confirm)
    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(CreateDeal.confirm, F.data == "create:yes")
async def cb_create_yes(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(callback.from_user.id)
    data = await state.get_data()
    await callback.answer(T(lang, "Создаю…", "Creating…"))
    try:
        deal = await escrow.create_deal(
            tg_user(callback.from_user, lang),
            {
                "title": data["title"],
                "description": "",
                "terms": data.get("terms", ""),
                "category": "other",
                "amount": data["amount"],
                "currency": data["currency"],
            },
        )
    except escrow.EscrowError as exc:
        await callback.message.answer(f"{html.escape(tr(exc.message, lang))}")
        return
    await state.clear()

    invite = deal["invite_link"]
    text = (
        f"<b>{tr('Сделка создана', lang)}</b>\n\n"
        f"<b>{html.escape(deal['title'])}</b>\n"
        f"<code>{deal['code']}</code> · {fmt_amount(deal['amount'], deal['currency'])}\n\n"
        f"{T(lang, 'Отправьте покупателю ссылку — он присоединится и оплатит счёт:', 'Send the buyer the link — they will join and pay the invoice:')}\n"
        f"<code>{invite}</code>\n\n"
        f"{tr('Деньги будут под защитой до подтверждения покупателем.', lang)}"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=tr("Открыть сделку", lang), web_app=WebAppInfo(url=deal["webapp_url"])))
    builder.row(
        InlineKeyboardButton(text=tr("Скопировать ссылку", lang), copy_text=CopyTextButton(text=invite)),
        InlineKeyboardButton(
            text=tr("Поделиться", lang),
            url=f"https://t.me/share/url?url={quote(invite)}&text={quote(T(lang, 'Сделка в ATLANTA: ', 'Deal on ATLANTA: ') + deal['title'])}",
        ),
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# --------------------------------------------------------------------------- enter by code


@router.callback_query(F.data == "enter_code")
async def cb_enter_code(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await lang_of(callback.from_user.id)
    await state.set_state(EnterCode.code)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=tr("Отмена", lang), callback_data="menu"))
    await callback.message.edit_text(
        T(
            lang,
            "Введите код сделки или ссылку-приглашение.\n<i>Например: KST-AB12CD</i>",
            "Enter the deal code or invite link.\n<i>Example: KST-AB12CD</i>",
        ),
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.message(EnterCode.code)
async def step_enter_code(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    code = normalize_code(message.text or "")
    if not code:
        await message.answer(
            T(
                lang,
                "Не похоже на код сделки. Пример: <code>KST-AB12CD</code>",
                "That doesn't look like a deal code. Example: <code>KST-AB12CD</code>",
            )
        )
        return
    await state.clear()
    await show_deal(message, code, message.from_user, lang)


@router.callback_query(F.data.startswith("join:"))
async def cb_join(callback: CallbackQuery) -> None:
    lang = await lang_of(callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    try:
        deal = await escrow.join_deal(tg_user(callback.from_user, lang), code)
    except escrow.EscrowError as exc:
        await callback.answer(tr(exc.message, lang), show_alert=True)
        return
    await callback.message.edit_text(deal_text(deal, lang), reply_markup=deal_keyboard(deal, callback.from_user.id, lang))
    await callback.answer(T(lang, "Вы в сделке", "You're in the deal"))


@router.callback_query(F.data.startswith("paybal:"))
async def cb_pay_balance(callback: CallbackQuery) -> None:
    lang = await lang_of(callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    user = await escrow.get_user(callback.from_user.id)
    try:
        deal = await escrow.pay_from_balance(user or tg_user(callback.from_user, lang), code)
    except escrow.EscrowError as exc:
        await callback.answer(tr(exc.message, lang), show_alert=True)
        return
    await callback.message.edit_text(deal_text(deal, lang), reply_markup=deal_keyboard(deal, callback.from_user.id, lang))
    await callback.answer(T(lang, "Деньги под защитой", "Funds are protected"))


# --------------------------------------------------------------------------- admin


@router.message(Command("anlantawallet"))
async def cmd_market_wallet(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    user = await escrow.get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer(tr("Команда доступна только арбитрам.", lang))
        return
    raw = (command.args or "").strip()
    if not raw:
        address = await escrow.get_setting("gram_receive_address", settings.gram_receive_address)
        current = address or T(lang, "не задан", "not set")
        await message.answer(
            T(lang, f"Адрес для пополнения GRAM: <code>{html.escape(current)}</code>\n\nФормат: <code>/anlantawallet &lt;адрес&gt;</code>",
              f"GRAM top-up address: <code>{html.escape(current)}</code>\n\nFormat: <code>/anlantawallet &lt;address&gt;</code>")
        )
        return
    address = raw.split()[0].strip()
    if len(address) < 20 or len(address) > 160:
        await message.answer(T(lang, "Адрес выглядит некорректно.", "The address looks invalid."))
        return
    await escrow.set_setting("gram_receive_address", address)
    await message.answer(
        T(lang, f"Адрес для пополнения GRAM сохранён: <code>{html.escape(address)}</code>",
          f"GRAM top-up address saved: <code>{html.escape(address)}</code>")
    )


@router.message(Command("anlantastore"))
async def cmd_market_store(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    user = await escrow.get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer(tr("Команда доступна только арбитрам.", lang))
        return
    raw = (command.args or "").strip().lstrip("@")
    if not raw:
        username = await escrow.get_setting("gift_receive_username", settings.gift_receive_username)
        current = "@" + username if username else T(lang, "не задан", "not set")
        await message.answer(
            T(lang, f"Служебный аккаунт для подарков: <code>{html.escape(current)}</code>\n\nФормат: <code>/anlantastore &lt;username&gt;</code>",
              f"Gift receiving account: <code>{html.escape(current)}</code>\n\nFormat: <code>/anlantastore &lt;username&gt;</code>")
        )
        return
    username = raw.split()[0].strip().lstrip("@")
    if len(username) < 4 or len(username) > 32 or not username.replace("_", "").isalnum():
        await message.answer(T(lang, "Юзернейм выглядит некорректно.", "The username looks invalid."))
        return
    await escrow.set_setting("gift_receive_username", username)
    await message.answer(
        T(lang, f"Служебный аккаунт сохранён: <code>@{html.escape(username)}</code>",
          f"Receiving account saved: <code>@{html.escape(username)}</code>")
    )


async def _market_admin(message: Message, lang: str) -> dict | None:
    """Проверить права арбитра для команд маркета."""
    user = await escrow.get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer(tr("Команда доступна только арбитрам.", lang))
        return None
    return user


@router.message(Command("marketorders"))
async def cmd_market_orders(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    user = await _market_admin(message, lang)
    if not user:
        return
    items = await market.admin_pending_orders(user)
    if not items:
        await message.answer(T(lang, "Нет заказов, ожидающих выдачи.", "No orders awaiting fulfilment."))
        return
    builder = InlineKeyboardBuilder()
    lines = [T(lang, "🧾 <b>Заказы маркета</b>\n", "🧾 <b>Market orders</b>\n")]
    for order in items:
        title = order.get("number") or order.get("title") or "—"
        lines.append(
            f"\n<code>{html.escape(order['id'])}</code>\n"
            f"{html.escape(str(title))} · {html.escape(order['amount'])} GRAM\n"
            f"<i>{html.escape(order['status_label'])}</i>"
        )
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {title}",
                callback_data=f"mkt:done:{order['id']}",
            ),
            InlineKeyboardButton(
                text="↩️",
                callback_data=f"mkt:ref:{order['id']}",
            ),
        )
    await message.answer("".join(lines), reply_markup=builder.as_markup())


@router.message(Command("marketdone"))
async def cmd_market_done(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    user = await _market_admin(message, lang)
    if not user:
        return
    order_id = (command.args or "").strip().split()[0] if (command.args or "").strip() else ""
    if not order_id:
        await message.answer(T(lang, "Формат: <code>/marketdone &lt;ID заказа&gt;</code>", "Format: <code>/marketdone &lt;order ID&gt;</code>"))
        return
    try:
        order = await market.admin_fulfill_order(user, order_id)
    except escrow.EscrowError as exc:
        await message.answer(tr(exc.message, lang))
        return
    await message.answer(
        T(lang, f"Заказ выдан: <code>{html.escape(order['id'])}</code> · {html.escape(order['title'])}",
          f"Order fulfilled: <code>{html.escape(order['id'])}</code> · {html.escape(order['title'])}")
    )


@router.message(Command("marketrefund"))
async def cmd_market_refund(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    user = await _market_admin(message, lang)
    if not user:
        return
    order_id = (command.args or "").strip().split()[0] if (command.args or "").strip() else ""
    if not order_id:
        await message.answer(T(lang, "Формат: <code>/marketrefund &lt;ID заказа&gt;</code>", "Format: <code>/marketrefund &lt;order ID&gt;</code>"))
        return
    try:
        order = await market.admin_refund_order(user, order_id)
    except escrow.EscrowError as exc:
        await message.answer(tr(exc.message, lang))
        return
    await message.answer(
        T(lang, f"Возврат выполнен: <code>{html.escape(order['id'])}</code> · {html.escape(order['amount'])} GRAM",
          f"Refunded: <code>{html.escape(order['id'])}</code> · {html.escape(order['amount'])} GRAM")
    )


@router.message(Command("marketpayouts"))
async def cmd_market_payouts(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    user = await _market_admin(message, lang)
    if not user:
        return
    items = await market.admin_pending_payouts(user)
    if not items:
        await message.answer(T(lang, "Нет заявок на вывод.", "No withdrawal requests."))
        return
    builder = InlineKeyboardBuilder()
    lines = [T(lang, "💸 <b>Заявки на вывод</b>\n", "💸 <b>Withdrawal requests</b>\n")]
    for item in items:
        lines.append(
            f"\n<code>{html.escape(item['id'])}</code> · {html.escape(str(item['amount']))} GRAM\n"
            f"<code>{html.escape(item['address'])}</code> · ID {item['user_id']}"
        )
        builder.row(
            InlineKeyboardButton(text="✅ Выплачено", callback_data=f"mkt:pay:{item['id']}"),
            InlineKeyboardButton(text="↩️ Отклонить", callback_data=f"mkt:rej:{item['id']}"),
        )
    await message.answer("".join(lines), reply_markup=builder.as_markup())


@router.message(Command("marketpaid"))
async def cmd_market_paid(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    user = await _market_admin(message, lang)
    if not user:
        return
    payout_id = (command.args or "").strip().split()[0] if (command.args or "").strip() else ""
    if not payout_id:
        await message.answer(T(lang, "Формат: <code>/marketpaid &lt;ID заявки&gt;</code>", "Format: <code>/marketpaid &lt;request ID&gt;</code>"))
        return
    try:
        await market.admin_set_payout(user, payout_id, "paid")
    except escrow.EscrowError as exc:
        await message.answer(tr(exc.message, lang))
        return
    await message.answer(T(lang, "Заявка отмечена как выплаченная.", "Withdrawal marked as paid."))


@router.callback_query(F.data.startswith("mkt:"))
async def cb_market_admin(callback: CallbackQuery) -> None:
    lang = await lang_of(callback.from_user.id)
    user = await escrow.get_user(callback.from_user.id)
    if not user or not user.get("is_admin"):
        await callback.answer(tr("Команда доступна только арбитрам.", lang), show_alert=True)
        return
    try:
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3:
            await callback.answer()
            return
        action, target = parts[1], parts[2]
        if action == "done":
            await market.admin_fulfill_order(user, target)
            await callback.answer(T(lang, "Заказ выдан", "Order fulfilled"))
        elif action == "ref":
            await market.admin_refund_order(user, target)
            await callback.answer(T(lang, "Возврат выполнен", "Refunded"))
        elif action in {"pay", "rej"}:
            await market.admin_set_payout(user, target, "paid" if action == "pay" else "rejected")
            await callback.answer(T(lang, "Готово", "Done"))
        else:
            await callback.answer()
            return
    except escrow.EscrowError as exc:
        await callback.answer(tr(exc.message, lang), show_alert=True)
        return


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    user = await escrow.get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer(tr("Команда доступна только арбитрам.", lang))
        return
    data = await escrow.stats()
    await message.answer(
        f"📊 <b>{T(lang, 'ATLANTA · статистика', 'ATLANTA · stats')}</b>\n\n"
        f"{T(lang, 'Пользователи: ', 'Users: ')}<b>{data['users']}</b>\n"
        f"{T(lang, 'Сделки: ', 'Deals: ')}<b>{data['deals']}</b> · {T(lang, 'завершено: ', 'completed: ')}{data['completed']}\n"
        f"{T(lang, 'В спорах: ', 'In dispute: ')}<b>{data['disputed']}</b>\n"
        f"{T(lang, 'Оборот: ', 'Volume: ')}<b>{fmt_usd(data['volume_usd'])}</b>\n"
        f"{T(lang, 'Среднее завершение: ', 'Average completion: ')}{data['avg_minutes']} {T(lang, 'мин.', 'min.')}"
    )


async def _lookup_target(
    message: Message, args: list[str], lang: str, *, numeric_needs_extra: bool = False
) -> tuple[int | None, list[str]]:
    """Найти получателя по ответу на сообщение, @username или ID."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id, args
    if not args:
        return None, args
    raw = args[0].strip()
    token = raw.lstrip("@")
    if raw.startswith("@"):
        found = await escrow.find_user_by_username(token)
        if not found:
            raise ValueError(
                T(lang, "Пользователь с таким юзернеймом не найден.", "User with this username was not found.")
            )
        return int(found["id"]), args[1:]
    if token.isdigit() and (not numeric_needs_extra or len(args) >= 3):
        return int(token), args[1:]
    return None, args


@router.message(Command("anlantachief"))
async def cmd_anlantachief(message: Message, bot: Bot) -> None:
    lang = await lang_of(message.from_user.id)
    try:
        await escrow.claim_chief(message.from_user.id)
    except escrow.EscrowError as exc:
        await message.answer(tr(exc.message, lang))
        return
    await refresh_admin_commands(bot)
    await message.answer(
        T(
            lang,
            "Вы главный арбитр. Можно назначать и снимать арбитров.",
            "You are the chief arbiter. You can appoint and remove arbiters.",
        )
    )


@router.message(Command("anlantaset", "anlantarevoke"))
async def cmd_arbiter_role(message: Message, command: CommandObject, bot: Bot) -> None:
    lang = await lang_of(message.from_user.id)
    chief = await escrow.get_user(message.from_user.id)
    try:
        uid, _ = await _lookup_target(message, (command.args or "").split(), lang)
        if uid is None:
            raise ValueError(
                T(
                    lang,
                    "Формат: <code>/anlantaset @пользователь</code> или ответьте на сообщение.",
                    "Format: <code>/anlantaset @user</code> or reply to a message.",
                )
            )
        enabled = (command.command or "").lower() == "anlantaset"
        target = await escrow.set_arbiter(chief or {}, uid, enabled)
    except escrow.EscrowError as exc:
        await message.answer(tr(exc.message, lang))
        return
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await refresh_admin_commands(bot)
    name = html.escape(escrow.user_name(target))
    if enabled:
        text = T(lang, f"<b>{name}</b> назначен арбитром.", f"<b>{name}</b> is now an arbiter.")
    else:
        text = T(lang, f"<b>{name}</b> больше не арбитр.", f"<b>{name}</b> is no longer an arbiter.")
    await message.answer(text)


@router.message(Command("anlantagive"))
async def cmd_anlantagive(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    arbiter = await escrow.get_user(message.from_user.id)
    args = (command.args or "").replace(",", ".").split()
    try:
        uid, rest = await _lookup_target(message, args, lang, numeric_needs_extra=True)
        if uid is None or len(rest) != 2:
            raise ValueError(
                T(
                    lang,
                    "Формат: <code>/anlantagive @пользователь сумма валюта</code>\nИли ответьте на сообщение: <code>/anlantagive 100 USDT</code>",
                    "Format: <code>/anlantagive @user amount currency</code>\nOr reply: <code>/anlantagive 100 USDT</code>",
                )
            )
        result = await escrow.give_balance(arbiter or {}, uid, rest[0], rest[1])
    except escrow.EscrowError as exc:
        await message.answer(html.escape(tr(exc.message, lang)))
        return
    except ValueError as exc:
        await message.answer(str(exc))
        return
    target = await escrow.get_user(result["user_id"])
    await message.answer(
        f"<b>{T(lang, 'Баланс начислен', 'Balance credited')}</b>\n\n"
        f"{tr('Пользователь', lang)}: {html.escape(escrow.user_name(target))}\n"
        f"{tr('Сумма', lang)}: {fmt_amount(result['amount'], result['currency'])}\n"
        f"{tr('Доступно', lang)}: {fmt_amount(result['available'], result['currency'])}"
    )


@router.message(Command("anlantamoney"))
async def cmd_anlantamoney(message: Message, command: CommandObject) -> None:
    lang = await lang_of(message.from_user.id)
    user = await escrow.get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer(tr("Команда доступна только арбитрам.", lang))
        return
    args = (command.args or "").replace(",", ".").split()
    try:
        uid, rest = await _lookup_target(message, args, lang, numeric_needs_extra=True)
        if uid is None:
            rest = args
        if len(rest) != 2:
            raise ValueError(
                T(
                    lang,
                    "Формат: <code>/anlantamoney сумма валюта</code> или <code>/anlantamoney @пользователь сумма валюта</code>\nНапример: <code>/anlantamoney 100 USDT</code>",
                    "Format: <code>/anlantamoney amount currency</code> or <code>/anlantamoney @user amount currency</code>\nExample: <code>/anlantamoney 100 USDT</code>",
                )
            )
        result = await escrow.admin_credit(user, rest[0], rest[1], to_uid=uid)
    except escrow.EscrowError as exc:
        await message.answer(html.escape(tr(exc.message, lang)))
        return
    except ValueError as exc:
        await message.answer(str(exc))
        return
    title = "Баланс пополнен" if not uid else "Баланс начислен"
    extra = ""
    if uid:
        target = await escrow.get_user(uid)
        extra = f"{tr('Пользователь', lang)}: {html.escape(escrow.user_name(target))}\n"
    await message.answer(
        f"<b>{tr(title, lang) if title == 'Баланс пополнен' else T(lang, title, 'Balance credited')}</b>\n\n"
        + extra
        + f"{tr('Сумма', lang)}: {fmt_amount(result['amount'], result['currency'])}\n"
        + f"{tr('Доступно', lang)}: {fmt_amount(result['available'], result['currency'])}"
    )


@router.message(Command("disputes"))
async def cmd_disputes(message: Message) -> None:
    lang = await lang_of(message.from_user.id)
    user = await escrow.get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer(tr("Команда доступна только арбитрам.", lang))
        return
    items = await escrow.admin_disputes(user)
    if not items:
        await message.answer(tr("Открытых споров нет.", lang))
        return
    await message.answer(
        T(lang, "Открытых споров: ", "Open disputes: ") + f"<b>{len(items)}</b>"
    )
    for deal in items[:10]:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=tr("Открыть", lang), web_app=WebAppInfo(url=deal["webapp_url"])))
        builder.row(
            InlineKeyboardButton(text=tr("Выплатить продавцу", lang), callback_data=f"arb:release:{deal['code']}"),
            InlineKeyboardButton(text=tr("Вернуть покупателю", lang), callback_data=f"arb:refund:{deal['code']}"),
        )
        await message.answer(
            f"<b>{html.escape(deal['title'])}</b>\n"
            f"<code>{deal['code']}</code> · {fmt_amount(deal['amount'], deal['currency'])}\n"
            f"{tr('Продавец', lang)}: {html.escape(deal['seller']['name'] if deal['seller'] else '—')}\n"
            f"{tr('Покупатель', lang)}: {html.escape(deal['buyer']['name'] if deal['buyer'] else '—')}\n\n"
            f"{tr('Причина', lang)}: {html.escape(deal['dispute_reason'] or '—')}",
            reply_markup=builder.as_markup(),
        )


@router.callback_query(F.data.startswith("arb:"))
async def cb_arbitrate(callback: CallbackQuery) -> None:
    lang = await lang_of(callback.from_user.id)
    _, outcome, code = callback.data.split(":", 2)
    user = await escrow.get_user(callback.from_user.id)
    if not user or not user.get("is_admin"):
        await callback.answer(tr("Недостаточно прав", lang), show_alert=True)
        return
    try:
        deal = await escrow.resolve(user, code, outcome)
    except escrow.EscrowError as exc:
        await callback.answer(tr(exc.message, lang), show_alert=True)
        return
    await callback.message.edit_text(
        T(lang, f"Решение принято по <code>{deal['code']}</code>\nСтатус: {deal['status_label']}",
          f"Decision made on <code>{deal['code']}</code>\nStatus: {deal['status_label']}"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=tr("Открыть сделку", lang), web_app=WebAppInfo(url=deal["webapp_url"]))]]
        ),
    )
    await callback.answer(T(lang, "Готово", "Done"))


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    lang = await lang_of(message.from_user.id)
    await state.clear()
    await message.answer(tr("Не понял команду. Вот меню:", lang), reply_markup=main_menu(lang))


RU_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="market", description="Маркет подарков"),
    BotCommand(command="create", description="Создать сделку"),
    BotCommand(command="deals", description="Мои сделки"),
    BotCommand(command="language", description="Сменить язык"),
    BotCommand(command="help", description="Как это работает"),
    BotCommand(command="id", description="Мой Telegram ID"),
]

EN_COMMANDS = [
    BotCommand(command="start", description="Main menu"),
    BotCommand(command="market", description="Gift market"),
    BotCommand(command="create", description="Create a deal"),
    BotCommand(command="deals", description="My deals"),
    BotCommand(command="language", description="Change language"),
    BotCommand(command="help", description="How it works"),
    BotCommand(command="id", description="My Telegram ID"),
]

RU_ADMIN_COMMANDS = RU_COMMANDS + [
    BotCommand(command="anlantamoney", description="Начислить баланс"),
    BotCommand(command="anlantagive", description="Выдать баланс арбитром"),
    BotCommand(command="anlantachief", description="Стать главным арбитром"),
    BotCommand(command="anlantaset", description="Назначить арбитра"),
    BotCommand(command="anlantarevoke", description="Забрать статус арбитра"),
    BotCommand(command="anlantawallet", description="Адрес для GRAM"),
    BotCommand(command="anlantastore", description="Аккаунт для подарков"),
    BotCommand(command="marketorders", description="Заказы маркета"),
    BotCommand(command="marketdone", description="Выдать заказ маркета"),
    BotCommand(command="marketrefund", description="Вернуть GRAM за заказ"),
    BotCommand(command="marketpayouts", description="Выплаты маркета"),
    BotCommand(command="marketpaid", description="Отметить выплату"),
]
EN_ADMIN_COMMANDS = EN_COMMANDS + [
    BotCommand(command="anlantamoney", description="Credit balance"),
    BotCommand(command="anlantagive", description="Grant balance as arbiter"),
    BotCommand(command="anlantachief", description="Become chief arbiter"),
    BotCommand(command="anlantaset", description="Appoint arbiter"),
    BotCommand(command="anlantarevoke", description="Revoke arbiter"),
    BotCommand(command="anlantawallet", description="GRAM wallet address"),
    BotCommand(command="anlantastore", description="Gift receiving account"),
    BotCommand(command="marketorders", description="Market orders"),
    BotCommand(command="marketdone", description="Fulfill market order"),
    BotCommand(command="marketrefund", description="Refund market order"),
    BotCommand(command="marketpayouts", description="Market payouts"),
    BotCommand(command="marketpaid", description="Mark payout"),
]


async def refresh_admin_commands(bot: Bot) -> None:
    """Обновить скрытые команды у владельца и всех арбитров."""
    privileged = sorted(set(settings.admin_ids) | set(await escrow.privileged_ids()))
    for admin_id in privileged:
        try:
            scope = BotCommandScopeChat(chat_id=admin_id)
            await bot.set_my_commands(RU_ADMIN_COMMANDS, scope=scope)
            await bot.set_my_commands(EN_ADMIN_COMMANDS, scope=scope, language_code="en")
        except Exception as exc:
            log.warning("Не удалось задать команды арбитру %s: %s", admin_id, exc)


def _telegram_session() -> AiohttpSession | None:
    """Использовать системный прокси, если он задан (иначе Telegram может быть недоступен)."""
    proxy = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    )
    return AiohttpSession(proxy=proxy) if proxy else None


async def _sync_menu_button(bot: Bot, attempts: int = 120, delay: float = 3.0) -> None:
    """Ставит кнопку меню, когда станет известен публичный HTTPS-адрес."""
    for _ in range(attempts):
        if settings.public_url_ready or settings.public_url_explicit:
            try:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="Mini App", web_app=WebAppInfo(url=settings.webapp_url))
                )
                log.info("Кнопка меню указывает на %s", settings.webapp_url)
            except Exception as exc:
                log.warning("Не удалось установить кнопку меню: %s", exc)
            return
        await asyncio.sleep(delay)
    log.warning("Публичный адрес не определён — задайте PUBLIC_URL в переменных окружения.")


async def run_bot() -> None:
    bot = Bot(
        token=settings.bot_token,
        session=_telegram_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    try:
        me = await bot.get_me()
        notifier.attach(bot, me.username or settings.bot_username)
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(router)

        await bot.set_my_commands(RU_COMMANDS)
        await bot.set_my_commands(EN_COMMANDS, language_code="en")
        await refresh_admin_commands(bot)

        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Бот @%s запущен", me.username)
        _menu_task = asyncio.create_task(_sync_menu_button(bot))
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
