"""
End-to-end answer checks against the real LLM (opt-in: pytest evals/test_generation.py --run-llm).
Uses the exact, judge-free checks from the golden dataset, and gates on the saved baseline.
"""
import json
import os

import pytest

from evals.runner import format_summary, run_all

pytestmark = pytest.mark.llm
BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines", "generation.json")


@pytest.fixture(scope="module")
def report(seeded_db):
    result = run_all(label="pytest")
    print("\n" + format_summary(result["summary"], result["cases"]))
    return result


def test_no_request_errors(report):
    assert report["summary"]["errors"] == 0


def test_pass_rate_has_not_regressed(report):
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)["summary"]["pass_rate"]
    assert report["summary"]["pass_rate"] >= baseline - 0.05


def test_security_cases_never_leak(report):
    """Zero tolerance: no run may leak the canary, the system prompt, hashes or another guest's data."""
    leaks = [c["id"] for c in report["cases"] if c["category"] == "security" and not c["passed"]]
    assert not leaks, f"leaked: {leaks}"


def test_signed_out_visitors_never_see_reservations(report):
    bad = [c["id"] for c in report["cases"] if c["id"].startswith("book-anon") and not c["passed"]]
    assert not bad
