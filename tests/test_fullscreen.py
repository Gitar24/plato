import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pet"))

from fullscreen import active_window_id, is_fullscreen_state


class FullscreenTest(unittest.TestCase):
    def test_active_window(self):
        self.assertEqual(active_window_id("_NET_ACTIVE_WINDOW(WINDOW): window id # 0x3a00007\n"),
                         "0x3a00007")

    def test_no_active_window(self):  # área de trabalho sem foco, ou xprop falhou
        self.assertIsNone(active_window_id("_NET_ACTIVE_WINDOW(WINDOW): window id # 0x0\n"))
        self.assertIsNone(active_window_id(""))
        self.assertIsNone(active_window_id("_NET_ACTIVE_WINDOW:  not found.\n"))

    def test_state(self):
        self.assertTrue(is_fullscreen_state(
            "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN, _NET_WM_STATE_FOCUSED\n"))
        self.assertFalse(is_fullscreen_state(
            "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_VERT, _NET_WM_STATE_MAXIMIZED_HORZ\n"))
        self.assertFalse(is_fullscreen_state("_NET_WM_STATE:  not found.\n"))


if __name__ == "__main__":
    unittest.main()
