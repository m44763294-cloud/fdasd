import hashlib
import hmac
import json
import time
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import normalize_code, verify_init_data

SELLER = {"X-Dev-User": "1001", "X-Dev-Name": "Seller"}
BUYER = {"X-Dev-User": "1002", "X-Dev-Name": "Buyer"}
ADMIN = {"X-Dev-User": "999999", "X-Dev-Name": "Arbiter"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_deal(client, headers, amount="1000", currency="USDT", title="Steam аккаунт с играми", creator_role=None):
    payload = {
        "title": title,
        "description": "Передача аккаунта и почты",
        "terms": "После оплаты передаю логин, пароль и почту.",
        "category": "accounts",
        "amount": amount,
        "currency": currency,
    }
    if creator_role:
        payload["creator_role"] = creator_role
    response = client.post("/api/deals", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def fund_via_webhook(client, code, amount, currency="USDT"):
    body = json.dumps(
        {
            "event": "payment.confirmed",
            "deal_code": code,
            "ref": f"webhook-{code}",
            "amount": str(amount),
            "currency": currency,
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    response = client.post(
        "/api/payments/webhook",
        content=body,
        headers={"X-Webhook-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def complete_deal(client, headers, buyer=BUYER, amount="1000", title="Сделка для вывода"):
    deal = create_deal(client, headers, amount=amount, title=title)
    code = deal["code"]
    joined = client.post(f"/api/deals/{code}/join", headers=buyer)
    assert joined.status_code == 200, joined.text
    fund_via_webhook(client, code, amount)
    delivered = client.post(f"/api/deals/{code}/deliver", headers=headers, json={"note": "Отправлено"})
    assert delivered.status_code == 200, delivered.text
    completed = client.post(f"/api/deals/{code}/confirm", headers=buyer)
    assert completed.status_code == 200, completed.text
    return completed.json()


def test_public_endpoints(client):
    assert client.get("/api/health").json()["ok"] is True
    config = client.get("/api/config").json()
    assert config["brand"] == "ATLANTA"
    codes = {item["code"] for item in config["currencies"]}
    assert {"USDT", "BTC", "ETH", "TON", "USDC", "RUB", "UAH", "KZT", "USD", "EUR"} <= codes
    stats = client.get("/api/stats").json()
    assert "volume_usd" in stats


def test_full_happy_flow(client):
    deal = create_deal(client, SELLER)
    code = deal["code"]
    assert deal["status"] == "waiting_buyer"
    assert deal["fee_amount"] == "15.00"
    assert deal["net_amount"] == "985.00"
    assert deal["invite_link"].endswith(code)

    joined = client.post(f"/api/deals/{code}/join", headers=BUYER)
    assert joined.status_code == 200, joined.text
    assert joined.json()["status"] == "waiting_payment"
    assert joined.json()["role"] == "buyer"

    payment = client.post(f"/api/deals/{code}/pay", headers=BUYER).json()["payment"]
    assert payment["address"]

    funded = fund_via_webhook(client, code, "1000")
    assert funded["status"] == "funded"

    # продавец не может подтвердить за покупателя
    forbidden = client.post(f"/api/deals/{code}/confirm", headers=SELLER)
    assert forbidden.status_code == 403

    delivered = client.post(f"/api/deals/{code}/deliver", headers=SELLER, json={"note": "Логин отправлен"})
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "delivered"

    completed = client.post(f"/api/deals/{code}/confirm", headers=BUYER)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    profile = client.get("/api/me", headers=SELLER).json()
    balance = next(item for item in profile["balances"]["items"] if item["currency"] == "USDT")
    assert Decimal(balance["available"]) == Decimal("985")

    again = client.post(f"/api/deals/{code}/confirm", headers=BUYER)
    assert again.status_code == 409


def test_buyer_created_deal_flow(client):
    deal = create_deal(
        client,
        BUYER,
        amount="200",
        title="iPhone 15 Pro 256 ГБ",
        creator_role="buyer",
    )
    code = deal["code"]
    assert deal["role"] == "buyer"
    assert deal["invite_role"] == "seller"
    assert deal["invite_link"].endswith(code)

    joined = client.post(f"/api/deals/{code}/join", headers=SELLER)
    assert joined.status_code == 200, joined.text
    assert joined.json()["role"] == "seller"
    assert joined.json()["status"] == "waiting_payment"

    funded = fund_via_webhook(client, code, "200")
    assert funded["status"] == "funded"

    delivered = client.post(f"/api/deals/{code}/deliver", headers=SELLER, json={"note": "Передан"})
    assert delivered.status_code == 200, delivered.text

    completed = client.post(f"/api/deals/{code}/confirm", headers=BUYER)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"


def test_dispute_and_arbitration(client):
    deal = create_deal(client, SELLER, amount="500", title="Редкий скин CS2")
    code = deal["code"]
    client.post(f"/api/deals/{code}/join", headers=BUYER)
    client.post(f"/api/deals/{code}/pay", headers=BUYER)
    fund_via_webhook(client, code, "500")

    dispute = client.post(
        f"/api/deals/{code}/dispute",
        headers=BUYER,
        json={"reason": "Скин не пришёл, продавец не отвечает"},
    )
    assert dispute.status_code == 200, dispute.text
    assert dispute.json()["status"] == "disputed"

    disputes = client.get("/api/admin/disputes", headers=ADMIN)
    assert disputes.status_code == 200
    assert any(item["code"] == code for item in disputes.json()["items"])

    not_admin = client.get("/api/admin/disputes", headers=SELLER)
    assert not_admin.status_code == 403

    resolved = client.post(
        f"/api/deals/{code}/resolve",
        headers=ADMIN,
        json={"outcome": "release", "note": "Продавец предоставил доказательства передачи"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "completed"
    assert resolved.json()["resolution"].startswith("Выплата продавцу")


def test_refund_flow(client):
    deal = create_deal(client, SELLER, amount="100", currency="TON", title="Подписка на сервис")
    code = deal["code"]
    client.post(f"/api/deals/{code}/join", headers=BUYER)
    client.post(f"/api/deals/{code}/pay", headers=BUYER)
    fund_via_webhook(client, code, "100", "TON")
    client.post(f"/api/deals/{code}/dispute", headers=BUYER, json={"reason": "Продавец не вышел на связь"})
    resolved = client.post(f"/api/deals/{code}/resolve", headers=ADMIN, json={"outcome": "refund"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "refunded"


def test_validation(client):
    bad = client.post(
        "/api/deals",
        headers=SELLER,
        json={"title": "ok", "amount": "10", "currency": "USDT"},
    )
    assert bad.status_code == 400
    bad_currency = client.post(
        "/api/deals",
        headers=SELLER,
        json={"title": "Нормальное название", "amount": "10", "currency": "DOGE"},
    )
    assert bad_currency.status_code == 400
    tiny = client.post(
        "/api/deals",
        headers=SELLER,
        json={"title": "Нормальное название", "amount": "0.00000001", "currency": "BTC"},
    )
    assert tiny.status_code == 400


def test_webhook_hmac(client):
    deal = create_deal(client, SELLER, amount="250", title="Ключ доступа к нейросети")
    code = deal["code"]
    client.post(f"/api/deals/{code}/join", headers=BUYER)
    client.post(f"/api/deals/{code}/pay", headers=BUYER)

    body = json.dumps(
        {"event": "payment.confirmed", "deal_code": code, "ref": "bank-1", "amount": "250", "currency": "USDT"},
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

    bad = client.post("/api/payments/webhook", content=body, headers={"X-Webhook-Signature": "nope"})
    assert bad.status_code == 400

    good = client.post(
        "/api/payments/webhook",
        content=body,
        headers={"X-Webhook-Signature": signature, "Content-Type": "application/json"},
    )
    assert good.status_code == 200, good.text
    assert good.json()["status"] == "funded"


def test_withdraw(client):
    new_user = {"X-Dev-User": "1003", "X-Dev-Name": "New"}
    locked = client.post(
        "/api/wallet/withdraw",
        headers=new_user,
        json={"currency": "USDT", "amount": "10", "address": "TXyz1234567890abcdef"},
    )
    assert locked.status_code == 403
    assert locked.json()["error"] == "withdraw_locked"

    access = client.get("/api/wallet/withdraw-access", headers=new_user).json()
    assert access["allowed"] is False
    assert access["required"] == 3

    for index in range(3):
        complete_deal(client, SELLER, title=f"Сделка для вывода {index}")

    unlocked = client.get("/api/wallet/withdraw-access", headers=SELLER).json()
    assert unlocked["allowed"] is True
    assert unlocked["completed"] >= 3

    response = client.post(
        "/api/wallet/withdraw",
        headers=SELLER,
        json={"currency": "USDT", "amount": "100", "address": "TXyz1234567890abcdef"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "sent"

    too_much = client.post(
        "/api/wallet/withdraw",
        headers=SELLER,
        json={"currency": "USDT", "amount": "999999", "address": "TXyz1234567890abcdef"},
    )
    assert too_much.status_code == 409


def test_admin_balance_can_pay_for_deal_and_get_refund(client):
    denied = client.post(
        "/api/admin/credit",
        headers=SELLER,
        json={"currency": "USDT", "amount": "500"},
    )
    assert denied.status_code == 403

    credit = client.post(
        "/api/admin/credit",
        headers=ADMIN,
        json={"currency": "USDT", "amount": "500"},
    )
    assert credit.status_code == 200, credit.text
    assert Decimal(credit.json()["available"]) == Decimal("500")

    before = client.get("/api/me", headers=ADMIN).json()["balances"]["items"]
    before_usdt = next(item for item in before if item["currency"] == "USDT")

    deal = create_deal(client, ADMIN, amount="200", title="Покупка для арбитра", creator_role="buyer")
    code = deal["code"]
    joined = client.post(f"/api/deals/{code}/join", headers=SELLER)
    assert joined.status_code == 200, joined.text

    paid = client.post(f"/api/deals/{code}/pay-balance", headers=ADMIN)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "funded"

    after_pay = client.get("/api/me", headers=ADMIN).json()["balances"]["items"]
    after_usdt = next(item for item in after_pay if item["currency"] == "USDT")
    assert Decimal(after_usdt["available"]) == Decimal(before_usdt["available"]) - Decimal("200")

    dispute = client.post(
        f"/api/deals/{code}/dispute",
        headers=ADMIN,
        json={"reason": "Товар не подошёл, возвращаю средств"},
    )
    assert dispute.status_code == 200, dispute.text

    resolved = client.post(
        f"/api/deals/{code}/resolve",
        headers=ADMIN,
        json={"outcome": "refund"},
    )
    assert resolved.status_code == 200, resolved.text

    after_refund = client.get("/api/me", headers=ADMIN).json()["balances"]["items"]
    refunded_usdt = next(item for item in after_refund if item["currency"] == "USDT")
    assert Decimal(refunded_usdt["available"]) == Decimal(before_usdt["available"])


def test_init_data_signature():
    token = "123456:TEST_TOKEN"
    user = {"id": 42, "first_name": "Тест", "username": "tester"}
    data = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    init_data = urlencode({**data, "hash": digest})

    parsed = verify_init_data(init_data, token)
    assert parsed is not None
    assert parsed["user"]["id"] == 42

    tampered = init_data.replace("tester", "hacker")
    assert verify_init_data(tampered, token) is None
    assert verify_init_data(init_data, "wrong:token") is None


def test_normalize_code():
    assert normalize_code("kst-ab12cd") == "KST-AB12CD"
    assert normalize_code("https://t.me/KustosBot?start=deal_KST-AB12CD") == "KST-AB12CD"
    assert normalize_code("DEAL_KST-AB12CD") == "KST-AB12CD"


def test_first_contact_creates_user_once(client):
    # Имя приходит percent-encoded: HTTP-заголовки не поддерживают кириллицу.
    headers = {"X-Dev-User": "4242", "X-Dev-Name": "%D0%90%D0%BB%D0%B5%D0%BA%D1%81%D0%B5%D0%B9"}
    me = client.get("/api/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["user"]["name"] == "Алексей"

    # Повторный первый контакт не должен ломаться на UNIQUE constraint.
    deals = client.get("/api/deals", headers=headers)
    assert deals.status_code == 200, deals.text
    assert deals.json()["items"] == []

    again = client.get("/api/me", headers=headers)
    assert again.status_code == 200
    assert again.json()["user"]["name"] == "Алексей"


def test_web_routes(client):
    landing = client.get("/")
    assert landing.status_code == 200
    assert "ATLANTA" in landing.text

    mini_app = client.get("/app/")
    assert mini_app.status_code == 200
    assert "app.js" in mini_app.text

    market = client.get("/market/")
    assert market.status_code == 200
    assert "market-data.js" in market.text
    assert "orders.js" in market.text

    assert client.get("/market/market-data.js").status_code == 200
    assert client.get("/market/numbers.json").status_code == 200


def test_chief_can_manage_arbiters_and_grant_balance(tmp_path, monkeypatch):
    import asyncio

    from app import escrow
    from app.config import settings
    from app.db import Database

    store = Database(tmp_path / "roles.db")
    monkeypatch.setattr(escrow, "db", store)
    monkeypatch.setattr(settings, "admin_ids", (777,))

    async def scenario():
        await store.connect()
        try:
            chief = await escrow.claim_chief(777)
            assert chief["is_chief"] == 1
            assert chief["is_admin"] == 1

            arbiter = await escrow.set_arbiter(chief, 778, True)
            assert arbiter["is_admin"] == 1

            with pytest.raises(escrow.EscrowError):
                await escrow.set_arbiter(arbiter, 779, True)
            with pytest.raises(escrow.EscrowError):
                await escrow.claim_chief(778)

            granted = await escrow.give_balance(arbiter, 779, "250", "USDT")
            assert granted["user_id"] == 779
            assert Decimal(granted["available"]) == Decimal("250")

            self_credit = await escrow.admin_credit(chief, "75", "USDT")
            assert self_credit["user_id"] == 777
            assert Decimal(self_credit["available"]) == Decimal("75")

            await escrow.set_arbiter(chief, 778, False)
            assert (await escrow.get_user(778))["is_admin"] == 0
            with pytest.raises(escrow.EscrowError):
                await escrow.give_balance(await escrow.get_user(778), 779, "10", "USDT")

            assert 777 in await escrow.privileged_ids()
        finally:
            await store.close()

    asyncio.run(scenario())

