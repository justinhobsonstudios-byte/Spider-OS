import tempfile
import unittest
from pathlib import Path

from spider_os.db import Database
from spider_os.personal_web import PersonalKnowledgeWeb


class PersonalKnowledgeWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name))
        self.db.initialize()
        self.web = PersonalKnowledgeWeb(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_fact_and_inference_remain_distinct(self):
        fact = self.web.remember(kind="fact", content="Prefers dark interfaces.", source="user:explicit")
        inference = self.web.remember(
            kind="inference",
            content="May prefer low-distraction dashboards.",
            source="webbie:pattern",
            evidence_ids=[fact["id"]],
        )
        self.assertEqual(fact["metadata"]["memory_kind"], "fact")
        self.assertEqual(inference["metadata"]["memory_kind"], "inference")
        self.assertLess(inference["confidence"], fact["confidence"])

    def test_inference_requires_evidence(self):
        with self.assertRaises(ValueError):
            self.web.remember(kind="inference", content="Guess", source="webbie:pattern")


if __name__ == "__main__":
    unittest.main()
