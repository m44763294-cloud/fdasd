import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "data" / "test_kustos.db"
os.environ["DB_PATH"] = str(TEST_DB)
os.environ["DEV_MODE"] = "1"
os.environ["BOT_TOKEN"] = ""
os.environ["BOT_USERNAME"] = "AtlantaTestBot"
os.environ["ADMIN_IDS"] = "999999"
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["PAYMENT_WEBHOOK_SECRET"] = "test-secret"

import pytest

for suffix in ("", "-wal", "-shm"):
    candidate = Path(str(TEST_DB) + suffix)
    if candidate.exists():
        candidate.unlink()
