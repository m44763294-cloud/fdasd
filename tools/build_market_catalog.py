"""Build the static ATLANTA market catalog from the @GiftChanges API.

thanks to @GiftChanges for this API (api.changes.tg)
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

API = "https://api.changes.tg"
OUT = Path(__file__).resolve().parents[1] / "web" / "market" / "catalog.json"
MAX_MODELS = 12


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def asset(path: str) -> str:
    return f"{API}/{path}"


async def load_gift(client: httpx.AsyncClient, sem: asyncio.Semaphore, name: str) -> dict:
    async with sem:
        response = await client.get(f"/gift/{quote(name, safe='')}")
        response.raise_for_status()
        data = response.json()

    gift = data.get("gift") or {}
    models = data.get("models") or []
    rarest = None
    for model in models:
        rarity = model.get("originalRarity")
        if rarity is None:
            rarity = model.get("rarity")
        if rarity is None:
            continue
        try:
            value = float(rarity)
        except (TypeError, ValueError):
            continue
        if rarest is None or value < rarest:
            rarest = value

    previews = []
    for model in models[:MAX_MODELS]:
        model_name = model.get("name")
        if not model_name:
            continue
        rarity = model.get("originalRarity")
        if rarity is None:
            rarity = model.get("rarity")
        previews.append(
            {
                "name": model.get("telegramName") or model_name,
                "rarity": rarity,
                "image": asset(
                    f"model/{quote(name, safe='')}/{quote(model_name, safe='')}.png?size=256"
                ),
            }
        )

    return {
        "name": name,
        "slug": slug(name),
        "id": str(gift.get("id") or ""),
        "image": asset(f"original/{quote(name, safe='')}.png?size=256"),
        "modelsCount": len(models),
        "backdropsCount": len(data.get("backdrops") or []),
        "symbolsCount": len(data.get("symbols") or []),
        "rarest": rarest,
        "models": previews,
    }


async def main() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=30.0, trust_env=True) as client:
        names_response = await client.get("/gifts")
        names_response.raise_for_status()
        names = names_response.json()

        sem = asyncio.Semaphore(8)
        gifts = await asyncio.gather(*(load_gift(client, sem, name) for name in names))

    gifts = [gift for gift in gifts if gift["modelsCount"] > 0]
    gifts.sort(key=lambda gift: gift["name"].lower())

    payload = {
        "source": API,
        "attribution": "thanks to @GiftChanges for this API (api.changes.tg)",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(gifts),
        "gifts": gifts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(gifts)} gifts)")


if __name__ == "__main__":
    asyncio.run(main())
