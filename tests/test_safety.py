import os, sys, unittest
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pet"))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main
from safety import safe_link

app = QApplication.instance() or QApplication([])


class SafeLink(unittest.TestCase):
    def test_accepts_plain_https(self):
        for url in ("https://www.bbc.com/news/a?x=1#0", "https://arstechnica.com:443/a"):
            self.assertEqual(safe_link(url), url)

    def test_refuses_suspicious(self):
        for url in ("http://bbc.com", "file:///etc/passwd", "javascript:alert(1)", "",
                    None, "https://banco.com@mal.com/", "https://u:s@mal.com",
                    "https://192.168.0.1/", "https://2130706433/", "https://0x7f.0.0.1/",
                    "https://[::1]/", "https://localhost/", "https://site.com:8080/",
                    "https://xn--pple-43d.com/", "https://аpple.com/",
                    "https://mal.com\\@bbc.com/", "https://bbc.com/\n", "https://site.com:abc/"):
            self.assertIsNone(safe_link(url), url)


class PetNews(unittest.TestCase):
    def setUp(self):
        self.pet = main.Pet()
        self.pet.poll.stop()
        self.acked = []
        self.pet.ack = self.acked.append
        self.pet.show()
        self.pet.hide_bubble()
        app.processEvents()
        self.addCleanup(self.pet.close)

    def news(self, **kw):
        return {"id": "1", "title": "<img src=x>", "comment": "a < b", "source": "S",
                "link": "https://www.bbc.com/n", **kw}

    def click(self, widget):
        pos = widget.mapTo(self.pet, widget.rect().center())
        with mock.patch.object(main.webbrowser, "open") as opened:
            QTest.mouseClick(self.pet, Qt.LeftButton, pos=pos)
        return opened.call_count

    def test_text_is_escaped_and_domain_shown(self):
        self.pet.show_news(self.news())
        text = self.pet.bubble.label.text()
        self.assertNotIn("<img", text)
        self.assertIn("a &lt; b", text)
        self.assertIn("www.bbc.com", text)

    def test_only_the_scroll_opens_the_link(self):
        self.pet.show_news(self.news())
        app.processEvents()
        self.assertEqual(self.click(self.pet.char), 0)
        self.assertEqual(self.click(self.pet.bubble), 1)

    def test_bad_link_never_opens(self):
        self.pet.show_news(self.news(link="http://mal.com"))
        app.processEvents()
        self.assertIn("link não aberto", self.pet.bubble.label.text())
        self.assertEqual(self.click(self.pet.bubble), 0)

    def test_chat_reply_has_no_link(self):
        self.pet.show_news(self.news())
        self.pet.say("resposta")
        self.assertIsNone(self.pet.link)

    def test_ack_after_showing_and_never_twice(self):
        self.pet.show_news(self.news())
        self.pet.hide_bubble()
        self.pet.show_news(self.news())  # o /ack falhou e o serviço mandou de novo
        self.assertFalse(self.pet.bubble.isVisible())
        self.assertEqual(self.acked, ["1", "1"])

    def test_busy_pet_does_not_ack(self):
        self.pet.dnd = True
        self.pet.show_news(self.news())
        self.assertEqual(self.acked, [])


if __name__ == "__main__":
    unittest.main()
