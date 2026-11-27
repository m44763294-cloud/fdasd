"""Локализация серверных строк: словарь RU → EN и безопасный перевод.

Русский остаётся исходным языком хранения. Перевод применяется на выдаче:
в API (по заголовку X-Lang), в боте (по языку пользователя) и в уведомлениях
(по языку получателя). Неизвестные строки возвращаются как есть.
"""

from __future__ import annotations

import re

LANGS = ("ru", "en")
LANG_LABELS = {"ru": "Русский", "en": "English"}

# Русская строка → английская. Ключи совпадают с текстом один-в-один.
EN: dict[str, str] = {
    # ---------------------------------------------------------- статусы сделок
    "Ожидает покупателя": "Awaiting buyer",
    "Ожидает оплаты": "Awaiting payment",
    "Средства под защитой": "Funds secured",
    "Товар передан": "Item delivered",
    "Завершена": "Completed",
    "Спор": "Dispute",
    "Отменена": "Cancelled",
    "Возврат средств": "Refunded",
    # -------------------------------------------------------------- категории
    "Цифровые товары": "Digital goods",
    "Аккаунты и доступы": "Accounts & access",
    "Услуги": "Services",
    "Игровое": "Gaming",
    "Товары": "Goods",
    "Другое": "Other",
    # ------------------------------------------------------------ следующие шаги
    "Отправьте ссылку покупателю — он присоединится к сделке.":
        "Send the link to the buyer — they will join the deal.",
    "Сделка ждёт покупателя. Вы можете занять это место.":
        "The deal is waiting for a buyer. You can take this spot.",
    "Оплатите счёт: деньги заблокируются и уйдут продавцу только после вашего подтверждения.":
        "Pay the invoice: funds are locked and go to the seller only after your confirmation.",
    "Ждём оплату покупателя. После зачисления средства будут под защитой.":
        "Waiting for the buyer's payment. Once received, funds become protected.",
    "Покупатель уже присоединился и оплачивает сделку.":
        "The buyer has joined and is paying for the deal.",
    "Деньги под защитой. Передайте товар и отметьте это в сделке.":
        "Funds are secured. Deliver the item and mark it in the deal.",
    "Деньги заблокированы. Проверьте товар и подтвердите получение.":
        "Funds are locked. Check the item and confirm receipt.",
    "Средства заблокированы до подтверждения покупателем.":
        "Funds are locked until the buyer confirms.",
    "Продавец отметил передачу. Подтвердите получение, чтобы выплатить ему деньги.":
        "The seller marked the delivery. Confirm receipt to release the payment.",
    "Ждём подтверждения покупателя.": "Waiting for the buyer's confirmation.",
    "Сделка завершена, средства выплачены продавцу.":
        "The deal is complete; funds were paid to the seller.",
    "Спор передан арбитру. Решение будет принято по условиям сделки.":
        "The dispute is with an arbitrator. A decision will follow the deal terms.",
    "Сделка отменена. Средства не списывались.":
        "The deal was cancelled. No funds were charged.",
    "Арбитр вернул средства покупателю.": "The arbitrator refunded the buyer.",
    # ------------------------------------------------------------------ действия
    "Присоединиться к сделке": "Join the deal",
    "Оплатить сделку": "Pay for the deal",
    "Оплатить с баланса": "Pay from balance",
    "Доступно": "Available",
    "Подтвердить получение": "Confirm receipt",
    "Открыть спор": "Open dispute",
    "Отменить сделку": "Cancel deal",
    "Выплатить продавцу": "Pay the seller",
    "Вернуть покупателю": "Refund the buyer",
    "Открыть сделку": "Open deal",
    "Открыть": "Open",
    "Вывести": "Withdraw",
    # -------------------------------------------------------------------- события
    "Сделка создана": "Deal created",
    "Покупатель присоединился к сделке": "Buyer joined the deal",
    "Счёт на оплату сформирован": "Invoice created",
    "Средства заблокированы под защитой Gumroad": "Funds secured by Gumroad",
    "Продавец отметил передачу товара": "Seller marked the item as delivered",
    "Покупатель подтвердил сделку · средства выплачены продавцу":
        "Buyer confirmed the deal · funds paid to the seller",
    "Выплата продавцу": "Payout to seller",
    "Возврат покупателю": "Refund to buyer",
    "Решение арбитра": "Arbitrator decision",
    "Выплата по сделке": "Deal payout",
    "Комиссия Gumroad": "Gumroad fee",
    "Сделка отменена": "Deal cancelled",
    "Вывод средств": "Withdrawal",
    "Вывод доступен после 3 успешных сделок": "Withdrawal is available after 3 successful deals",
    "Вывод отправлен": "Withdrawal submitted",
    # ------------------------------------------------------------------- уведомления
    "Покупатель присоединился": "Buyer joined",
    "Деньги под защитой": "Funds secured",
    "Товар передан": "Item delivered",
    "Сделка завершена": "Deal completed",
    "Сделка отменена": "Deal cancelled",
    "Открыт спор": "Dispute opened",
    "Арбитр завершил сделку": "Arbitrator completed the deal",
    "Арбитр вернул средства": "Arbitrator refunded the funds",
    "Арбитраж": "Arbitration",
    "Участник отменил сделку.": "A participant cancelled the deal.",
    "Покупатель оплатил сделку. Продавец может передавать товар, покупатель — подтверждать получение.":
        "The buyer paid for the deal. The seller can deliver, and the buyer can confirm receipt.",
    "Проверьте товар. Деньги уйдут продавцу только после вашего подтверждения.":
        "Check the item. The money goes to the seller only after your confirmation.",
    "Арбитр изучит условия сделки и примет решение. Не выводите общение из чата сделки.":
        "An arbitrator will review the deal terms and decide. Keep communication inside the deal chat.",
    "Сделка": "Deal",
    "Сумма": "Amount",
    "Комиссия": "Fee",
    "Покупатель": "Buyer",
    "Продавец": "Seller",
    "Причина": "Reason",
    "Комментарий": "Comment",
    "Статус": "Status",
    # ---------------------------------------------------------------- ошибки
    "Сделка не найдена": "Deal not found",
    "Нельзя присоединиться к собственной сделке": "You can't join your own deal",
    "К сделке уже присоединился покупатель": "A buyer has already joined this deal",
    "Сделка уже занята": "This deal is already taken",
    "Оплатить сделку может только покупатель": "Only the buyer can pay for this deal",
    "Сделка не ожидает оплаты": "This deal isn't awaiting payment",
    "Только покупатель может оплатить сделку": "Only the buyer can pay for this deal",
    "Отметить передачу может только продавец": "Only the seller can mark the delivery",
    "Передать товар можно только после оплаты": "The item can be delivered only after payment",
    "Подтвердить сделку может только покупатель": "Only the buyer can confirm the deal",
    "Сейчас подтверждение недоступно": "Confirmation isn't available right now",
    "Отменить сделку может только участник": "Only a participant can cancel the deal",
    "Оплаченную сделку нельзя просто отменить — откройте спор":
        "A paid deal can't simply be cancelled — open a dispute",
    "Открыть спор может только участник": "Only a participant can open a dispute",
    "Спор можно открыть только по оплаченной сделке":
        "A dispute can be opened only for a paid deal",
    "Опишите проблему — минимум 10 символов": "Describe the problem — at least 10 characters",
    "Недостаточно прав": "Not enough permissions",
    "Неверный пользователь": "Invalid user",
    "Не удалось найти пользователя": "Couldn't find the user",
    "Пользователь с таким юзернеймом не найден.": "User with this username was not found.",
    "Главный арбитр уже назначен": "A chief arbiter has already been assigned",
    "Команда доступна только владельцу бота": "This command is available to the bot owner only",
    "Некорректное решение арбитра": "Invalid arbitrator decision",
    "Сделка не находится в споре": "The deal isn't in dispute",
    "Недостаточно средств на балансе": "Not enough funds in the balance",
    "Укажите корректные реквизиты получателя": "Enter valid recipient details",
    "Сумма должна быть больше нуля": "The amount must be greater than zero",
    "Недостаточно средств": "Not enough funds",
    "Название сделки — от 5 до 120 символов": "Deal title must be 5–120 characters",
    "Описание — не длиннее 1500 символов": "Description must be at most 1500 characters",
    "Условия — не длиннее 3000 символов": "Terms must be at most 3000 characters",
    "Неизвестная валюта": "Unknown currency",
    "Минимальная сумма сделки — эквивалент 1 USD": "Minimum deal amount is the equivalent of 1 USD",
    "Статус сделки уже изменился": "The deal status has already changed",
    "Не удалось создать код сделки, попробуйте ещё раз":
        "Couldn't create a deal code, please try again",
    "Сделка не ожидает оплаты": "The deal is not awaiting payment",
    "Оплата списана с баланса и зачислена под защиту Gumroad":
        "Payment was charged from the balance and placed under Gumroad protection",
    "Покупатель оплатил сделку с баланса. Продавец может передавать товар, покупатель — подтверждать получение.":
        "The buyer paid from their balance. The seller can deliver the item and the buyer can confirm receipt.",
    "Бот не настроен: проверка Telegram недоступна":
        "The bot isn't configured: Telegram verification is unavailable",
    "Подпись Telegram недействительна": "Invalid Telegram signature",
    "В данных Telegram нет пользователя": "No user in the Telegram data",
    "Откройте приложение внутри Telegram": "Open the app inside Telegram",
    "Некорректная сумма": "Invalid amount",
    "Сумма слишком мала для сделки": "The amount is too small for a deal",
    # ------------------------------------------------------------------- бот
    "Открыть Gumroad": "Open Gumroad",
    "Создать сделку": "Create deal",
    "Войти по коду": "Join by code",
    "Мои сделки": "My deals",
    "Как это работает": "How it works",
    "Поддержка": "Support",
    "Язык": "Language",
    "Присоединиться": "Join",
    "Присоединиться как продавец": "Join as seller",
    "Ссылка для продавца:": "Seller link:",
    "Ссылка для покупателя:": "Buyer link:",
    "Место в сделке уже занято": "The slot in this deal is already taken",
    "Сделка ждёт продавца. Вы можете занять это место.":
        "The deal is waiting for a seller. You can take this slot.",
    "Отправьте ссылку продавцу — он присоединится к сделке и передаст товар.":
        "Send the link to the seller — they will join the deal and deliver the item.",
    "Продавец присоединился к сделке": "Seller joined the deal",
    "Покупатель присоединился к сделке": "Buyer joined the deal",
    "Продавец присоединился": "Seller joined",
    "Покупатель присоединился": "Buyer joined",
    "Покупатель может оплатить счёт.": "The buyer can now pay the invoice.",
    "Теперь он оплачивает счёт.": "Now they will pay the invoice.",
    "Следующий шаг — дождаться оплаты покупателя. После неё деньги окажутся под защитой.":
        "Next step: wait for the buyer to pay. The funds will then be protected.",
    "Скопировать ссылку": "Copy link",
    "Поделиться": "Share",
    "Открыть мои сделки": "Open my deals",
    "Главное меню Gumroad:": "Gumroad main menu:",
    "Главное меню:": "Main menu:",
    "Ок, отменил. Возвращайтесь, когда будете готовы.":
        "Okay, cancelled. Come back when you're ready.",
    "Создание сделки отменено.": "Deal creation cancelled.",
    "Все сделки — в приложении:": "All deals are in the app:",
    "Ваш Telegram ID:": "Your Telegram ID:",
    "Получайте выплату и создавайте сделки в мини-приложении.":
        "Receive payouts and create deals in the mini app.",
    "Команда доступна только арбитрам.": "This command is available to arbitrators only.",
    "Баланс пополнен": "Balance topped up",
    "Баланс": "Balance",
    "Пополнить GRAM": "Top up GRAM",
    "Команда доступна только арбитрам.": "Only arbiters can use this command.",
    "Адрес выглядит некорректно.": "The address looks invalid.",
    "Юзернейм выглядит некорректно.": "The username looks invalid.",
    "Формат: <code>/anlantamoney сумма валюта</code>\nНапример: <code>/anlantamoney 100 USDT</code>":
        "Format: <code>/anlantamoney amount currency</code>\nExample: <code>/anlantamoney 100 USDT</code>",
    "Оплата сделки с баланса": "Deal payment from balance",
    "Пополнение администратором": "Admin credit",
    "Деньги под защитой": "Funds are protected",
    "Открытых споров нет.": "No open disputes.",
    "Не понял команду. Вот меню:": "I didn't catch that. Here's the menu:",
    "Вы в сделке": "You're in the deal",
    "Следующий шаг — оплатить счёт в приложении. Деньги будут заблокированы до вашего подтверждения.":
        "Next step: pay the invoice in the app. Funds stay locked until you confirm.",
    "Сделка создана": "Deal created",
    "Отправьте покупателю ссылку — он присоединится и оплатит счёт:":
        "Send the buyer the link — they will join and pay the invoice:",
    "Деньги будут под защитой до подтверждения покупателем.":
        "Funds stay protected until the buyer confirms.",
    "Выберите валюту сделки:": "Choose the deal currency:",
    "Перейти в приложение": "Open the app",
    "Перейти в OTC": "Go to OTC",
    "Перейти в маркет": "Go to market",
    "Открыть OTC": "Open OTC",
    "Открыть маркетплейс": "Open marketplace",
    "Маркет": "Market",
    "Открыть маркет": "Open market",
    "Маркет подарков": "Gift market",
    "Подарки, аренда и анонимные номера +888.": "Gifts, rent and anonymous +888 numbers.",
    "Открыть приложение": "Open the app",
    "Как назовём сделку?": "What should we call the deal?",
    "Например: «Аккаунт Steam с 50 играми»": "e.g. “Steam account with 50 games”",
    "Название — от 5 до 120 символов. Попробуйте ещё раз.":
        "Title must be 5–120 characters. Try again.",
    "Сумма в": "Amount in",
    "Введите число, например:": "Enter a number, for example:",
    "Не понял сумму. Введите число, например:": "Couldn't read the amount. Enter a number, for example:",
    "Сумма:": "Amount:",
    "Комиссия": "Fee",
    "продавец получит": "seller gets",
    "Пропустить": "Skip",
    "Опишите условия: что именно передаётся и что считается выполнением.":
        "Describe the terms: what is delivered and what counts as completion.",
    "Отправьте текст или нажмите «Пропустить».": "Send the text or tap “Skip”.",
    "Слишком длинно, максимум 3000 символов.": "Too long, 3000 characters max.",
    "🧾 Проверьте сделку": "🧾 Review the deal",
    "Продавец получит:": "Seller receives:",
    "Условия": "Terms",
    "Создать сделку": "Create deal",
    "Заново": "Start over",
    "Отмена": "Cancel",
    "Создаю…": "Creating…",
    "Введите код сделки или ссылку-приглашение.":
        "Enter the deal code or invite link.",
    "Например:": "Example:",
    "Не похоже на код сделки. Пример:": "That doesn't look like a deal code. Example:",
    "📊 Gumroad · статистика": "📊 Gumroad · stats",
    "Пользователи:": "Users:",
    "Сделки:": "Deals:",
    "завершено:": "completed:",
    "В спорах:": "In dispute:",
    "Оборот:": "Volume:",
    "Среднее завершение:": "Average completion:",
    "мин.": "min.",
    "Открытых споров:": "Open disputes:",
    "Сумма сделки": "Deal amount",
    # ------------------------------------------------------------------- прочее
    "Пользователь": "User",
    "Русский": "Russian",
    "Choosing a language": "Choosing a language",
}


def tr(text: str, lang: str = "ru") -> str:
    """Перевести строку на язык lang. Неизвестное возвращается без изменений."""
    if not text or lang != "en":
        return text
    if text in EN:
        return EN[text]
    return _translate_dynamic(text)


# Динамические строки: префиксы и шаблоны с подставленными значениями.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^Открыт спор: (.+)$", re.S), r"Dispute opened: \1"),
    (re.compile(r"^Сделка отменена: (.+)$", re.S), r"Deal cancelled: \1"),
    (re.compile(r"^Продавец отметил передачу товара: (.+)$", re.S), r"Seller marked delivery: \1"),
    (re.compile(r"^Выплата продавцу: (.+)$", re.S), r"Payout to seller: \1"),
    (re.compile(r"^Возврат покупателю: (.+)$", re.S), r"Refund to buyer: \1"),
    (re.compile(r"^Минимальная сумма — (.+)$", re.S), r"Minimum amount — \1"),
    (re.compile(r"^Оплачено меньше суммы сделки: (.+)$", re.S), r"Underpaid: \1"),
    (re.compile(r"^Платёжный провайдер недоступен: (.+)$", re.S), r"Payment provider unavailable: \1"),
    (re.compile(r"^Вывод не выполнен: (.+)$", re.S), r"Withdrawal failed: \1"),
    (re.compile(r"^(.+) вошёл в сделку\. Теперь он оплачивает счёт\.$", re.S),
     r"\1 joined the deal. They are now paying the invoice."),
    (re.compile(r"^Покупатель подтвердил получение\. Продавцу выплачено (.+)\.$", re.S),
     r"Buyer confirmed receipt. Seller was paid \1."),
    (re.compile(r"^Средства выплачены продавцу: (.+)\.$", re.S), r"Funds paid to the seller: \1."),
    (re.compile(r"^Покупателю возвращено (.+)\.$", re.S), r"Buyer was refunded \1."),
    (re.compile(r"^Причина: (.+?)\n\nАрбитр изучит условия сделки и примет решение\. Не выводите общение из чата сделки\.$", re.S),
     r"Reason: \1\n\nAn arbitrator will review the deal terms and decide. Keep communication inside the deal chat."),
    (re.compile(r"^Причина: (.+)$", re.S), r"Reason: \1"),
    (re.compile(r"^Комментарий: (.+)$", re.S), r"Comment: \1"),
    (re.compile(r"^Сделка (.+?) · (.+)$", re.S), r"Deal \1 · \2"),
]


def _translate_dynamic(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        if pattern.match(text):
            return pattern.sub(replacement, text)
    return text


def lang_of(value: str | None) -> str:
    return "en" if (value or "").lower().startswith("en") else "ru"
