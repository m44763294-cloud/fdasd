/* ==========================================================================
   Gumroad — RU/EN interface translation (landing + mini app)
   ========================================================================== */
(() => {
  "use strict";

  const STORAGE_KEY = "atlanta_lang";

  const getLang = () => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "ru";
    } catch (_) {
      return "ru";
    }
  };

  const setLang = (lang) => {
    const next = lang === "en" ? "en" : "ru";
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (_) {
      /* noop */
    }
    return next;
  };

  /* Russian source -> English. Keys must match rendered text exactly. */
  const DICT = {
    /* ------------------------------------------------ navigation / common */
    "Как работает": "How it works",
    "Возможности": "Features",
    "Комиссии": "Fees",
    "Безопасность": "Security",
    "Тарифы": "Pricing",
    "Открыть бота": "Open bot",
    "Начать сделку": "Start a deal",
    "Написать в поддержку": "Contact support",
    "Посмотреть мини-апп": "Open mini app",
    "Меню": "Menu",
    "Назад": "Back",
    "Обновить": "Refresh",
    "Копировать": "Copy",
    "Поделиться": "Share",
    "Открыть сделку": "Open deal",
    "Открыть в Telegram": "Open in Telegram",
    "Поддержка": "Support",
    "Профиль": "Profile",
    "Топы": "Top",
    "Главная": "Home",
    "Сделки": "Deals",
    "Создать": "Create",
    "Создать сделку": "Create deal",
    "Новая сделка": "New deal",
    "Мои сделки": "My deals",
    "Навигация": "Navigation",

    /* ------------------------------------------------------------- hero */
    "Безопасные сделки в Telegram · крипта и фиат": "Secure deals in Telegram · crypto & fiat",
    "Сделки под контролем": "Deals under control",
    "Сделка под охраной": "Deals under control",
    "Gumroad · сделки под контролем": "Gumroad · deals under control",
    "Интерфейс бота и приложения": "Bot and app interface",
    "под защитой Gumroad": "protected by Gumroad",
    "сейчас": "now",
    "Steam · 50 игр": "Steam · 50 games",
    "≈ 1 250 USD · комиссия 1,5%": "≈ 1,250 USD · fee 1.5%",
    "Сервис работает · платежи под защитой":
      "Service is running · payments are protected",
    "сделок": "deals",
    "Сделки без риска": "Deals without risk",
    "без риска": "without risk",
    "Начните": "Start",
    "уже сейчас!": "right now!",
    "Начните уже сейчас!": "Start right now!",
    "Gumroad держит оплату под защитой, пока покупатель не получит товар.":
      "Gumroad holds the payment until the buyer receives the goods.",
    "Продавец видит, что деньги уже есть. Покупатель знает, что они уйдут только после подтверждения.":
      "The seller sees the funds are there. The buyer knows they are released only after confirmation.",
    "Как это работает": "How it works",
    "комиссия в крипте": "crypto fee",
    "за создание сделки": "to create a deal",
    "арбитраж": "arbitration",
    "Без хранения данных карт · подтверждение вручную · журнал каждого действия":
      "No card data stored · manual confirmation · full action log",
    "Под защитой": "Protected",
    "Средства заблокированы": "Funds locked",
    "Продавец передал товар": "Seller delivered",
    "Подтверждение покупателя": "Buyer confirmation",
    "Подтвердить получение": "Confirm receipt",
    "Выплата продавцу": "Seller payout",
    "1 231,25 USDT · мгновенно": "1 231.25 USDT · instant",
    "Покупатель": "Buyer",
    "Продавец": "Seller",
    "Товар": "Item",
    "Создана": "Created",
    "Оплачена": "Paid",
    "Передача": "Delivery",
    "Выплата": "Payout",
    "карта": "card",
    "перевод": "transfer",
    "СБП": "SBP",
    "ЕРИП": "ERIP",

    /* ----------------------------------------------------------- factbar */
    "Крипта и фиат": "Crypto & fiat",
    "USDT, BTC, TON, рубли, тенге, гривны и другие": "USDT, BTC, TON, RUB, KZT, UAH and more",
    "прозрачная комиссия, без скрытых сборов": "transparent fee, no hidden charges",
    "арбитраж по спорным сделкам": "arbitration for disputed deals",
    "за создание и отмену сделки": "to create or cancel a deal",

    /* --------------------------------------------------------------- how */
    "Четыре шага до безопасной сделки": "Four steps to a secure deal",
    "Три шага до безопасной сделки": "Three steps to a secure deal",
    "Продавец и покупатель видят один и тот же статус. Деньги двигаются только по правилам сделки.":
      "Both sides see the same status. Money moves only by the rules of the deal.",
    "Сделка создана": "Deal created",
    "Продавец описывает товар, сумму и условия. Сервис формирует код и ссылку для покупателя.":
      "The seller describes the item, amount and terms. The service creates a code and a buyer link.",
    "Покупатель платит": "Buyer pays",
    "Оплата блокируется у Gumroad, а не уходит продавцу. В сделке появляется подтверждение: деньги под защитой.":
      "Payment is locked with Gumroad instead of going to the seller. The deal shows that funds are secured.",
    "Передача товара": "Item delivery",
    "Продавец передаёт товар или доступ и фиксирует это в сделке. Покупатель получает уведомление.":
      "The seller delivers the item or access and records it in the deal. The buyer gets a notification.",
    "Подтверждение и выплата": "Confirmation & payout",
    "Покупатель проверяет результат и подтверждает. Продавец получает деньги за вычетом комиссии.":
      "The buyer checks the result and confirms. The seller receives the amount minus the fee.",
    "Оплата под защитой": "Payment protected",
    "Деньги не уходят продавцу": "Funds don't go to the seller",
    "Деньги не уходят продавцу.": "Funds don't go to the seller.",
    "Передача": "Delivery",
    "Продавец фиксирует факт передачи, для решения возможных споров":
      "The seller records the delivery to help resolve possible disputes",
    "Продавец фиксирует факт передачи, для решения возможных споров.":
      "The seller records the delivery to help resolve possible disputes.",
    "Выплата": "Payout",
    "После подтверждения покупателем или арбитром": "After confirmation by the buyer or an arbitrator",
    "После подтверждения покупателем или арбитром.": "After confirmation by the buyer or an arbitrator.",
    "Если что-то пошло не так": "If something goes wrong",
    " — любой участник открывает спор. Арбитр изучает условия, историю сделки и доказательства, затем выплачивает средства продавцу или возвращает покупателю.":
      " — either party can open a dispute. An arbitrator reviews the terms, deal history and evidence, then pays the seller or refunds the buyer.",
    "— любой участник открывает спор. Арбитр изучает условия, историю сделки и доказательства, затем выплачивает средства продавцу или возвращает покупателю.":
      "— either party can open a dispute. An arbitrator reviews the terms, deal history and evidence, then pays the seller or refunds the buyer.",
    "Аудит": "Audit",

    /* ---------------------------------------------------------- features */
    "Всё, чтобы сделка дошла до конца": "Everything to finish the deal",
    "Не просто «перевод с подписью». Полноценный процесс с ролями, статусами и историей.":
      "Not just a transfer with a note. A full process with roles, statuses and history.",
    "Защита от недобросовестных сделок": "Protection from bad-faith deals",
    "Продавец не получит деньги, пока покупатель не подтвердит результат. Покупатель не останется без товара и денег одновременно.":
      "The seller is not paid until the buyer confirms the result. The buyer never loses both the item and the money.",
    "USDT, BTC, ETH, TON, USDC, а также рубли, гривны, тенге, доллары, евро и другие фиатные валюты. Курс для оценки показывается сразу.":
      "USDT, BTC, ETH, TON, USDC plus RUB, UAH, KZT, USD, EUR and other fiat currencies. The reference rate is shown instantly.",
    "Арбитраж": "Arbitration",
    "Спор не теряется в переписке: причина, условия и таймлайн собраны в одном месте для решения.":
      "A dispute never gets lost in chat: the reason, terms and timeline are collected in one place.",
    "Вход по ссылке": "Join by link",
    "Покупателю не нужно регистрироваться: он открывает ссылку из Telegram и сразу попадает в сделку.":
      "The buyer doesn't need to sign up: they open the Telegram link and land in the deal.",
    "Журнал действий": "Action log",
    "Каждый шаг фиксируется: кто, когда и что сделал. История не редактируется участниками.":
      "Every step is recorded: who did what and when. Participants cannot edit the history.",
    "Выплаты на кошелёк": "Wallet payouts",
    "После завершения деньги попадают на баланс Gumroad. Вывод — на адрес или реквизиты в пару кликов.":
      "After completion the money lands in the Gumroad balance. Withdraw to an address or bank details in a couple of clicks.",

    /* -------------------------------------------------------------- fees */
    "Платите только за результат": "Pay only for the result",
    "Комиссия удерживается из суммы сделки при успешной выплате. Создание, вход и отмена — бесплатно.":
      "The fee is deducted from the deal amount on a successful payout. Creating, joining and cancelling are free.",
    "Криптовалюта": "Crypto",
    "Фиат": "Fiat",
    "Минимальная комиссия — 0,30 USD в эквиваленте.": "Minimum fee — 0.30 USD equivalent.",
    "Пример расчёта": "Example calculation",
    "крипта · 1,5%": "crypto · 1.5%",
    "Сумма сделки": "Deal amount",
    "Комиссия": "Fee",
    "Продавцу": "To seller",
    "Комиссия фиксируется при создании сделки и не меняется задним числом.":
      "The fee is fixed when the deal is created and never changes retroactively.",

    /* ---------------------------------------------------------- security */
    "Деньги не у продавца. И не у покупателя.": "The money is neither with the seller nor the buyer.",
    "Пока сделка активна, оплата находится под защитой Gumroad. Доступ к ней появляется только по правилам, которые обе стороны видели заранее.":
      "While the deal is active, the payment is held by Gumroad. It is released only by rules both sides saw in advance.",
    "Ручное подтверждение": "Manual confirmation",
    "Покупатель сам подтверждает получение — автоматических списаний нет.":
      "The buyer confirms receipt personally — there are no automatic charges.",
    "Независимый арбитр": "Independent arbitrator",
    "Спор рассматривается по условиям сделки и журналу действий.":
      "A dispute is reviewed against the deal terms and the action log.",
    "Платёжные провайдеры": "Payment providers",
    "Сервис не хранит данные банковских карт и ключи от кошельков.":
      "The service never stores card data or wallet keys.",
    "Прозрачные статусы": "Transparent statuses",
    "Обе стороны видят один и тот же статус и историю изменений.":
      "Both sides see the same status and change history.",
    "Средства на время сделки находятся под защитой. Выплаты выполняются только по правилам, которые видели обе стороны.":
      "Funds stay protected during the deal. Payouts follow the terms both parties saw in advance.",

    /* --------------------------------------------------------------- faq */
    "Частые вопросы": "FAQ",
    "Не нашли ответ? Напишите в поддержку — поможем разобраться со сделкой.":
      "Didn't find an answer? Contact support — we'll help with the deal.",
    "Как работает защита оплаты?": "How does payment protection work?",
    "Gumroad временно держит деньги покупателя. Покупатель платит не продавцу напрямую, а на защищённый счёт сервиса. Продавец видит, что оплата есть, и передаёт товар. Деньги уходят продавцу только после подтверждения покупателя.":
      "Gumroad temporarily holds the buyer's money. The buyer pays the service's protected account, not the seller directly. The seller sees the payment and delivers. The money reaches the seller only after the buyer confirms.",
    "Когда продавец получает деньги?": "When does the seller get paid?",
    "Сразу после того, как покупатель нажмёт «Подтвердить получение». Выплата зачисляется на баланс Gumroad за вычетом комиссии, после чего её можно вывести на кошелёк или реквизиты.":
      "Right after the buyer taps “Confirm receipt”. The payout is credited to the Gumroad balance minus the fee, and can then be withdrawn to a wallet or bank details.",
    "Что делать, если товар не соответствует описанию?": "What if the item doesn't match the description?",
    "Не подтверждайте сделку. Откройте спор и опишите проблему: арбитр увидит условия, историю статусов и сообщения сторон. По итогам он выплатит деньги продавцу или вернёт их покупателю.":
      "Don't confirm the deal. Open a dispute and describe the problem: the arbitrator will see the terms, status history and both sides' messages, then pay the seller or refund the buyer.",
    "Какие валюты поддерживаются?": "Which currencies are supported?",
    "USDT и USDC в сети TRON, BTC, ETH, TON, а также RUB, UAH, KZT, BYN, TRY, AMD, GEL, USD и EUR. Для криптовалют показывается ориентировочная стоимость в долларах, комиссия фиксируется в валюте сделки.":
      "USDT and USDC on TRON, BTC, ETH, TON, plus RUB, UAH, KZT, BYN, TRY, AMD, GEL, USD and EUR. Crypto shows an estimated USD value; the fee is fixed in the deal currency.",
    "Сколько стоит сервис?": "How much does the service cost?",
    "1,5% от суммы сделки в криптовалюте и 2,5% в фиате, минимум 0,30 USD. Комиссия удерживается только при успешном завершении. Создание сделки, вход по ссылке и отмена — бесплатно.":
      "1.5% of the deal amount in crypto and 2.5% in fiat, minimum 0.30 USD. The fee applies only on successful completion. Creating a deal, joining by link and cancelling are free.",
    "Как покупатель попадает в сделку?": "How does the buyer join a deal?",
    "Продавец отправляет ссылку вида t.me/бот?start=deal_KST-XXXXXX. Покупатель открывает её в Telegram, нажимает «Присоединиться» и оплачивает счёт. Регистрация не нужна.":
      "The seller sends a link like t.me/bot?start=deal_KST-XXXXXX. The buyer opens it in Telegram, taps “Join” and pays the invoice. No sign-up needed.",
    "Кто хранит деньги и это законно?": "Who holds the money and is it legal?",
    "Gumroad — технологическая платформа: средства на время сделки находятся под защитой и выплачиваются только по правилам сделки. Перед коммерческим запуском нужна юридическая проверка в вашей юрисдикции.":
      "Gumroad is a technology platform: funds stay protected during the deal and are paid out only under the agreed terms. Legal review in your jurisdiction is required before launch.",

    /* --------------------------------------------------------------- cta */
    "Первый шаг — 30 секунд": "First step — 30 seconds",
    "Проведите сделку,": "Run a deal",
    "за которую не страшно": "you won't worry about",
    "Откройте Gumroad в Telegram, создайте сделку и отправьте ссылку покупателю.":
      "Open Gumroad in Telegram, create a deal and send the link to the buyer.",
    "Без регистрации": "No sign-up",
    "Арбитраж 24/7": "24/7 arbitration",

    /* ------------------------------------------------------------ footer */
    "Сервис безопасных сделок в Telegram. Деньги под защитой до подтверждения.":
      "Secure deal service in Telegram. Money is protected until confirmation.",
    "© 2026 Gumroad · Сделки под контролем": "© 2026 Gumroad · Deals under control",
    "Продукт": "Product",
    "Помощь": "Help",
    "Документы": "Legal",
    "Мини-приложение": "Mini app",
    "Telegram-бот": "Telegram bot",
    "Защищённые сделки": "Protected deals",
    "Gumroad не является банком или инвестиционной платформой. Средства на время сделки находятся под защитой сервиса.":
      "Gumroad is not a bank or an investment platform. Funds stay protected by the service during the deal.",
    "Сделано для честных сделок": "Built for fair deals",

    /* ------------------------------------------------------------- mini app */
    "С возвращением": "Welcome back",
    "Приветствуем!": "Welcome!",
    "Друг": "Friend",
    "Баланс к выводу": "Available balance",
    "Доступно после завершённых сделок": "Available after completed deals",
    "Появится после первой завершённой сделки": "Appears after your first completed deal",
    "Вывести": "Withdraw",
    "Вывод недоступен": "Withdrawal unavailable",
    "Вывод станет доступен после 3 успешных сделок.": "Withdrawal will be available after 3 successful deals.",
    "Закрыть": "Close",
    "Обновлено сейчас": "Updated now",
    "Проведено сделок": "Deals completed",
    "Оборот сервиса 13 432 USD": "Service volume 13 432 USD",
    "Успешных сделок": "Successful deals",
    "Топ участников": "Top members",
    "по сделкам": "by deals",
    "топ-100": "Top 100",
    "Пользователь скрыл информацию о себе": "User has hidden their info",
    "Деньги замораживаются до подтверждения. Продавец получает оплату после подтверждения сделки":
      "Funds are locked until confirmation. The seller receives payment after the deal is confirmed.",
    "Войти по коду": "Join by code",
    "Войти в сделку": "Join a deal",
    "по коду или ссылке": "by code or link",
    "Код сделки": "Deal code",
    "Войти": "Join",
    "Активные сделки": "Active deals",
    "Все": "All",
    "Пока тихо": "Nothing yet",
    "Создайте сделку или войдите по ссылке покупателя.":
      "Create a deal or open the buyer's link.",
    "Оплата под защитой": "Payment protected",
    "Деньги блокируются": "Funds are locked",
    "Продавец фиксирует": "Seller confirms",
    "После подтверждения": "After confirmation",
    "Активные": "Active",
    "Завершённые": "Completed",
    "Активных сделок нет": "No active deals",
    "Здесь пока пусто": "Nothing here yet",
    "Создайте сделку или откройте ссылку-приглашение.":
      "Create a deal or open the invite link.",
    "Наблюдатель": "Observer",

    /* --------------------------------------------------------- welcome */
    "1,5%": "1.5%",
    "0": "0",
    "24/7": "24/7",
    "Пропустить": "Skip",
    "Gumroad держит оплату под защитой, пока покупатель не получит товар. Продавец видит, что деньги уже есть. Покупатель знает, что они уйдут только после подтверждения.":
      "Gumroad holds the payment until the buyer receives the item. The seller sees that the money is there. The buyer knows it's paid out only after confirmation.",

    /* ----------------------------------------------------------- create */
    "Деньги под защитой Gumroad": "Money protected by Gumroad",
    "Что продаём": "What are you selling",
    "Предмет сделки": "Deal item",
    "Создать сделку может любая сторона — вы будете её владельцем.":
      "Either party can create a deal — you'll be its owner.",
    "Кто вы в сделке?": "What's your role?",
    "Я продавец": "I'm the seller",
    "Я покупатель": "I'm the buyer",
    "Покупатель опишет, что хочет купить, и оплатит после того, как продавец присоединится.":
      "The buyer describes what they want and pays once the seller joins.",
    "Название": "Title",
    "5–120 символов": "5–120 characters",
    "Например: аккаунт Steam с 50 играми": "e.g. Steam account with 50 games",
    "Категория": "Category",
    "Сумма и валюта": "Amount & currency",
    "Сумма сделки": "Deal amount",
    "Валюта": "Currency",
    "Защита действует до подтверждения покупателем.":
      "Protection lasts until the buyer confirms.",
    "Детали": "Details",
    "Описание": "Description",
    "необязательно": "optional",
    "Что входит в сделку, состояние товара, детали передачи":
      "What's included, item condition, delivery details",
    "Условия": "Terms",
    "Что считается выполнением сделки и что делать при проблеме":
      "What counts as completion and what to do if there's a problem",
    "Комиссия сервиса": "Service fee",
    "Продавец получит": "Seller receives",
    "Покупатель платит": "Buyer pays",
    "Оплата попадёт под защиту Gumroad. Продавец получит деньги только после вашего подтверждения или решения арбитра.":
      "Payment goes under Gumroad protection. The seller is paid only after your confirmation or an arbitrator's decision.",
    "Название — минимум 5 символов": "Title must be at least 5 characters",
    "Укажите сумму сделки": "Enter the deal amount",
    "Введите код сделки": "Enter the deal code",
    "Код выглядит неверно. Пример: KST-AB12CD": "That code looks wrong. Example: KST-AB12CD",
    "Комиссия": "Fee",

    /* ---------------------------------------------------------- created */
    "Отправьте ссылку покупателю. Он присоединится и оплатит счёт — деньги окажутся под защитой.":
      "Send the link to the buyer. They will join and pay the invoice — the funds become protected.",
    "Отправьте ссылку продавцу. Он присоединится к сделке, а вы оплатите счёт — деньги окажутся под защитой.":
      "Send the link to the seller. They will join the deal, then you pay the invoice — the funds become protected.",
    "Ссылка для покупателя": "Buyer link",
    "Ссылка для продавца": "Seller link",
    "Пока покупатель не оплатил, сделку можно отменить без потерь. Ссылка действует, пока сделку не займут.":
      "Until the buyer pays, the deal can be cancelled without loss. The link works until someone takes the deal.",
    "Пока продавец не присоединился, сделку можно отменить без потерь. Ссылка действует, пока сделку не займут.":
      "Until the seller joins, the deal can be cancelled without loss. The link works until someone takes the deal.",

    /* ------------------------------------------------------------- deal */
    "Ожидается": "Pending",
    "Счёт на оплату": "Payment invoice",
    "Адрес": "Address",
    "Счёт истёк": "Invoice expired",
    "Осталось": "Time left",
    "Оплатить счёт": "Pay invoice",
    "Открыть кошелёк": "Open wallet",
    "Проверить оплату": "Check payment",
    "После оплаты статус обновится автоматически в течение пары минут.":
      "After payment the status updates automatically within a couple of minutes.",
    "Пригласите покупателя": "Invite the buyer",
    "Пригласите продавца": "Invite the seller",
    "ссылка": "link",
    "История сделки": "Deal history",
    "Срок": "Deadline",
    "Завершена": "Completed",
    "Условия сделки": "Deal terms",
    "Спор": "Dispute",
    "на рассмотрении": "under review",
    "решён": "resolved",
    "Решение": "Resolution",
    "Обновить сделку": "Refresh deal",
    "Вы видите сделку как арбитр. Решение по спору доступно в блоке действий.":
      "You are viewing this deal as an arbitrator. The dispute decision is available in the actions block.",

    /* ---------------------------------------------------------- profile */
    "Аккаунт Gumroad": "Gumroad account",
    "без username": "no username",
    "Арбитр": "Arbitrator",
    "сделок": "deals",
    "завершено": "completed",
    "оборот": "volume",
    "Баланс": "Balance",
    "Баланс пуст": "Balance is empty",
    "Средства появятся после завершённой сделки.":
      "Funds will appear after a completed deal.",
    "Ещё": "More",
    "Как работает Gumroad": "How Gumroad works",
    "Арбитраж и споры": "Arbitration & disputes",
    "Gumroad не хранит данные карт и ключи кошельков. Все действия по сделке фиксируются в журнале.":
      "Gumroad never stores card data or wallet keys. Every deal action is recorded in the log.",
    "Язык": "Language",

    /* ------------------------------------------------------------ admin */
    "Нет доступа": "Access denied",
    "Сделка не открылась": "The deal failed to open",
    "Название — минимум 5 символов": "Title must be at least 5 characters",
    "Укажите сумму сделки": "Enter the deal amount",
    "Введите код сделки": "Enter the deal code",
    "Код выглядит неверно. Пример: KST-AB12CD": "That code looks wrong. Example: KST-AB12CD",
    "Раздел доступен только арбитрам.": "This section is available to arbitrators only.",
    "Арбитраж недоступен": "Arbitration unavailable",
    "Последние сделки": "Recent deals",
    "Причина не указана": "No reason provided",
    "Покупателю": "To buyer",
    "Споров нет": "No disputes",
    "Все сделки идут по плану.": "All deals are on track.",
    "Сделок пока нет": "No deals yet",
    "Здесь появятся все сделки сервиса.": "All service deals will appear here.",

    /* ------------------------------------------------------------ misc */
    "Скопировано": "Copied",
    "Не удалось скопировать": "Couldn't copy",
    "Попробовать снова": "Try again",
    "Подтвердить": "Confirm",
    "Отмена": "Cancel",
    "Не получилось": "Something went wrong",
    "Отправить": "Send",
    "Комментарий": "Comment",
    "Опишите ситуацию": "Describe the situation",
    "Опишите подробнее — минимум 10 символов": "Please add more detail — at least 10 characters",
    "Сумма": "Amount",
    "Адрес или реквизиты": "Address or details",
    "Телефон СБП или карта": "SBP phone or card",
    "Адрес кошелька": "Wallet address",
    "Вывод отправлен": "Withdrawal submitted",
    "Понятно": "Got it",
    "Вы присоединились к сделке": "You joined the deal",
    "Счёт сформирован": "Invoice created",
    "Демо-оплата": "Demo payment",
    "Сымитировать зачисление средств? В продакшене этот шаг выполняет платёжный провайдер.":
      "Simulate the incoming payment? In production this step is handled by the payment provider.",
    "Подтвердить оплату": "Confirm payment",
    "Деньги под защитой": "Funds secured",
    "Товар передан": "Item delivered",
    "Покупатель получит уведомление и сможет проверить результат.":
      "The buyer will get a notification and can check the result.",
    "Подтвердить передачу": "Confirm delivery",
    "Что передано": "What was delivered",
    "Передача отмечена": "Delivery recorded",
    "Подтвердить получение?": "Confirm receipt?",
    "После подтверждения деньги уйдут продавцу. Отменить это действие нельзя — при проблеме сначала откройте спор.":
      "After confirmation the money goes to the seller. This cannot be undone — if there's a problem, open a dispute first.",
    "Да, всё получил": "Yes, received",
    "Сделка завершена": "Deal completed",
    "Отменить сделку?": "Cancel the deal?",
    "Сделка будет закрыта без движения средств. Это возможно, пока покупатель не оплатил.":
      "The deal will be closed without moving funds. This is possible until the buyer pays.",
    "Отменить сделку": "Cancel deal",
    "Причина": "Reason",
    "Сделка отменена": "Deal cancelled",
    "Открыть спор": "Open dispute",
    "Опишите проблему. Арбитр увидит условия сделки, историю и ваш комментарий.":
      "Describe the problem. The arbitrator will see the deal terms, history and your comment.",
    "Передать арбитру": "Send to arbitration",
    "Что случилось": "What happened",
    "Спор открыт, арбитр подключится": "Dispute opened; an arbitrator will join",
    "Выплатить продавцу?": "Pay the seller?",
    "Вернуть покупателю?": "Refund the buyer?",
    "Сделка завершится, продавец получит сумму за вычетом комиссии.":
      "The deal will complete and the seller receives the amount minus the fee.",
    "Сделка будет закрыта возвратом средств покупателю.":
      "The deal will be closed with a refund to the buyer.",
    "Выплатить продавцу": "Pay the seller",
    "Вернуть покупателю": "Refund the buyer",
    "Комментарий арбитра": "Arbitrator comment",
    "Решение принято": "Decision made",
    "Приложение не открылось": "The app failed to open",
    "Откройте приложение через Telegram-бота Gumroad — так безопаснее.":
      "Open the app through the Gumroad Telegram bot — it's safer.",
    "Не удалось загрузить данные": "Failed to load data",

    /* ------------------------------------------- backend: statuses */
    "Ожидает покупателя": "Awaiting buyer",
    "Ожидает оплаты": "Awaiting payment",
    "Средства под защитой": "Funds secured",
    "Завершена": "Completed",
    "Отменена": "Cancelled",
    "Возврат средств": "Refunded",

    /* ------------------------------------------- backend: categories */
    "Цифровые товары": "Digital goods",
    "Аккаунты и доступы": "Accounts & access",
    "Услуги": "Services",
    "Игровое": "Gaming",
    "Товары": "Goods",
    "Другое": "Other",

    /* ------------------------------------------- backend: next steps */
    "Отправьте ссылку покупателю — он присоединится к сделке.":
      "Send the link to the buyer — they will join the deal.",
    "Сделка ждёт покупателя. Вы можете занять это место.":
      "The deal is waiting for a buyer. You can take this spot.",
    "Оплатите счёт: деньги заблокируются и уйдут продавцу только после вашего подтверждения.":
      "Pay the invoice: funds are locked and go to the seller only after your confirmation.",
    "Ждём оплату покупателя. После зачисления средства будут под защитой.":
      "Waiting for the buyer's payment. Once received, funds become protected.",
    "Покупатель уже присоединился и оплачивает сделку.":
      "The buyer has joined and is paying for the deal.",
    "Деньги под защитой. Передайте товар и отметьте это в сделке.":
      "Funds are secured. Deliver the item and mark it in the deal.",
    "Деньги заблокированы. Проверьте товар и подтвердите получение.":
      "Funds are locked. Check the item and confirm receipt.",
    "Средства заблокированы до подтверждения покупателем.":
      "Funds are locked until the buyer confirms.",
    "Продавец отметил передачу. Подтвердите получение, чтобы выплатить ему деньги.":
      "The seller marked the delivery. Confirm receipt to release the payment.",
    "Ждём подтверждения покупателя.": "Waiting for the buyer's confirmation.",
    "Сделка завершена, средства выплачены продавцу.":
      "The deal is complete; funds were paid to the seller.",
    "Спор передан арбитру. Решение будет принято по условиям сделки.":
      "The dispute is with an arbitrator. A decision will follow the deal terms.",
    "Сделка отменена. Средства не списывались.":
      "The deal was cancelled. No funds were charged.",
    "Арбитр вернул средства покупателю.": "The arbitrator refunded the buyer.",

    /* ------------------------------------------- backend: actions */
    "Присоединиться к сделке": "Join the deal",
    "Оплатить сделку": "Pay for the deal",
    "Оплатить с баланса": "Pay from balance",
    "Оплата с баланса": "Balance payment",
    "Оплатить": "Pay",
    "Подтвердите оплату сделки с баланса.": "Confirm paying for the deal from your balance.",
    "Товар передан": "Item delivered",

    /* ------------------------------------------- backend: events */
    "Покупатель присоединился к сделке": "Buyer joined the deal",
    "Счёт на оплату сформирован": "Invoice created",
    "Средства заблокированы под защитой Gumroad": "Funds secured by Gumroad",
    "Продавец отметил передачу товара": "Seller marked the item as delivered",
    "Покупатель подтвердил сделку · средства выплачены продавцу":
      "Buyer confirmed the deal · funds paid to the seller",
    "Выплата продавцу": "Payout to seller",
    "Возврат покупателю": "Refund to buyer",
    "Сделка создана": "Deal created",

    /* ------------------------------------------- backend: errors */
    "Сделка не найдена": "Deal not found",
    "Нельзя присоединиться к собственной сделке": "You can't join your own deal",
    "К сделке уже присоединился покупатель": "A buyer has already joined this deal",
    "Сделка уже занята": "This deal is already taken",
    "Оплатить сделку может только покупатель": "Only the buyer can pay for this deal",
    "Сделка не ожидает оплаты": "This deal isn't awaiting payment",
    "Только покупатель может оплатить сделку": "Only the buyer can pay for this deal",
    "Отметить передачу может только продавец": "Only the seller can mark the delivery",
    "Передать товар можно только после оплаты": "The item can be delivered only after payment",
    "Подтвердить сделку может только покупатель": "Only the buyer can confirm the deal",
    "Сейчас подтверждение недоступно": "Confirmation isn't available right now",
    "Отменить сделку может только участник": "Only a participant can cancel the deal",
    "Оплаченную сделку нельзя просто отменить — откройте спор":
      "A paid deal can't simply be cancelled — open a dispute",
    "Открыть спор может только участник": "Only a participant can open a dispute",
    "Спор можно открыть только по оплаченной сделке":
      "A dispute can be opened only for a paid deal",
    "Опишите проблему — минимум 10 символов": "Describe the problem — at least 10 characters",
    "Недостаточно прав": "Not enough permissions",
    "Некорректное решение арбитра": "Invalid arbitrator decision",
    "Сделка не находится в споре": "The deal isn't in dispute",
    "Недостаточно средств на балансе": "Not enough funds in the balance",
    "Укажите корректные реквизиты получателя": "Enter valid recipient details",
    "Сумма должна быть больше нуля": "The amount must be greater than zero",
    "Недостаточно средств": "Not enough funds",
    "Название сделки — от 5 до 120 символов": "Deal title must be 5–120 characters",
    "Описание — не длиннее 1500 символов": "Description must be at most 1500 characters",
    "Условия — не длиннее 3000 символов": "Terms must be at most 3000 characters",
    "Неизвестная валюта": "Unknown currency",
    "Минимальная сумма сделки — эквивалент 1 USD": "Minimum deal amount is the equivalent of 1 USD",
    "Статус сделки уже изменился": "The deal status has already changed",
    "Не удалось создать код сделки, попробуйте ещё раз":
      "Couldn't create a deal code, please try again",
    "Демо-оплата отключена": "Demo payment is disabled",
    "Бот не настроен: проверка Telegram недоступна":
      "The bot isn't configured: Telegram verification is unavailable",
    "Подпись Telegram недействительна": "Invalid Telegram signature",
    "В данных Telegram нет пользователя": "No user in the Telegram data",
    "Откройте приложение внутри Telegram": "Open the app inside Telegram",
  };

  const PATTERNS = [
    [/^(\d+)\s+завершено$/, "$1 completed"],
    [/^(\d+)\s+всего$/, "$1 total"],
    [/^Все\s+(\d+)$/, "All $1"],
    [/^Активные\s+(\d+)$/, "Active $1"],
    [/^Завершённые\s+(\d+)$/, "Completed $1"],
    [/^Споры\s+(\d+)$/, "Disputes $1"],
    [/^(\d+)\s+открытых споров$/, "$1 open disputes"],
    [/^Вывод\s+([A-Z]{3,5})$/, "Withdraw $1"],
    [/^Спишем\s+(.+)\s+с вашего баланса и поставим под защиту сделки\.$/, "We'll charge $1 from your balance and place it under protection."],
    [/^с\s+(.+)$/, "since $1"],
    [/^Комиссия\s+([\d.,]+)%\s+·\s+продавцу\s+(.+)$/, "Fee $1% · seller gets $2"],
    [/^≈\s*(.+)\s*·\s*комиссия\s*([\d.,]+)%$/, "≈ $1 · fee $2%"],
    [/^Фиат\s+·\s+(.+)\s+·\s+комиссия\s+([\d.]+)%$/, "Fiat · $1 · fee $2%"],
    [/^Крипта\s+·\s+(.+)\s+·\s+комиссия\s+([\d.]+)%\s+·\s+≈\s+(.+)$/, "Crypto · $1 · fee $2% · ≈ $3"],
    [/^Открыт спор:\s*(.+)$/, "Dispute opened: $1"],
    [/^Сделка отменена:\s*(.+)$/, "Deal cancelled: $1"],
    [/^Продавец отметил передачу товара:\s*(.+)$/, "Seller marked delivery: $1"],
    [/^Выплата продавцу:\s*(.+)$/, "Payout to seller: $1"],
    [/^Возврат покупателю:\s*(.+)$/, "Refund to buyer: $1"],
    [/^Минимальная сумма —\s*(.+)$/, "Minimum amount — $1"],
    [/^Платёжный провайдер недоступен:\s*(.+)$/, "Payment provider unavailable: $1"],
    [/^Вывод не выполнен:\s*(.+)$/, "Withdrawal failed: $1"],
    [/^Ошибка\s+(\d+)$/, "Error $1"],
    [/^Сделка Gumroad:\s*(.+)$/, "Gumroad deal: $1"],
    [/^Продавец\s*·\s*(.+)$/, "Seller · $1"],
    [/^Покупатель\s*·\s*(.+)$/, "Buyer · $1"],
  ];

  const META = {
    landing: {
      ru: {
        title: "Gumroad — сделки под контролем",
        description:
          "Gumroad — безопасные сделки в Telegram. Покупатель платит, деньги блокируются, продавец получает их только после подтверждения. Крипта и фиат, арбитраж 24/7.",
      },
      en: {
        title: "Gumroad — deals under control",
        description:
          "Gumroad — secure deals in Telegram. The buyer pays, funds are locked, and the seller is paid only after confirmation. Crypto and fiat, 24/7 arbitration.",
      },
    },
    app: {
      ru: {
        title: "Gumroad — сделки под контролем",
        description:
          "Безопасные сделки в Telegram: крипта и фиат, арбитраж, прозрачные статусы.",
      },
      en: {
        title: "Gumroad — deals under control",
        description:
          "Secure deals in Telegram: crypto and fiat, arbitration, transparent statuses.",
      },
    },
  };

  function translateString(value) {
    const text = String(value ?? "");
    const trimmed = text.trim();
    if (!trimmed) return text;
    if (Object.prototype.hasOwnProperty.call(DICT, trimmed)) {
      return text.replace(trimmed, DICT[trimmed]);
    }
    for (const [pattern, replacement] of PATTERNS) {
      if (pattern.test(trimmed)) {
        const next = trimmed.replace(pattern, replacement);
        return text.replace(trimmed, next);
      }
    }
    return text;
  }

  const t = (value) => (getLang() === "en" ? translateString(value) : String(value ?? ""));

  /* ------------------------------------------------------------- DOM walk */
  const textState = new WeakMap();
  const attrState = new WeakMap();
  const ATTRS = ["placeholder", "aria-label", "title"];
  let applying = false;

  function applyTextNode(node) {
    const lang = getLang();
    let entry = textState.get(node);
    const current = node.nodeValue || "";
    if (!entry || (entry.last !== undefined && current !== entry.last)) {
      entry = { src: current, last: current };
      textState.set(node, entry);
    }
    const next = lang === "en" ? translateString(entry.src) : entry.src;
    entry.last = next;
    if (node.nodeValue !== next) node.nodeValue = next;
  }

  function applyAttr(element, attr) {
    if (!element || !element.getAttribute) return;
    const lang = getLang();
    const current = element.getAttribute(attr);
    if (current === null) return;
    let map = attrState.get(element);
    if (!map) {
      map = {};
      attrState.set(element, map);
    }
    let entry = map[attr];
    if (!entry || (entry.last !== undefined && current !== entry.last)) {
      entry = { src: current, last: current };
      map[attr] = entry;
    }
    const next = lang === "en" ? translateString(entry.src) : entry.src;
    entry.last = next;
    if (current !== next) element.setAttribute(attr, next);
  }

  function applyNode(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      applyTextNode(root);
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
    const element = root.nodeType === Node.ELEMENT_NODE ? root : null;
    if (element && element.closest?.(".no-i18n")) return;
    if (element) ATTRS.forEach((attr) => applyAttr(element, attr));
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode(node) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          if (node.classList?.contains("no-i18n")) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_SKIP;
        }
        const parent = node.parentElement;
        if (!parent || parent.closest(".no-i18n, script, style, code, pre")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let node = walker.nextNode();
    while (node) {
      if (node.nodeType === Node.TEXT_NODE) applyTextNode(node);
      node = walker.nextNode();
    }
    if (element) {
      element.querySelectorAll?.("[placeholder], [aria-label], [title]").forEach((el) => {
        ATTRS.forEach((attr) => applyAttr(el, attr));
      });
    }
  }

  function updateMeta() {
    const page = document.documentElement.dataset.page;
    const pack = META[page]?.[getLang()];
    if (!pack) return;
    document.title = pack.title;
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute("content", pack.description);
  }

  function updateSwitches() {
    const lang = getLang();
    document.querySelectorAll(".lang-switch [data-lang]").forEach((button) => {
      button.classList.toggle("active", button.dataset.lang === lang);
      button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
    });
  }

  function apply(root = document) {
    if (applying) return;
    applying = true;
    try {
      applyNode(root);
      updateMeta();
      updateSwitches();
      document.documentElement.lang = getLang() === "en" ? "en" : "ru";
    } finally {
      applying = false;
    }
  }

  function mountSwitcher(target) {
    const host = typeof target === "string" ? document.querySelector(target) : target;
    if (!host || host.querySelector(".lang-switch")) return;
    host.innerHTML = `
      <div class="lang-switch no-i18n" role="group" aria-label="Language">
        <button type="button" data-lang="ru">RU</button>
        <button type="button" data-lang="en">EN</button>
      </div>`;
    updateSwitches();
  }

  function injectStyles() {
    if (document.getElementById("atlanta-i18n-style")) return;
    const style = document.createElement("style");
    style.id = "atlanta-i18n-style";
    style.textContent = `
      .lang-switch{display:inline-flex;align-items:center;gap:2px;padding:3px;border:1px solid rgba(255,255,255,.10);border-radius:999px;background:rgba(255,255,255,.035);vertical-align:middle}
      .lang-switch button{appearance:none;border:0;background:transparent;color:#8b93a3;font:700 10px/1 Manrope,-apple-system,Segoe UI,sans-serif;letter-spacing:.10em;padding:7px 9px;border-radius:999px;cursor:pointer;transition:background .18s ease,color .18s ease}
      .lang-switch button:hover{color:#e8edf5}
      .lang-switch button.active{background:linear-gradient(135deg,#9BFFCB,#5CEBC0 48%,#3FC8FF);color:#05120d;box-shadow:0 6px 18px -8px rgba(92,235,192,.7)}
      .lang-slot{display:inline-flex;align-items:center}
    `;
    document.head.appendChild(style);
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest(".lang-switch [data-lang]");
    if (!button) return;
    const next = button.dataset.lang;
    if (next === getLang()) return;
    setLang(next);
    apply(document);
    window.dispatchEvent(new CustomEvent("atlanta:lang", { detail: { lang: next } }));
  });

  function boot() {
    injectStyles();
    document.querySelectorAll("[data-lang-switch]").forEach(mountSwitcher);
    if (getLang() === "en") apply(document);
    else updateSwitches();
    const observer = new MutationObserver((mutations) => {
      if (applying || getLang() !== "en") return;
      applying = true;
      try {
        for (const mutation of mutations) {
          if (mutation.type === "childList") {
            mutation.addedNodes.forEach((node) => applyNode(node));
          } else if (mutation.type === "characterData") {
            applyTextNode(mutation.target);
          } else if (mutation.type === "attributes") {
            applyAttr(mutation.target, mutation.attributeName);
          }
        }
      } finally {
        applying = false;
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS,
    });
  }

  window.ATLANTA_I18N = { getLang, setLang, apply, t, mountSwitcher, translateString };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
