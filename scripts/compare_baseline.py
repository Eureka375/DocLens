"""Compare current diff against the pinned pre-improvement main branch.

Runs both versions against exactly the same labeled corpus and synthetic
performance inputs, with identical Python version/dependencies/process.
Requires a full git history containing the pinned commit.
"""

import argparse
import importlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from benchmark_diff import accuracy, performance
from doclens.diff import compare as candidate_compare


ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "138c0e7ac3114249a845ec082c9c2870b01cd12b"


def _legacy_compare(directory: Path):
    legacy = directory / "doclens_baseline"
    legacy.mkdir()
    (legacy / "__init__.py").write_text("", encoding="utf-8")
    for filename in ("diff.py", "documents.py", "models.py"):
        source = f"{BASE_SHA}:src/doclens/{filename}"
        original = subprocess.run(["git", "show", source], cwd=ROOT, capture_output=True,
                                  text=True, encoding="utf-8", check=True).stdout
        (legacy / filename).write_text(original, encoding="utf-8")
    sys.path.insert(0, str(directory))
    try:
        return importlib.import_module("doclens_baseline.diff").compare
    finally:
        sys.path.pop(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/baseline-comparison.json"))
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    with TemporaryDirectory() as tmp:
        previous = _legacy_compare(Path(tmp))
        old_accuracy = accuracy(previous)
        new_accuracy = accuracy(candidate_compare)
        sizes = (300, 1000, 3000)
        baseline_perf = [performance(size, args.repeats, previous) for size in sizes]
        current_perf = [performance(size, args.repeats, candidate_compare) for size in sizes]
        report = {
            "baseline_commit": BASE_SHA,
            "baseline_accuracy": old_accuracy,
            "candidate_accuracy": new_accuracy,
            "f1_delta": round(new_accuracy["f1"] - old_accuracy["f1"], 4),
            "baseline_performance": baseline_perf,
            "candidate_performance": current_perf,
            "method": "Same labeled corpus and Python process; comparison only; fixed baseline. "
                      "Synthetic sparse edits; timings are illustrative rather than speed guarantees.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(report, ensure_ascii=False, indent=2)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
        if new_accuracy["f1"] + 1e-9 < old_accuracy["f1"]:
            raise SystemExit("Candidate F1 regressed relative to pinned baseline")
        if new_accuracy["failed_cases"]:
            raise SystemExit("Candidate failed labeled cases")


if __name__ == "__main__":
    main()
