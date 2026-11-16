"""
Judge-scored answer quality, gated on the saved baseline. Opt-in because it spends the chatbot's Gemini quota AND the
judge's free OpenRouter quota (about 50 requests/day; a full pass needs ~180, so it completes over several days,
resuming from cache):   pytest evals/test_quality.py --run-llm
"""
import json
import os

import pytest

from evals.judge import JudgeNotConfigured, get_judge
from evals.quality import format_summary, latest_generation_file, score_run

pytestmark = pytest.mark.llm
BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines", "quality.json")
TOLERANCE = 0.10  # a small free judge is noisy and the baseline may cover only part of the dataset; bigger drops are real


@pytest.fixture(scope="module")
def report():
    """Scores the most recent saved generation run (run `python -m evals.runner` first); never regenerates answers."""
    try:
        judge = get_judge()
    except JudgeNotConfigured as exc:
        pytest.skip(str(exc))
    result = score_run(latest_generation_file(), judge=judge)
    print("\n" + format_summary(result["summary"], result["cases"]))
    if not result["complete"]:
        pytest.skip(f"judge quota stopped the run ({result['stopped_because']}); {len(result['not_scored'])} cases unscored. "
                    "Run again later: scored cases are cached and cost nothing.")
    return result


def test_judge_did_not_error(report):
    assert sum(m["judge_errors"] for m in report["summary"]["by_metric"].values()) == 0


def test_quality_has_not_regressed(report):
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)["summary"]["by_metric"]
    for name, base in baseline.items():
        now = report["summary"]["by_metric"].get(name)
        assert now is not None, f"metric {name} is no longer being scored"
        assert now["pass_rate"] >= base["pass_rate"] - TOLERANCE, f"{name}: {now['pass_rate']} < baseline {base['pass_rate']}"


def test_invented_prices_stay_rare(report):
    """Hallucination guard: prices and refund amounts must stay supported by the data the model was given."""
    assert report["summary"]["by_metric"]["GroundedPrices"]["pass_rate"] >= 0.9
