"""O Plato na área de trabalho. Pergunta ao serviço (localhost:8765) se há notícia e mostra num balão."""
import math, os, sys, threading, time, webbrowser, ctypes
from ctypes import wintypes

import httpx
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint
from PySide6.QtGui import QPainter, QPixmap, QAction, QColor
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                               QLabel, QLineEdit, QMenu)

from look import (EYES, EYE_W, EYE_H, LEGS_X, LEG_TOP, LEG_W, eye_offset, leg_lengths,
                  monocle_on)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SPRITE_SCALE = 3  # o desenho tem 57x41 e aparece 3x maior, sem borrar

EYE_COLOR = "#0a0a0f"
BODY_COLOR, MONOCLE_COLOR = "#6c9aff", "#ffd54a"

# cores do balão e da caixa de perguntas
BG, FG, BORDER = "#000000", "#ffffff", "#555555"
BOX = f"background:{BG};border:1px solid {BORDER};border-radius:8px;"

API = "http://127.0.0.1:8765"
POLL_MS = 3000


def fullscreen_app_active():
    """Diz se há algo em tela cheia (jogo, vídeo, apresentação), para o Plato ficar quieto."""
    try:
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
    except Exception:
        return False


class Bridge(QObject):
    news = Signal(dict)
    reply = Signal(str)


class Character(QWidget):
    def __init__(self):
        super().__init__()
        src = QPixmap(os.path.join(ASSETS, "pet.png"))
        self.sprite = src.scaled(src.width() * SPRITE_SCALE, src.height() * SPRITE_SCALE,
                                 Qt.IgnoreAspectRatio, Qt.FastTransformation)
        self.setFixedSize(self.sprite.width() + 16, self.sprite.height() + 24)
        self.t = 0.0
        self.talking = False
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(33)

    def _tick(self):
        self.t += 0.12 * (3 if self.talking else 1)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)  # sem suavização, para os pixels ficarem nítidos
        amp = 6 if self.talking else 4  # quando fala, flutua mais
        bob = round(math.sin(self.t) * amp / SPRITE_SCALE) * SPRITE_SCALE  # sobe e desce de pixel em pixel
        x = (self.width() - self.sprite.width()) // 2
        # do PNG vem só o corpo; as pernas são desenhadas aqui para poderem se mexer
        p.drawPixmap(x, 8 + bob, self.sprite, 0, 0, self.sprite.width(), LEG_TOP * SPRITE_SCALE)

        def block(px, py, w, h, color):  # posições contadas nos pixels do desenho original
            p.fillRect(x + px * SPRITE_SCALE, 8 + bob + py * SPRITE_SCALE,
                       w * SPRITE_SCALE, h * SPRITE_SCALE, QColor(color))

        now = time.monotonic()
        for lx, length in zip(LEGS_X, leg_lengths(now)):
            block(lx, LEG_TOP, LEG_W, length, BODY_COLOR)
        look = eye_offset(now)
        for ex, ey in EYES:  # os olhos vão por cima e sobem junto com o corpo
            block(ex + look, ey, EYE_W, EYE_H, EYE_COLOR)
        if monocle_on(now):  # monóculo: aro e cordão no olho direito
            mx, my = EYES[1][0] + look - 3, EYES[1][1] - 2
            for px, py, w, h in ((2, 0, 5, 1), (2, 9, 5, 1), (0, 2, 1, 6), (8, 2, 1, 6),
                                 (1, 1, 1, 1), (7, 1, 1, 1), (1, 8, 1, 1), (7, 8, 1, 1),
                                 (8, 9, 1, 3), (9, 12, 1, 3), (10, 15, 1, 3)):
                block(mx + px, my + py, w, h, MONOCLE_COLOR)


class Pet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.bridge = Bridge()
        self.bridge.news.connect(self.show_news)
        self.bridge.reply.connect(lambda t: self.say(t, 15000))
        self.dnd = False
        self.link = None
        self.drag = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.bubble = QLabel()
        self.bubble.setWordWrap(True)
        self.bubble.setFixedWidth(300)
        self.bubble.setStyleSheet(f"{BOX}color:{FG};padding:8px;")
        self.bubble.hide()
        # onde você digita a pergunta
        self.input_box = QFrame()
        self.input_box.setFixedWidth(300)
        self.input_box.setStyleSheet(f"QFrame{{{BOX}}}")
        row = QHBoxLayout(self.input_box)
        row.setContentsMargins(8, 4, 8, 4)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Pergunte ao Plato...")
        self.input.setStyleSheet(f"background:transparent;color:{FG};border:none;"
                                 f"selection-background-color:{BORDER};")
        self.input.returnPressed.connect(self.send_chat)
        row.addWidget(self.input)
        self.input_box.hide()
        self.char = Character()
        lay.addWidget(self.bubble, alignment=Qt.AlignRight)
        lay.addWidget(self.input_box, alignment=Qt.AlignRight)
        lay.addWidget(self.char, alignment=Qt.AlignRight)

        self.hide_timer = QTimer(self, singleShot=True)
        self.hide_timer.timeout.connect(self.hide_bubble)
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.poll_news)
        self.poll.start(POLL_MS)

        geo = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(geo.right() - 330, geo.bottom() - 200)

    # --- fala ---
    def say(self, text, ms=12000):
        self.bubble.setText(text)
        self.bubble.show()
        self.char.talking = True
        self.adjustSize()
        self.hide_timer.start(ms)
        QTimer.singleShot(min(ms, 4000), lambda: setattr(self.char, "talking", False))

    def hide_bubble(self):
        self.bubble.hide()
        self.char.talking = False
        self.link = None
        self.adjustSize()

    def show_news(self, n):
        self.link = n.get("link")
        star = "⭐ " if n.get("priority") else ""
        self.say(f"{star}<b>{n.get('title_pt') or n['title']}</b><br>{n['comment']}<br>"
                 f"<small>{n['source']} · clique para abrir</small>", 20000)

    # --- rede (em segundo plano, para a animação não travar) ---
    def poll_news(self):
        if self.dnd or fullscreen_app_active() or self.bubble.isVisible() or self.input_box.isVisible():
            return  # não é hora de interromper; a notícia espera na fila

        def work():
            try:
                r = httpx.get(f"{API}/next", timeout=5)
                if r.status_code == 200:
                    self.bridge.news.emit(r.json())
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def send_chat(self):
        msg = self.input.text().strip()
        if not msg:
            return
        self.input.clear()
        self.say("Pensando…", 60000)

        def work():
            try:
                r = httpx.post(f"{API}/chat", json={"message": msg}, timeout=90)
                self.bridge.reply.emit(r.json()["reply"])
            except Exception as e:
                self.bridge.reply.emit(f"Não consegui falar com o serviço: {e}")
        threading.Thread(target=work, daemon=True).start()

    # --- interação ---
    def resizeEvent(self, e):
        # o balão e a caixa mudam o tamanho da janela; movemos a janela para o Plato ficar parado
        if not e.oldSize().isValid():
            return
        d = e.oldSize() - e.size()
        delta = QPoint(d.width(), d.height())
        self.move(self.pos() + delta)
        if self.drag is not None:  # isso aconteceu enquanto você arrastava
            self.drag -= delta

    def toggle_chat(self):
        self.input_box.setVisible(not self.input_box.isVisible())
        if self.input_box.isVisible():
            self.input.setFocus()
        self.adjustSize()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        moved = self.drag is not None and (
            e.globalPosition().toPoint() - self.frameGeometry().topLeft() - self.drag).manhattanLength() > 3
        self.drag = None
        if e.button() == Qt.LeftButton and not moved and self.link:
            webbrowser.open(self.link)

    def mouseDoubleClickEvent(self, e):
        self.toggle_chat()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("Conversar", self.toggle_chat)
        dnd = QAction("Não perturbe", m, checkable=True, checked=self.dnd)
        dnd.toggled.connect(lambda v: setattr(self, "dnd", v))
        m.addAction(dnd)
        m.addSeparator()
        m.addAction("Sair", QApplication.quit)
        m.exec(e.globalPos())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = Pet()
    pet.show()
    pet.say("Sou o Plato. Dois cliques, se tiver coragem de perguntar.", 6000)
    sys.exit(app.exec())
