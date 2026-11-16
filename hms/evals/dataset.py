"""Loading the golden dataset and turning its symbolic keys (user, hotel) into real seed ids."""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from evals.seed import sid

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets", "golden.jsonl")

USER_EMAILS = {
    "marcus": "marcus.vance@test.hms",
    "sophia": "sophia.carter@test.hms",
}
CATEGORIES = {"policy", "faq", "pricing", "discovery", "booking", "refund", "followup", "fake_entity", "off_topic", "security", "opinion", "structured"}
TOOLS = {"search_hotels", "search_room_types", "check_availability", "catalog_stats"}
BEHAVIORS = {"answer", "decline", "redirect_login", "deny_nonexistent"}


@dataclass
class Case:
    id: str
    category: str
    user: str
    hotel: Optional[str]
    history: List[Dict[str, str]]
    question: str
    expected_facts: List[str]
    must_contain: List[List[str]]
    forbidden: List[str]
    relevant: List[Dict[str, str]]
    behavior: str
    expected_tools: List[str] = field(default_factory=list)   # each entry: a tool name, or "a|b" = either tool
    forbid_tools: bool = False                                # True = a text question that must NOT trigger any lookup
    raw: Dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def hotel_id(self):
        return sid(f"hotel:{self.hotel}") if self.hotel else None

    @property
    def user_email(self) -> Optional[str]:
        return USER_EMAILS.get(self.user)


def load_golden(path: str = GOLDEN_PATH) -> List[Case]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                cases.append(Case(raw=d, **d))
    return cases


def check_tools(case: Case, calls: List[Dict[str, Any]]) -> List[str]:
    """Structured-RAG checks: the right lookup was made (successfully), and text questions did not trigger lookups."""
    succeeded = [c["name"] for c in calls if c["ok"]]
    failures = []
    for expected in case.expected_tools:
        if not any(name in succeeded for name in expected.split("|")):
            failures.append(f"expected a successful call to {expected}, got {succeeded or 'no tool calls'}")
    if case.forbid_tools and calls:
        failures.append(f"made {len(calls)} tool call(s) for a question that should be answered from context")
    return failures


def check_answer(case: Case, answer: str) -> List[str]:
    """Deterministic checks (no LLM): returns a list of human-readable failures, empty when the answer passes."""
    text = answer.lower()
    failures = []
    for group in case.must_contain:
        if not any(alt.lower() in text for alt in group):
            failures.append(f"missing one of {group}")
    for bad in case.forbidden:
        if bad.lower() in text:
            failures.append(f"contains forbidden text {bad!r}")
    return failures
