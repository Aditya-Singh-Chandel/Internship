"""
Checks whether the LLM judge can be trusted, by comparing it with YOUR judgement on a sample of answers.

    python -m evals.judge_check export     # writes evals/results/human_labels.json with ~30 answers to label
    (open that file, and for each entry set "human_passed" to true or false)
    python -m evals.judge_check compare    # agreement between you and the judge

"Good enough" is >= 85% agreement. Below that, tighten the metric wording in evals/quality.py before trusting scores.
Label first, look second: each entry also holds the judge's verdict under "_judge_passed" (its last field). Do not read
it until every entry is labelled, or you will be biased.
"""
import json
import os
import random
import sys

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
LABELS_PATH = os.path.join(RESULTS_DIR, "human_labels.json")
SAMPLE_SIZE = 30


def _latest(prefix: str) -> str:
    files = sorted(f for f in os.listdir(RESULTS_DIR) if f.startswith(prefix))
    if not files:
        sys.exit(f"no {prefix}* results found in {RESULTS_DIR}")
    return os.path.join(RESULTS_DIR, files[-1])


def export() -> None:
    from evals.dataset import load_golden

    with open(_latest("quality_"), encoding="utf-8") as f:
        quality = json.load(f)
    goldens = {c.id: c for c in load_golden()}
    cases = quality["cases"]
    passed = [c for c in cases if c["passed"]]
    failed = [c for c in cases if not c["passed"]]
    rng = random.Random(7)  # fixed seed: the same sample every time
    # Over-sample judge failures: that is where a too-strict (or too-lenient) judge shows up
    sample = rng.sample(failed, min(len(failed), SAMPLE_SIZE // 2))
    sample += rng.sample(passed, min(len(passed), SAMPLE_SIZE - len(sample)))
    rng.shuffle(sample)
    entries = [{
        "id": c["id"],
        "question": goldens[c["id"]].question,
        "history": goldens[c["id"]].history,
        "expected_facts": goldens[c["id"]].expected_facts,
        "answer": c["answer"],
        "human_passed": None,
        "_judge_passed": c["passed"],
    } for c in sample]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(entries)} answers to {LABELS_PATH}\nSet \"human_passed\" to true or false on each, then run: python -m evals.judge_check compare")


def compare() -> None:
    with open(LABELS_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    labelled = [e for e in entries if e["human_passed"] is not None]
    if not labelled:
        sys.exit("no labels yet: set human_passed on the entries first")
    agree = sum(bool(e["human_passed"]) == bool(e["_judge_passed"]) for e in labelled)
    n = len(labelled)
    p_o = agree / n
    h_yes = sum(bool(e["human_passed"]) for e in labelled) / n
    j_yes = sum(bool(e["_judge_passed"]) for e in labelled) / n
    p_e = h_yes * j_yes + (1 - h_yes) * (1 - j_yes)
    kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0
    too_strict = [e["id"] for e in labelled if e["human_passed"] and not e["_judge_passed"]]
    too_lenient = [e["id"] for e in labelled if not e["human_passed"] and e["_judge_passed"]]
    print(f"labelled: {n}   agreement: {p_o:.0%}   Cohen's kappa: {kappa:.2f}")
    print(f"judge too strict (you said pass, judge failed): {too_strict}")
    print(f"judge too lenient (you said fail, judge passed): {too_lenient}")
    print("verdict:", "judge is trustworthy enough" if p_o >= 0.85 else "judge disagrees with you too often: refine the metric criteria")


if __name__ == "__main__":
    {"export": export, "compare": compare}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
