"""O serviço do Plato: lê os feeds, pede a análise ao LLM, grava a nota no Obsidian
e deixa a notícia na fila até o pet falar."""
import calendar, json, os, re, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import feedparser, httpx
from apscheduler.schedulers.background import BackgroundScheduler

import config, llm, store, vault

scheduler = BackgroundScheduler()
JOB = "cycle"
ATTEMPTS = 3  # falhas por notícia antes de desistir dela
CALLS_PER_CYCLE = 3  # chamadas ao LLM por ciclo, ao pular repetidas ou falhas


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def max_age(cfg):
    return cfg.get("max_age_days", 4) * 86400


def published(e):
    """Data de publicação (ou de atualização) em segundos, ou None se o feed não disser."""
    parsed = e.get("published_parsed") or e.get("updated_parsed")
    return calendar.timegm(parsed) if parsed else None


def candidates(cfg):
    """Notícias novas e dentro do prazo, por fonte, da mais nova para a mais antiga."""
    limit = time.time() - max_age(cfg)
    found = {}
    for feed in cfg["feeds"]:
        try:
            raw = httpx.get(feed["url"], timeout=20, follow_redirects=True,
                            headers={"User-Agent": "plato/0.1"}).content
            for e in feedparser.parse(raw).entries:
                date = published(e)
                if date is None or date < limit:
                    continue
                iid = store.item_id(e.get("link"), e.get("title", ""))
                if not store.is_seen(iid):
                    found.setdefault(feed["name"], []).append((date, iid, feed, e))
        except Exception as e:
            print(f"[feed] {feed['name']}: {e}")
    for items in found.values():
        items.sort(key=lambda c: c[0], reverse=True)
    return found


def next_unseen(found):
    """Tira a notícia mais nova da fonte usada há mais tempo."""
    names = [n for n in found if found[n]]
    if not names:
        return None
    used = store.last_used()
    return found[min(names, key=lambda n: used.get(n, 0))].pop(0)


def same_title(a, b):
    x, y = vault.keywords(a), vault.keywords(b)
    return bool(x) and len(x & y) / len(x | y) >= 0.8


def cycle():
    cfg = config.load()
    limit = cfg.get("max_pending", 5)
    store.peek_pending(max_age(cfg))  # limpa as vencidas antes de contar a fila
    waiting = store.pending_count()
    if waiting >= limit:
        # a fila encheu: só voltamos a coletar depois que o pet falar o que está esperando
        print(f"[news] coleta pausada: {waiting} notícias esperando para serem faladas (limite {limit})")
        schedule(cfg, False)
        return
    found = candidates(cfg)
    calls = 0
    while calls < CALLS_PER_CYCLE:
        item = next_unseen(found)
        if not item:
            print("[news] nada novo")
            break
        date, iid, feed, e = item
        title = strip_html(e.get("title", "Sem título"))
        text = strip_html(e.get("summary", ""))
        recent = store.since(max_age(cfg))
        known = [r["title"] for r in recent]
        if not llm.has_key(cfg) and any(same_title(title, k) for k in known):
            print(f"[news] repetida, pulada: {title}")
            store.skip(iid)
            continue
        calls += 1
        try:
            info = llm.analyze(cfg, title, text, known)
        except llm.Unusable as err:
            total = store.fail(iid)
            print(f"[news] análise falhou ({total}/{ATTEMPTS}) para '{title}': {err}")
            if total < ATTEMPTS:
                return schedule(cfg, True)
            store.skip(iid)
            continue
        if info is None and llm.has_key(cfg):
            # o LLM está fora (cota, rede ou demora). Não conta contra a notícia
            print("[news] LLM indisponível, tentando de novo no próximo ciclo")
            return schedule(cfg, True)
        info = info or {}
        if info.get("duplicate_of") in known:
            print(f"[news] mesmo fato de '{info['duplicate_of']}', pulada: {title}")
            store.skip(iid)
            continue
        store.use_source(feed["name"])
        return publish(cfg, iid, date, feed, e, title, text, known, info)
    schedule(cfg, False)


def publish(cfg, iid, date, feed, e, title, text, known, info):
    """Grava a nota e põe a notícia na fila."""
    if text.startswith("Article URL:") or text.startswith("Comments URL:"):
        text = ""  # o "resumo" do Hacker News só traz links, não serve
    summary = info.get("summary") or text[:400] or title
    category = info.get("category") or feed["category"]
    related = [r for r in info.get("related", []) if r in known]
    if not related:
        related = vault.fallback_related(title, known, cfg["max_related"])
    related = related[: cfg["max_related"]]
    kw_hit = any(k in title.lower() for k in cfg["priority_keywords"])
    priority = bool(info.get("priority")) or bool(related) or kw_hit
    name = vault.write_note(cfg, title=title, summary=summary, source=feed["name"],
                            category=category, link=e.get("link", ""), related=related,
                            title_pt=info.get("title_pt", ""))
    store.mark(iid, {"title": name, "title_pt": info.get("title_pt", ""), "summary": summary,
                     "link": e.get("link", "")})
    store.add_pending({"id": iid, "published": date,
                       "title": name, "title_pt": info.get("title_pt") or title,
                       "comment": info.get("comment") or summary[:260],
                       "summary": summary, "source": feed["name"], "link": e.get("link", ""),
                       "priority": priority})
    print(f"[news] {name} (prioridade={priority}, relações={related})")
    schedule(cfg, priority)


def schedule(cfg, priority):
    iv = cfg["active_intervals"]
    seconds = iv["priority_seconds"] if priority else iv["normal_seconds"]
    scheduler.reschedule_job(JOB, trigger="interval", seconds=seconds)
    print(f"[sched] modo={cfg['mode']} próximo em {seconds}s")


class Handler(BaseHTTPRequestHandler):
    history = []

    def _send(self, code, body=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/next":
            news = store.peek_pending(max_age(config.load()))
            if news:
                self._send(200, news)
            else:
                self._send(204)
        elif self.path == "/health":
            self._send(200, {"ok": True, "mode": config.load()["mode"],
                             "pending": store.pending_count()})
        else:
            self._send(404, {})

    def do_POST(self):
        if self.path not in ("/chat", "/ack"):
            return self._send(404, {})
        # só JSON: assim uma página aberta no navegador não consegue chamar a API às escondidas
        if self.headers.get_content_type() != "application/json":
            return self._send(415, {})
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/ack":
            store.ack(body.get("id"))
            return self._send(200, {"ok": True})
        msg = body.get("message", "")
        cfg = config.load()
        ctx = "\n".join(f"- {r['title']}: {r.get('summary', '')}"
                        for r in store.context(msg)) or "(nenhuma ainda)"
        reply = llm.chat(cfg, ctx, Handler.history[-10:], msg)
        # guarda só as últimas 10 mensagens, que são as que vão para o LLM
        turn = [{"role": "user", "content": msg}, {"role": "assistant", "content": reply}]
        Handler.history = (Handler.history + turn)[-10:]
        self._send(200, {"reply": reply})

    def log_message(self, *a):
        pass


def host():
    """Só este computador. O Docker define HOST=0.0.0.0 e publica a porta apenas em 127.0.0.1."""
    return os.environ.get("HOST", "127.0.0.1")


if __name__ == "__main__":
    cfg = config.load()
    first = cfg["active_intervals"]["normal_seconds"]
    scheduler.add_job(cycle, "interval", seconds=first, id=JOB, max_instances=1, coalesce=True)
    scheduler.start()
    threading.Thread(target=cycle, daemon=True).start()  # busca a primeira notícia já na partida
    print(f"[start] modo={cfg['mode']} intervalos={cfg['active_intervals']}")
    ThreadingHTTPServer((host(), 8765), Handler).serve_forever()
