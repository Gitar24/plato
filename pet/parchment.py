"""Pergaminho e bilhete do Plato, em pixel art no mesmo tamanho de pixel do personagem.

O balão das falas é um pergaminho com rolos nas pontas (e um selo de cera quando a notícia
é prioritária). A caixa de perguntas é um bilhete com a ponta dobrada.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

U = 3  # um "pixel" do desenho, igual ao SPRITE_SCALE do personagem
TEXT_W = 300  # largura do papel
WIDTH = TEXT_W + 4 * U  # papel + as pontas de madeira dos rolos
ROLL_H = 5 * U

PAPER, PAPER_SHADE, PAPER_EDGE = "#f2e2b6", "#e3cc96", "#a8854f"
PAPER_SPOT = "#e8d5a5"
ROLL = ("#7a5530", "#f7e9c6", "#e2c68e", "#c39f63", "#7a5530")  # de cima para baixo
WOOD, WOOD_LIGHT = "#5a3818", "#8a5a2b"
INK, INK_SOFT = "#3b2412", "#7a5a3a"
WAX = {"r": "#7d1a1f", "R": "#b3262e", "d": "#de5c63"}
SEAL = ("..rrr..",
        ".rRRRr.",
        "rRRdRRr",
        "rRdddRr",
        "rRRdRRr",
        ".rRRRr.",
        "..rrr..")

FONT = ('font-family:"Palatino Linotype","Book Antiqua",Georgia,"Noto Serif","DejaVu Serif",serif;'
        "font-size:11pt;")


def _block(p, x, y, w, h, color):
    p.fillRect(x, y, w, h, QColor(color))


def _paper(p, x0, y0, x1, y1):
    """Papel envelhecido entre (x0, y0) e (x1, y1), com borda e sombra nas laterais."""
    _block(p, x0, y0, x1 - x0, y1 - y0, PAPER)
    _block(p, x0, y0, U, y1 - y0, PAPER_EDGE)
    _block(p, x1 - U, y0, U, y1 - y0, PAPER_EDGE)
    _block(p, x0 + U, y0, U, y1 - y0, PAPER_SHADE)
    _block(p, x1 - 2 * U, y0, U, y1 - y0, PAPER_SHADE)
    # manchinhas do tempo, sempre nos mesmos lugares para não piscar
    cols, rows = (x1 - x0) // U, (y1 - y0) // U
    for i in range(1, max(2, cols * rows // 90)):
        cx, cy = (i * 37) % max(1, cols - 8) + 4, (i * 23) % max(1, rows - 4) + 2
        _block(p, x0 + cx * U, y0 + cy * U, U * (1 + i % 2), U, PAPER_SPOT)


class Scroll(QFrame):
    """Pergaminho onde o Plato escreve as falas."""

    def __init__(self):
        super().__init__()
        self.sealed = False
        self.setFixedWidth(WIDTH)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)  # senão o texto escapado pode aparecer como &lt;
        self.label.setStyleSheet(f"background:transparent;color:{INK};{FONT}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6 * U, ROLL_H + 3 * U, 6 * U, ROLL_H + 3 * U)
        lay.addWidget(self.label)

    def setText(self, text, sealed=False):
        self.label.setText(text)
        self.sealed = sealed
        self.update()

    def _roll(self, p, y):
        x0, x1 = 2 * U, self.width() - 2 * U
        for i, color in enumerate(ROLL):
            _block(p, x0, y + i * U, x1 - x0, U, color)
        for kx in (0, x1):  # as pontas de madeira
            _block(p, kx, y, 2 * U, ROLL_H, WOOD)
            _block(p, kx, y + U, 2 * U, U, WOOD_LIGHT)

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        _paper(p, 2 * U, ROLL_H - U, w - 2 * U, h - ROLL_H + U)
        _block(p, 3 * U, ROLL_H, w - 6 * U, U, PAPER_SHADE)  # sombra dos rolos no papel
        _block(p, 3 * U, h - ROLL_H - U, w - 6 * U, U, PAPER_SHADE)
        self._roll(p, 0)
        self._roll(p, h - ROLL_H)
        if self.sealed:  # selo de cera sobre o rolo de baixo
            sx, sy = w - 14 * U, h - len(SEAL) * U
            for r, row in enumerate(SEAL):
                for c, ch in enumerate(row):
                    if ch in WAX:
                        _block(p, sx + c * U, sy + r * U, U, U, WAX[ch])


class Note(QFrame):
    """Bilhete com a ponta dobrada, onde você escreve ao Plato."""

    def __init__(self, placeholder):
        super().__init__()
        self.setFixedWidth(WIDTH)
        quill = QLabel("✒")
        quill.setStyleSheet(f"background:transparent;color:{INK};{FONT}")
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet(f"background:transparent;color:{INK};border:none;{FONT}"
                                 f"selection-background-color:{ROLL[3]};font-style:italic;")
        pal = self.input.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(INK_SOFT))
        self.input.setPalette(pal)
        row = QHBoxLayout(self)
        row.setContentsMargins(6 * U, 3 * U, 8 * U, 3 * U)
        row.addWidget(quill)
        row.addWidget(self.input)

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        x0, x1 = 2 * U, w - 2 * U
        _paper(p, x0, 0, x1, h)
        _block(p, x0, 0, x1 - x0, U, PAPER_EDGE)
        _block(p, x0, h - U, x1 - x0, U, PAPER_EDGE)
        _block(p, x0 + U, h - 2 * U, x1 - x0 - 2 * U, U, PAPER_SHADE)
        # ponta dobrada no canto de cima, à direita: em cada linha do quadrado da dobra,
        # a parte da direita some (vira transparente) e a da esquerda é o verso do papel
        fold, fx = 5, x1 - 5 * U
        for i in range(fold):
            p.setCompositionMode(QPainter.CompositionMode_Source)
            _block(p, fx + i * U, i * U, (fold - i) * U, U, QColor(0, 0, 0, 0))
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            _block(p, fx, i * U, i * U, U, PAPER_SHADE)
            _block(p, fx + i * U, i * U, U, U, PAPER_EDGE)  # a dobra, na diagonal
        _block(p, fx, fold * U, fold * U, U, PAPER_EDGE)  # o pé da dobra
        _block(p, fx, 0, U, fold * U, PAPER_EDGE)  # o lado da dobra


MENU_STYLE = (f"QMenu{{background:{PAPER};color:{INK};border:{U}px solid {WOOD};padding:{U}px;{FONT}}}"
              f"QMenu::item{{padding:4px 18px;}}"
              f"QMenu::item:selected{{background:{ROLL[3]};color:{INK};}}"
              f"QMenu::separator{{height:{U}px;background:{PAPER_SHADE};margin:4px 8px;}}"
              f"QMenu::indicator{{width:12px;height:12px;}}")
