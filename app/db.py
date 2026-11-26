"""Тонкая асинхронная обёртка над SQLite (aiosqlite)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import aiosqlite

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    username        TEXT,
    first_name      TEXT NOT NULL DEFAULT '',
    last_name       TEXT,
    photo_url       TEXT,
    language        TEXT NOT NULL DEFAULT 'ru',
    is_admin        INTEGER NOT NULL DEFAULT 0,
    is_chief        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deals (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    terms               TEXT NOT NULL DEFAULT '',
    category            TEXT NOT NULL DEFAULT 'other',
    amount              TEXT NOT NULL,
    currency            TEXT NOT NULL,
    fee_percent         REAL NOT NULL,
    fee_amount          TEXT NOT NULL,
    net_amount          TEXT NOT NULL,
    status              TEXT NOT NULL,
    seller_id           INTEGER NOT NULL,
    buyer_id            INTEGER,
    creator_role        TEXT NOT NULL DEFAULT 'seller',
    arbiter_id          INTEGER,
    invite_token        TEXT NOT NULL UNIQUE,
    payment_provider    TEXT,
    payment_ref         TEXT,
    deposit_address     TEXT,
    deposit_memo        TEXT,
    deposit_uri         TEXT,
    pay_url             TEXT,
    invoice_expires_at  TEXT,
    paid_at             TEXT,
    delivered_at        TEXT,
    completed_at        TEXT,
    deadline_at         TEXT,
    dispute_reason      TEXT,
    resolution          TEXT,
    version             INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deals_seller ON deals(seller_id);
CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id);
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id     TEXT NOT NULL,
    actor_id    INTEGER,
    kind        TEXT NOT NULL,
    text        TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_deal ON events(deal_id);

CREATE TABLE IF NOT EXISTS wallets (
    user_id     INTEGER NOT NULL,
    currency    TEXT NOT NULL,
    available   TEXT NOT NULL DEFAULT '0',
    pending     TEXT NOT NULL DEFAULT '0',
    PRIMARY KEY (user_id, currency)
);

CREATE TABLE IF NOT EXISTS ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    deal_id     TEXT,
    currency    TEXT NOT NULL,
    amount      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payouts (
    id           TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    currency     TEXT NOT NULL,
    amount       TEXT NOT NULL,
    address      TEXT NOT NULL,
    status       TEXT NOT NULL,
    provider_ref TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_wallets (
    user_id     INTEGER PRIMARY KEY,
    available   TEXT NOT NULL DEFAULT '0',
    pending     TEXT NOT NULL DEFAULT '0'
);

CREATE TABLE IF NOT EXISTS market_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    ref         TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_ledger_user ON market_ledger(user_id);

CREATE TABLE IF NOT EXISTS market_orders (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    type        TEXT NOT NULL,
    mode        TEXT NOT NULL,
    title       TEXT NOT NULL,
    subtitle    TEXT NOT NULL DEFAULT '',
    amount      TEXT NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'GRAM',
    months      INTEGER NOT NULL DEFAULT 1,
    gift_id     TEXT,
    number      TEXT,
    anonymous   INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_orders_user ON market_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_market_orders_status ON market_orders(status);

CREATE TABLE IF NOT EXISTS market_invoices (
    id           TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    gram         TEXT NOT NULL,
    asset        TEXT NOT NULL,
    units        TEXT NOT NULL,
    status       TEXT NOT NULL,
    pay_url      TEXT,
    mini_app_url TEXT,
    created_at   TEXT NOT NULL,
    paid_at      TEXT
);

CREATE TABLE IF NOT EXISTS market_payouts (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    amount      TEXT NOT NULL,
    address     TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    paid_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_market_payouts_status ON market_payouts(status);

CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path, isolation_level=None)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA synchronous=NORMAL")
        await self.conn.execute("PRAGMA busy_timeout=5000")
        await self.conn.executescript(SCHEMA)
        await self._migrate()
        await self.conn.commit()

    async def _migrate(self) -> None:
        """Догоняющие миграции для баз, созданных до появления колонок."""
        async with self._require().execute("PRAGMA table_info(users)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        if "language" not in columns:
            await self._require().execute(
                "ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'ru'"
            )
        if "is_chief" not in columns:
            await self._require().execute(
                "ALTER TABLE users ADD COLUMN is_chief INTEGER NOT NULL DEFAULT 0"
            )

        async with self._require().execute("PRAGMA table_info(deals)") as cur:
            deal_columns = {row[1] for row in await cur.fetchall()}
        if "creator_role" not in deal_columns:
            await self._require().execute(
                "ALTER TABLE deals ADD COLUMN creator_role TEXT NOT NULL DEFAULT 'seller'"
            )

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    def _require(self) -> aiosqlite.Connection:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        return self.conn

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        async with self._require().execute(sql, tuple(params)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        async with self._require().execute(sql, tuple(params)) as cur:
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    async def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = await self.fetchone(sql, params)
        return next(iter(row.values())) if row else None

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = await self._require().execute(sql, tuple(params))
        await self._require().commit()
        return cur.lastrowid or 0

    async def executemany(self, sql: str, rows: Iterable[Iterable[Any]]) -> None:
        await self._require().executemany(sql, [tuple(r) for r in rows])
        await self._require().commit()

    @asynccontextmanager
    async def tx(self) -> AsyncIterator[aiosqlite.Connection]:
        """Транзакция с блокировкой. Все записи внутри — через переданное соединение."""
        conn = self._require()
        async with self._lock:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                await conn.rollback()
                raise
            else:
                await conn.commit()


db = Database(settings.db_path)
