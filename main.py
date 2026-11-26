"""Точка входа для автодетекта главного файла на хостинге (Bothost и др.).

Полный аналог `run.py`: поднимает FastAPI, статику и бота в одном процессе.
`python main.py` и `python run.py` работают одинаково.
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    print(f"ATLANTA: starting on {host}:{port}", flush=True)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "0") == "1",
        log_level="info",
    )
