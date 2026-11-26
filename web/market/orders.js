/* Atlanta Market — заказы на сервере ATLANTA.
 *
 * Заказ создаётся только после проверки initData и списания GRAM с баланса.
 * Сумму считает сервер по каталогу, клиент не может её подменить.
 */
(function () {
  'use strict';

  var items = [];

  function initData() {
    var tg = window.Telegram && window.Telegram.WebApp;
    return (tg && tg.initData) || '';
  }

  function headers(extra) {
    var h = Object.assign({ Accept: 'application/json' }, extra || {});
    var init = initData();
    if (init) h['X-Telegram-Init-Data'] = init;
    return h;
  }

  async function request(path, opts) {
    opts = opts || {};
    var res = await fetch('/api/market' + path, Object.assign({}, opts, { headers: headers(opts.headers) }));
    var data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      var detail = data && data.detail;
      var msg = (data && (data.message || data.error)) || (typeof detail === 'string' ? detail : '') || ('HTTP ' + res.status);
      var err = new Error(msg);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function refresh() {
    try {
      var data = await request('/orders');
      items = Array.isArray(data.items) ? data.items : [];
    } catch (e) {}
    return items;
  }

  async function create(input) {
    var data = await request('/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input || {})
    });
    if (data.order) items.unshift(data.order);
    return data.order;
  }

  function list() { return items; }

  function clear() {
    /* Журнал заказов хранится на сервере; удалять его из клиента нельзя. */
  }

  function count(type, mode) {
    return items.filter(function (o) {
      return (!type || o.type === type) && (!mode || o.mode === mode);
    }).length;
  }

  window.AtlantaOrders = {
    list: list,
    refresh: refresh,
    create: create,
    clear: clear,
    count: count,
    get items() { return items; },
    set items(value) { items = Array.isArray(value) ? value : []; }
  };
})();
