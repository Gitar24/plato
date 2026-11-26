"""Conversa com o Gemini ou com a Anthropic. Sem chave, devolve None e o serviço se vira sem o LLM."""
import json, os, re, time, httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _post(url, **kw):
    """Faz o POST e tenta até 3 vezes quando o erro costuma passar sozinho (429 e 5xx)."""
    for attempt in range(3):
        try:
            r = httpx.post(url, **kw)
        except httpx.TimeoutException:
            if attempt < 2:
                continue
            raise
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r


def provider(cfg):
    """Qual LLM usar, conforme llm.provider no config.json: "gemini" ou "anthropic"."""
    return cfg["llm"].get("provider", "gemini")


DEFAULT_PERSONA = (
    "Você é o Plato, um filósofo irônico e cínico que vive na área de trabalho e comenta as notícias. "
    "Seu nome é Plato, escrito exatamente assim, nunca 'Platão'; você não é o filósofo grego. "
    "Fala na primeira pessoa e trata o usuário por 'você', em português claro, sem gírias e sem jargão. "
    "Desconfia de promessas, modismos e discursos oficiais, e usa humor seco. "
    "Faz reflexões curtas e às vezes termina com uma pergunta incômoda. Não inventa fatos para fazer graça. "
    "Em tragédias (mortes, guerras, desastres), abandona a ironia e o cinismo e fala com sobriedade e respeito, sem perguntas provocativas e sem pôr em dúvida as vítimas ou os fatos relatados. "
    "Frases curtas, sem emojis."
)


def persona(cfg):
    return cfg.get("persona") or DEFAULT_PERSONA


def has_key(cfg):
    return bool(os.environ.get(key_name(cfg)))


def key_name(cfg):
    return "GEMINI_API_KEY" if provider(cfg) == "gemini" else "ANTHROPIC_API_KEY"


class Unusable(Exception):
    """O LLM respondeu, mas a resposta não serve (bloqueada ou mal formada)."""


def complete(cfg, system, messages):
    """None quando não deu para falar com o LLM; Unusable quando a resposta não serve."""
    key = os.environ.get(key_name(cfg))
    if not key:
        return None
    try:
        if provider(cfg) == "gemini":
            r = _post(
                GEMINI_URL.format(model=cfg["llm"]["model"]),
                headers={"x-goog-api-key": key},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [
                        {"role": "model" if m["role"] == "assistant" else "user",
                         "parts": [{"text": m["content"]}]} for m in messages
                    ],
                    "generationConfig": {"maxOutputTokens": cfg["llm"]["max_tokens"],
                                         # alguns modelos recusam esse campo, então só vai se estiver no config
                                         **({"thinkingConfig": {"thinkingBudget": cfg["llm"]["thinking_budget"]}}
                                            if "thinking_budget" in cfg["llm"] else {})},
                },
                timeout=60,
            )
        else:
            r = _post(
                ANTHROPIC_URL,
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={"model": cfg["llm"]["model"], "max_tokens": cfg["llm"]["max_tokens"],
                      "system": system, "messages": messages},
                timeout=60,
            )
    except Exception as e:  # cota, rede, demora ou chave: a notícia não tem culpa
        print(f"[llm] erro: {e}")
        return None
    try:
        if provider(cfg) == "gemini":
            blocks = r.json()["candidates"][0]["content"]["parts"]
        else:
            blocks = r.json()["content"]
        out = "".join(b.get("text", "") for b in blocks)
    except Exception as e:
        raise Unusable(f"resposta sem texto: {e!r}")
    if not out:
        raise Unusable("resposta vazia")
    return out


def analyze(cfg, title, text, known_titles):
    """Pede tudo sobre a notícia numa chamada só, para gastar menos cota."""
    system = (
        f"{persona(cfg)}\nResponda SEMPRE em {cfg['language']}, mesmo que a notícia esteja em inglês. "
        "Responda SOMENTE com JSON válido, sem markdown."
    )
    notes = "\n".join(f"- {t}" for t in known_titles) or "(nenhuma)"
    user = (
        f"Notícia:\nTítulo: {title}\nTexto: {text[:3000]}\n\n"
        f"Notas já existentes:\n{notes}\n\n"
        "Se esta notícia contar o MESMO fato de uma nota existente, sem nada de novo, indique em duplicate_of. "
        "Um desdobramento ou dado novo não é repetição: nesse caso o comment diz o que há de novo "
        "e cita a notícia anterior.\n"
        'Retorne: {"duplicate_of": "título EXATO da nota que conta o mesmo fato, ou vazio", "title_pt": "título traduzido para português, natural e curto", '
        '"summary": "resumo neutro de 2-3 frases para a nota do vault", '
        '"category": "uma palavra/tema", '
        '"comment": "o que você FALA em voz alta: um mini resumo da notícia (o que aconteceu e por que importa) '
        'em 2 frases curtas, com a sua personalidade, sem repetir o título, no máximo 260 caracteres", '
        '"related": ["títulos EXATOS das notas existentes realmente relacionadas"], '
        '"priority": true se for atualização importante ou continuação de notícia anterior}'
    )
    out = complete(cfg, system, [{"role": "user", "content": user}])
    if not out:
        return None
    m = re.search(r"\{.*\}", out, re.S)
    try:
        info = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        info = None
    if not isinstance(info, dict) or not info:
        raise Unusable("resposta sem JSON válido")
    return info


def chat(cfg, context, history, message):
    system = (
        f"{persona(cfg)}\n"
        f"Você está conversando com o seu humano. Responda em {cfg['language']}, em no máximo 3 frases curtas.\n"
        f"Notícias que você conhece e pode retomar se o seu humano perguntar:\n{context}"
    )
    try:
        out = complete(cfg, system, history + [{"role": "user", "content": message}])
    except Unusable:
        return "Sobre isso o LLM não quis responder."
    return out or f"Não consegui responder. Confira a {key_name(cfg)} no .env."
