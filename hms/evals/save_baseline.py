"""
Saves the scores the pytest gates compare against (evals/baselines/*.json). Do this ONLY after a change you have
decided to keep, and write the change into evals/baselines/EXPERIMENTS.md.

    python -m evals.save_baseline retrieval                  # resets+seeds the test database, measures, saves
    python -m evals.save_baseline generation                 # saves the newest evals/results/generation_*.json
    python -m evals.save_baseline generation --label final   # ...the newest one with that label
    python -m evals.save_baseline quality                    # saves the newest evals/results/quality_*.json
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
BASELINES = os.path.join(HERE, "baselines")


def _newest(pattern: str) -> str:
    files = sorted(glob.glob(os.path.join(RESULTS, pattern)), key=os.path.getmtime)
    if not files:
        sys.exit(f"no files matching {pattern} in {RESULTS}: run the evaluation first")
    return files[-1]


def _write(name: str, data: dict) -> None:
    os.makedirs(BASELINES, exist_ok=True)
    path = os.path.join(BASELINES, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("saved", path)


def save_retrieval() -> None:
    import conftest  # noqa: F401  (points the app at the test database)
    from evals.retrieval_metrics import evaluate_retrieval, format_report
    from evals.runner import _prepare_database
    from app.core.database import session_maker

    _prepare_database()
    with session_maker() as db:
        report = evaluate_retrieval(db)
    print(format_report(report))
    report.pop("cases")
    _write("retrieval.json", report)


def save_generation(label: str) -> None:
    path = _newest(f"generation_{label}_2*.json" if label else "generation_*_2*.json")
    with open(path, encoding="utf-8") as f:
        run = json.load(f)
    print("from", os.path.basename(path), "->", run["summary"]["pass_rate"], "pass rate")
    _write("generation.json", {"label": run["label"], "summary": run["summary"],
                               "failing_ids": [c["id"] for c in run["cases"] if not c["passed"]]})


def save_quality() -> None:
    path = _newest("quality_*.json")
    with open(path, encoding="utf-8") as f:
        run = json.load(f)
    note = "complete" if run.get("complete") else f"PARTIAL: {len(run['cases'])} cases scored, {len(run.get('not_scored', []))} not yet scored"
    print("from", os.path.basename(path), "->", note)
    _write("quality.json", {"label": f"saved from {os.path.basename(path)} ({note})", "judge": run["judge"],
                            "complete": run.get("complete"), "scored_cases": len(run["cases"]), "summary": run["summary"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["retrieval", "generation", "quality"])
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    {"retrieval": save_retrieval, "generation": lambda: save_generation(args.label), "quality": save_quality}[args.what]()
