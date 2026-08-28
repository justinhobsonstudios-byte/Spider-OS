import unittest

from spider_os.authority import GraduatedAuthority


class AuthorityTests(unittest.TestCase):
    def test_routine_reversible_actions_can_be_automatic(self):
        policy = GraduatedAuthority()
        self.assertFalse(policy.classify("create_item", {"sensitivity": "standard"}).requires_confirmation)
        self.assertFalse(policy.classify("complete_item", {}).requires_confirmation)

    def test_sensitive_actions_require_confirmation(self):
        policy = GraduatedAuthority()
        decision = policy.classify("create_item", {"sensitivity": "private"})
        self.assertTrue(decision.requires_confirmation)
        self.assertEqual(decision.tier, "sensitive")


if __name__ == "__main__":
    unittest.main()
