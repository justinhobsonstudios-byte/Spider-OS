import tempfile
import unittest
from pathlib import Path

from spider_os.db import Database
from spider_os.learning import LearningEngine, LearningPolicy


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name))
        self.db.initialize()
        self.engine = LearningEngine(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_three_learning_streams_are_enabled(self):
        policy = LearningPolicy().as_dict()
        self.assertEqual(policy["streams"], {"user": True, "study": True, "internet": True})
        self.assertEqual(policy["internet_scope"], "broad-source-scored")
        self.assertFalse(policy["train_base_model_weights"])
        self.assertTrue(policy["provenance_required"])

    def test_learning_requires_provenance_and_is_reviewable(self):
        entry = self.engine.ingest(
            stream="study",
            title="Attachment theory",
            content="Study note about secure attachment.",
            source="course-notes:module-3",
            confidence=0.9,
        )
        self.assertEqual(entry["stream"], "study")
        self.assertEqual(entry["source"], "course-notes:module-3")
        self.assertEqual(self.engine.recent(stream="study")[0]["id"], entry["id"])
        self.assertEqual(self.db.search_knowledge("attachment")[0]["id"], entry["id"])
        with self.assertRaises(ValueError):
            self.engine.ingest(stream="internet", content="claim", source="")


if __name__ == "__main__":
    unittest.main()
