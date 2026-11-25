import os, sys, unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pet"))

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
import main

app = QApplication.instance() or QApplication([])


class AnchorTest(unittest.TestCase):
    def setUp(self):
        self.pet = main.Pet()
        self.pet.poll.stop()  # para o teste não gastar notícias da fila de verdade
        self.pet.move(300, 300)
        self.pet.show()
        app.processEvents()
        self.start = self.where()

    def tearDown(self):
        self.pet.close()

    def where(self):
        return self.pet.char.mapToGlobal(QPoint(0, 0))

    def check(self, action):
        action()
        app.processEvents()
        self.assertEqual(self.where(), self.start)

    def test_character_stays_when_speaking(self):
        self.check(lambda: self.pet.say("uma notícia bem comprida " * 12))
        self.check(lambda: self.pet.say("curta"))
        self.check(self.pet.hide_bubble)

    def test_character_stays_with_question_box(self):
        self.check(self.pet.toggle_chat)
        self.check(lambda: self.pet.say("resposta " * 30))
        self.check(self.pet.toggle_chat)
        self.check(self.pet.hide_bubble)


if __name__ == "__main__":
    unittest.main()
