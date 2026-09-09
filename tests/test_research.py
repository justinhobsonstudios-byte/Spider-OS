import tempfile
import unittest
from pathlib import Path

from spider_os.db import Database
from spider_os.research import ResearchEngine, SearchResult


class FakeProvider:
    def search(self, query, limit=8):
        return [
            SearchResult("Primary source", "https://example.edu/a", "Useful current evidence.", 0.9),
            SearchResult("Secondary source", "https://example.org/b", "Additional context.", 0.7),
        ]


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name))
        self.db.initialize()
        self.engine = ResearchEngine(self.db, provider=FakeProvider())

    def tearDown(self):
        self.temp.cleanup()

    def test_autonomous_research_preserves_sources_and_finding(self):
        question = self.engine.queue(
            query="What changed in a useful field?",
            rationale="Webbie noticed a knowledge gap.",
            anchor_id="school",
            priority=3,
        )
        result = self.engine.run_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["question"]["id"], question["id"])
        self.assertEqual(len(result["sources"]), 2)
        finding = self.db.list_research_findings()[0]
        self.assertEqual(finding["urgency"], "worth-knowing")
        self.assertGreaterEqual(finding["confidence"], 0.7)

    def test_high_priority_thread_can_seed_own_research_question(self):
        self.db.create_item(
            space_id="school",
            kind="project",
            title="Prepare major paper",
            priority=4,
            status="active",
        )
        queued = self.engine.derive_questions_from_threads(limit=2)
        self.assertEqual(len(queued), 1)
        self.assertIn("Prepare major paper", queued[0]["query"])


if __name__ == "__main__":
    unittest.main()
