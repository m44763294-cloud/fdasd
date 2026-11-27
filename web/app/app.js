/* ==========================================================================
   Gumroad — Telegram Mini App
   ========================================================================== */
(() => {
  "use strict";

  const tg = window.Telegram?.WebApp;

  // Telegram рисует кнопку закрытия поверх контента — отступаем под неё.
  const syncTopInset = () => {
    const insets = tg?.contentSafeAreaInsets || tg?.safeAreaInsets || {};
    const top = Math.max(Number(insets.top) || 0, tg ? 44 : 0);
    document.documentElement.style.setProperty(
      "--safe-top",
      `calc(${top}px + env(safe-area-inset-top, 0px))`
    );
  };
  syncTopInset();
  tg?.onEvent?.("contentSafeAreaChanged", syncTopInset);
  tg?.onEvent?.("safeAreaChanged", syncTopInset);
  tg?.onEvent?.("viewportChanged", syncTopInset);

  const app = document.getElementById("app");
  const modalRoot = document.getElementById("modalRoot");
  const toastRoot = document.getElementById("toastRoot");

  // Первый вход показываем «как на сайте», дальше — рабочий интерфейс сделок.
  const ONBOARD_KEY = "atlanta_onboarded";
  const markOnboarded = () => {
    try { sessionStorage.setItem(ONBOARD_KEY, "1"); } catch (_) { /* noop */ }
  };
  const isOnboarded = () => {
    try { return sessionStorage.getItem(ONBOARD_KEY) === "1"; } catch (_) { return false; }
  };

  const displayName = (name) => name;

  const state = {
    config: null,
    me: null,
    deals: [],
    route: "home",
    deal: null,
    createdDeal: null,
    dealFilter: "active",
    adminTab: "disputes",
    adminDisputes: [],
    adminRecent: [],
    timer: null,
    busy: false,
  };

  let renderSeq = 0;

  /* ------------------------------------------------------------------ utils */

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const getLang = () => window.ATLANTA_I18N?.getLang?.() || "ru";
  const locale = () => (getLang() === "en" ? "en-US" : "ru-RU");

  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));

  const icon = (name, cls = "icon") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  const usd = (value) =>
    Number(value || 0).toLocaleString(locale(), { maximumFractionDigits: 2 }) + " USD";

  // Главный экран показывает баланс в рублях, курс берём из настроек сервиса.
  const rubPerUsd = () => {
    const rub = (state.config?.currencies || []).find((item) => item.code === "RUB");
    const rate = Number(rub?.rate_usd) || 0.0112;
    return rate > 0 ? 1 / rate : 1 / 0.0112;
  };
  const rub = (value) =>
    (Number(value || 0) * rubPerUsd()).toLocaleString(locale(), { maximumFractionDigits: 2 }) + " RUB";

  const gram = (value) =>
    Number(value || 0).toLocaleString(locale(), { maximumFractionDigits: 2 }) + " GRAM";

  function money(amount, code) {
    const currency = (state.config?.currencies || []).find((c) => c.code === code);
    const decimals = Math.min(Math.max(currency?.decimals ?? 2, 2), 6);
    const number = Number(amount || 0);
    const text = number.toLocaleString(locale(), {
      minimumFractionDigits: 2,
      maximumFractionDigits: decimals,
    });
    return `${text} ${code}`;
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString(locale(), {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function fmtDay(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" });
  }

  const initials = (name) =>
    String(name || "?")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0] || "")
      .join("")
      .toUpperCase();

  function haptic(type = "light") {
    try {
      if (!tg?.HapticFeedback) return;
      if (["success", "error", "warning"].includes(type)) {
        tg.HapticFeedback.notificationOccurred(type);
      } else {
        tg.HapticFeedback.impactOccurred(type);
      }
    } catch (_) {
      /* noop */
    }
  }

  function toast(message, type = "ok") {
    const node = document.createElement("div");
    node.className = `toast ${type === "error" ? "error" : ""}`;
    node.innerHTML = `${icon(type === "error" ? "alert" : "check")}<span>${esc(message)}</span>`;
    toastRoot.appendChild(node);
    setTimeout(() => {
      node.style.opacity = "0";
      node.style.transform = "translateY(-6px)";
      node.style.transition = "opacity .2s ease, transform .2s ease";
      setTimeout(() => node.remove(), 220);
    }, 3400);
  }

  function setBusy(button, busy) {
    if (!button) return;
    if (busy) {
      button.dataset.label = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<span class="spinner"></span>';
    } else {
      button.disabled = false;
      if (button.dataset.label) button.innerHTML = button.dataset.label;
    }
  }

  function copyText(text) {
    const done = () => {
      toast("Скопировано");
      haptic("light");
    };
    const fallback = () => {
      try {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
        done();
      } catch (_) {
        toast("Не удалось скопировать", "error");
      }
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else {
      fallback();
    }
  }

  function shareLink(deal) {
    const invite = deal?.invite_link || `${location.origin}/app/?deal=${encodeURIComponent(deal?.code || "")}`;
    const text = `Сделка Gumroad: ${deal?.title || ""} · ${money(deal?.amount, deal?.currency)}`;
    const url = `https://t.me/share/url?url=${encodeURIComponent(invite)}&text=${encodeURIComponent(text)}`;
    try {
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(url);
      } else {
        window.open(url, "_blank", "noopener");
      }
    } catch (_) {
      copyText(invite);
    }
  }

  /* -------------------------------------------------------------------- api */

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    headers["X-Lang"] = getLang();

    const response = await fetch("/api" + path, {
      method: options.method || "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch (_) {
      data = { message: raw };
    }
    if (!response.ok) {
      const error = new Error(data.message || data.detail || `Ошибка ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  async function reloadMe() {
    state.me = await api("/me");
  }

  async function reloadDeals() {
    const data = await api("/deals");
    state.deals = data.items || [];
  }

  async function syncData() {
    try {
      const [me, deals] = await Promise.all([api("/me"), api("/deals")]);
      state.me = me;
      state.deals = deals.items || [];
    } catch (_) {
      /* не блокируем интерфейс */
    }
  }

  /* ------------------------------------------------------------------ router */

  function getRoute() {
    // Telegram дописывает к адресу #tgWebAppData=... — это не маршрут.
    const raw = location.hash || "";
    const hash = raw.startsWith("#/") ? raw.replace(/^#\/?/, "").trim() : "";
    if (hash) return hash;
    const params = new URLSearchParams(location.search);
    const deal = params.get("deal");
    if (deal) return `deal/${deal}`;
    if (params.get("tab") === "deals") return "deals";
    if (params.get("tab") === "top") return "top";
    if (params.get("tab") === "create") return "create";
    return isOnboarded() ? "home" : "welcome";
  }

  function navigate(route) {
    haptic("light");
    const target = "#/" + route;
    if (location.hash === target) {
      renderRoute();
    } else {
      location.hash = target;
    }
  }

  function renderRoute() {
    const route = getRoute();
    const [name, arg] = route.split("/");
    state.route = name;
    clearInterval(state.timer);
    state.timer = null;

    if (name === "deal" && arg) return renderDeal(decodeURIComponent(arg));
    if (name === "welcome") return renderWelcome();
    if (name === "deals") return renderDeals();
    if (name === "top") return renderTop();
    if (name === "create") return renderCreate();
    if (name === "created") return renderCreated();
    if (name === "profile") return renderProfile();
    if (name === "admin") return renderAdmin();
    return renderHome();
  }

  /* ------------------------------------------------------------------ layout */

  function setScreen(html, { nav = true, active = "home", dock = "", keepScroll = false } = {}) {
    renderSeq += 1;
    clearInterval(state.timer);
    state.timer = null;
    const scrollY = window.scrollY;
    app.className = "app" + (dock ? " with-dock" : "");
    app.innerHTML = `<div class="screen">${html}</div>` + (nav ? bottomNav(active) : "") + (dock ? `<div class="dock"><div class="dock-inner">${dock}</div></div>` : "");
    window.ATLANTA_I18N?.apply(app);
    if (keepScroll) {
      window.scrollTo(0, scrollY);
    } else {
      window.scrollTo(0, 0);
    }
  }

  function bottomNav(active) {
    const item = (key, label, iconName) => `
      <button class="nav-item ${active === key ? "active" : ""}" data-nav="${key}">
        ${icon(iconName)}<span>${label}</span>
      </button>`;
    return `
      <nav class="bottom-nav" aria-label="Навигация">
        ${item("home", "Главная", "home")}
        ${item("deals", "Сделки", "deals")}
        <button class="nav-item create" data-nav="create" aria-label="Создать сделку">
          <span class="nav-fab">${icon("plus")}</span><span>Создать</span>
        </button>
        ${item("top", "Топы", "top")}
        ${item("profile", "Профиль", "user")}
      </nav>`;
  }

  function pageHead(title, subtitle = "", back = true, right = "") {
    return `
      <div class="page-head">
        ${back ? `<button class="icon-btn" data-nav="back" aria-label="Назад">${icon("arrow-left")}</button>` : ""}
        <div class="page-title"><h1>${esc(title)}</h1>${subtitle ? `<span>${esc(subtitle)}</span>` : ""}</div>
        ${right}
      </div>`;
  }

  function footerBrand() {
    return `<div class="footer-brand">Gumroad · сделки под контролем</div>`;
  }

  function avatar(user, cls = "avatar") {
    const name = displayName(user?.name || "?");
    return `<div class="${cls}"><span>${esc(initials(name))}</span>${
      user?.photo_url ? `<img src="${esc(user.photo_url)}" alt="" loading="lazy" onerror="this.remove()">` : ""
    }</div>`;
  }

  function statusPill(deal) {
    return `<span class="status-pill tone-${esc(deal.status_tone)}">${esc(deal.status_label)}</span>`;
  }

  function dealCard(deal) {
    const roleLabel = deal.role === "seller" ? "Продавец" : deal.role === "buyer" ? "Покупатель" : "Наблюдатель";
    const counterparty = deal.role === "buyer" ? deal.seller?.name : deal.buyer?.name;
    return `
      <button class="deal-card" data-deal="${esc(deal.code)}">
        <div class="dc-top">
          <span class="dc-code">${esc(deal.code)}</span>
          ${statusPill(deal)}
        </div>
        <p class="dc-title">${esc(deal.title)}</p>
        <div class="dc-bottom">
          <div>
            <div class="dc-amount">${money(deal.amount, deal.currency)}</div>
            <div class="dc-side">${roleLabel}${counterparty ? " · " + esc(counterparty) : ""}</div>
          </div>
          <span class="dc-arrow">${icon("chevron")}</span>
        </div>
      </button>`;
  }

  const ACTIVE_STATUSES = ["waiting_buyer", "waiting_payment", "funded", "delivered", "disputed"];

  /* ----------------------------------------------------------------- welcome */

  function renderWelcome() {
    const steps = [
      ["Оплата под защитой", "Деньги не уходят продавцу"],
      ["Передача", "Продавец фиксирует факт передачи, для решения возможных споров"],
      ["Выплата", "После подтверждения покупателем или арбитром"],
    ];
    const faq = [
      ["Как работает защита оплаты?", "Gumroad временно держит деньги покупателя. Покупатель платит не продавцу напрямую, а на защищённый счёт сервиса. Продавец видит, что оплата есть, и передаёт товар. Деньги уходят продавцу только после подтверждения покупателя."],
      ["Когда продавец получает деньги?", "Сразу после того, как покупатель нажмёт «Подтвердить получение». Выплата зачисляется на баланс Gumroad за вычетом комиссии, после чего её можно вывести на кошелёк или реквизиты."],
      ["Что делать, если товар не соответствует описанию?", "Не подтверждайте сделку. Откройте спор и опишите проблему: арбитр увидит условия, историю статусов и сообщения сторон. По итогам он выплатит деньги продавцу или вернёт их покупателю."],
      ["Сколько стоит сервис?", "1,5% от суммы сделки в криптовалюте и 2,5% в фиате, минимум 0,30 USD. Комиссия удерживается только при успешном завершении. Создание сделки, вход по ссылке и отмена — бесплатно."],
      ["Как покупатель попадает в сделку?", "Продавец отправляет ссылку вида t.me/бот?start=deal_KST-XXXXXX. Покупатель открывает её в Telegram, нажимает «Присоединиться» и оплачивает счёт. Регистрация не нужна."],
    ];

    const content = `
      <div class="welcome">
        <div class="w-top">
          <div class="w-brand"><b>Gumroad</b></div>
          <div class="lang-switch no-i18n" role="group" aria-label="Language">
            <button type="button" data-lang="ru">RU</button>
            <button type="button" data-lang="en">EN</button>
          </div>
        </div>

        <section class="w-hero">
          <span class="w-badge">${icon("shield")} Безопасные сделки в Telegram · крипта и фиат</span>
          <h1>Сделки<br>без риска<em>Начните уже сейчас!</em></h1>
          <p>Gumroad держит оплату под защитой, пока покупатель не получит товар. Продавец видит, что деньги уже есть. Покупатель знает, что они уйдут только после подтверждения.</p>
          <button class="w-cta" data-action="start-deal">Начать сделку ${icon("arrow-right")}</button>
        </section>

        <div class="w-stats">
          <div><b>1,5%</b><span>комиссия в крипте</span></div>
          <div><b>0 ₽</b><span>за создание сделки</span></div>
          <div><b>24/7</b><span>арбитраж</span></div>
        </div>

        <section class="section">
          <div class="section-head"><h3>Как это работает</h3></div>
          <div class="w-steps">
            ${steps
              .map(
                ([title, text]) => `<div class="w-step">
                  <div><b>${esc(title)}</b><span>${esc(text)}</span></div>
                </div>`
              )
              .join("")}
          </div>
        </section>

        <section class="section">
          <div class="section-head"><h3>Частые вопросы</h3></div>
          <div class="w-faq">
            ${faq
              .map(
                ([question, answer], index) => `<details class="w-q" ${index === 0 ? "open" : ""}>
                  <summary>${esc(question)}${icon("chevron", "icon chev")}</summary>
                  <div class="w-q-body">${esc(answer)}</div>
                </details>`
              )
              .join("")}
          </div>
          <div class="w-help">Не нашли ответ? Напишите в поддержку — поможем разобраться со сделкой.</div>
        </section>

        <button class="btn btn-primary btn-block" data-action="start-deal">Начать сделку ${icon("arrow-right")}</button>
        <button class="w-skip" data-action="skip-welcome">Пропустить</button>
        ${footerBrand()}
      </div>
    `;

    setScreen(content, { nav: false });
  }

  /* -------------------------------------------------------------------- home */

  function renderHome() {
    const me = state.me;
    const user = me?.user;
    const balances = me?.balances;
    const active = state.deals.filter((deal) => ACTIVE_STATUSES.includes(deal.status));
    const completed = me?.stats?.completed || 0;
    const greeting = state.deals.length === 0 && completed === 0 ? "Приветствуем!" : "С возвращением";

    const content = `
      <div class="topbar">
        <div class="hello">
          ${avatar(user)}
          <div class="hello-text">
            <span>${greeting}</span>
            <b>${esc(displayName(user?.name || "Друг"))}</b>
          </div>
        </div>
        <button class="icon-btn" data-nav="profile" aria-label="Профиль">${icon("user")}</button>
      </div>

      <section class="balance-card">
        <div class="bc-glow"></div>
        <div class="bc-top">
          <span>Баланс</span>
        </div>
        <div class="bc-value">${rub(balances?.total_usd || 0)}</div>
        <div class="bc-actions">
          <button class="btn btn-ghost btn-sm" data-nav="profile">${icon("wallet")} Вывести</button>
        </div>
      </section>

      <section class="cta-create">
        <span class="cta-badge" aria-label="Защита">${icon("shield")}</span>
        <h2>Новая сделка</h2>
        <p>Деньги замораживаются до подтверждения. Продавец получает оплату после подтверждения сделки</p>
        <button class="cta-btn" data-nav="create">Создать сделку ${icon("arrow-right")}</button>
      </section>

      <div class="quick-grid">
        <button class="quick-card" data-action="focus-join">
          ${icon("key")}
          <span><b>Войти по коду</b><span>KST-XXXXXX</span></span>
        </button>
        <button class="quick-card" data-nav="deals">
          ${icon("deals")}
          <span><b>Мои сделки</b><span>${state.deals.length} всего</span></span>
        </button>
      </div>

      <section class="section">
        <div class="section-head"><h3>Войти в сделку</h3><span class="count-chip">по коду или ссылке</span></div>
        <form class="join-card" id="joinForm" autocomplete="off">
          <input class="input" name="code" placeholder="KST-AB12CD" maxlength="120" aria-label="Код сделки">
          <button class="btn btn-primary" type="submit" aria-label="Войти">${icon("arrow-right")}</button>
        </form>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>Активные сделки</h3>
          <button class="link-btn" data-nav="deals">Все ${icon("chevron")}</button>
        </div>
        ${
          active.length
            ? `<div class="deal-list">${active.slice(0, 3).map(dealCard).join("")}</div>`
            : `<div class="empty">
                 <div class="empty-icon">${icon("shield")}</div>
                 <b>Пока тихо</b>
                 <span>Создайте сделку или войдите по ссылке покупателя.</span>
               </div>`
        }
      </section>

      <section class="section">
        <div class="section-head"><h3>Как это работает</h3></div>
        <div class="how-mini">
          <div class="hm-step"><b>Оплата под защитой</b><span>Деньги не уходят продавцу</span></div>
          <div class="hm-step"><b>Передача</b><span>Продавец фиксирует факт передачи, для решения возможных споров</span></div>
          <div class="hm-step"><b>Выплата</b><span>После подтверждения покупателем или арбитром</span></div>
        </div>
      </section>

      ${footerBrand()}
    `;

    setScreen(content, { active: "home" });
  }

  /* ------------------------------------------------------------------- deals */

  function renderDeals() {
    const filter = state.dealFilter;
    const filtered = state.deals.filter((deal) => {
      if (filter === "active") return ACTIVE_STATUSES.includes(deal.status);
      if (filter === "done") return !ACTIVE_STATUSES.includes(deal.status);
      return true;
    });
    const counts = {
      active: state.deals.filter((d) => ACTIVE_STATUSES.includes(d.status)).length,
      done: state.deals.filter((d) => !ACTIVE_STATUSES.includes(d.status)).length,
      all: state.deals.length,
    };

    const content = `
      ${pageHead("Мои сделки", `${counts.all} всего`, false, `<button class="icon-btn" data-action="refresh-list" aria-label="Обновить">${icon("refresh")}</button>`)}
      <div class="tabs">
        <button class="tab ${filter === "active" ? "active" : ""}" data-filter="active">Активные ${counts.active}</button>
        <button class="tab ${filter === "done" ? "active" : ""}" data-filter="done">Завершённые ${counts.done}</button>
        <button class="tab ${filter === "all" ? "active" : ""}" data-filter="all">Все ${counts.all}</button>
      </div>
      ${
        filtered.length
          ? `<div class="deal-list">${filtered.map(dealCard).join("")}</div>`
          : `<div class="empty">
               <div class="empty-icon">${icon("deals")}</div>
               <b>${filter === "active" ? "Активных сделок нет" : "Здесь пока пусто"}</b>
               <span>Создайте сделку или откройте ссылку-приглашение.</span>
             </div>`
      }
      <div style="height:16px"></div>
      <button class="btn btn-primary btn-block" data-nav="create">${icon("plus")} Новая сделка</button>
      ${footerBrand()}
    `;
    setScreen(content, { active: "deals" });
  }

  function renderTop() {
    const people = [
      { user: "@nixena", name: "Evgeniya" },
      { user: "@aisus", name: "Б" },
      { user: "@denis33371", name: "Denis" },
      { user: "@depytatka", name: "Депутат" },
      { user: "@prizma", name: "𝕊𝕥𝕚𝕧 ₀₉₁₁.ₜₒₙ" },
      { user: "@prizm", name: "Dragon" },
      { user: "@crashit", name: "Crash" },
      { user: "@boxe", name: "🖤𝙅𝙊𝙀 𝘽𝙇𝘼𝘾𝙆🖤 𝙈𝙈" },
      { user: "@WebSpeak", name: "Serhii Palamarchuk" },
      { user: "@anton", name: "Антон" },
      { user: "@moonrise", name: "Дарья Соколова" },
      { user: "@dmitry_k", name: "Дмитрий" },
      { user: "@wilson_m", name: "Michael Wilson" },
      { user: "@vortexx", name: "Виктор" },
      { user: "@maximka", name: "Максим" },
      { user: "@ewilliams", name: "Emma Williams" },
      { user: "@kira_moon", name: "Кирилл Орлов" },
      { user: "@solarfl", name: "София" },
      { user: "@onyx_7", name: "Пользователь скрыл информацию о себе" },
      { user: "@luna_v", name: "Мария Кузнецова" },
      { user: "@zen_inside", name: "Тимур" },
      { user: "@aura_light", name: "Алина" },
      { user: "@fluxcap", name: "Robert Brown" },
      { user: "@raven_tt", name: "Егор" },
      { user: "@noirsky", name: "Вероника Зайцева" },
      { user: "@echovoid", name: "Ethan" },
      { user: "@pulse_x", name: "Полина" },
      { user: "@jstreet", name: "James" },
      { user: "@nodeone", name: "Антон Волков" },
      { user: "@glitcher", name: "Дарья" },
      { user: "@frostbyte", name: "Nicholas Young" },
      { user: "@ember_9", name: "Илья Морозов" },
      { user: "@zephyr", name: "Пользователь скрыл информацию о себе" },
      { user: "@orbitcc", name: "Ольга" },
      { user: "@prism_art", name: "John Davis" },
      { user: "@crystal", name: "Ксения" },
      { user: "@wraith_tt", name: "Пользователь скрыл информацию о себе" },
      { user: "@sunny", name: "Matthew Harris" },
      { user: "@vega_star", name: "Валерия" },
      { user: "@nebula_tt", name: "Андрей Новиков" },
      { user: "@quantz", name: "Константин" },
      { user: "@shadow_one", name: "Анастасия Фёдорова" },
      { user: "@blazefire", name: "Brandon Baker" },
      { user: "@misty", name: "Мирон" },
      { user: "@darkwave", name: "BLESSED" },
      { user: "@ronin_tt", name: "Лев" },
      { user: "@sable_x", name: "Harper Gonzalez" },
      { user: "@vexed", name: "Олег" },
      { user: "@nexus_01", name: "Иван Смирнов" },
      { user: "@helix_dna", name: "Александр" },
      { user: "@arcane_tt", name: "Evelyn Wilson" },
      { user: "@mythos", name: "Пользователь скрыл информацию о себе" },
      { user: "@oracle_x", name: "Станислав Ефимов" },
      { user: "@sirius_s", name: "Grace Anderson" },
      { user: "@lyra_moon", name: "Оксана" },
      { user: "@drifter", name: "George Campbell" },
      { user: "@haven_tt", name: "Наталья" },
      { user: "@riot_mode", name: "Justin Adams" },
      { user: "@hush_tt", name: "Глеб Ткачёв" },
      { user: "@vividcol", name: "Chloe Taylor" },
      { user: "@midas_t", name: "Даниил" },
      { user: "@eclipse_z", name: "Ирина Медведева" },
      { user: "@jbrooks", name: "James Brown" },
      { user: "@titan_x", name: "Kevin Nelson" },
      { user: "@astral_tt", name: "Светлана" },
      { user: "@cobalt_tt", name: "Brian Hill" },
      { user: "@indigo_v", name: "Edward Mitchell" },
      { user: "@violet_tt", name: "Пользователь скрыл информацию о себе" },
      { user: "@haze_tt", name: "Samuel Roberts" },
      { user: "@storm_tt", name: "Татьяна Гусева" },
      { user: "@thunder_tt", name: "Christopher Lee" },
      { user: "@max_suh", name: "Максим Сухоцкий" },
      { user: "@bolt_tt", name: "Anthony Turner" },
      { user: "@flare_tt", name: "Влад Ковалёв" },
      { user: "@zeropoint", name: "Olivia Johnson" },
      { user: "@krypt_tt", name: "Юрий Тарасов" },
      { user: "@cipher_tt", name: "Ava Smith" },
      { user: "@token_tt", name: "Michael" },
      { user: "@block_tt", name: "Sophia Martinez" },
      { user: "@chain_tt", name: "Роман" },
      { user: "@pulsar_tt", name: "Isabella Garcia" },
      { user: "@comet_tt", name: "Артём" },
      { user: "@meteor_tt", name: "Mia Rodriguez" },
      { user: "@galaxy_tt", name: "Екатерина" },
      { user: "@cosmos_tt", name: "Amelia Lopez" },
      { user: "@stardust_tt", name: "Пользователь скрыл информацию о себе" },
      { user: "@moonlight_tt", name: "Lily Jackson" },
      { user: "@sunset_tt", name: "Елена Соловьёва" },
      { user: "@dawn_tt", name: "Nora Harris" },
      { user: "@dusk_tt", name: "Макар" },
      { user: "@twilight_tt", name: "Ruby Clark" },
      { user: "@mirage_tt", name: "Владислав" },
      { user: "@phantom_tt", name: "Abigail Davis" },
      { user: "@spectre_tt", name: "Зоя" },
      { user: "@ghost_tt", name: "Ella Miller" },
      { user: "@michaelw", name: "Michael" },
      { user: "@robertb", name: "Пользователь скрыл информацию о себе" },
      { user: "@johnd", name: "John" },
      { user: "@davidm", name: "David Miller" },
      { user: "@richarda", name: "Richard Anderson" },
    ];
    const dealCounts = [
      70, 68, 69, 67, 66, 68, 65, 67, 64, 66,
      63, 65, 64, 62, 63, 61, 62, 60, 61, 60,
      69, 67, 68, 66, 65, 67, 64, 66, 63, 65,
      62, 64, 61, 63, 60, 62, 61, 60, 60, 60,
      70, 68, 67, 69, 66, 65, 68, 64, 66, 63,
      65, 62, 64, 61, 63, 60, 62, 61, 60, 60,
      68, 70, 69, 67, 66, 68, 65, 67, 64, 66,
      63, 65, 62, 64, 61, 63, 60, 62, 61, 60,
      69, 67, 68, 66, 65, 67, 64, 66, 63, 65,
      62, 64, 61, 63, 60, 62, 61, 60, 60, 60,
    ];
    // Первые три места заданы вручную, дальше плавный спад от 470 USD.
    const volumes = [
      1143, 764, 543, 470,
      ...Array.from({ length: 96 }, (_, index) =>
        Math.round(30 + 420 * Math.pow(0.9452333674735214, index))
      ),
    ];
    const hiddenInfo = "Пользователь скрыл информацию о себе";
    const leaders = people.map(({ user, name }, index) => ({
      user: name === hiddenInfo ? "" : user,
      name,
      deals: String(dealCounts[index]),
      volume: `${volumes[index]} USD`,
    }));

    const content = `
      ${pageHead("Топы", "Обновлено сейчас", false)}
      <section class="top-hero">
        <div class="top-hero-label">Проведено сделок</div>
        <div class="top-hero-value">6 412</div>
        <div class="top-hero-sub">Оборот сервиса 13 432 USD</div>
        <div class="top-hero-grid">
          <div class="top-mini"><b>98,7%</b><span>Успешных сделок</span></div>
        </div>
      </section>
      <section class="section">
        <div class="section-head"><h3>Топ участников</h3><span class="count-chip">топ-100</span></div>
        <div class="top-list">
          ${leaders
            .map(
              ({ user, name, deals, volume }, index) => `
            <div class="top-row">
              <span class="top-rank">${index + 1}</span>
              <span class="top-identity">
                <span class="top-name">${esc(name)}</span>
                ${user ? `<span class="top-user">${esc(user)}</span>` : ""}
              </span>
              <span class="top-meta"><b>${deals}</b><span>${volume}</span></span>
            </div>`
            )
            .join("")}
        </div>
      </section>
      ${footerBrand()}
    `;
    setScreen(content, { active: "top" });
  }

  /* ------------------------------------------------------------------ create */

  function renderCreate() {
    const currencies = state.config?.currencies || [];
    const categories = state.config?.categories || [];
    const currencyOptions = currencies
      .map((c) => `<option value="${c.code}"${c.code === "RUB" ? " selected" : ""}>${c.code}</option>`)
      .join("");

    const content = `
      ${pageHead("Новая сделка", "Деньги под защитой Gumroad")}
      <form id="createForm" autocomplete="off">
        <div class="form-card">
          <h4>Предмет сделки</h4>
          <div class="hint-text">Создать сделку может любая сторона — вы будете её владельцем.</div>
          <div class="field">
            <label>Кто вы в сделке?</label>
            <input type="hidden" name="creator_role" value="seller">
            <div class="chips" id="roleChips">
              <button type="button" class="chip active" data-role="seller">Я продавец</button>
              <button type="button" class="chip" data-role="buyer">Я покупатель</button>
            </div>
          </div>
          <div class="field">
            <label>Название <span class="hint">5–120 символов</span></label>
            <input class="input" name="title" maxlength="120" placeholder="Например: NFT-подарок Telegram" required>
          </div>
          <div class="field" style="margin-bottom:0">
            <label>Категория</label>
            <input type="hidden" name="category" value="${categories[0]?.key || "other"}">
            <div class="chips" id="categoryChips">
              ${categories
                .map(
                  (c, index) =>
                    `<button type="button" class="chip ${index === 0 ? "active" : ""}" data-cat="${c.key}">${esc(c.label)}</button>`
                )
                .join("")}
            </div>
          </div>
        </div>

        <div class="form-card">
          <h4>Сумма и валюта</h4>
          <div class="row-2">
            <div class="field">
              <label>Сумма сделки</label>
              <input class="input" name="amount" inputmode="decimal" pattern="[0-9.,]+" placeholder="0.00" required>
            </div>
            <div class="field">
              <label>Валюта</label>
              <div class="select-wrap">
                <select class="select" name="currency" id="currencySelect">${currencyOptions}</select>
              </div>
            </div>
          </div>
          <div class="hint-text" id="currencyHint">Защита действует до подтверждения покупателем.</div>
        </div>

        <div class="form-card">
          <h4>Детали</h4>
          <div class="field" style="margin-bottom:0">
            <label>Описание</label>
            <textarea class="textarea" name="description" maxlength="1500" placeholder="Что входит в сделку"></textarea>
          </div>
        </div>

        <div class="summary">
          <div class="sum-row"><span>Комиссия сервиса</span><b id="sumFee">—</b></div>
          <div class="sum-row"><span>Продавец получит</span><b id="sumNet">—</b></div>
          <div class="sum-row total"><span>Покупатель платит</span><b id="sumTotal">—</b></div>
        </div>

        <div class="note">
          ${icon("shield")}
          <span>Оплата попадёт под защиту Gumroad. Продавец получит деньги только после подтверждения покупателя или решения арбитра.</span>
        </div>
      </form>
      ${footerBrand()}
    `;

    const dock = `<button class="btn btn-primary" type="submit" form="createForm" id="createBtn">Создать сделку ${icon("arrow-right")}</button>`;
    setScreen(content, { nav: false, dock });
    updateSummary();
  }

  function updateSummary() {
    const form = $("#createForm");
    if (!form) return;
    const amount = Number(String(form.elements.amount?.value || "0").replace(",", ".")) || 0;
    const code = form.elements.currency?.value;
    const currency = (state.config?.currencies || []).find((c) => c.code === code);
    const fees = state.config?.fees || { crypto: 1.5, fiat: 2.5, min_usd: 0.3 };
    const percent = currency?.kind === "fiat" ? fees.fiat : fees.crypto;
    const rate = currency?.rate_usd || 1;
    const fee = amount > 0 ? Math.max((amount * percent) / 100, fees.min_usd / rate) : 0;
    const net = Math.max(amount - fee, 0);

    const feeNode = $("#sumFee");
    const netNode = $("#sumNet");
    const totalNode = $("#sumTotal");
    if (feeNode) feeNode.textContent = amount > 0 ? `${money(fee, code)} · ${percent}%` : "—";
    if (netNode) netNode.textContent = amount > 0 ? money(net, code) : "—";
    if (totalNode) totalNode.textContent = amount > 0 ? money(amount, code) : "—";
    const hint = $("#currencyHint");
    if (hint && currency) {
      hint.textContent =
        currency.kind === "fiat"
          ? `Фиат · ${currency.network} · комиссия ${fees.fiat}%`
          : `Крипта · ${currency.network} · комиссия ${fees.crypto}% · ≈ ${usd(amount * rate)}`;
    }
  }

  async function submitCreate(form) {
    const data = new FormData(form);
    const payload = {
      title: String(data.get("title") || "").trim(),
      description: String(data.get("description") || "").trim(),
      terms: String(data.get("terms") || "").trim(),
      category: String(data.get("category") || "other"),
      amount: String(data.get("amount") || "").replace(/\s/g, "").replace(",", "."),
      currency: String(data.get("currency") || "RUB"),
      creator_role: String(data.get("creator_role") || "seller"),
    };
    if (payload.title.length < 5) {
      toast("Название — минимум 5 символов", "error");
      return;
    }
    if (!payload.amount || Number(payload.amount) <= 0) {
      toast("Укажите сумму сделки", "error");
      return;
    }
    const button = $("#createBtn");
    setBusy(button, true);
    try {
      const deal = await api("/deals", { method: "POST", body: payload });
      state.createdDeal = deal;
      await reloadDeals();
      haptic("success");
      navigate("created");
    } catch (error) {
      toast(error.message, "error");
      haptic("error");
    } finally {
      setBusy(button, false);
    }
  }

  function joinByCode(form) {
    const raw = String(new FormData(form).get("code") || "").trim().toUpperCase();
    if (!raw) {
      toast("Введите код сделки", "error");
      return;
    }
    let code = raw.replace(/^HTTPS?:\/\/T\.ME\/[^?]+\?START=DEAL_/, "").replace(/^DEAL_/, "").replace(/^KST-?/, "");
    if (!/^[A-Z0-9]{4,10}$/.test(code)) {
      toast("Код выглядит неверно. Пример: KST-AB12CD", "error");
      return;
    }
    navigate(`deal/KST-${code}`);
  }

  /* ------------------------------------------------------------------ created */

  function renderCreated() {
    const deal = state.createdDeal;
    if (!deal) return renderDeals();
    const invite = deal.invite_link || "";
    const sellerInvite = deal.invite_role === "seller";
    const intro = sellerInvite
      ? "Отправьте ссылку продавцу. Он присоединится к сделке, а вы оплатите счёт — деньги окажутся под защитой."
      : "Отправьте ссылку покупателю. Он присоединится и оплатит счёт — деньги окажутся под защитой.";
    const inviteLabel = sellerInvite ? "Ссылка для продавца" : "Ссылка для покупателя";
    const cancelNote = sellerInvite
      ? "Пока продавец не присоединился, сделку можно отменить без потерь. Ссылка действует, пока сделку не займут."
      : "Пока покупатель не оплатил, сделку можно отменить без потерь. Ссылка действует, пока сделку не займут.";

    const content = `
      <div class="success-screen">
        <div class="success-icon">${icon("check")}</div>
        <h1>Сделка создана</h1>
        <p class="sub">${intro}</p>

        <div class="created-card">
          <div class="created-top">
            <span class="created-code">${esc(deal.code)}</span>
            ${statusPill(deal)}
          </div>
          <div class="created-title">${esc(deal.title)}</div>
          <div class="created-amount">${money(deal.amount, deal.currency)}</div>
          <div class="created-note">Комиссия ${deal.fee_percent}% · продавцу ${money(deal.net_amount, deal.currency)}</div>
        </div>

        <div class="panel" style="text-align:left">
          <div class="panel-head"><div class="panel-title">${icon("key")} ${inviteLabel}</div></div>
          <button class="invite-link" data-copy="${esc(invite)}">${esc(invite)}</button>
          <div class="copy-row">
            <button class="btn btn-ghost btn-sm" data-copy="${esc(invite)}">${icon("copy")} Копировать</button>
            <button class="btn btn-soft btn-sm" data-action="share" data-code="${esc(deal.code)}">${icon("share")} Поделиться</button>
          </div>
        </div>

        <div class="note" style="text-align:left">
          ${icon("lock")}
          <span>${cancelNote}</span>
        </div>
        ${footerBrand()}
      </div>
    `;

    const dock = `<button class="btn btn-primary" data-deal="${esc(deal.code)}">Открыть сделку ${icon("arrow-right")}</button>`;
    setScreen(content, { nav: false, dock });
  }

  /* --------------------------------------------------------------------- deal */

  const STEP_LABELS = ["Создана", "Оплачена", "Передача", "Выплата"];
  const STEP_INDEX = {
    waiting_buyer: 0,
    waiting_payment: 1,
    funded: 2,
    delivered: 3,
    completed: 4,
    disputed: 2,
    cancelled: 0,
    refunded: 4,
  };

  const ACTION_ICONS = {
    join: "user",
    pay: "wallet",
    pay_balance: "wallet",
    deliver: "send",
    confirm: "check",
    dispute: "scale",
    cancel: "x",
    resolve_release: "check",
    resolve_refund: "refresh",
  };

  const ACTION_BTN = {
    primary: "btn-primary",
    success: "btn-success",
    danger: "btn-danger",
    "danger-ghost": "btn-danger",
    ghost: "btn-ghost",
  };

  async function renderDeal(code, keepScroll = false) {
    const seq = ++renderSeq;
    clearInterval(state.timer);
    state.timer = null;
    app.className = "app";
    app.innerHTML = `<div class="screen"><div class="boot" style="padding-top:14vh">
      <div class="skeleton sk-card" style="height:150px"></div>
      <div class="skeleton sk-row"></div>
      <div class="skeleton sk-row"></div>
      <div class="skeleton sk-row" style="height:110px"></div>
    </div></div>`;
    try {
      const deal = await api(`/deals/${encodeURIComponent(code)}`);
      if (seq !== renderSeq) return;
      state.deal = deal;
      drawDeal(deal, keepScroll);
    } catch (error) {
      if (seq !== renderSeq) return;
      drawError("Сделка не открылась", error.message);
    }
  }

  function progressHtml(status) {
    const index = STEP_INDEX[status] ?? 0;
    return `
      <div class="progress">
        ${STEP_LABELS.map((_, i) => `<span class="${i < index ? "done" : i === index && index < 4 ? "now" : ""}"></span>`).join("")}
      </div>
      <div class="progress-labels">${STEP_LABELS.map((label) => `<span>${label}</span>`).join("")}</div>`;
  }

  function personHtml(user, label) {
    if (!user) {
      return `<div class="person">
        <div class="person-avatar">${icon("user")}</div>
        <div class="person-info"><div class="person-label">${label}</div><div class="person-name" style="color:var(--muted-2)">Ожидается</div></div>
      </div>`;
    }
    return `<div class="person">
      ${avatar(user, "person-avatar")}
      <div class="person-info">
        <div class="person-label">${label}</div>
        <div class="person-name">${esc(displayName(user.name))}</div>
      </div>
    </div>`;
  }

  function actionButton(action) {
    const cls = action.style === "primary" ? "primary" : action.style === "success" ? "success" : action.style === "danger" || action.style === "danger-ghost" ? "danger-ghost" : "";
    return `<button class="action-btn ${cls}" data-action="${action.key}" data-code="${esc(state.deal?.code || "")}">
      ${icon(ACTION_ICONS[action.key] || "chevron")} ${esc(action.label)}
    </button>`;
  }

  function paymentHtml(deal) {
    const payment = deal.payment;
    if (!payment || deal.status !== "waiting_payment") return "";
    if (deal.role !== "buyer" && !deal.is_admin) return "";
    const expired = payment.expired;
    const address = payment.address || "";
    const payUrl = payment.pay_url || "";
    return `
      <section class="pay-panel">
        <div class="pay-head">
          <span>${icon("lock")} Счёт на оплату</span>
        </div>
        <div class="pay-amount">${money(payment.amount, payment.currency)}</div>
        ${
          address
            ? `<div class="pay-label">Адрес ${esc(payment.currency)}${payment.memo ? " · memo " + esc(payment.memo) : ""}</div>
               <button class="addr-btn" data-copy="${esc(address)}"><span>${esc(address)}</span>${icon("copy")}</button>`
            : ""
        }
        <div class="pay-meta">
          <span>${icon("clock")} ${expired ? "Счёт истёк" : "Осталось"} <b id="countdown">${expired ? "00:00" : "—"}</b></span>
          <span>${esc(payment.provider)}</span>
        </div>
        ${
          payUrl
            ? `<a class="btn btn-primary" href="${esc(payUrl)}" target="_blank" rel="noopener">${icon("external")} Оплатить счёт</a>`
            : payment.uri
            ? `<a class="btn btn-ghost" href="${esc(payment.uri)}" target="_blank" rel="noopener">${icon("wallet")} Открыть кошелёк</a>`
            : ""
        }
        <button class="btn btn-ghost" data-action="refresh" data-code="${esc(deal.code)}">${icon("refresh")} Проверить оплату</button>
        <p class="pay-note">После оплаты статус обновится автоматически в течение пары минут.</p>
      </section>`;
  }

  function inviteHtml(deal) {
    if (!["seller", "buyer"].includes(deal.role) || deal.status !== "waiting_buyer" || !deal.invite_link) return "";
    const title = deal.invite_role === "seller" ? "Пригласите продавца" : "Пригласите покупателя";
    return `
      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">${icon("key")} ${title}</div>
          <span class="count-chip">ссылка</span>
        </div>
        <button class="invite-link" data-copy="${esc(deal.invite_link)}">${esc(deal.invite_link)}</button>
        <div class="copy-row">
          <button class="btn btn-ghost btn-sm" data-copy="${esc(deal.invite_link)}">${icon("copy")} Копировать</button>
          <button class="btn btn-soft btn-sm" data-action="share" data-code="${esc(deal.code)}">${icon("share")} Поделиться</button>
        </div>
      </section>`;
  }

  function timelineHtml(deal) {
    if (!deal.events?.length) return "";
    return `
      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">${icon("clock")} История сделки</div>
          <span class="count-chip">${deal.events.length}</span>
        </div>
        <div class="timeline">
          ${deal.events
            .map((event) => {
              const tone = ["completed", "funded", "resolved_release"].includes(event.kind)
                ? "ok"
                : ["disputed", "resolved_refund"].includes(event.kind)
                ? "warn"
                : ["cancelled", "refunded"].includes(event.kind)
                ? "bad"
                : "";
              return `<div class="tl-item">
                <span class="tl-dot ${tone}"></span>
                <div class="tl-body">
                  <div class="tl-text">${esc(event.text)}</div>
                  <div class="tl-meta"><span>${esc(displayName(event.actor || "Gumroad"))}</span><span>${fmtDate(event.created_at)}</span></div>
                </div>
              </div>`;
            })
            .join("")}
        </div>
      </section>`;
  }

  function detailsHtml(deal) {
    const rows = [
      ["Категория", deal.category_label],
      ["Комиссия", `${deal.fee_percent}% · ${money(deal.fee_amount, deal.currency)}`],
      ["Продавец получит", money(deal.net_amount, deal.currency)],
      ["Создана", fmtDate(deal.created_at)],
    ];
    if (deal.completed_at) rows.push(["Завершена", fmtDate(deal.completed_at)]);
    return `
      <section class="panel details">
        <div class="panel-head"><div class="panel-title">${icon("doc")} Детали</div></div>
        ${rows.map(([label, value]) => `<div class="detail-row"><span class="detail-label">${label}</span><span class="detail-value">${esc(value)}</span></div>`).join("")}
        ${
          deal.description
            ? `<div class="detail-block"><span class="detail-label">Описание</span><p>${esc(deal.description)}</p></div>`
            : ""
        }
      </section>`;
  }

  function disputeHtml(deal) {
    if (!deal.dispute_reason && !deal.resolution) return "";
    return `
      <section class="panel" style="border-color:rgba(255,107,122,.22);background:rgba(255,107,122,.035)">
        <div class="panel-head">
          <div class="panel-title" style="color:var(--red)">${icon("scale")} Спор</div>
          <span class="status-pill tone-red">${deal.status === "disputed" ? "на рассмотрении" : "решён"}</span>
        </div>
        ${deal.dispute_reason ? `<div class="ad-reason">${esc(deal.dispute_reason)}</div>` : ""}
        ${deal.resolution ? `<div class="detail-row"><span class="detail-label">Решение</span><span class="detail-value">${esc(deal.resolution)}</span></div>` : ""}
      </section>`;
  }

  function drawDeal(deal, keepScroll = false) {
    let primary = deal.actions?.find((action) => action.style === "primary" || action.style === "success");
    if (deal.status === "waiting_payment" && deal.payment && (deal.role === "buyer" || deal.is_admin)) {
      primary = { key: "refresh", label: "Проверить оплату", style: "primary" };
    }
    const secondary = (deal.actions || []).filter(
      (action) => action !== primary && !(deal.payment && action.key === "pay")
    );
    const dock = primary
      ? `<button class="btn ${ACTION_BTN[primary.style] || "btn-primary"}" data-action="${primary.key}" data-code="${esc(deal.code)}">${esc(primary.label)}</button>
         <button class="btn btn-ghost icon-only" data-action="refresh" data-code="${esc(deal.code)}" aria-label="Обновить">${icon("refresh")}</button>`
      : `<button class="btn btn-ghost" data-action="refresh" data-code="${esc(deal.code)}">${icon("refresh")} Обновить сделку</button>`;

    const content = `
      <div class="page-head">
        <button class="icon-btn" data-nav="back" aria-label="Назад">${icon("arrow-left")}</button>
        <div class="page-title"><h1>${esc(deal.code)}</h1><span>${esc(deal.category_label)}</span></div>
        <button class="icon-btn" data-action="refresh" data-code="${esc(deal.code)}" aria-label="Обновить">${icon("refresh")}</button>
      </div>

      <section class="deal-hero ${deal.status === "disputed" ? "disputed" : ""}">
        <div class="dh-top">
          <span class="dh-code">${esc(deal.code)}</span>
          ${statusPill(deal)}
        </div>
        <div class="dh-amount">${money(deal.amount, deal.currency)}</div>
        <div class="dh-usd">≈ ${usd(deal.amount_usd)} · комиссия ${deal.fee_percent}%</div>
        <div class="dh-hint">${icon(deal.status === "disputed" ? "alert" : "shield")}<span>${esc(deal.next_step)}</span></div>
        ${progressHtml(deal.status)}
      </section>

      <div class="parties">
        ${personHtml(deal.seller, "Продавец")}
        ${personHtml(deal.buyer, "Покупатель")}
      </div>

      ${inviteHtml(deal)}
      ${paymentHtml(deal)}
      ${disputeHtml(deal)}

      ${secondary.length ? `<div class="actions">${secondary.map(actionButton).join("")}</div>` : ""}

      ${timelineHtml(deal)}
      ${detailsHtml(deal)}

      ${
        deal.is_admin
          ? `<div class="note">${icon("scale")}<span>Вы видите сделку как арбитр. Решение по спору доступно в блоке действий.</span></div>`
          : ""
      }
      ${footerBrand()}
    `;

    setScreen(content, { nav: false, dock, keepScroll });

    if (deal.payment && deal.status === "waiting_payment" && !deal.payment.expired) {
      startCountdown(deal.payment.expires_at);
    }
  }

  function startCountdown(expiresAt) {
    const node = document.getElementById("countdown");
    if (!node || !expiresAt) return;
    const end = new Date(expiresAt).getTime();
    const tick = () => {
      const current = document.getElementById("countdown");
      if (!current) {
        clearInterval(state.timer);
        return;
      }
      const diff = end - Date.now();
      if (diff <= 0) {
        current.textContent = "00:00";
        clearInterval(state.timer);
        return;
      }
      const total = Math.floor(diff / 1000);
      const minutes = String(Math.floor(total / 60)).padStart(2, "0");
      const seconds = String(total % 60).padStart(2, "0");
      current.textContent = `${minutes}:${seconds}`;
    };
    tick();
    state.timer = setInterval(tick, 1000);
  }

  /* ------------------------------------------------------------------ profile */

  function renderProfile() {
    const me = state.me;
    if (!me) return renderHome();
    const user = me.user;
    const stats = me.stats || {};
    const balances = me.balances?.items || [];

    const content = `
      ${pageHead("Профиль", "Аккаунт Gumroad", false)}
      <section class="profile-hero">
        ${avatar(user, "ph-avatar")}
        <div class="ph-name">${esc(displayName(user.name))}</div>
        <div class="ph-username">${user.username ? "@" + esc(user.username) : "без username"}</div>
        <div class="ph-id">ID ${esc(user.id)}</div>
        <div class="ph-badges">
          ${user.is_admin ? `<span class="mini-chip">Арбитр</span>` : ""}
          <span class="mini-chip">с ${fmtDay(me.created_at)}</span>
        </div>
      </section>

      <div class="stat-grid">
        <div class="stat"><b>${stats.deals || 0}</b><span>сделок</span></div>
        <div class="stat"><b>${stats.completed || 0}</b><span>завершено</span></div>
        <div class="stat"><b>${usd(stats.volume_usd || 0)}</b><span>оборот</span></div>
      </div>

      <section class="section">
        <div class="section-head"><h3>Баланс</h3><span class="count-chip">${usd(me.balances?.total_usd || 0)}</span></div>
        ${
          balances.length
            ? `<div class="balance-list">${balances
                .map(
                  (item) => `<div class="bal-item">
                    <div class="bal-info"><b>${money(item.available, item.currency)}</b><span>≈ ${usd(item.usd)}</span></div>
                    <button class="bal-withdraw" data-action="withdraw" data-currency="${esc(item.currency)}">Вывести</button>
                  </div>`
                )
                .join("")}</div>`
            : `<div class="empty"><div class="empty-icon">${icon("wallet")}</div><b>Баланс пуст</b><span>Средства появятся после завершённой сделки.</span></div>`
        }
      </section>

      <section class="section">
        <div class="section-head"><h3>Язык</h3></div>
        <div class="lang-row">
          <div class="lang-switch" role="group" aria-label="Language">
            <button type="button" data-lang="ru">RU</button>
            <button type="button" data-lang="en">EN</button>
          </div>
          <span class="lang-hint">Интерфейс бота и приложения</span>
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h3>Ещё</h3></div>
        <div class="menu-list">
          <button class="menu-item" data-action="how">
            <span class="menu-icon">${icon("shield")}</span><span>Как работает Gumroad</span>${icon("chevron", "icon chev")}
          </button>
          ${
            user.is_admin
              ? `<button class="menu-item" data-nav="admin">
                   <span class="menu-icon">${icon("scale")}</span><span>Арбитраж и споры</span>${icon("chevron", "icon chev")}
                 </button>`
              : ""
          }
          ${
            state.config?.support
              ? `<a class="menu-item" href="https://t.me/${esc(state.config.support)}" target="_blank" rel="noopener">
                   <span class="menu-icon">${icon("support")}</span><span>Поддержка</span>${icon("external", "icon chev")}
                 </a>`
              : ""
          }
          ${
            !tg
              ? `<a class="menu-item" href="${esc(state.config?.bot_link || "https://t.me/GumroadCoinApp")}" target="_blank" rel="noopener">
                   <span class="menu-icon">${icon("send")}</span><span>Открыть в Telegram</span>${icon("external", "icon chev")}
                 </a>`
              : ""
          }
        </div>
      </section>

      <div class="note">
        ${icon("lock")}
        <span>Gumroad не хранит данные карт и ключи кошельков. Все действия по сделке фиксируются в журнале.</span>
      </div>
      ${footerBrand()}
    `;

    setScreen(content, { active: "profile" });
  }

  /* -------------------------------------------------------------------- admin */

  async function renderAdmin() {
    if (!state.me?.is_admin) {
      drawError("Нет доступа", "Раздел доступен только арбитрам.");
      return;
    }
    const seq = ++renderSeq;
    app.className = "app";
    app.innerHTML = `<div class="screen"><div class="boot" style="padding-top:14vh">
      <div class="skeleton sk-card" style="height:110px"></div>
      <div class="skeleton sk-row"></div>
      <div class="skeleton sk-row"></div>
    </div></div>`;
    try {
      const [disputes, recent] = await Promise.all([api("/admin/disputes"), api("/admin/deals")]);
      if (seq !== renderSeq) return;
      state.adminDisputes = disputes.items || [];
      state.adminRecent = recent.items || [];
      drawAdmin();
    } catch (error) {
      if (seq !== renderSeq) return;
      drawError("Арбитраж недоступен", error.message);
    }
  }

  function drawAdmin() {
    const tab = state.adminTab;
    const disputes = state.adminDisputes;
    const recent = state.adminRecent;

    const content = `
      ${pageHead("Арбитраж", `${disputes.length} открытых споров`)}
      <div class="tabs">
        <button class="tab ${tab === "disputes" ? "active" : ""}" data-admin-tab="disputes">Споры ${disputes.length}</button>
        <button class="tab ${tab === "recent" ? "active" : ""}" data-admin-tab="recent">Последние сделки</button>
      </div>
      ${
        tab === "disputes"
          ? disputes.length
            ? disputes
                .map(
                  (deal) => `<article class="admin-dispute">
                    <div class="ad-head">
                      <span class="dc-code">${esc(deal.code)}</span>
                      ${statusPill(deal)}
                    </div>
                    <div class="ad-title">${esc(deal.title)}</div>
                    <div class="dc-side" style="margin-top:3px">${money(deal.amount, deal.currency)} · ${usd(deal.amount_usd)}</div>
                    <div class="ad-reason">${esc(deal.dispute_reason || "Причина не указана")}</div>
                    <div class="dc-side" style="margin-bottom:9px">
                      ${icon("user")} ${esc(deal.seller?.name || "—")} → ${esc(deal.buyer?.name || "—")}
                    </div>
                    <div class="ad-actions">
                      <button class="btn btn-success btn-sm" data-action="resolve_release" data-code="${esc(deal.code)}">Продавцу</button>
                      <button class="btn btn-danger btn-sm" data-action="resolve_refund" data-code="${esc(deal.code)}">Покупателю</button>
                    </div>
                    <button class="btn btn-ghost btn-sm btn-block" style="margin-top:7px" data-deal="${esc(deal.code)}">Открыть сделку</button>
                  </article>`
                )
                .join("")
            : `<div class="empty"><div class="empty-icon">${icon("check")}</div><b>Споров нет</b><span>Все сделки идут по плану.</span></div>`
          : recent.length
          ? `<div class="deal-list">${recent.map(dealCard).join("")}</div>`
          : `<div class="empty"><div class="empty-icon">${icon("deals")}</div><b>Сделок пока нет</b><span>Здесь появятся все сделки сервиса.</span></div>`
      }
      ${footerBrand()}
    `;
    setScreen(content, { active: "profile" });
  }

  /* ------------------------------------------------------------------- errors */

  function drawError(title, message) {
    const botUrl = state.config?.bot_link || "https://t.me/GumroadCoinApp";
    const content = `
      <div class="error-screen">
        ${icon("alert")}
        <h2>${esc(title)}</h2>
        <p>${esc(message)}</p>
        <button class="btn btn-primary btn-block" data-action="retry">Попробовать снова</button>
        <a class="btn btn-ghost btn-block" style="margin-top:8px" href="${esc(botUrl)}" target="_blank" rel="noopener">Открыть бота</a>
      </div>`;
    setScreen(content, { nav: false });
  }

  /* -------------------------------------------------------------------- sheet */

  function openSheet({ title, text = "", fields = "", submit = "Подтвердить", cancel = "Отмена", danger = false, onSubmit }) {
    return new Promise((resolve) => {
      const backdrop = document.createElement("div");
      backdrop.className = "modal-backdrop";
      backdrop.innerHTML = `
        <div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}">
          <div class="sheet-handle"></div>
          <h3 class="sheet-title">${esc(title)}</h3>
          ${text ? `<p class="sheet-text">${text}</p>` : ""}
          <form class="sheet-form" novalidate>
            ${fields}
            <div class="sheet-actions">
              <button type="button" class="btn btn-ghost" data-close>${esc(cancel)}</button>
              <button type="submit" class="btn ${danger ? "btn-danger" : "btn-primary"}">${esc(submit)}</button>
            </div>
          </form>
        </div>`;
      modalRoot.appendChild(backdrop);

      const close = (value) => {
        backdrop.remove();
        resolve(value);
      };
      backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) close(null);
      });
      backdrop.querySelector("[data-close]").addEventListener("click", () => close(null));

      const form = backdrop.querySelector("form");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(form).entries());
        const button = form.querySelector('button[type="submit"]');
        setBusy(button, true);
        try {
          const result = onSubmit ? await onSubmit(data) : data;
          close(result === undefined ? true : result);
        } catch (error) {
          setBusy(button, false);
          toast(error.message || "Не получилось", "error");
          haptic("error");
        }
      });

      setTimeout(() => {
        const field = backdrop.querySelector("input, textarea");
        if (field) field.focus({ preventScroll: true });
      }, 80);
    });
  }

  async function confirmSheet({ title, text, submit = "Подтвердить", danger = false }) {
    const result = await openSheet({
      title,
      text,
      submit,
      danger,
      onSubmit: () => true,
    });
    return result === true;
  }

  async function reasonSheet({ title, text, submit = "Отправить", danger = false, required = false, label = "Комментарий" }) {
    return openSheet({
      title,
      text,
      submit,
      danger,
      fields: `<div class="field">
        <label>${esc(label)} ${required ? "" : '<span class="hint">необязательно</span>'}</label>
        <textarea class="textarea" name="reason" maxlength="1000" placeholder="Опишите ситуацию" ${required ? "required" : ""}></textarea>
      </div>`,
      onSubmit: (data) => {
        const reason = String(data.reason || "").trim();
        if (required && reason.length < 10) {
          throw new Error("Опишите подробнее — минимум 10 символов");
        }
        return { reason };
      },
    });
  }

  async function openWithdraw(item) {
    let access;
    try {
      access = await api("/wallet/withdraw-access");
    } catch (error) {
      toast(error.message || "Не получилось", "error");
      return;
    }
    if (!access.allowed) {
      await openSheet({
        title: "Вывод недоступен",
        text: `Вывод станет доступен после ${access.required} успешных сделок.`,
        submit: "Понятно",
        cancel: "Закрыть",
        onSubmit: () => true,
      });
      return;
    }
    openSheet({
      title: `Вывод ${item.currency}`,
      text: `Доступно <b>${money(item.available, item.currency)}</b>. Укажите сумму и реквизиты получателя.`,
      submit: "Вывести",
      fields: `
        <div class="field">
          <label>Сумма</label>
          <input class="input" name="amount" inputmode="decimal" value="${esc(item.available)}" required>
        </div>
        <div class="field">
          <label>Адрес или реквизиты</label>
          <input class="input" name="address" placeholder="${item.currency === "RUB" ? "Телефон СБП или карта" : "Адрес кошелька"}" required>
        </div>`,
      onSubmit: async (data) => {
        await api("/wallet/withdraw", {
          method: "POST",
          body: { currency: item.currency, amount: data.amount, address: data.address },
        });
        toast("Вывод отправлен");
        haptic("success");
        await reloadMe();
        if (state.route === "profile") renderProfile();
        return true;
      },
    });
  }

  /* ------------------------------------------------------------------ actions */

  async function handleAction(action, element) {
    const code = element?.dataset?.code || state.deal?.code;
    if (state.busy) return;

    switch (action) {
      case "retry":
        return boot();

      case "refresh":
      case "refresh-list":
        haptic("light");
        if (action === "refresh-list") {
          try {
            await reloadDeals();
            renderDeals();
          } catch (error) {
            toast(error.message, "error");
          }
          return;
        }
        return code ? renderDeal(code, true) : renderRoute();

      case "focus-join": {
        const form = document.getElementById("joinForm");
        if (form) {
          form.scrollIntoView({ behavior: "smooth", block: "center" });
          form.elements.code?.focus();
        } else {
          renderHome();
          setTimeout(() => {
            const created = document.getElementById("joinForm");
            created?.scrollIntoView({ behavior: "smooth", block: "center" });
            created?.elements.code?.focus();
          }, 60);
        }
        return;
      }

      case "how":
        return navigate("welcome");

      case "start-deal":
        markOnboarded();
        return navigate("create");

      case "skip-welcome":
        markOnboarded();
        return navigate("home");


      case "share": {
        const deal = state.deal?.code === code ? state.deal : state.createdDeal?.code === code ? state.createdDeal : null;
        if (deal) shareLink(deal);
        return;
      }

      case "withdraw": {
        const currency = element.dataset.currency;
        const item = state.me?.balances?.items?.find((balance) => balance.currency === currency);
        if (item) await openWithdraw(item);
        return;
      }

      case "join":
      case "pay":
      case "pay_balance":
      case "deliver":
      case "confirm":
      case "cancel":
      case "dispute":
      case "resolve_release":
      case "resolve_refund":
        break;

      default:
        return;
    }

    if (!code) return;

    state.busy = true;
    try {
      if (action === "join") {
        await api(`/deals/${encodeURIComponent(code)}/join`, { method: "POST" });
        toast("Вы присоединились к сделке");
        haptic("success");
        await syncData();
        await renderDeal(code, true);
        return;
      }

      if (action === "pay") {
        const data = await api(`/deals/${encodeURIComponent(code)}/pay`, { method: "POST" });
        if (state.deal) state.deal.payment = data.payment;
        toast("Счёт сформирован");
        haptic("success");
        await renderDeal(code, true);
        return;
      }

      if (action === "pay_balance") {
        const deal = state.deal?.code === code ? state.deal : null;
        const ok = await confirmSheet({
          title: "Оплата с баланса",
          text: deal
            ? `Спишем ${money(deal.amount, deal.currency)} с вашего баланса и поставим под защиту сделки.`
            : "Подтвердите оплату сделки с баланса.",
          submit: "Оплатить",
        });
        if (!ok) return;
        await api(`/deals/${encodeURIComponent(code)}/pay-balance`, { method: "POST" });
        toast("Деньги под защитой");
        haptic("success");
        await syncData();
        await renderDeal(code, true);
        return;
      }

      if (action === "deliver") {
        const result = await reasonSheet({
          title: "Товар передан",
          text: "Покупатель получит уведомление и сможет проверить результат.",
          submit: "Подтвердить передачу",
          label: "Что передано",
        });
        if (!result) return;
        await api(`/deals/${encodeURIComponent(code)}/deliver`, {
          method: "POST",
          body: { note: result.reason },
        });
        toast("Передача отмечена");
        haptic("success");
        await syncData();
        await renderDeal(code, true);
        return;
      }

      if (action === "confirm") {
        const ok = await confirmSheet({
          title: "Подтвердить получение?",
          text: "После подтверждения деньги уйдут продавцу. Отменить это действие нельзя — при проблеме сначала откройте спор.",
          submit: "Да, всё получил",
          danger: false,
        });
        if (!ok) return;
        await api(`/deals/${encodeURIComponent(code)}/confirm`, { method: "POST" });
        toast("Сделка завершена");
        haptic("success");
        await syncData();
        await renderDeal(code, true);
        return;
      }

      if (action === "cancel") {
        const result = await reasonSheet({
          title: "Отменить сделку?",
          text: "Сделка будет закрыта без движения средств. Это возможно, пока покупатель не оплатил.",
          submit: "Отменить сделку",
          danger: true,
          label: "Причина",
        });
        if (!result) return;
        await api(`/deals/${encodeURIComponent(code)}/cancel`, {
          method: "POST",
          body: { reason: result.reason },
        });
        toast("Сделка отменена");
        await syncData();
        await renderDeal(code, true);
        return;
      }

      if (action === "dispute") {
        const result = await reasonSheet({
          title: "Открыть спор",
          text: "Опишите проблему. Арбитр увидит условия сделки, историю и ваш комментарий.",
          submit: "Передать арбитру",
          danger: true,
          required: true,
          label: "Что случилось",
        });
        if (!result) return;
        await api(`/deals/${encodeURIComponent(code)}/dispute`, {
          method: "POST",
          body: { reason: result.reason },
        });
        toast("Спор открыт, арбитр подключится");
        haptic("warning");
        await syncData();
        await renderDeal(code, true);
        return;
      }

      if (action === "resolve_release" || action === "resolve_refund") {
        const release = action === "resolve_release";
        const result = await reasonSheet({
          title: release ? "Выплатить продавцу?" : "Вернуть покупателю?",
          text: release
            ? "Сделка завершится, продавец получит сумму за вычетом комиссии."
            : "Сделка будет закрыта возвратом средств покупателю.",
          submit: release ? "Выплатить продавцу" : "Вернуть покупателю",
          danger: !release,
          label: "Комментарий арбитра",
        });
        if (!result) return;
        await api(`/deals/${encodeURIComponent(code)}/resolve`, {
          method: "POST",
          body: { outcome: release ? "release" : "refund", note: result.reason },
        });
        toast("Решение принято");
        haptic("success");
        await syncData();
        if (state.route === "admin") {
          await renderAdmin();
        } else {
          await renderDeal(code, true);
        }
        return;
      }
    } catch (error) {
      toast(error.message, "error");
      haptic("error");
    } finally {
      state.busy = false;
    }
  }

  /* ------------------------------------------------------------------ events */

  document.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-nav]");
    if (nav) {
      const route = nav.dataset.nav;
      if (route === "back") {
        if (history.length > 1) history.back();
        else navigate("home");
      } else {
        navigate(route);
      }
      return;
    }

    const dealNode = event.target.closest("[data-deal]");
    if (dealNode) {
      navigate(`deal/${dealNode.dataset.deal}`);
      return;
    }

    const copyNode = event.target.closest("[data-copy]");
    if (copyNode) {
      copyText(copyNode.dataset.copy || "");
      return;
    }

    const filter = event.target.closest("[data-filter]");
    if (filter) {
      state.dealFilter = filter.dataset.filter;
      renderDeals();
      haptic("light");
      return;
    }

    const adminTab = event.target.closest("[data-admin-tab]");
    if (adminTab) {
      state.adminTab = adminTab.dataset.adminTab;
      drawAdmin();
      haptic("light");
      return;
    }

    const role = event.target.closest("[data-role]");
    if (role) {
      const wrapper = role.closest("#roleChips");
      $$(".chip", wrapper).forEach((chip) => chip.classList.remove("active"));
      role.classList.add("active");
      const input = document.querySelector('#createForm input[name="creator_role"]');
      if (input) input.value = role.dataset.role;
      haptic("light");
      return;
    }

    const category = event.target.closest("[data-cat]");
    if (category) {
      const wrapper = category.closest("#categoryChips");
      $$(".chip", wrapper).forEach((chip) => chip.classList.remove("active"));
      category.classList.add("active");
      const input = document.querySelector('#createForm input[name="category"]');
      if (input) input.value = category.dataset.cat;
      haptic("light");
      return;
    }

    const faqHead = event.target.closest(".w-q > summary");
    if (faqHead) {
      event.preventDefault();
      faqHead.parentElement.open = !faqHead.parentElement.open;
      return;
    }

    const action = event.target.closest("[data-action]");
    if (action) {
      event.preventDefault();
      handleAction(action.dataset.action, action);
    }
  });

  document.addEventListener("submit", (event) => {
    if (event.target.id === "createForm") {
      event.preventDefault();
      submitCreate(event.target);
    } else if (event.target.id === "joinForm") {
      event.preventDefault();
      joinByCode(event.target);
    }
  });

  document.addEventListener("input", (event) => {
    if (event.target.closest("#createForm") && event.target.name === "amount") {
      const clean = String(event.target.value)
        .replace(/[^\d.,]/g, "")
        .replace(/,/g, ".")
        .replace(/\.(?=.*\.)/g, "");
      if (clean !== event.target.value) event.target.value = clean;
      updateSummary();
    }
  });

  document.addEventListener("change", (event) => {
    if (event.target.id === "currencySelect") updateSummary();
  });

  window.addEventListener("hashchange", () => {
    renderRoute();
  });

  window.addEventListener("atlanta:lang", async () => {
    // Серверные подписи (статусы, шаги, события) приходят на выбранном языке.
    try {
      await syncData();
    } catch (_) {
      /* офлайн — остаёмся на текущих данных */
    }
    renderRoute();
  });

  /* --------------------------------------------------------------------- boot */

  async function boot() {
    try {
      // Убираем служебный хэш Telegram, чтобы ?tab=... и ?deal=... читались.
      if (location.hash && !location.hash.startsWith("#/")) {
        try {
          history.replaceState(null, "", location.pathname + location.search);
        } catch (_) {
          /* noop */
        }
      }
      state.config = await api("/config");
      const [me, deals] = await Promise.all([api("/me"), api("/deals")]);
      state.me = me;
      state.deals = deals.items || [];
      renderRoute();
    } catch (error) {
      const message =
        error.status === 401
          ? "Откройте приложение через Telegram-бота Gumroad — так безопаснее."
          : error.message || "Не удалось загрузить данные";
      drawError("Приложение не открылось", message);
    }
  }

  if (tg) {
    try {
      tg.ready();
      tg.expand();
      tg.requestFullscreen?.();
      tg.setHeaderColor("#06070B");
      tg.setBackgroundColor("#06070B");
      tg.disableVerticalSwipes?.();
    } catch (_) {
      /* noop */
    }
  }

  boot();
})();
