"""Точка входа: `py run.py` (или `python run.py`)."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8080")),
        reload=os.getenv("RELOAD", "0") == "1",
        log_level="info",
    )
