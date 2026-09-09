from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from spider_os.actions import ActionBroker
from spider_os.db import Database


class ActionBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name))
        self.database.initialize()
        self.broker = ActionBroker(self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_read_action_runs_without_proposal(self) -> None:
        outcome = self.broker.handle_ai_call("list_items", {"space_id": "school"})
        self.assertEqual(outcome["type"], "result")

    def test_routine_write_can_auto_execute(self) -> None:
        outcome = self.broker.handle_ai_call(
            "create_item",
            {
                "space_id": "school",
                "kind": "task",
                "title": "Finish discussion post",
            },
        )
        self.assertEqual(outcome["type"], "result")
        self.assertEqual(outcome["authority_tier"], "routine")
        self.assertEqual(len(self.database.list_items(space_id="school")), 1)

    def test_sensitive_write_requires_approval(self) -> None:
        outcome = self.broker.handle_ai_call(
            "create_item",
            {
                "space_id": "personal",
                "kind": "note",
                "title": "Private note",
                "sensitivity": "private",
            },
        )
        self.assertEqual(outcome["type"], "proposal")
        approved = self.broker.approve(outcome["proposal"]["id"])
        self.assertEqual(approved["status"], "approved")

    def test_proposal_cannot_execute_twice(self) -> None:
        outcome = self.broker.handle_ai_call(
            "create_item",
            {"space_id": "personal", "kind": "note", "title": "One copy", "sensitivity": "private"},
        )
        proposal_id = outcome["proposal"]["id"]
        self.broker.approve(proposal_id)
        with self.assertRaises(ValueError):
            self.broker.approve(proposal_id)
        self.assertEqual(len(self.database.list_items(space_id="personal")), 1)

    def test_web_can_search_learned_knowledge_without_confirmation(self) -> None:
        self.database.add_knowledge(
            stream="study",
            title="Systems theory",
            content="Person-in-environment perspective.",
            source="course-notes",
            confidence=0.9,
        )
        outcome = self.broker.handle_ai_call("search_knowledge", {"query": "person-in-environment"})
        self.assertEqual(outcome["type"], "result")
        self.assertEqual(outcome["data"][0]["stream"], "study")

    def test_webbie_can_queue_research_without_confirmation(self) -> None:
        outcome = self.broker.handle_ai_call(
            "queue_research",
            {
                "query": "Current evidence on a study topic",
                "rationale": "Knowledge gap detected.",
                "anchor_id": "school",
                "priority": 3,
            },
        )
        self.assertEqual(outcome["type"], "result")
        self.assertEqual(outcome["authority_tier"], "routine")
        self.assertEqual(self.database.list_research_questions()[0]["query"], "Current evidence on a study topic")

    def test_private_personal_memory_requires_confirmation(self) -> None:
        outcome = self.broker.handle_ai_call(
            "remember_personal",
            {
                "memory_kind": "observation",
                "content": "Private preference",
                "source": "conversation",
                "sensitivity": "private",
            },
        )
        self.assertEqual(outcome["type"], "proposal")


if __name__ == "__main__":
    unittest.main()

