import json, os, sys, tempfile, time, types, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))

import app, config, llm, store, vault

DAY = 86400


def entry(name, age_days=0.0, dated=True):
    e = {"title": name, "link": f"https://site.com/{name}", "summary": "texto"}
    if dated:
        e["published_parsed"] = time.gmtime(time.time() - age_days * DAY)
    return e


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.cfg = {"feeds": [{"name": "A", "url": "A", "category": "x"},
                              {"name": "B", "url": "B", "category": "x"}],
                    "llm": {"provider": "gemini", "model": "m", "max_tokens": 10},
                    "language": "pt", "priority_keywords": [], "max_related": 3,
                    "max_pending": 5, "max_age_days": 4, "mode": "test",
                    "active_intervals": {"normal_seconds": 60, "priority_seconds": 30}}
        self.feeds = {"A": [], "B": []}
        for p in (mock.patch.object(config, "DATA_DIR", self.dir),
                  mock.patch.object(config, "VAULT_PATH", self.dir),
                  mock.patch.object(config, "load", lambda: self.cfg),
                  mock.patch.object(app.httpx, "get",
                                    lambda url, **k: types.SimpleNamespace(content=url)),
                  mock.patch.object(app.feedparser, "parse",
                                    lambda u: types.SimpleNamespace(entries=self.feeds[u])),
                  mock.patch.object(app.scheduler, "reschedule_job", lambda *a, **k: None),
                  mock.patch.dict(os.environ, {"GEMINI_API_KEY": "chave-falsa"}),
                  mock.patch("builtins.print")):
            p.start()
            self.addCleanup(p.stop)

    def run_cycle(self, answers):
        """Roda um ciclo; `answers` mapeia título -> resposta do LLM (ou exceção)."""
        asked = []

        def analyze(cfg, title, text, known):
            asked.append(title)
            a = answers.get(title, {"summary": "s", "comment": "c"})
            if isinstance(a, type) and issubclass(a, Exception):
                raise a()
            return a
        with mock.patch.object(llm, "analyze", analyze):
            app.cycle()
        return asked

    def queued(self):
        return [n["title"] for n in store._load().get("pending", [])]


class Freshness(Base):
    def test_old_and_undated_are_ignored(self):
        self.feeds["A"] = [entry("velha", 5), entry("sem-data", dated=False)]
        self.assertEqual(self.run_cycle({}), [])
        self.assertEqual(self.queued(), [])

    def test_newest_first_even_when_deep_in_the_feed(self):
        self.feeds["A"] = [entry(f"n{i}", 1) for i in range(20)] + [entry("fresca", 0.01)]
        self.assertEqual(self.run_cycle({}), ["fresca"])

    def test_sources_alternate(self):
        self.feeds["A"] = [entry("a1", 0.1), entry("a2", 0.2)]
        self.feeds["B"] = [entry("b1", 1), entry("b2", 2)]
        got = self.run_cycle({}) + self.run_cycle({}) + self.run_cycle({})
        self.assertEqual(got, ["a1", "b1", "a2"])


class Queue(Base):
    def add(self, iid, age_days):
        store.add_pending({"id": iid, "title": iid, "published": time.time() - age_days * DAY})

    def test_delivery_drops_expired_and_prefers_newest(self):
        self.add("vencida", 5)
        self.add("ontem", 1)
        self.add("agora", 0)
        store.add_pending({"title": "sem-data"})
        self.assertEqual(store.peek_pending(4 * DAY)["id"], "agora")
        self.assertEqual(self.queued(), ["ontem", "agora"])

    def test_news_leaves_only_after_ack(self):
        self.add("x", 0)
        store.peek_pending(4 * DAY)
        self.assertEqual(store.pending_count(), 1)
        store.ack("x")
        self.assertEqual(store.pending_count(), 0)


class Attempts(Base):
    def test_gives_up_on_third_bad_answer_and_moves_on(self):
        self.feeds["A"] = [entry("ruim", 0.1), entry("boa", 0.2)]
        bad = {"ruim": llm.Unusable}
        self.assertEqual(self.run_cycle(bad), ["ruim"])
        self.assertEqual(self.run_cycle(bad), ["ruim"])
        self.assertEqual(self.run_cycle(bad), ["ruim", "boa"])
        self.assertEqual(self.queued(), ["boa"])

    def test_outage_never_discards(self):
        self.feeds["A"] = [entry("n", 0.1)]
        for _ in range(6):
            self.assertEqual(self.run_cycle({"n": None}), ["n"])
        self.run_cycle({})
        self.assertEqual(self.queued(), ["n"])

    def test_blocked_response_is_unusable_but_http_error_is_not(self):
        blocked = types.SimpleNamespace(json=lambda: {"promptFeedback": {}})
        with mock.patch.object(llm, "_post", lambda *a, **k: blocked):
            with self.assertRaises(llm.Unusable):
                llm.analyze(self.cfg, "t", "x", [])
        with mock.patch.object(llm, "_post", side_effect=RuntimeError("429")):
            self.assertIsNone(llm.analyze(self.cfg, "t", "x", []))
        with mock.patch.object(llm, "_post", side_effect=RuntimeError("429")):
            self.assertIn("Não consegui", llm.chat(self.cfg, "", [], "oi"))


class Repetition(Base):
    def test_same_fact_from_other_source_is_skipped(self):
        self.feeds["A"] = [entry("FCC aprova satelites", 0.1)]
        self.run_cycle({})
        self.feeds["B"] = [entry("FCC autoriza a SpaceX", 0.1), entry("outra", 0.2)]
        dup = {"FCC autoriza a SpaceX": {"duplicate_of": "FCC aprova satelites"}}
        self.assertEqual(self.run_cycle(dup), ["FCC autoriza a SpaceX", "outra"])
        self.assertEqual(self.queued(), ["FCC aprova satelites", "outra"])

    def test_unknown_duplicate_title_is_not_trusted(self):
        self.feeds["A"] = [entry("n", 0.1)]
        self.run_cycle({"n": {"duplicate_of": "inventada", "comment": "c"}})
        self.assertEqual(self.queued(), ["n"])

    def test_at_most_three_llm_calls_per_cycle(self):
        store.mark("0", {"title": "base"})
        self.feeds["A"] = [entry(f"d{i}", 0.1 + i / 100) for i in range(6)]
        dup = {f"d{i}": {"duplicate_of": "base"} for i in range(6)}
        self.assertEqual(len(self.run_cycle(dup)), 3)

    def test_with_key_the_llm_decides_about_similar_titles(self):
        store.mark("0", {"title": "Terremoto deixa 20 mortos no Chile"})
        self.feeds["A"] = [entry("Terremoto deixa 30 mortos no Chile", 0.1)]
        self.assertEqual(len(self.run_cycle({})), 1)

    def test_without_key_near_identical_title_is_skipped(self):
        del os.environ["GEMINI_API_KEY"]
        store.mark("0", {"title": "SpaceX wins FCC approval for satellites"})
        self.feeds["A"] = [entry("SpaceX wins FCC approval for satellites!", 0.1)]
        app.cycle()
        self.assertEqual(self.queued(), [])


class History(Base):
    def test_chat_finds_old_news_by_words(self):
        store.mark("1", {"title": "Old", "title_pt": "Vulcão desperta", "summary": "s"})
        for i in range(60):
            store.mark(f"n{i}", {"title": f"t{i}", "summary": "s"})
        found = [r["title"] for r in store.context("e o vulcão?")]
        self.assertIn("Old", found)
        self.assertIn("t59", found)

    def test_corrupted_file_is_kept(self):
        with open(os.path.join(self.dir, "history.json"), "w") as f:
            f.write("{quebrado")
        store.mark("1", {"title": "a"})
        kept = [n for n in os.listdir(self.dir) if "corrupt" in n]
        self.assertEqual(len(kept), 1)

    def test_failed_write_keeps_previous_history(self):
        store.mark("1", {"title": "a"})
        with mock.patch.object(store.json, "dump", side_effect=OSError("disco cheio")):
            with self.assertRaises(OSError):
                store.mark("2", {"title": "b"})
        self.assertTrue(store.is_seen("1"))


class Notes(Base):
    def write(self, title, category="Política"):
        return vault.write_note(self.cfg, title=title, summary="s", source="BBC: World",
                                category=category, link="https://a.com", related=[])

    def test_tag_name_and_yaml(self):
        first, second = self.write("Igual"), self.write("Igual", 'a: "b"\nc')
        self.assertEqual((first, second), ("Igual", "Igual (2)"))
        folder = os.path.join(self.dir, "Noticias")
        with open(os.path.join(folder, "Igual.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("tags: [noticia, politica]", text)
        self.assertIn('source: "BBC: World"', text)
        with open(os.path.join(folder, "Igual (2).md"), encoding="utf-8") as f:
            self.assertIn('category: "a: \\"b\\"\\nc"', f.read())


class Network(unittest.TestCase):
    def test_listens_only_locally_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app.host(), "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
