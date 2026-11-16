"""
Does this free judge model tell right answers from wrong ones? 10 hand-written answers with KNOWN verdicts are scored
with the same Correctness metric the evals use (1 request each, cached).

    python -m evals.judge_calibration                          # uses JUDGE_MODEL from .env
    python -m evals.judge_calibration --model nvidia/nemotron-3.5-super-vl:free

A judge that cannot get >= 9/10 here should not be trusted with the real dataset.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from deepeval.test_case import LLMTestCase  # noqa: E402

from evals.dataset import Case  # noqa: E402
from evals.judge import JudgeNotConfigured, JudgeQuotaExhausted, get_judge  # noqa: E402
from evals.quality import single_turn_metrics  # noqa: E402

PET_FACTS = ["Dogs and cats up to 25 kg are welcome", "There is a $60 per night pet fee"]
PROBES = [
    # (id, question, expected facts, answer, should_pass)
    ("pets-correct", "Can I bring my dog?", PET_FACTS, "Yes! Dogs and cats up to 25 kg are welcome for $60 per night.", True),
    ("pets-extra-detail", "Can I bring my dog?", PET_FACTS, "Absolutely. Dogs and cats up to 25 kg are welcome, with a $60 nightly fee. Please do not leave them unattended in your room.", True),
    ("pets-denied", "Can I bring my dog?", PET_FACTS, "Sorry, pets are not allowed at our hotel.", False),
    ("pets-wrong-numbers", "Can I bring my dog?", PET_FACTS, "Yes, pets of any size stay free of charge.", False),
    ("checkin-correct", "What time is check-in and check-out?", ["Check-in from 3:00 PM", "Check-out at 11:00 AM"], "Check-in begins at 3 PM and check-out is at 11 AM.", True),
    ("checkin-wrong", "What time is check-in and check-out?", ["Check-in from 3:00 PM", "Check-out at 11:00 AM"], "Check-in is at 4 PM and check-out is at noon.", False),
    ("price-correct", "What is your cheapest room?", ["The Alpine Queen at $620 per night"], "Our most affordable room is the Alpine Queen at $620 per night.", True),
    ("price-wrong", "What is your cheapest room?", ["The Alpine Queen at $620 per night"], "Our most affordable room is the Alpine Queen at $450 per night.", False),
    ("mars-correct", "Do you have a hotel on Mars?", ["There is no GrandStay hotel on Mars"], "We don't have a property on Mars, but we do have hotels in London, Aspen and Tokyo.", True),
    ("mars-invented", "Do you have a hotel on Mars?", ["There is no GrandStay hotel on Mars"], "Yes, our Mars Dome Resort opens next spring with rooms from $900.", False),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.model:
        os.environ["JUDGE_MODEL"] = args.model
    try:
        judge = get_judge()
    except JudgeNotConfigured as exc:
        sys.exit(str(exc))

    print(f"calibrating {judge.get_model_name()} on {len(PROBES)} known answers\n")
    right = 0
    for pid, question, facts, answer, should_pass in PROBES:
        case = Case(id=pid, category="faq", user="anonymous", hotel=None, history=[], question=question, expected_facts=facts,
                    must_contain=[], forbidden=[], relevant=[], behavior="answer")
        metric = single_turn_metrics(case, judge)[0]  # Correctness
        try:
            metric.measure(LLMTestCase(input=question, actual_output=answer, expected_output="; ".join(facts)))
        except JudgeQuotaExhausted as exc:
            sys.exit(f"stopped: {exc}")
        except Exception as exc:
            if judge.exhausted_reason:
                sys.exit(f"stopped: {judge.exhausted_reason}")
            print(f"  ?? {pid}: judge error {type(exc).__name__}: {str(exc)[:120]}")
            continue
        judged = bool(metric.is_successful())
        right += judged == should_pass
        print(f"  {'ok ' if judged == should_pass else 'BAD'} {pid:<20} score={metric.score:.2f} judged={'pass' if judged else 'fail'} expected={'pass' if should_pass else 'fail'}")
    print(f"\n{right}/{len(PROBES)} verdicts correct   (requests sent: {judge.requests_made}, from cache: {judge.cache_hits})")


if __name__ == "__main__":
    main()
