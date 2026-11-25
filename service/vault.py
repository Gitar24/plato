"""Grava as notícias como notas do Obsidian e liga umas às outras com [[links]]."""
import os, re
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
    name = clean_name(title)
    related = [r for r in related if r != name]
    tag = re.sub(r"[^a-z0-9]", "", category.lower()) or "geral"
    lines = [
        "---",
        f'title: "{name}"',
        f"date: {datetime.now().isoformat(timespec='seconds')}",
        f"source: {source}",
        f"category: {category}",
        f"link: {link}",
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
