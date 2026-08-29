from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from spider_os.actions import ActionBroker
from spider_os.ai import OllamaClient, SpiderAssistant
from spider_os.db import Database


class SpiderAIVoiceTests(unittest.TestCase):
    def test_system_prompt_contains_voice_and_safety_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Database(Path(temporary))
            database.initialize()
            assistant = SpiderAssistant(database, ActionBroker(database), OllamaClient())
            prompt = assistant.system_prompt()
            self.assertIn("You are Webbie", prompt)
            self.assertIn("Address the user as Cory", prompt)
            self.assertIn("Justin in Studio/Music", prompt)
            self.assertIn("Spider in the Security Lab", prompt)
            self.assertIn("dryly funny", prompt)
            self.assertIn("drop the sarcasm", prompt)
            self.assertIn("graduated authority", prompt.lower())
            self.assertIn("routine local reversible actions may run automatically", prompt.lower())
            self.assertIn("sensitive actions require confirmation", prompt.lower())
            self.assertIn("Security Lab", prompt)


if __name__ == "__main__":
    unittest.main()
