import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pet"))


class LegsMonocleTest(unittest.TestCase):
    def test_legs_alternate(self):
        from look import leg_lengths
        a, b = leg_lengths(0), leg_lengths(0.5)
        self.assertEqual(a, [8, 5, 8, 5])
        self.assertEqual(b, [5, 8, 5, 8])
        self.assertEqual(leg_lengths(1.0), a)

    def test_monocle_only_sometimes(self):
        from look import monocle_on
        got = [monocle_on(s) for s in (0, 29.9, 30, 39.9, 40, 70)]
        self.assertEqual(got, [False, False, True, True, False, True])


if __name__ == "__main__":
    unittest.main()
