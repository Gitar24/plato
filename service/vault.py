"""Grava as notícias como notas do Obsidian e liga umas às outras com [[links]]."""
import json, os, re, unicodedata
from datetime import datetime
import config

STOP = set("the and for with from this that what why how new para com uma uns das dos que sobre".split())


def clean_name(title):
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "", title).strip()[:120] or "Sem titulo"


def folder(cfg):
    p = os.path.join(config.VAULT_PATH, cfg.get("vault_subfolder", "Noticias"))
    os.makedirs(p, exist_ok=True)
    return p


def keywords(text):
    return {w for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", text.lower()) if w not in STOP}


def fallback_related(title, known_titles, limit):
    kw = keywords(title)
    scored = [(len(kw & keywords(t)), t) for t in known_titles]
    return [t for s, t in sorted(scored, reverse=True) if s >= 2][:limit]


def write_note(cfg, *, title, summary, source, category, link, related, title_pt=""):
    base = name = clean_name(title)
    n = 1
    while os.path.exists(os.path.join(folder(cfg), name + ".md")):
        n += 1
        name = f"{base} ({n})"
    related = [r for r in related if r != name]
    plain = unicodedata.normalize("NFKD", str(category).lower())
    tag = re.sub(r"[^a-z0-9]", "", plain) or "geral"
    quote = lambda v: json.dumps(str(v), ensure_ascii=False)  # texto entre aspas é YAML válido
    lines = [
        "---",
        f"title: {quote(name)}",
        f"date: {datetime.now().isoformat(timespec='seconds')}",
        f"source: {quote(source)}",
        f"category: {quote(category)}",
        f"link: {quote(link)}",
        f"tags: [noticia, {tag}]",
        "---",
        f"# {name}", "",
        *([f"*{title_pt}*", ""] if title_pt and title_pt != title else []),
        summary, "",
        f"**Fonte:** [{source}]({link})", "",
    ]
    if related:
        lines += ["## Relacionadas"] + [f"- [[{r}]]" for r in related] + [""]
    with open(os.path.join(folder(cfg), name + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    for r in related:  # a nota antiga também ganha um link para a nova
        rp = os.path.join(folder(cfg), clean_name(r) + ".md")
        if os.path.exists(rp):
            with open(rp, "a", encoding="utf-8") as f:
                f.write(f"\n- Veja também: [[{name}]]\n")
    return name
