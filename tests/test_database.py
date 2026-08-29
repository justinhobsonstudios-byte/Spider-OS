from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from spider_os.db import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name))
        self.database.initialize()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_default_spaces_include_social_work_and_music_projects(self) -> None:
        spaces = {space["id"]: space for space in self.database.list_spaces()}
        self.assertEqual(spaces["social-work"]["parent_id"], "work")
        self.assertEqual(spaces["broken-sorrow"]["parent_id"], "music")
        self.assertNotEqual(spaces["broken-sorrow"]["id"], "work")

    def test_item_lifecycle_and_search(self) -> None:
        item = self.database.create_item(
            space_id="social-work",
            kind="task",
            title="Compare MSW field placements",
            body="Review supervision and placement requirements.",
        )
        self.assertEqual(item["status"], "open")
        found = self.database.search_items("field placements")
        self.assertEqual(found[0]["id"], item["id"])
        completed = self.database.set_item_status(item["id"], "done")
        self.assertEqual(completed["status"], "done")

    def test_preloaded_knowledge_is_seeded_once(self) -> None:
        first = self.database.list_knowledge(limit=200)
        self.assertGreaterEqual(len(first), 30)
        self.assertTrue(any(row["title"] == "Resident AI identity" for row in first))
        self.assertTrue(any(row["title"] == "Broken City concept" for row in first))
        self.database.initialize()
        second = self.database.list_knowledge(limit=200)
        self.assertEqual(len(first), len(second))

    def test_owner_only_permissions(self) -> None:
        mode = self.database.path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()

