// ATLANTA: статика на Cloudflare Workers, API и бот — на отдельном хосте.
// Matching static assets are served automatically; this handler gets /api/*.

function proxyToBot(request, env, url) {
  const origin = String(env.BOT_ORIGIN || "").replace(/\/+$/, "");
  if (!origin) {
    return new Response("BOT_ORIGIN is not configured", { status: 500 });
  }

  const target = new URL(url.pathname + url.search, origin);
  const upstream = new Request(target, request);

  return fetch(upstream).then((response) => {
    const headers = new Headers(response.headers);
    headers.delete("connection");
    headers.delete("keep-alive");
    headers.delete("transfer-encoding");
    headers.delete("content-encoding");
    headers.delete("content-length");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/") || url.pathname === "/health") {
      return proxyToBot(request, env, url);
    }
    return env.ASSETS.fetch(request);
  },
};
