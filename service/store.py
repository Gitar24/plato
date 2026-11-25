"""A memória do serviço, num JSON: o que já vimos, as últimas notas e a fila."""
import json, os, threading, hashlib
import config

_lock = threading.Lock()


def _path():
    return os.path.join(config.DATA_DIR, "history.json")


def _load():
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen": [], "recent": []}


def _save(d):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def item_id(link, title):
    return hashlib.sha1((link or title).encode()).hexdigest()[:16]


def is_seen(iid):
    with _lock:
        return iid in _load()["seen"]


def mark(iid, entry):
    with _lock:
        d = _load()
        d["seen"] = (d["seen"] + [iid])[-2000:]
        d["recent"] = (d["recent"] + [entry])[-50:]
        _save(d)


def add_pending(news):
    """Põe a notícia na fila. Fica em disco, então sobrevive a um reinício."""
    with _lock:
        d = _load()
        d.setdefault("pending", []).append(news)
        _save(d)


def pop_pending():
    """Tira da fila a notícia mais antiga. Devolve None se não houver."""
    with _lock:
        d = _load()
        pend = d.get("pending", [])
        if not pend:
            return None
        news = pend.pop(0)
        d["pending"] = pend
        _save(d)
        return news


def pending_count():
    with _lock:
        return len(_load().get("pending", []))


def recent(n=30):
    with _lock:
        return _load()["recent"][-n:]
