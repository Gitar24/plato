"""O Plato na área de trabalho. Pergunta ao serviço (localhost:8765) se há notícia e mostra num balão."""
import html, math, os, sys, threading, time, webbrowser

import httpx
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap, QAction, QColor
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QMenu

from fullscreen import fullscreen_app_active
from look import (EYES, EYE_W, EYE_H, LEGS_X, LEG_TOP, LEG_W, eye_offset, leg_lengths,
                  monocle_on)
from parchment import Scroll, Note, MENU_STYLE, INK_SOFT
from safety import safe_link, domain

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SPRITE_SCALE = 3  # o desenho tem 64x40 e aparece 3x maior, sem borrar

EYE_COLOR = "#0a0a0f"
BODY_COLOR, MONOCLE_COLOR = "#6c9aff", "#ffd54a"

API = "http://127.0.0.1:8765"
POLL_MS = 3000


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
            for px, py, w, h in ((2, 0, 6, 1), (2, 11, 6, 1), (0, 2, 1, 8), (9, 2, 1, 8),
                                 (1, 1, 1, 1), (8, 1, 1, 1), (1, 10, 1, 1), (8, 10, 1, 1),
                                 (9, 11, 1, 3), (10, 14, 1, 3), (11, 17, 1, 3)):
                block(mx + px, my + py, w, h, MONOCLE_COLOR)


class Pet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.bridge = Bridge()
        self.bridge.news.connect(self.show_news)
        self.bridge.reply.connect(lambda t: self.say(html.escape(t).replace("\n", "<br>"), 15000))
        self.dnd = False
        self.link = None
        self.shown = set()  # ids já falados, caso a confirmação se perca
        self.drag = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self.bubble = Scroll()  # o pergaminho das falas
        self.bubble.hide()
        self.input_box = Note("Escreva ao Plato…")  # o bilhete das perguntas
        self.input = self.input_box.input
        self.input.returnPressed.connect(self.send_chat)
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
        # o canto de baixo, à direita, do Plato fica fixo; a janela cresce para cima e para a esquerda
        self.anchor = QPoint(geo.right() - 136, geo.bottom() - 46)
        self.relayout()

    # --- fala ---
    def say(self, text, ms=12000, sealed=False):
        self.link = None  # só a notícia tem link; ela o define depois
        self.bubble.setText(text, sealed)
        self.bubble.show()
        self.char.talking = True
        self.relayout()
        self.hide_timer.start(ms)
        QTimer.singleShot(min(ms, 4000), lambda: setattr(self.char, "talking", False))

    def hide_bubble(self):
        self.bubble.hide()
        self.char.talking = False
        self.link = None
        self.relayout()

    def busy(self):
        """Não é hora de interromper; a notícia espera na fila."""
        return (self.dnd or fullscreen_app_active() or self.bubble.isVisible()
                or self.input_box.isVisible())

    def show_news(self, n):
        iid = n.get("id")
        if iid in self.shown:
            return self.ack(iid)  # já foi falada: só confirma de novo
        if self.busy():
            return  # sem confirmação, ela continua na fila
        link = safe_link(n.get("link"))
        where = f"{domain(link)} · clique para abrir" if link else "link não aberto"
        esc = lambda v: html.escape(str(v or ""))  # texto do feed e do LLM nunca vira código
        # notícia prioritária vem lacrada com selo de cera
        self.say(f"<b>{esc(n.get('title_pt') or n.get('title'))}</b><br>{esc(n.get('comment'))}<br>"
                 f"<small><i style='color:{INK_SOFT}'>{esc(n.get('source'))} · {esc(where)}</i></small>",
                 20000, sealed=bool(n.get("priority")))
        self.link = link
        self.shown.add(iid)
        self.ack(iid)

    def ack(self, iid):
        """Avisa o serviço que a notícia foi falada, para ele tirá-la da fila."""
        def work():
            try:
                httpx.post(f"{API}/ack", json={"id": iid}, timeout=5)
            except Exception:
                pass  # o serviço manda de novo e confirmamos outra vez
        threading.Thread(target=work, daemon=True).start()

    # --- rede (em segundo plano, para a animação não travar) ---
    def poll_news(self):
        if self.busy():
            return

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
        self.say("<i>Molhando a pena no tinteiro…</i>", 60000)

        def work():
            try:
                r = httpx.post(f"{API}/chat", json={"message": msg}, timeout=90)
                self.bridge.reply.emit(r.json()["reply"])
            except Exception as e:
                self.bridge.reply.emit(f"Não consegui falar com o serviço: {e}")
        threading.Thread(target=work, daemon=True).start()

    # --- posição ---
    def relayout(self):
        """Ajusta o tamanho ao conteúdo sem tirar o Plato do lugar.

        Tamanho e posição saem juntos, calculados a partir da âncora. Corrigir pela diferença
        de tamanho (como antes) acumulava erro no X11, onde a janela muda de forma assíncrona,
        e o Plato ia afundando ou subindo a cada fala.
        """
        self.layout().activate()  # senão o tamanho mínimo antigo barra a janela de encolher
        s = self.sizeHint()
        if self.hasHeightForWidth():
            s.setHeight(self.heightForWidth(s.width()))
        self.setGeometry(QRect(self.anchor - QPoint(s.width() - 1, s.height() - 1), s))

    # --- interação ---

    def toggle_chat(self):
        self.input_box.setVisible(not self.input_box.isVisible())
        if self.input_box.isVisible():
            self.input.setFocus()
        self.relayout()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag)
            self.anchor = self.geometry().bottomRight()

    def on_scroll(self, e):
        return self.bubble.isVisible() and self.bubble.geometry().contains(e.position().toPoint())

    def mouseReleaseEvent(self, e):
        moved = self.drag is not None and (
            e.globalPosition().toPoint() - self.frameGeometry().topLeft() - self.drag).manhattanLength() > 3
        self.drag = None
        # só o pergaminho abre a notícia; o link é conferido de novo na hora de abrir
        if e.button() == Qt.LeftButton and not moved and self.on_scroll(e) and safe_link(self.link):
            webbrowser.open(self.link)

    def mouseDoubleClickEvent(self, e):
        if not self.on_scroll(e):
            self.toggle_chat()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(MENU_STYLE)
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
