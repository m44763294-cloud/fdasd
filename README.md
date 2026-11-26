# ATLANTA — сделки под контролем

Сервис безопасных сделок в Telegram: бот, лендинг и мини-приложение в одном проекте.

**ATLANTA** держит деньги покупателя до подтверждения получения товара. Продавец видит, что оплата уже под защитой, покупатель — что деньги уйдут только после его подтверждения или решения арбитра.

```
Telegram-бот  ──►  @atlantaotcbot
Лендинг       ──►  /
Мини-приложение ─► /app/
API           ──►  /api/*
```

Интерфейс полностью двуязычный: русский и английский. Язык переключается в боте (`/language`), в профиле мини-приложения и в шапке лендинга; выбор запоминается.

---

## Что уже умеет

**Сделки**
- Создание сделки с названием, описанием, условиями, категорией, суммой и валютой. Сделку может создать и покупатель, и продавец.
- Код сделки вида `KST-AB12CD` и ссылка-приглашение для второй стороны.
- Роли: продавец, покупатель, арбитр, наблюдатель.
- Статусы: `waiting_buyer → waiting_payment → funded → delivered → completed`, а также `disputed`, `cancelled`, `refunded`.
- Полная история событий по каждой сделке (кто, что и когда сделал).
- Споры и арбитраж: арбитр видит условия, историю и комментарии, затем выплачивает продавцу или возвращает покупателю.

**Деньги**
- 14 валют: `USDT`, `BTC`, `ETH`, `TON`, `USDC` (крипта) и `RUB`, `UAH`, `KZT`, `BYN`, `TRY`, `AMD`, `GEL`, `USD`, `EUR` (фиат).
- Комиссия: 1,5 % с крипты, 2,5 % с фиата, минимум 0,30 USD. Удерживается из выплаты продавцу.
- Внутренний баланс, история операций и вывод средств.
- Оплата счёта провайдером или с внутреннего баланса (`Оплатить с баланса`).
- Реальный приём крипты через CryptoPay (включается токеном).

**Интерфейсы**
- Лендинг с живыми цифрами сервиса и честным описанием механики.
- Telegram Mini App: главная, сделки, создание, карточка сделки, профиль, арбитраж.
- Telegram-бот: меню, создание сделки через FSM, `/deals`, `/language`, `/disputes`, `/stats`, `/id`, `/anlantamoney` (для арбитров).
- Переключение RU/EN в боте, мини-приложении и на лендинге.

---

## Быстрый старт (Windows)

Нужен только Python 3.11+ (проверено на 3.12). Node.js и сборка фронтенда не требуются.

```powershell
cd kustos
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
copy .env.example .env
py run.py
```

Откройте:

| Адрес | Что это |
| --- | --- |
| http://127.0.0.1:8080/ | Лендинг |
| http://127.0.0.1:8080/app/ | Мини-приложение OTC |
| http://127.0.0.1:8080/market/ | ATLANTA Market |
| http://127.0.0.1:8080/api/docs | Swagger (только в `DEV_MODE=1`) |

Без `BOT_TOKEN` бот не запускается. В `DEV_MODE=1` сайт и мини-приложение доступны с авторизацией по заголовку `X-Dev-User` — это режим разработки, а не демо-оплата.

### Сценарий сделки

1. Создайте сделку в мини-приложении или боте — как продавец или как покупатель.
2. Отправьте ссылку-приглашение второй стороне.
3. Вторая сторона присоединяется; покупатель оплачивает счёт или нажимает «Оплатить с баланса».
4. Продавец отмечает передачу, покупатель подтверждает получение — деньги уходят продавцу.
5. Если что-то пошло не так, откройте спор; арбитр решает, кому выплатить средства.

Вывод средств: **Профиль → Вывести**.

### Баланс арбитра

Команда `/anlantamoney сумма валюта` пополняет баланс арбитра, например: `/anlantamoney 100 USDT`. Эти деньги можно потратить в сделках: в карточке сделки покупателя есть кнопка **«Оплатить с баланса»**. При возврате по спору средства возвращаются на тот же баланс.

---

## ATLANTA Market

Второй раздел бота — маркет подарков, аренды и анонимных номеров `+888`. Открывается кнопкой **«Маркет»** в меню и командой `/market`; страница живёт на `/market/` того же FastAPI-процесса. OTC-приложение не меняется.

- Каталог и цены — из `web/market/market-data.js` (4 792 лота) и `web/market/numbers.json`. Сумму заказа считает сервер, клиентские суммы игнорируются.
- Баланс маркета — отдельные таблицы `market_wallets` / `market_ledger` в GRAM. OTC-кошелёк (`wallets`) не затрагивается.
- Пополнение — реальный счёт Crypto Pay (`PAYMENT_PROVIDER=cryptopay`), минимум `MARKET_MIN_TOPUP` GRAM. Баланс зачисляется по вебхуку после проверки статуса счёта в API Crypto Pay.
- Покупка и аренда списывают GRAM сразу и создают заказ со статусом `paid` («ожидает выдачи»).
- Вывод — заявка `pending`: GRAM резервируются, выплата выполняется вручную.
- Выдача заказов и выплаты — вручную арбитром: `/marketorders`, `/marketdone <id>`, `/marketrefund <id>`, `/marketpayouts`, `/marketpaid <id>` (или кнопками под списком).

Демо-режима в маркете нет: без Telegram `initData` API отвечает `401`, без Crypto Pay пополнение отвечает `503`.

---

## Структура проекта

```
kustos/
├─ app/
│  ├─ main.py        сборка FastAPI, статика, запуск бота
│  ├─ api.py         REST API OTC и авторизация
│  ├─ auth.py        проверка Telegram initData
│  ├─ market.py      маркет: каталог, кошелёк GRAM, заказы, Crypto Pay
│  ├─ bot.py         aiogram-хендлеры
│  ├─ escrow.py      доменная логика сделок и арбитража
│  ├─ payments.py    MockProvider и CryptoPayProvider
│  ├─ models.py      валюты, комиссии, форматирование
│  ├─ i18n.py        словарь RU → EN для API, бота и уведомлений
│  ├─ security.py    проверка Telegram initData, коды сделок
│  ├─ db.py          SQLite-схема и доступ к данным
│  ├─ notify.py      уведомления в Telegram
│  └─ config.py      настройки из .env
├─ web/
│  ├─ index.html     лендинг
│  ├─ static/        стили и скрипты лендинга
│  ├─ app/           мини-приложение OTC (index.html, app.css, app.js)
│  ├─ market/        ATLANTA Market (index.html, market-data.js, orders.js, assets/lots)
│  └─ assets/        логотип, favicon, robots.txt
├─ tests/            pytest
├─ run.py            точка входа
└─ .env.example
```

---

## Настройки

Все переменные читаются из `.env` (или из окружения — приоритет у окружения).

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `BOT_TOKEN` | — | Токен бота от @BotFather. Без него бот выключен. |
| `BOT_USERNAME` | `atlantaotcbot` | Username бота без `@`. |
| `ADMIN_IDS` | — | Telegram ID арбитров через запятую. |
| `SUPPORT_USERNAME` | — | Username поддержки для ссылок в интерфейсе. |
| `PUBLIC_URL` | определяется автоматически | Публичный адрес сервиса. Если не задан — берётся из заголовков первого запроса (`X-Forwarded-Host` / `Host`). |
| `WEBAPP_URL` | `PUBLIC_URL/app/` | Адрес мини-приложения OTC. |
| `MARKET_URL` | `PUBLIC_URL/market/` | Адрес маркета (кнопка «Маркет»). |
| `HOST` / `PORT` | `127.0.0.1` / `8080` | Адрес и порт сервера. В Docker-образе порт `3000`. |
| `DEV_MODE` | `1` | Вход для разработки через `X-Dev-User`. В продакшене — `0`. |
| `DB_PATH` | `data/kustos.db` | Путь к SQLite-базе. |
| `FEE_CRYPTO` | `1.5` | Комиссия с крипты, %. |
| `FEE_FIAT` | `2.5` | Комиссия с фиата, %. |
| `MIN_FEE_USD` | `0.30` | Минимальная комиссия в долларах. |
| `PAYMENT_TTL_MINUTES` | `45` | Время жизни счёта. |
| `PAYMENT_PROVIDER` | `mock` | `mock` или `cryptopay`. |
| `CRYPTOPAY_TOKEN` | — | Токен CryptoPay API. |
| `PAYMENT_WEBHOOK_SECRET` | `dev-webhook-secret` | Секрет HMAC для вебхуков OTC. |
| `TOPUP_ASSET` | `TON` | Валюта счёта Crypto Pay для пополнения маркета. |
| `GRAM_PER_UNIT` | `1000` | Сколько GRAM зачисляется за 1 единицу `TOPUP_ASSET`. |
| `MARKET_MIN_TOPUP` | `10` | Минимальное пополнение маркета, GRAM. |
| `MARKET_MIN_WITHDRAW` | `10` | Минимальный вывод маркета, GRAM. |
| `GRAM_RECEIVE_ADDRESS` | — | Резервный адрес для ручного пополнения GRAM. |
| `GIFT_RECEIVE_USERNAME` | — | Служебный аккаунт для приёма подарков. |
| `RELOAD` | `0` | `1` — автоперезапуск uvicorn при разработке. |

> `DEV_MODE=1` в публичном доступе опасен: любой может представиться любым пользователем через `X-Dev-User`. На продакшене всегда `DEV_MODE=0`.

---

## API

Авторизация — заголовок `X-Telegram-Init-Data` (строка `initData` из Telegram WebApp). В `DEV_MODE=1` можно использовать `X-Dev-User: <telegram_id>`; имя передаётся percent-encoded в `X-Dev-Name`. Язык ответа задаётся заголовком `X-Lang: ru|en` (или параметром `?lang=en`); он же сохраняется в профиле пользователя.

| Метод | Путь | Описание |
| --- | --- | --- |
| `GET` | `/api/health` | Проверка живости. |
| `GET` | `/api/config` | Бренд, валюты, категории, комиссии, ссылки. |
| `GET` | `/api/stats` | Публичная статистика сервиса. |
| `GET` | `/api/me` | Профиль, баланс, статистика пользователя. |
| `GET` | `/api/deals` | Сделки пользователя. |
| `POST` | `/api/deals` | Создать сделку. |
| `GET` | `/api/deals/{code}` | Карточка сделки с действиями и историей. |
| `POST` | `/api/deals/{code}/join` | Покупатель занимает место. |
| `POST` | `/api/deals/{code}/pay` | Сформировать счёт. |
| `POST` | `/api/deals/{code}/simulate-payment` | Демо-зачисление (только mock). |
| `POST` | `/api/deals/{code}/deliver` | Продавец отметил передачу. |
| `POST` | `/api/deals/{code}/confirm` | Покупатель подтвердил получение. |
| `POST` | `/api/deals/{code}/cancel` | Отмена до оплаты. |
| `POST` | `/api/deals/{code}/dispute` | Открыть спор. |
| `POST` | `/api/deals/{code}/resolve` | Решение арбитра: `release` или `refund`. |
| `POST` | `/api/wallet/withdraw` | Заявка на вывод. |
| `GET` | `/api/admin/disputes` | Открытые споры (арбитр). |
| `GET` | `/api/admin/deals` | Последние сделки (арбитр). |
| `GET` | `/api/market/config` | Параметры пополнения и лимиты маркета. |
| `GET` | `/api/market/me` | Профиль, баланс GRAM, история операций и заказы. |
| `GET` | `/api/market/orders` | Заказы пользователя. |
| `POST` | `/api/market/orders` | Создать заказ: `gift` / `number`, `buy` / `rent`. |
| `POST` | `/api/market/topup` | Создать счёт Crypto Pay на пополнение GRAM. |
| `GET` | `/api/market/topup/{id}` | Статус счёта пополнения. |
| `POST` | `/api/market/withdraw` | Заявка на вывод GRAM. |
| `GET` | `/api/market/admin/orders` | Заказы к выдаче (арбитр). |
| `POST` | `/api/market/admin/orders/{id}/fulfill` | Отметить заказ выданным. |
| `POST` | `/api/market/admin/orders/{id}/refund` | Вернуть GRAM за заказ. |
| `GET` | `/api/market/admin/payouts` | Заявки на вывод (арбитр). |
| `POST` | `/api/market/admin/payouts/{id}` | `paid` или `rejected`. |
| `POST` | `/api/market/crypto/webhook` | Вебхук Crypto Pay для пополнения маркета. |
| `POST` | `/api/payments/webhook` | Вебхук платёжного провайдера OTC. |

Пример создания сделки в демо-режиме:

```powershell
curl -X POST http://127.0.0.1:8080/api/deals `
  -H "X-Dev-User: 1001" `
  -H "Content-Type: application/json" `
  -d '{\"title\":\"Аккаунт Steam\",\"amount\":\"120\",\"currency\":\"USDT\",\"category\":\"accounts\"}'
```

### Вебхук оплаты

Подпись: `X-Webhook-Signature` = hex(HMAC-SHA256(raw_body, PAYMENT_WEBHOOK_SECRET)).

```json
{"event":"payment.confirmed","deal_code":"KST-AB12CD","ref":"bank-1","amount":"120","currency":"USDT"}
```

---

## Деплой: один сервер на бота и мини-приложение

Бот, лендинг, `/app/`, `/market/` и `/api/` — один процесс FastAPI. Отдельно мини-приложение хостить не нужно.

1. Залийте на GitHub **только код**: `app/`, `web/`, `run.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `README.md`, `.env.example`, `deploy.env.example`, `preview_welcome.png`.
   `.env`, `data/`, `__pycache__/`, `*.db`, `*.log` в Git **не добавлять** — они уже в `.gitignore`.
2. На VPS установите Docker + Docker Compose, сделайте `git clone <ваш-репозиторий>`.
3. `cp deploy.env.example .env`, заполните `DOMAIN`, `EMAIL`, `BOT_TOKEN`, `ADMIN_IDS`, `PUBLIC_URL`, `WEBAPP_URL`, `MARKET_URL`. Все URL — только `https://`.
4. Пропишите A-запись домена на IP сервера и откройте порты `80` и `443`.
5. `docker compose up -d --build`. Caddy сам получит HTTPS-сертификат.
6. Проверьте `https://example.com/health`, затем `/start` у бота. Menu Button поставится автоматически.

База `data/kustos.db` создаётся на сервере при первом запуске и хранится в volume. Рабочая база в Git не попадает. Для переноса балансов и арбитров снимок лежит в `deploy/kustos.db` — скопируйте его на сервер как `data/kustos.db`. **Репозиторий должен быть приватным.** На чистой базе главный арбитр назначается командой `/anlantachief` от ID из `ADMIN_IDS`.

Альтернатива без VPS: Railway/Render/Fly.io с `Dockerfile`, `HOST=0.0.0.0`, `PORT` из окружения и постоянным диском под `data/`. Без постоянного диска балансы и сделки потеряются при перезапуске.

### Bothost: бот, OTC и маркет в одном контейнере

Bothost подходит: один Docker-контейнер отдаёт FastAPI (`/`, `/app/`, `/market/`, `/api/*`) и держит long-polling бота.

1. Загрузите репозиторий в Git и создайте бота на Bothost по `Dockerfile` (либо укажите `run.py` как главный файл для шаблона Python).
2. Включите домен и HTTPS. Приложение слушает `0.0.0.0` из `HOST`, порт контейнера — `3000` (задан в `Dockerfile` через `PORT`). В панели Bothost укажите тот же порт `3000`; если платформа передаёт свой `PORT`, он имеет приоритет.
3. Переменные окружения: `BOT_TOKEN`, `BOT_USERNAME`, `ADMIN_IDS`, `HOST=0.0.0.0`, `DEV_MODE=0`, `PAYMENT_PROVIDER=cryptopay`, `CRYPTOPAY_TOKEN`, `TOPUP_ASSET`, `GRAM_PER_UNIT`.
   `PUBLIC_URL`, `WEBAPP_URL` и `MARKET_URL` можно не задавать: если домен выдаёт платформа, приложение само возьмёт его из заголовков первого запроса (`X-Forwarded-Host` / `Host`) и подставит в кнопки бота и Mini App. Указывайте их вручную только когда домен известен заранее.
4. Храните базу в `/app/data`: платформа сохраняет каталог `data` между пересборками (`DATA_DIR=/app/data`). `DB_PATH` по умолчанию уже указывает туда. Не переносите базу в корень проекта — при деплое из Git она потеряется.
5. Вебхуки Crypto Pay: `/api/payments/webhook` (OTC) и `/api/market/crypto/webhook` (маркет) на публичном домене.
6. Каталог маркета (35 МБ картинок) входит в образ, отдельное хранилище для него не нужно.

### Раздельный деплой: Workers + отдельный хост для бота

Можно держать статику на Cloudflare Workers, а FastAPI с ботом — на другом хосте:

1. В Cloudflare Dashboard откройте Worker `hdfhdfb` → Settings → Variables and Secrets → добавьте переменную `BOT_ORIGIN` = `https://<хост-бота>` (без завершающего `/`).
2. Подключите GitHub-репозиторий через Workers Builds. Root directory: `kustos`, deploy command: `npx wrangler deploy`. Workers раздаёт `web/` и проксирует `/api/*` и `/health` на бот-хост. Адрес будет `https://hdfhdfb.m44763294.workers.dev`.
3. На бот-хосте в `.env` укажите публичные адреса Worker:
   ```env
   PUBLIC_URL=https://hdfhdfb.m44763294.workers.dev
   WEBAPP_URL=https://hdfhdfb.m44763294.workers.dev/app/
   MARKET_URL=https://hdfhdfb.m44763294.workers.dev/market/
   HOST=0.0.0.0
   DEV_MODE=0
   ```
   `BOT_TOKEN`, `ADMIN_IDS`, база и платежи остаются на бот-хосте.
4. Menu Button бот поставит сам на `WEBAPP_URL`. Mini App и маркет будут открываться с домена Workers, а все `/api/*`-запросы незаметно уходить на бот-хост.

Важно: на бот-хосте тоже нужен HTTPS, иначе Workers не сможет проксировать запросы. CORS в FastAPI уже разрешён для всех origin.

---

## Подключение к Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather), получите токен.
2. Пропишите `BOT_TOKEN`, `BOT_USERNAME`, `PUBLIC_URL` и `ADMIN_IDS` в `.env`.
3. Поставьте сервис за HTTPS (Telegram требует HTTPS для WebApp-кнопок).
4. Запустите `py run.py`. Бот поднимется в фоне вместе с API и сам поставит Menu Button → Web App на `WEBAPP_URL`. В BotFather это делать не обязательно.
5. Свой Telegram ID можно узнать командой `/id` в боте и добавить в `ADMIN_IDS`.

---

## Быстрый HTTPS для телефона (временно)

Если своего домена нет, поднимите туннель к локальному серверу:

```powershell
& "C:\Program Files\Git\usr\bin\ssh.exe" -p 443 -R0:127.0.0.1:8080 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -tt free.pinggy.io
```

В выводе появятся два адреса. Возьмите `https://...free.pinggy.net`, пропишите его в `PUBLIC_URL`, а `https://...free.pinggy.net/app/` — в `WEBAPP_URL`, затем перезапустите `py run.py`. Бесплатный Pinggy при первом заходе из браузера показывает страницу «Enter site» — нажмите её один раз. Такой адрес живёт около часа и меняется при перезапуске туннеля.

---

## CryptoPay

1. Получите токен в [@CryptoBot](https://t.me/CryptoBot) → Crypto Pay → Create App.
2. Укажите в `.env`:

```env
PAYMENT_PROVIDER=cryptopay
CRYPTOPAY_TOKEN=ваш_токен
PAYMENT_WEBHOOK_SECRET=длинный_случайный_секрет
DEV_MODE=0
```

3. В настройках приложения CryptoPay укажите URL вебхука: `https://ваш-домен/api/payments/webhook`.
4. Для пополнения маркета добавьте второй вебхук: `https://ваш-домен/api/market/crypto/webhook` (тот же токен). Подпись проверяется по `crypto-pay-api-signature`.
5. Проверьте, что суммы и валюты счетов совпадают с настройками сервиса. Курс маркета: 1 `TOPUP_ASSET` = `GRAM_PER_UNIT` GRAM.

Фиат (RUB/USD/EUR) в текущей версии всегда проходит через ручной/демо-сценарий: для реального приёма нужен эквайринг (ЮKassa, Stripe и т. п.) и отдельная интеграция.

---

## Тесты

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

Покрыто: полный счастливый путь, спор и арбитраж, возврат, валидация, HMAC вебхука, вывод средств, подпись `initData`, нормализация кодов, первый вход пользователя и веб-маршруты.

Тестовая база — `data/test_kustos.db`. Чтобы пересоздать, удалите файл.

---

## Чек-лист перед продакшеном

- [ ] `DEV_MODE=0`.
- [ ] Сильный `PAYMENT_WEBHOOK_SECRET`, HTTPS и корректный `PUBLIC_URL`.
- [ ] `ADMIN_IDS` заполнен реальными арбитрами.
- [ ] Бэкап `data/kustos.db` по расписанию (SQLite WAL).
- [ ] Ограничение доступа к `/api/docs` (в продакшене он выключен автоматически).
- [ ] Юридические документы: оферта, правила сервиса, политика конфиденциальности, KYC/AML при необходимости.
- [ ] Логи и мониторинг, алерты на ошибки платежей.
- [ ] Проверка сценариев спора и возврата на реальных тестовых платежах.
- [ ] Пополнение маркета проверено на реальном счёте Crypto Pay, вебхук `/api/market/crypto/webhook` доступен.
- [ ] Настроен ручной процесс выдачи подарков и номеров, а также выплат по заявкам `/marketpayouts`.

---

## Важно

Это демонстрационная реализация сервиса безопасных сделок, а не готовый финансовый продукт. Демо-платежи не двигают реальные деньги, баланс хранится в локальной базе, а вывод средств в демо-режиме лишь фиксирует заявку.

Маркет принимает реальные платежи через Crypto Pay, но выдача подарков, номеров Fragment и выплаты GRAM выполняются вручную арбитром. Автоматической интеграции с Fragment и передачей подарков в текущей версии нет.

Реальные расчёты через третью сторону регулируются законодательством о платёжных услугах и требуют юридической проработки, лицензий (в зависимости от юрисдикции) и партнёрства с провайдером. Перед запуском проконсультируйтесь с юристом.

---

© ATLANTA · Сделки под контролем
