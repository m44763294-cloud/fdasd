"""Доменные справочники, статусы и форматирование сумм."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP


@dataclass(frozen=True)
class CurrencyInfo:
    code: str
    name: str
    network: str
    kind: str  # crypto | fiat
    decimals: int
    min_amount: str
    rate_usd: float


CURRENCIES: dict[str, CurrencyInfo] = {
    "USDT": CurrencyInfo("USDT", "Tether USD", "TRON · TRC-20", "crypto", 2, "1", 1.0),
    "BTC": CurrencyInfo("BTC", "Bitcoin", "Bitcoin", "crypto", 8, "0.0002", 96_000.0),
    "ETH": CurrencyInfo("ETH", "Ethereum", "Ethereum", "crypto", 6, "0.002", 3_100.0),
    "TON": CurrencyInfo("TON", "Toncoin", "TON", "crypto", 4, "1", 5.3),
    "USDC": CurrencyInfo("USDC", "USD Coin", "TRON · TRC-20", "crypto", 2, "1", 1.0),
    "RUB": CurrencyInfo("RUB", "Российский рубль", "СБП / карта", "fiat", 2, "100", 0.0112),
    "UAH": CurrencyInfo("UAH", "Украинская гривна", "Карта / P2P", "fiat", 2, "50", 0.024),
    "KZT": CurrencyInfo("KZT", "Казахстанский тенге", "Карта / перевод", "fiat", 2, "600", 0.0019),
    "BYN": CurrencyInfo("BYN", "Белорусский рубль", "Карта / ЕРИП", "fiat", 2, "5", 0.31),
    "TRY": CurrencyInfo("TRY", "Турецкая лира", "Карта / перевод", "fiat", 2, "50", 0.029),
    "AMD": CurrencyInfo("AMD", "Армянский драм", "Карта / перевод", "fiat", 2, "400", 0.0026),
    "GEL": CurrencyInfo("GEL", "Грузинский лари", "Карта / перевод", "fiat", 2, "3", 0.37),
    "USD": CurrencyInfo("USD", "Доллар США", "Карта / перевод", "fiat", 2, "1", 1.0),
    "EUR": CurrencyInfo("EUR", "Евро", "Карта / перевод", "fiat", 2, "1", 1.09),
}

CATEGORIES: dict[str, str] = {
    "digital": "Цифровые товары",
    "accounts": "Аккаунты и доступы",
    "services": "Услуги",
    "other": "Другое",
}

STATUS_LABELS: dict[str, str] = {
    "waiting_buyer": "Ожидает покупателя",
    "waiting_payment": "Ожидает оплаты",
    "funded": "Средства под защитой",
    "delivered": "Товар передан",
    "completed": "Завершена",
    "disputed": "Спор",
    "cancelled": "Отменена",
    "refunded": "Возврат средств",
}

STATUS_TONES: dict[str, str] = {
    "waiting_buyer": "neutral",
    "waiting_payment": "amber",
    "funded": "blue",
    "delivered": "violet",
    "completed": "green",
    "disputed": "red",
    "cancelled": "neutral",
    "refunded": "amber",
}

FINAL_STATUSES = {"completed", "cancelled", "refunded"}


def currency_or_raise(code: str) -> CurrencyInfo:
    info = CURRENCIES.get((code or "").upper())
    if info is None:
        raise KeyError(code)
    return info


def parse_amount(raw: str | float | Decimal) -> Decimal:
    if isinstance(raw, Decimal):
        return raw
    text = str(raw).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Некорректная сумма") from exc


def quantize(amount: Decimal, currency: str) -> Decimal:
    info = currency_or_raise(currency)
    step = Decimal(1).scaleb(-info.decimals)
    return amount.quantize(step, rounding=ROUND_HALF_UP)


def usd_value(amount: Decimal | str, currency: str) -> float:
    info = currency_or_raise(currency)
    return round(float(Decimal(str(amount))) * info.rate_usd, 2)


def fmt_amount(amount: Decimal | str, currency: str, with_code: bool = True) -> str:
    info = currency_or_raise(currency)
    value = Decimal(str(amount))
    text = f"{value:,.{info.decimals}f}".replace(",", "\u202f").replace(".", ",")
    if "." in text and info.decimals > 2:
        whole, _, frac = text.partition(",")
        frac = frac.rstrip("0")
        while len(frac) < 2:
            frac += "0"
        text = f"{whole},{frac}"
    return f"{text} {info.code}" if with_code else text


def fmt_usd(amount: Decimal | str | float) -> str:
    value = Decimal(str(amount))
    text = f"{value:,.2f}".replace(",", "\u202f").replace(".", ",")
    return f"USD {text}"


def fee_percent_for(currency: str, fee_crypto: float, fee_fiat: float) -> float:
    info = currency_or_raise(currency)
    return fee_fiat if info.kind == "fiat" else fee_crypto


def split_fee(amount: Decimal, currency: str, fee_crypto: float, fee_fiat: float, min_fee_usd: float) -> tuple[Decimal, Decimal, float]:
    """Возвращает (комиссия, к выплате, процент)."""
    info = currency_or_raise(currency)
    percent = fee_percent_for(currency, fee_crypto, fee_fiat)
    step = Decimal(1).scaleb(-info.decimals)
    fee = (amount * Decimal(str(percent)) / Decimal(100)).quantize(step, rounding=ROUND_CEILING)
    min_fee = (Decimal(str(min_fee_usd)) / Decimal(str(info.rate_usd))).quantize(step, rounding=ROUND_CEILING)
    if fee < min_fee:
        fee = min_fee
    if fee >= amount:
        raise ValueError("Сумма слишком мала для сделки")
    return fee, amount - fee, percent


def public_currencies() -> list[dict]:
    return [
        {
            "code": c.code,
            "name": c.name,
            "network": c.network,
            "kind": c.kind,
            "decimals": c.decimals,
            "min_amount": c.min_amount,
            "rate_usd": c.rate_usd,
        }
        for c in CURRENCIES.values()
    ]
