import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))


class PersonaTest(unittest.TestCase):
    def test_persona(self):
        import llm
        p = llm.persona({})
        for termo in ("Plato", "filósofo", "irônico", "cínico", "tragédias"):
            self.assertIn(termo, p)
        self.assertNotIn("mano", p)
        self.assertIn("nunca 'Platão'", p)


    def test_tragedy_has_no_provocation(self):
        import llm
        regra = llm.persona({}).split("Em tragédias", 1)[1]
        self.assertIn("sem perguntas provocativas", regra)
        self.assertIn("sem pôr em dúvida as vítimas", regra)


if __name__ == "__main__":
    unittest.main()
