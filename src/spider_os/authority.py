from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuthorityDecision:
    tier: str
    requires_confirmation: bool
    reason: str


class GraduatedAuthority:
    """Webbie's graduated-action policy.

    Tier 0: read/observe only.
    Tier 1: routine, local and reversible actions may execute automatically.
    Tier 2: sensitive or externally visible actions require confirmation.
    Tier 3: destructive, financial, security-critical or irreversible actions
            always require explicit approval at execution time.
    """

    def classify(self, action_name: str, arguments: dict[str, Any] | None = None) -> AuthorityDecision:
        args = arguments or {}
        sensitivity = str(args.get("sensitivity", "standard"))
        if action_name in {"list_items", "search_items", "search_knowledge", "list_research_findings"}:
            return AuthorityDecision("observe", False, "read-only local action")
        if action_name in {"queue_research", "remember_personal"} and sensitivity == "standard":
            return AuthorityDecision("routine", False, "reviewable local knowledge action")
        if action_name == "create_item" and sensitivity == "standard":
            return AuthorityDecision("routine", False, "local reversible organization")
        if action_name == "complete_item":
            return AuthorityDecision("routine", False, "local reversible state change")
        if sensitivity in {"private", "restricted"}:
            return AuthorityDecision("sensitive", True, "sensitive information")
        return AuthorityDecision("sensitive", True, "unclassified write defaults to confirmation")
