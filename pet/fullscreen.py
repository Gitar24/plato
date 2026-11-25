"""Diz se há algo em tela cheia (jogo, vídeo, apresentação), para o Plato ficar quieto.

No Windows pergunta à API do sistema. No Linux (X11, como no Mint/Cinnamon) pergunta ao
gerenciador de janelas pelo xprop. No Wayland não há como saber, então responde que não.
"""
import ctypes, os, re, subprocess, sys

_WINDOW_ID = re.compile(r"window id # (0x[0-9a-fA-F]+)")


def active_window_id(xprop_root):
    """Tira o id da janela ativa da saída de `xprop -root _NET_ACTIVE_WINDOW`."""
    m = _WINDOW_ID.search(xprop_root or "")
    if not m or int(m.group(1), 16) == 0:
        return None
    return m.group(1)


def is_fullscreen_state(xprop_state):
    """Lê a saída de `xprop -id <janela> _NET_WM_STATE`."""
    return "_NET_WM_STATE_FULLSCREEN" in (xprop_state or "")


def _xprop(*args):
    return subprocess.run(["xprop", *args], capture_output=True, text=True, timeout=1).stdout


def _linux():
    if not os.environ.get("DISPLAY"):
        return False  # sem X11 (Wayland puro): não dá para saber
    wid = active_window_id(_xprop("-root", "_NET_ACTIVE_WINDOW"))
    return bool(wid) and is_fullscreen_state(_xprop("-id", wid, "_NET_WM_STATE"))


def _windows():
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return False
    cls = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(hwnd, cls, 64)
    if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
        return False
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.right - r.left >= u.GetSystemMetrics(0)
            and r.bottom - r.top >= u.GetSystemMetrics(1))


def fullscreen_app_active():
    try:
        return _windows() if sys.platform == "win32" else _linux()
    except Exception:
        return False  # na dúvida, deixa o Plato falar
