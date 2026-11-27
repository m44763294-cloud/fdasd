"""Сборка FastAPI-приложения, статика и запуск Telegram-бота."""

from __future__ import annotations

# Если файл запустили напрямую (python app/main.py), поднимаем сервер как модуль,
# иначе относительные импорты ниже не сработают.
if __package__ in (None, ""):
    import os as _os
    import pathlib as _pathlib
    import sys as _sys

    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))
    import uvicorn as _uvicorn

    _uvicorn.run(
        "app.main:app",
        host=_os.getenv("HOST", "0.0.0.0"),
        port=int(_os.getenv("PORT", "3000")),
        log_level="info",
    )
    raise SystemExit(0)

import asyncio
import contextlib
import logging
import mimetypes
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import settings
from .db import db
from .escrow import EscrowError
from .i18n import tr
from .market import router as market_router
from .payments import init_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("kustos")

WEB_DIR = settings.web_dir

_PRIVATE_HOST = re.compile(r"^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)")

# Windows и slim-образы без /etc/mime.types не знают WebP: без этого браузер
# откажется показывать картинки каталога из-за X-Content-Type-Options: nosniff.
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/javascript", ".js")


async def _run_bot_background() -> None:
    from .bot import run_bot

    try:
        await run_bot()
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Telegram-бот остановлен из-за ошибки")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    init_provider()
    task: asyncio.Task | None = None
    if settings.bot_token:
        task = asyncio.create_task(_run_bot_background(), name="kustos-bot")
        log.info("Telegram-бот запускается в фоне")
    else:
        log.warning("BOT_TOKEN не задан — бот выключен")
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await db.close()


app = FastAPI(
    title="Gumroad API",
    version="1.0.0",
    description="Сервис безопасных сделок в Telegram",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.dev_mode else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _public_url_from_request(request: Request) -> str:
    """Публичный адрес, который видит прокси хостинга (Bothost, Railway, Caddy)."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    host = host.split(",")[0].strip().lower()
    if not host:
        return ""
    name = host.rsplit(":", 1)[0].strip("[]")
    if "." not in name or _PRIVATE_HOST.match(name):
        return ""
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if proto and proto != "https":
        return ""
    return f"https://{host}"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if not settings.public_url_explicit:
        detected = _public_url_from_request(request)
        if detected and settings.set_public_url(detected):
            log.info("Публичный адрес определён по запросу: %s", detected)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    path = request.url.path
    if path.startswith(("/app", "/market", "/static", "/assets")) or path in {"/", "/health"}:
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.exception_handler(EscrowError)
async def escrow_error_handler(request: Request, exc: EscrowError):
    lang = (request.headers.get("X-Lang") or request.query_params.get("lang") or "ru").lower()
    message = tr(exc.message, "en" if lang.startswith("en") else "ru")
    return JSONResponse(status_code=exc.status, content={"error": exc.code, "message": message})


app.include_router(router)
app.include_router(market_router)

app.mount("/app", StaticFiles(directory=str(WEB_DIR / "app"), html=True), name="miniapp")
app.mount("/market", StaticFiles(directory=str(WEB_DIR / "market"), html=True), name="market")
app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/", include_in_schema=False)
async def landing():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/assets/favicon.svg", status_code=307)


@app.get("/health", include_in_schema=False)
async def health():
    return {"ok": True}


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    path = WEB_DIR / "robots.txt"
    if path.exists():
        return FileResponse(path, media_type="text/plain")
    return JSONResponse({"error": "not found"}, status_code=404)
