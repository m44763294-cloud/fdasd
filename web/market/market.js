/* ATLANTA — маркет подарков Telegram. Только каталог и пополнение GRAM на кошелёк владельца. */
(() => {
  "use strict";

  const tg = window.Telegram?.WebApp;
  const root = document.getElementById("market");
  const modalRoot = document.getElementById("modalRoot");
  const toastRoot = document.getElementById("toastRoot");

  const syncTopInset = () => {
    const insets = tg?.contentSafeAreaInsets || tg?.safeAreaInsets || {};
    const top = Math.max(Number(insets.top) || 0, tg ? 44 : 0);
    document.documentElement.style.setProperty("--safe-top", `calc(${top}px + env(safe-area-inset-top, 0px))`);
  };
  syncTopInset();
  tg?.onEvent?.("contentSafeAreaChanged", syncTopInset);
  tg?.onEvent?.("safeAreaChanged", syncTopInset);
  tg?.onEvent?.("viewportChanged", syncTopInset);

  const detected = String(
    new URLSearchParams(location.search).get("lang") ||
    tg?.initDataUnsafe?.user?.language_code ||
    navigator.language || "ru"
  ).toLowerCase();

  const state = {
    lang: detected.startsWith("en") ? "en" : "ru",
    tab: "store",
    query: "",
    sort: "popular",
    selected: null,
    config: { gram_receive_address: "", gram_receive_comment: "ATLANTA GRAM topup", gift_receive_username: "" },
  };

  const DICT = {
    ru: {
      search: "Поиск подарка",
      sortPopular: "Популярные",
      sortPriceLow: "Сначала дешёвые",
      sortPriceHigh: "Сначала дорогие",
      sortName: "По названию",
      catalogue: "Каталог",
      found: "найдено",
      store: "Маркет",
      collections: "Коллекции",
      topup: "Пополнить GRAM",
      profile: "Профиль",
      price: "Цена",
      model: "Модель",
      collection: "Коллекция",
      close: "Закрыть",
      empty: "Ничего не нашлось. Попробуйте другой запрос.",
      emptyGifts: "Здесь пока пусто.",
      toStore: "К покупкам",
      langShort: "EN",
      myGifts: "Мои подарки",
      gifts: "подарков",
      topupTitle: "Пополнение GRAM",
      topupHint: "Переведите GRAM на кошелёк ниже. Это прямой перевод владельцу маркета.",
      walletAddress: "Адрес кошелька",
      comment: "Комментарий",
      copy: "Скопировать",
      copied: "Скопировано",
      noAddress: "Адрес для пополнения пока не настроен. Напишите в поддержку.",
      depositGift: "Пополнить подарок",
      depositGiftHint: "Отправьте коллекционный подарок этому аккаунту в Telegram. Покупка и продажа подарков в маркете недоступны.",
      receiveAccount: "Аккаунт для подарков",
      openAccount: "Открыть аккаунт",
      noAccount: "Аккаунт для приёма подарков пока не настроен.",
    },
    en: {
      search: "Search a gift",
      sortPopular: "Popular",
      sortPriceLow: "Price: low to high",
      sortPriceHigh: "Price: high to low",
      sortName: "By name",
      catalogue: "Catalogue",
      found: "found",
      store: "Store",
      collections: "Collections",
      topup: "Top up GRAM",
      profile: "Profile",
      price: "Price",
      model: "Model",
      collection: "Collection",
      close: "Close",
      empty: "Nothing found. Try another request.",
      emptyGifts: "It's empty here.",
      toStore: "Browse gifts",
      langShort: "RU",
      myGifts: "My gifts",
      gifts: "gifts",
      topupTitle: "Top up GRAM",
      topupHint: "Send GRAM to the wallet below. This is a direct transfer to the market owner.",
      walletAddress: "Wallet address",
      comment: "Comment",
      copy: "Copy",
      copied: "Copied",
      noAddress: "Top-up address is not configured yet. Contact support.",
      depositGift: "Deposit a gift",
      depositGiftHint: "Send your collectible gift to this Telegram account. Buying and selling gifts in the market is not available.",
      receiveAccount: "Gift receiving account",
      openAccount: "Open account",
      noAccount: "The gift receiving account is not configured yet.",
    },
  };

  const GIFTS = [{"id":1,"slug":"algorithmcup","name":"Algorithm Cup","model":"Silver","price":75},{"id":2,"slug":"artisanbrick","name":"Artisan Brick","model":"Art Nouveau","price":25},{"id":3,"slug":"astralshard","name":"Astral Shard","model":"Amethyst","price":35},{"id":4,"slug":"bdaycandle","name":"B-Day Candle","model":"Anniversary","price":50},{"id":5,"slug":"berrybox","name":"Berry Box","model":"Alpha","price":75},{"id":6,"slug":"bigyear","name":"Big Year","model":"2048","price":100},{"id":7,"slug":"blingbinky","name":"Bling Binky","model":"Abyss Binky","price":150},{"id":8,"slug":"bondedring","name":"Bonded Ring","model":"Anaconda","price":200},{"id":9,"slug":"bowtie","name":"Bow Tie","model":"Baby Yoda","price":250},{"id":10,"slug":"bunnymuffin","name":"Bunny Muffin","model":"Airy Souffle","price":770},{"id":11,"slug":"candycane","name":"Candy Cane","model":"Amber Glitter","price":500},{"id":12,"slug":"chillflame","name":"Chill Flame","model":"Baba Yaga","price":750},{"id":13,"slug":"cloverpin","name":"Clover Pin","model":"Balloon","price":1000},{"id":14,"slug":"cookieheart","name":"Cookie Heart","model":"Affection","price":1500},{"id":15,"slug":"crystalball","name":"Crystal Ball","model":"Amanita","price":2500},{"id":16,"slug":"cupidcharm","name":"Cupid Charm","model":"Antique","price":5000},{"id":17,"slug":"deskcalendar","name":"Desk Calendar","model":"Adult Tasks","price":15},{"id":18,"slug":"diamondring","name":"Diamond Ring","model":"Acid Green","price":125},{"id":19,"slug":"durovscap","name":"Durov's Cap","model":"Apple Slice","price":77},{"id":20,"slug":"durovsglasses","name":"Durov's Glasses","model":"Aliens","price":50},{"id":21,"slug":"easteregg","name":"Easter Egg","model":"3D Render","price":75},{"id":22,"slug":"electricskull","name":"Electric Skull","model":"Bad Fortune","price":100},{"id":23,"slug":"eternalcandle","name":"Eternal Candle","model":"Baphomet","price":150},{"id":24,"slug":"eternalrose","name":"Eternal Rose","model":"3D Glow","price":200},{"id":25,"slug":"evileye","name":"Evil Eye","model":"Aqua Heart","price":250},{"id":26,"slug":"faithamulet","name":"Faith Amulet","model":"Amethyst","price":350},{"id":27,"slug":"finepen","name":"Fine Pen","model":"Black & Gold","price":500},{"id":28,"slug":"flyingbroom","name":"Flying Broom","model":"Acorn Whisk","price":750},{"id":29,"slug":"freshsocks","name":"Fresh Socks","model":"Avocado","price":1000},{"id":30,"slug":"gemsignet","name":"Gem Signet","model":"Aqua Ring","price":1500},{"id":31,"slug":"genielamp","name":"Genie Lamp","model":"Abyssal","price":2500},{"id":32,"slug":"gingercookie","name":"Ginger Cookie","model":"Bone Chiller","price":5000},{"id":33,"slug":"hangingstar","name":"Hanging Star","model":"Agaric","price":15},{"id":34,"slug":"happybrownie","name":"Happy Brownie","model":"After Dark","price":25},{"id":35,"slug":"heartlocket","name":"Heart Locket","model":"Amore","price":35},{"id":36,"slug":"heroichelmet","name":"Heroic Helmet","model":"Arctic","price":50},{"id":37,"slug":"hexpot","name":"Hex Pot","model":"Aconite","price":75},{"id":38,"slug":"holidaydrink","name":"Holiday Drink","model":"Amaretto","price":100},{"id":39,"slug":"homemadecake","name":"Homemade Cake","model":"Amanita","price":150},{"id":40,"slug":"hypnolollipop","name":"Hypno Lollipop","model":"Afterparty","price":200},{"id":41,"slug":"icecream","name":"Ice Cream","model":"Banana","price":250},{"id":42,"slug":"inputkey","name":"Input Key","model":"1-Bit","price":350},{"id":43,"slug":"instantramen","name":"Instant Ramen","model":"Admiral","price":500},{"id":44,"slug":"intelligencecup","name":"Intelligence Cup","model":"Brass","price":750},{"id":45,"slug":"iongem","name":"Ion Gem","model":"Amber","price":1000},{"id":46,"slug":"ionicdryer","name":"Ionic Dryer","model":"Aurora","price":1500},{"id":47,"slug":"jackinthebox","name":"Jack-in-the-Box","model":"Alien","price":2500},{"id":48,"slug":"jellybunny","name":"Jelly Bunny","model":"Aurora","price":5000},{"id":49,"slug":"jesterhat","name":"Jester Hat","model":"Affinity","price":15},{"id":50,"slug":"jinglebells","name":"Jingle Bells","model":"Alarm Bell","price":25},{"id":51,"slug":"jollychimp","name":"Jolly Chimp","model":"Albino","price":35},{"id":52,"slug":"joyfulbundle","name":"Joyful Bundle","model":"Balance","price":50},{"id":53,"slug":"khabibspapakha","name":"Khabib's Papakha","model":"Ashen","price":75},{"id":54,"slug":"kissedfrog","name":"Kissed Frog","model":"Anime","price":100},{"id":55,"slug":"libertyfigure","name":"Liberty Figure","model":"Anarchy","price":150},{"id":56,"slug":"lightsword","name":"Light Sword","model":"Anakin","price":200},{"id":57,"slug":"lolpop","name":"Lol Pop","model":"Blueberry","price":250},{"id":58,"slug":"lootbag","name":"Loot Bag","model":"B-Day","price":350},{"id":59,"slug":"lovecandle","name":"Love Candle","model":"Caramel","price":500},{"id":60,"slug":"lovepotion","name":"Love Potion","model":"Amaretto","price":750},{"id":61,"slug":"lowrider","name":"Low Rider","model":"Acid Cab","price":1000},{"id":62,"slug":"luckylocket","name":"Lucky Locket","model":"Bon Appetit","price":1500},{"id":63,"slug":"lunarsnake","name":"Lunar Snake","model":"Albino","price":2500},{"id":64,"slug":"lushbouquet","name":"Lush Bouquet","model":"Amethyst","price":5000},{"id":65,"slug":"madpumpkin","name":"Mad Pumpkin","model":"Babadook","price":15},{"id":66,"slug":"magicpotion","name":"Magic Potion","model":"Aperol","price":25},{"id":67,"slug":"mightyarm","name":"Mighty Arm","model":"Amethyst","price":35},{"id":68,"slug":"minioscar","name":"Mini Oscar","model":"Amethyst","price":50},{"id":69,"slug":"miragelamp","name":"Mirage Lamp","model":"Ataraxia","price":75},{"id":70,"slug":"moneypot","name":"Money Pot","model":"Algae","price":100},{"id":71,"slug":"moodpack","name":"Mood Pack","model":"Allergic","price":150},{"id":72,"slug":"moonpendant","name":"Moon Pendant","model":"Aiguilles","price":200},{"id":73,"slug":"moussecake","name":"Mousse Cake","model":"Aurora","price":250},{"id":74,"slug":"mythmask","name":"Myth Mask","model":"Abaddon","price":350},{"id":75,"slug":"nailbracelet","name":"Nail Bracelet","model":"Aethel","price":500},{"id":76,"slug":"nekohelmet","name":"Neko Helmet","model":"Andromeda","price":750},{"id":77,"slug":"partysparkler","name":"Party Sparkler","model":"Aurora","price":1000},{"id":78,"slug":"perfumebottle","name":"Perfume Bottle","model":"Anna Karenina","price":1500},{"id":79,"slug":"petsnake","name":"Pet Snake","model":"Albino","price":2500},{"id":80,"slug":"plushpepe","name":"Plush Pepe","model":"Aqua Plush","price":5000},{"id":81,"slug":"recordplayer","name":"Record Player","model":"Afterlife","price":15},{"id":82,"slug":"restlessjar","name":"Restless Jar","model":"Alabaster","price":25},{"id":83,"slug":"ringofstrength","name":"Ring of Strength","model":"Alloy","price":35},{"id":84,"slug":"sakuraflower","name":"Sakura Flower","model":"Aurora","price":50},{"id":85,"slug":"santahat","name":"Santa Hat","model":"B-Day Boy","price":75},{"id":86,"slug":"scaredcat","name":"Scared Cat","model":"Bastet","price":100},{"id":87,"slug":"sharpfang","name":"Sharp Fang","model":"Alchemy","price":150},{"id":88,"slug":"shinydisplay","name":"Shiny Display","model":"Aquamarine","price":200},{"id":89,"slug":"signetring","name":"Signet Ring","model":"Alucard","price":250},{"id":90,"slug":"skullflower","name":"Skull Flower","model":"Alder Bloom","price":350},{"id":91,"slug":"sleighbell","name":"Sleigh Bell","model":"Amaretto","price":500},{"id":92,"slug":"snakebox","name":"Snake Box","model":"Arcane","price":750},{"id":93,"slug":"snoopcigar","name":"Snoop Cigar","model":"Ashtray","price":1000},{"id":94,"slug":"snoopdogg","name":"Snoop Dogg","model":"Adios","price":1500},{"id":95,"slug":"snowglobe","name":"Snow Globe","model":"Amethyst","price":2500},{"id":96,"slug":"snowmittens","name":"Snow Mittens","model":"Alien","price":5000},{"id":97,"slug":"spicedwine","name":"Spiced Wine","model":"Absinthe","price":15},{"id":98,"slug":"spyagaric","name":"Spy Agaric","model":"Agar Agar","price":25},{"id":99,"slug":"starnotepad","name":"Star Notepad","model":"Archie","price":35},{"id":100,"slug":"stellarrocket","name":"Stellar Rocket","model":"Airdrop","price":50},{"id":101,"slug":"swisswatch","name":"Swiss Watch","model":"Amnesia","price":75},{"id":102,"slug":"tama","name":"Tama Gadget","model":"Alabaster","price":100},{"id":103,"slug":"tophat","name":"Top Hat","model":"Admiral","price":150},{"id":104,"slug":"toy","name":"Toy Bear","model":"Angel","price":200},{"id":105,"slug":"trappedheart","name":"Trapped Heart","model":"Amethyst","price":250},{"id":106,"slug":"trophy","name":"Victory Cup","model":"Bamboo","price":350},{"id":107,"slug":"valentinebox","name":"Valentine Box","model":"Alicorn","price":500},{"id":108,"slug":"vintagecigar","name":"Vintage Cigar","model":"Ashen","price":750},{"id":109,"slug":"voodoodoll","name":"Voodoo Doll","model":"Anubis","price":1000},{"id":110,"slug":"westwallet","name":"West Wallet","model":"Amethyst","price":1500},{"id":111,"slug":"whipcupcake","name":"Whip Cupcake","model":"Blueberry","price":2500},{"id":112,"slug":"winterwreath","name":"Winter Wreath","model":"Amethyst","price":5000},{"id":113,"slug":"witchhat","name":"Witch Hat","model":"Alchemist","price":15},{"id":114,"slug":"xmastree","name":"Xmas Stocking","model":"Amethyst","price":25},{"id":115,"slug":"zeushelm","name":"Zeus Helm","model":"Ares","price":35},{"id":116,"slug":"xmasball","name":"Holiday Ball","model":"Bubblegum","price":50},{"id":117,"slug":"plague","name":"Plague Doctor","model":"Ashen","price":75},{"id":118,"slug":"springbasket","name":"Spring Basket","model":"Bunny","price":100},{"id":119,"slug":"easterbunny","name":"Easter Bunny","model":"Cotton","price":150},{"id":120,"slug":"gemclock","name":"Gem Clock","model":"Amber","price":200},{"id":121,"slug":"pepecap","name":"Pepe Cap","model":"Classic","price":250},{"id":122,"slug":"preciouspeach","name":"Precious Peach","model":"Amber","price":350},{"id":123,"slug":"sakurabranch","name":"Sakura Branch","model":"Bloom","price":500},{"id":124,"slug":"skyrocket","name":"Sky Rocket","model":"Nova","price":750}];

  const t = (key) => DICT[state.lang][key] || key;
  const locale = () => (state.lang === "en" ? "en-US" : "ru-RU");
  const num = (value) => Number(value || 0).toLocaleString(locale(), { maximumFractionDigits: 0 });
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[char]));
  const icon = (name, cls = "icon") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;

  function giftImg(gift, cls = "") {
    const src = `https://cdn.changes.tg/gifts/models/${encodeURIComponent(gift.name)}/png/${encodeURIComponent(gift.model)}.png`;
    return `<img class="${cls}" src="${esc(src)}" alt="${esc(gift.name)}" loading="lazy" decoding="async" onerror="this.style.display='none'">`;
  }

  let toastTimer;
  function toast(message) {
    toastRoot.innerHTML = `<div class="toast">${esc(message)}</div>`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastRoot.innerHTML = ""; }, 2400);
  }

  async function copyText(value) {
    const text = String(value || "");
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast(t("copied"));
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast(t("copied")); } catch (e) { toast(text); }
      ta.remove();
    }
  }

  async function loadConfig() {
    try {
      const res = await fetch("/api/market/config", { headers: { "Accept": "application/json" } });
      if (res.ok) {
        const data = await res.json();
        state.config = { ...state.config, ...data };
      }
    } catch (_) {}
  }

  function header() {
    return `
      <div class="m-head">
        <div class="brand"><img class="brand-logo" src="/assets/atlanta-logo.png" alt="ATLANTA"></div>
        <button class="lang-btn" data-action="lang">${esc(t("langShort"))}</button>
      </div>`;
  }

  function filtered() {
    const query = state.query.trim().toLowerCase();
    const items = GIFTS.filter((gift) => !query || (gift.name + " " + gift.model).toLowerCase().includes(query));
    if (state.sort === "priceLow") items.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name));
    else if (state.sort === "priceHigh") items.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name));
    else if (state.sort === "name") items.sort((a, b) => a.name.localeCompare(b.name));
    return items;
  }

  function giftCard(gift) {
    return `
      <article class="gift-card" data-gift="${gift.id}">
        <div class="gift-art">${giftImg(gift)}</div>
        <div class="gift-body">
          <b>${esc(gift.name)}</b>
          <small>${esc(gift.model)}</small>
          <div class="gift-price"><b>${num(gift.price)} GRAM</b></div>
        </div>
      </article>`;
  }

  function renderStore() {
    const items = filtered();
    return `
      ${header()}
      <div class="m-tools">
        <div class="search-wrap">${icon("search")}
          <input class="search-input" id="marketSearch" type="text" value="${esc(state.query)}" placeholder="${esc(t("search"))}">
        </div>
        <div class="sort-row">
          <div class="sort-links">
            ${["popular","priceLow","priceHigh","name"].map((key) =>
              `<button class="sort-link ${state.sort === key ? "active" : ""}" data-sort="${key}">${esc(t("sort" + key.charAt(0).toUpperCase() + key.slice(1)))}</button>`
            ).join("")}
          </div>
        </div>
      </div>
      <div class="m-section-head"><h2>${esc(t("catalogue"))}</h2><span>${items.length} ${esc(t("found"))}</span></div>
      ${items.length ? `<div class="gift-grid">${items.map(giftCard).join("")}</div>` : `<div class="empty">${esc(t("empty"))}</div>`}`;
  }

  function renderCollections() {
    const groups = [...new Set(GIFTS.map((g) => g.name))];
    return `
      ${header()}
      <div class="m-section-head"><h2>${esc(t("collections"))}</h2><span>${groups.length}</span></div>
      <div class="gift-grid">
        ${groups.map((name) => {
          const list = GIFTS.filter((g) => g.name === name);
          const min = Math.min(...list.map((g) => g.price));
          const cover = list[0];
          return `
            <article class="gift-card" data-collection="${esc(name)}">
              <div class="gift-art">${giftImg(cover)}</div>
              <div class="gift-body"><b>${esc(name)}</b><small>${list.length} ${esc(t("gifts"))}</small>
                <div class="gift-price"><b>от ${num(min)} GRAM</b></div>
              </div>
            </article>`;
        }).join("")}
      </div>`;
  }

  function renderTopup() {
    const addr = String(state.config.gram_receive_address || "").trim();
    const comment = String(state.config.gram_receive_comment || "ATLANTA GRAM topup").trim();
    return `
      ${header()}
      <div class="m-section-head"><h2>${esc(t("topupTitle"))}</h2></div>
      <div class="topup-card">
        <p class="topup-hint">${esc(t("topupHint"))}</p>
        ${addr ? `
          <div class="topup-field">
            <span class="topup-label">${esc(t("walletAddress"))}</span>
            <div class="topup-value">${esc(addr)}</div>
            <button class="btn-secondary" data-action="copy-addr" data-copy="${esc(addr)}">${esc(t("copy"))}</button>
          </div>
          <div class="topup-field">
            <span class="topup-label">${esc(t("comment"))}</span>
            <div class="topup-value">${esc(comment)}</div>
            <button class="btn-secondary" data-action="copy-comment" data-copy="${esc(comment)}">${esc(t("copy"))}</button>
          </div>
        ` : `<div class="empty">${esc(t("noAddress"))}</div>`}
      </div>
      <div class="topup-card" style="margin-top:14px">
        <h3 class="topup-sub">${esc(t("depositGift"))}</h3>
        <p class="topup-hint">${esc(t("depositGiftHint"))}</p>
        ${state.config.gift_receive_username ? `
          <div class="topup-field">
            <span class="topup-label">${esc(t("receiveAccount"))}</span>
            <div class="topup-value">@${esc(state.config.gift_receive_username)}</div>
            <button class="btn-secondary" data-action="open-account" data-url="https://t.me/${esc(state.config.gift_receive_username)}">${esc(t("openAccount"))}</button>
          </div>
        ` : `<div class="empty">${esc(t("noAccount"))}</div>`}
      </div>`;
  }

  function renderProfile() {
    return `
      ${header()}
      <div class="m-section-head"><h2>${esc(t("myGifts"))}</h2><span>0</span></div>
      <div class="empty">${esc(t("emptyGifts"))}</div>
      <button class="btn-main" data-action="to-store">${esc(t("toStore"))}</button>`;
  }

  function render() {
    document.documentElement.lang = state.lang;
    const screens = { store: renderStore, collections: renderCollections, topup: renderTopup, profile: renderProfile };
    root.innerHTML = (screens[state.tab] || renderStore)() + `
      <nav class="bottom-nav">
        ${[["store","gift","store"],["collections","grid","collections"],["topup","wallet","topup"],["profile","user","profile"]].map(([tab,ico,label]) => `
          <button class="nav-btn ${state.tab === tab ? "active" : ""}" data-tab="${tab}">${icon(ico)}<span>${esc(t(label))}</span></button>
        `).join("")}
      </nav>`;
  }

  function closeSheet() { modalRoot.innerHTML = ""; state.selected = null; }

  function openSheet(id) {
    const gift = GIFTS.find((item) => item.id === Number(id));
    if (!gift) return;
    state.selected = gift;
    modalRoot.innerHTML = `
      <div class="sheet-back" data-action="close-sheet">
        <div class="sheet" data-sheet>
          <div class="sheet-grab"></div>
          <div class="sheet-top">
            <div><h3>${esc(gift.name)}</h3><small>${esc(gift.model)}</small></div>
            <button class="icon-btn" data-action="close-sheet">${icon("x")}</button>
          </div>
          <div class="sheet-art">${giftImg(gift)}</div>
          <div class="sheet-rows">
            <div class="sheet-row"><span>${esc(t("price"))}</span><b>${num(gift.price)} GRAM</b></div>
            <div class="sheet-row"><span>${esc(t("model"))}</span><b>${esc(gift.model)}</b></div>
            <div class="sheet-row"><span>${esc(t("collection"))}</span><b>${esc(gift.name)}</b></div>
          </div>
          <button class="btn-main" data-action="close-sheet-btn">${esc(t("close"))}</button>
        </div>
      </div>`;
  }

  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-action='lang']")) { state.lang = state.lang === "ru" ? "en" : "ru"; render(); return; }
    const tabBtn = event.target.closest("[data-tab]");
    if (tabBtn) { state.tab = tabBtn.dataset.tab; render(); window.scrollTo({ top: 0, behavior: "instant" }); return; }
    const sortBtn = event.target.closest("[data-sort]");
    if (sortBtn) { state.sort = sortBtn.dataset.sort; render(); return; }
    if (event.target.closest("[data-action='to-store']")) { state.tab = "store"; render(); window.scrollTo({ top: 0, behavior: "instant" }); return; }
    const copyBtn = event.target.closest("[data-copy]");
    if (copyBtn) { copyText(copyBtn.dataset.copy || ""); return; }
    const openBtn = event.target.closest("[data-action='open-account']");
    if (openBtn) {
      const url = openBtn.dataset.url || "";
      try { if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, "_blank"); }
      catch (_) { window.location.href = url; }
      return;
    }
    const col = event.target.closest("[data-collection]");
    if (col) { state.tab = "store"; state.query = col.dataset.collection; render(); window.scrollTo({ top: 0, behavior: "instant" }); return; }
    const card = event.target.closest("[data-gift]");
    if (card) openSheet(card.dataset.gift);
  });

  root.addEventListener("input", (event) => {
    if (event.target.id !== "marketSearch") return;
    const caret = event.target.selectionStart;
    state.query = event.target.value;
    render();
    const input = document.getElementById("marketSearch");
    if (input) { input.focus(); input.setSelectionRange(caret, caret); }
  });

  modalRoot.addEventListener("click", (event) => {
    if (event.target.closest("[data-action='close-sheet-btn']")) { closeSheet(); return; }
    const close = event.target.closest("[data-action='close-sheet']");
    if (close && (close === event.target || close.classList.contains("sheet-back") || close.classList.contains("icon-btn"))) closeSheet();
  });

  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeSheet(); });
  try { tg?.ready(); tg?.expand(); tg?.requestFullscreen?.(); } catch (_) {}
  loadConfig().finally(render);
})();
