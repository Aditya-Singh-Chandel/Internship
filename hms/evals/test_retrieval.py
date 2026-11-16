"""Retrieval baseline gate. Thresholds sit just below the measured baseline, so a regression fails the build."""
import json
import os

import pytest

from evals.retrieval_metrics import evaluate_retrieval, format_report, save_report

BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines", "retrieval.json")


@pytest.fixture(scope="module")
def report(seeded_db):
    from app.core.database import session_maker

    with session_maker() as db:
        result = evaluate_retrieval(db)
    print("\n" + format_report(result))
    save_report(result)
    return result


def test_report_covers_the_labelled_cases(report):
    assert report["overall"]["n"] >= 35


def test_overall_retrieval_has_not_regressed(report):
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)["overall"]
    for metric in ("hit", "hit@1", "mrr", "recall"):
        assert report["overall"][metric] >= baseline[metric] - 0.03, f"{metric} dropped below the saved baseline"


@pytest.mark.parametrize("category", ["policy", "faq", "refund"])
def test_direct_questions_always_find_their_source(report, category):
    assert report["by_category"][category]["hit"] == 1.0


def test_follow_up_questions_find_their_source(report):
    """Was a known weakness (searched without the conversation); fixed by chat_service.build_retrieval_query."""
    assert report["by_category"]["followup"]["hit"] >= 0.9


def test_reranking_puts_the_right_chunk_first(report):
    """Cross-encoder re-ranking (rerank_service) lifted first-place accuracy from 0.80; vector order alone fails this."""
    assert report["overall"]["hit@1"] >= 0.85
