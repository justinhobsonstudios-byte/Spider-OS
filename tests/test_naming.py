from pathlib import Path
import unittest

from spider_os.constants import (
    AI_NAME,
    ANCHOR_NAME,
    ANCHORS_NAME,
    APP_NAME,
    DESKTOP_NAME,
    MEMORY_NAME,
    SECURITY_NAME,
    STARTUP_NAME,
    THREAD_NAME,
    THREADS_NAME,
)


class NamingContractTests(unittest.TestCase):
    def test_canonical_names(self):
        self.assertEqual(APP_NAME, "Spider OS")
        self.assertEqual(DESKTOP_NAME, "The Web")
        self.assertEqual(AI_NAME, "Webbie")
        self.assertEqual(MEMORY_NAME, "Personal Knowledge Web")
        self.assertEqual(STARTUP_NAME, "Web Assembly")
        self.assertEqual(SECURITY_NAME, "Kali Bay")
        self.assertEqual(ANCHOR_NAME, "Anchor")
        self.assertEqual(ANCHORS_NAME, "Anchors")
        self.assertEqual(THREAD_NAME, "Thread")
        self.assertEqual(THREADS_NAME, "Threads")

    def test_legacy_life_space_wording_is_not_user_facing(self):
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/spider_os/web/index.html",
            root / "src/spider_os/web/app.js",
            root / "docs/BRAND.md",
            root / "docs/NAMING.md",
        ]
        for path in checked:
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("life space", text, str(path))


if __name__ == "__main__":
    unittest.main()
