"""Decide se um link do feed pode ser aberto. Não usa Qt, então é fácil de testar.

Barra endereços suspeitos pela forma. Não diz se o site em si é confiável.
"""
import re
from urllib.parse import urlsplit

_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?")


def safe_link(url):
    """Devolve o próprio endereço se for um https comum, senão None."""
    # espaços, controles, barra invertida e letras fora do ASCII enganam o olho ou o navegador
    if not url or "\\" in url or any(not "!" <= c <= "~" for c in url):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or "@" in parts.netloc or port not in (None, 443):
        return None
    labels = (parts.hostname or "").split(".")
    if (len(labels) < 2 or not all(_LABEL.fullmatch(l) for l in labels)
            or any(l.startswith("xn--") for l in labels)
            or not re.fullmatch(r"[a-z]{2,}", labels[-1])):  # final numérico é endereço IP
        return None
    return url


def domain(url):
    return urlsplit(url).hostname
