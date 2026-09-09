import unittest

from spider_os.screen_context import ScreenContextBuffer


class ScreenContextTests(unittest.TestCase):
    def test_context_is_ephemeral_and_has_no_pixels(self):
        buffer = ScreenContextBuffer()
        context = buffer.update(app_name="Writer", window_title="Essay", text_summary="Drafting introduction")
        self.assertTrue(context["active"])
        self.assertFalse(context["persisted"])
        self.assertFalse(context["raw_pixels_retained"])

    def test_sensitive_windows_are_excluded(self):
        buffer = ScreenContextBuffer()
        context = buffer.update(app_name="Browser", window_title="Password manager")
        self.assertTrue(context["excluded"])
        self.assertFalse(context["active"])
        self.assertEqual(context["app_name"], "excluded")


if __name__ == "__main__":
    unittest.main()
