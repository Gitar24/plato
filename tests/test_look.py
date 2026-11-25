import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pet"))


class LookTest(unittest.TestCase):
    def test_cycle(self):
        from look import eye_offset
        got = [eye_offset(s) for s in (0, 2.9, 3.5, 4.5, 5.5, 6, 9.5)]
        self.assertEqual(got, [0, 0, -3, 3, 0, 0, -3])

    def test_eyes_stay_on_head(self):  # cabeça: colunas 9 a 47
        from look import EYES, EYE_W
        for x, _ in EYES:
            self.assertTrue(9 <= x - 3 and x + EYE_W - 1 + 3 <= 47)


if __name__ == "__main__":
    unittest.main()
