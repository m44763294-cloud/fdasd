/* ATLANTA landing — поведение без зависимостей */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ------------------------------- nav ------------------------------- */
  const nav = $("#nav");
  const burger = $("#burger");
  const navLinks = $("#navLinks");

  const onScroll = () => nav && nav.classList.toggle("scrolled", window.scrollY > 12);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  if (burger && navLinks) {
    burger.addEventListener("click", () => {
      const open = navLinks.classList.toggle("open");
      burger.setAttribute("aria-expanded", String(open));
    });
    $$("a", navLinks).forEach((link) =>
      link.addEventListener("click", () => {
        navLinks.classList.remove("open");
        burger.setAttribute("aria-expanded", "false");
      })
    );
  }

  /* ------------------------------ reveal ----------------------------- */
  const reveals = $$(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    reveals.forEach((el) => observer.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("in"));
  }

  /* ------------------------------ ticker ----------------------------- */
  const ticker = $("#ticker");
  if (ticker) {
    ticker.innerHTML += ticker.innerHTML;
  }

  /* ------------------------------- data ------------------------------ */
  const isEn = () => (window.ATLANTA_I18N?.getLang?.() || "ru") === "en";
  const formatUsd = (value) =>
    Math.round(Number(value) || 0).toLocaleString(isEn() ? "en-US" : "ru-RU") + " USD";

  async function loadConfig() {
    try {
      const response = await fetch("/api/config");
      if (!response.ok) return;
      const config = await response.json();
      const botUrl = config.bot_link || `https://t.me/${config.bot_username}`;

      $$("[data-bot-link]").forEach((link) => {
        link.href = botUrl;
      });

      const supportUrl = config.support ? `https://t.me/${config.support}` : botUrl;
      ["#supportLink", "#footerSupport"].forEach((selector) => {
        const node = $(selector);
        if (node) node.href = supportUrl;
      });
    } catch (_) {
      /* лендинг остаётся рабочим без API */
    }
  }

  async function loadStats() {
    const line = $("#liveLine");
    if (!line) return;
    try {
      const response = await fetch("/api/stats", { headers: { "X-Lang": isEn() ? "en" : "ru" } });
      if (!response.ok) return;
      const stats = await response.json();
      const en = isEn();
      if (stats.deals > 0) {
        const avg = stats.avg_minutes > 0
          ? (en ? ` · average completion ${stats.avg_minutes} min` : ` · среднее завершение ${stats.avg_minutes} мин`)
          : "";
        const lead = en ? "Deals completed:" : "Уже проведено";
        const tail = en ? "for" : "сделок на";
        line.innerHTML =
          `<span class="live-dot"></span> ${lead} <b>${stats.deals}</b> ${tail} ${formatUsd(
            stats.volume_usd
          )}${avg}`;
      } else {
        line.innerHTML = en
          ? `<span class="live-dot"></span> Service is running · payments are protected`
          : `<span class="live-dot"></span> Сервис работает · платежи под защитой`;
      }
    } catch (_) {
      /* ignore */
    }
  }

  loadConfig();
  loadStats();
  window.addEventListener("atlanta:lang", () => loadStats());
})();
