"""A memória do serviço, num JSON: o que já vimos, as notas, as falhas e a fila."""
import json, os, re, threading, hashlib, time
import config

_lock = threading.Lock()


def _path():
    return os.path.join(config.DATA_DIR, "history.json")


def _load():
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        pass
    except ValueError:
        # guarda o arquivo estragado para não escrever por cima dele
        kept = f"{_path()}.corrupt-{int(time.time())}"
        os.replace(_path(), kept)
        print(f"[store] history.json ilegível, preservado em {kept}")
    return {"seen": [], "recent": []}


def _save(d):
    """Grava num arquivo ao lado e troca de uma vez, para nunca sobrar meio arquivo."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _path())


def item_id(link, title):
    return hashlib.sha1((link or title).encode()).hexdigest()[:16]


def is_seen(iid):
    with _lock:
        return iid in _load()["seen"]


def _see(d, iid):
    d["seen"] = (d["seen"] + [iid])[-2000:]
    d.get("failures", {}).pop(iid, None)


def mark(iid, entry):
    """Notícia aceita: entra no histórico, que alimenta o chat e o controle de repetição."""
    with _lock:
        d = _load()
        _see(d, iid)
        d["recent"] = (d["recent"] + [{**entry, "added": time.time()}])[-500:]
        _save(d)


def skip(iid):
    """Notícia descartada: não volta, mas não entra no histórico."""
    with _lock:
        d = _load()
        _see(d, iid)
        _save(d)


def fail(iid):
    """Conta uma tentativa que deu errado e devolve o total."""
    with _lock:
        d = _load()
        failures = d.setdefault("failures", {})
        total = failures[iid] = failures.get(iid, 0) + 1
        d["failures"] = dict(list(failures.items())[-200:])
        _save(d)
        return total


def last_used():
    """Ordem em que as fontes foram usadas: quanto maior o número, mais recente."""
    with _lock:
        return _load().get("used", {})


def use_source(name):
    with _lock:
        d = _load()
        used = d.setdefault("used", {})
        used[name] = max(used.values(), default=0) + 1
        _save(d)


def add_pending(news):
    """Põe a notícia na fila. Fica em disco, então sobrevive a um reinício."""
    with _lock:
        d = _load()
        d.setdefault("pending", []).append(news)
        _save(d)


def peek_pending(max_age):
    """A notícia publicada mais recentemente, sem tirar da fila. As velhas (ou sem data) saem aqui."""
    with _lock:
        d = _load()
        pend = d.get("pending", [])
        limit = time.time() - max_age
        fresh = [n for n in pend if n.get("id") and n.get("published", 0) >= limit]
        if len(fresh) != len(pend):
            d["pending"] = fresh
            _save(d)
        return max(fresh, key=lambda n: n["published"], default=None)


def ack(iid):
    """O pet confirmou que falou: agora sim sai da fila."""
    with _lock:
        d = _load()
        d["pending"] = [n for n in d.get("pending", []) if n.get("id") != iid]
        _save(d)


def pending_count():
    with _lock:
        return len(_load().get("pending", []))


def recent(n=30):
    with _lock:
        return _load()["recent"][-n:]


def since(seconds):
    """Notícias aceitas nos últimos `seconds`. As antigas, sem horário, contam como recentes."""
    limit = time.time() - seconds
    with _lock:
        return [r for r in _load()["recent"] if r.get("added", limit) >= limit]


def _words(text):
    return {w for w in re.findall(r"\w{4,}", (text or "").lower())}


def context(question, latest=10, matches=5):
    """As últimas notícias, mais as antigas que têm palavras da pergunta."""
    with _lock:
        items = _load()["recent"]
    asked = _words(question)
    scored = []
    for i, r in enumerate(items[:-latest]):
        score = len(asked & _words(f"{r.get('title')} {r.get('title_pt', '')} {r.get('summary', '')}"))
        if score:
            scored.append((score, i, r))
    old = [r for _, _, r in sorted(scored, key=lambda s: s[:2], reverse=True)[:matches]]
    return old + items[-latest:]
