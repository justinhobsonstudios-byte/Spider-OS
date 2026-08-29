import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from spider_os.db import Database
from spider_os.proactive import ProactiveEngine


class ProactiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name))
        self.db.initialize()
        self.engine = ProactiveEngine(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_due_thread_creates_one_deduplicated_spoken_alert(self):
        now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        due = (now + timedelta(hours=6)).isoformat()
        self.db.create_item(space_id="school", kind="task", title="Submit paper", due_at=due)
        first = self.engine.scan_due_threads(now=now)
        second = self.engine.scan_due_threads(now=now)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)
        briefing = self.engine.briefing()
        self.assertTrue(briefing["speak"])
        self.assertEqual(briefing["important"][0]["title"], "Due within 24 hours: Submit paper")


if __name__ == "__main__":
    unittest.main()
