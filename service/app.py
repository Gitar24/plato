"""O serviço do Plato: lê os feeds, pede a análise ao LLM, grava a nota no Obsidian
e deixa a notícia na fila até o pet falar."""
import json, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import feedparser, httpx
from apscheduler.schedulers.background import BackgroundScheduler

import config, llm, store, vault

scheduler = BackgroundScheduler()
JOB = "cycle"


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def next_unseen(cfg):
    """Pega a próxima notícia que ainda não vimos. Passa um feed de cada vez, da mais nova para a mais antiga."""
    lists = []
    for feed in cfg["feeds"]:
        try:
            raw = httpx.get(feed["url"], timeout=20, follow_redirects=True,
                            headers={"User-Agent": "plato/0.1"}).content
            entries = feedparser.parse(raw).entries[:15]
            lists.append([(feed, e) for e in entries])
        except Exception as e:
            print(f"[feed] {feed['name']}: {e}")
    for i in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if i < len(l):
                feed, e = l[i]
                iid = store.item_id(e.get("link"), e.get("title", ""))
                if not store.is_seen(iid):
                    return iid, feed, e
    return None


def cycle():
    cfg = config.load()
    limit = cfg.get("max_pending", 5)
    waiting = store.pending_count()
    if waiting >= limit:
        # a fila encheu: só voltamos a coletar depois que o pet falar o que está esperando
        print(f"[news] coleta pausada: {waiting} notícias esperando para serem faladas (limite {limit})")
        schedule(cfg, False)
        return
    found = next_unseen(cfg)
    priority = False
    if found:
        iid, feed, e = found
        title = strip_html(e.get("title", "Sem título"))
        text = strip_html(e.get("summary", ""))
        known = [r["title"] for r in store.recent(30)]
        info = llm.analyze(cfg, title, text, known) or {}
        if not info and llm.has_key(cfg):
            # o LLM não respondeu (cota ou demora). Em vez de gravar um texto genérico, tentamos de novo mais cedo
            print(f"[news] análise falhou para '{title}', tentando de novo no próximo ciclo")
            schedule(cfg, True)
            return
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
        store.mark(iid, {"title": name, "summary": summary, "link": e.get("link", "")})
        store.add_pending({"title": name, "title_pt": info.get("title_pt") or title,
                           "comment": info.get("comment") or summary[:260],
                           "summary": summary, "source": feed["name"], "link": e.get("link", ""),
                           "priority": priority})
        print(f"[news] {name} (prioridade={priority}, relações={related})")
    else:
        print("[news] nada novo")
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
            news = store.pop_pending()
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
        if self.path != "/chat":
            return self._send(404, {})
        n = int(self.headers.get("Content-Length", 0))
        msg = json.loads(self.rfile.read(n) or b"{}").get("message", "")
        cfg = config.load()
        ctx = "\n".join(f"- {r['title']}: {r['summary']}" for r in store.recent(10)) or "(nenhuma ainda)"
        reply = llm.chat(cfg, ctx, Handler.history[-10:], msg)
        # guarda só as últimas 10 mensagens, que são as que vão para o LLM
        turn = [{"role": "user", "content": msg}, {"role": "assistant", "content": reply}]
        Handler.history = (Handler.history + turn)[-10:]
        self._send(200, {"reply": reply})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    cfg = config.load()
    first = cfg["active_intervals"]["normal_seconds"]
    scheduler.add_job(cycle, "interval", seconds=first, id=JOB, max_instances=1, coalesce=True)
    scheduler.start()
    threading.Thread(target=cycle, daemon=True).start()  # busca a primeira notícia já na partida
    print(f"[start] modo={cfg['mode']} intervalos={cfg['active_intervals']}")
    ThreadingHTTPServer(("0.0.0.0", 8765), Handler).serve_forever()
