import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from spider_os.resident import ResidentAgent, read_resident_state


class ResidentTests(unittest.TestCase):
    def test_resident_state_defaults_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"SPIDER_OS_DATA_DIR": tmp}, clear=False):
                agent = ResidentAgent(interval=1)
                state = agent.state(core_ready=True)
                self.assertTrue(state["active"])
                self.assertEqual(state["ai_name"], "Webbie")
                self.assertEqual(state["wake_phrases"], ["Hey Webbie", "Webbie", "Hey Web", "Web"])
                self.assertEqual(state["address_names"]["default"], "Cory")
                self.assertEqual(state["address_names"]["studio"], "Justin")
                self.assertEqual(state["address_names"]["security-lab"], "Spider")
                self.assertTrue(state["screen_awareness"])
                self.assertFalse(state["screen_frames_archived"])
                self.assertEqual(state["attention_style"], "cue-then-speak")
                self.assertFalse(state["ambient_audio_stored"])
                self.assertFalse(state["arbitrary_shell_access"])

    def test_resident_state_can_be_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"SPIDER_OS_DATA_DIR": tmp}, clear=False):
                agent = ResidentAgent(interval=1)
                agent.write_state(agent.state(core_ready=False))
                state = read_resident_state()
                self.assertTrue(state["active"])
                self.assertFalse(state["core_ready"])
                self.assertEqual(state["mode"], "resident")


if __name__ == "__main__":
    unittest.main()
