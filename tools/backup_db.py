"""Сделать консистентную копию базы прямо на работающем сервере.

Использование:
    py tools/backup_db.py

Результат: data/kustos.snapshot.db — готовый файл для переноса на хост.
Его нужно скопировать как data/kustos.db в целевом окружении.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "kustos.db"
TARGET = ROOT / "data" / "kustos.snapshot.db"


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"База не найдена: {SOURCE}")

    TARGET.unlink(missing_ok=True)
    with sqlite3.connect(SOURCE) as source:
        with sqlite3.connect(TARGET) as target:
            source.backup(target)

    print(f"Готово: {TARGET} ({TARGET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
