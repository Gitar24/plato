import json, os

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config/config.json")
DATA_DIR = os.environ.get("DATA_DIR", "data")
VAULT_PATH = os.environ.get("VAULT_PATH", "vault")


def load():
    """Relê o config.json toda vez, então dá para editar com o serviço ligado."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    mode = os.environ.get("NEWS_MODE") or cfg.get("mode", "production")
    if mode not in cfg["intervals"]:
        mode = "production"
    cfg["mode"] = mode
    cfg["active_intervals"] = cfg["intervals"][mode]
    return cfg
