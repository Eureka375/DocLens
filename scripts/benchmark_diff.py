"""Repeatable diff-corpus accuracy and latency/memory report (not a CI time gate).

From the repository root:
    python scripts/benchmark_diff.py --repeats 5 --output build/diff-metrics.json
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from doclens.diff import compare
from doclens.documents import read_document
from doclens.models import Snapshot, Span, TextBlock


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "diff_cases.json"


def snapshot(lines: list[str], name: str) -> Snapshot:
    text = "\n".join(lines)
    blocks = []
    start = 0
    for index, line in enumerate(lines, 1):
        blocks.append(TextBlock(line, Span(start, start + len(line)), f"第 {index} 行"))
        start += len(line) + 1
    return Snapshot(Path(name), sha256(text.encode("utf-8")).hexdigest(),
                    text, tuple(blocks), ())


def predicted(left: Snapshot, right: Snapshot, compare_fn=compare):
    return [
        (c.kind, left.text[c.left.start:c.left.end], right.text[c.right.start:c.right.end])
        for c in compare_fn(left, right).changes
    ]


def accuracy(compare_fn=compare):
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))
    tp = fp = fn = 0
    errors = []
    with TemporaryDirectory() as directory:
        for case in cases:
            a, b = Path(directory) / "old.txt", Path(directory) / "new.txt"
            a.write_text(case["old"], encoding="utf-8")
            b.write_text(case["new"], encoding="utf-8")
            actual = Counter(predicted(read_document(a), read_document(b), compare_fn))
            expected = Counter((c["kind"], c["left"], c["right"]) for c in case["expected"])
            good = sum((actual & expected).values())
            wrong = sum((actual - expected).values())
            missing = sum((expected - actual).values())
            tp += good
            fp += wrong
            fn += missing
            if wrong or missing:
                errors.append(case["id"])
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"cases": len(cases), "true_positive": tp, "false_positive": fp,
            "false_negative": fn, "precision": round(precision, 4),
            "recall": round(recall, 4), "f1": round(f1, 4), "failed_cases": errors}


def performance(lines_count: int, repeats: int, compare_fn=compare):
    original = [f"第{i:05d}条通用归档条款，使用统一编号和固定文本" for i in range(lines_count)]
    edited = original.copy()
    edited[0] = "第00000条通用归档条款，完成期限改为15天"
    edited[lines_count // 2] = f"第{lines_count // 2:05d}条通用归档条款，金额改为200元"
    edited[-1] = "末尾条款新增责任说明"
    left, right = snapshot(original, "benchmark-old.txt"), snapshot(edited, "benchmark-new.txt")
    # Warm-up; explicitly exclude extraction, UI, network and file I/O.
    reference = compare_fn(left, right)
    samples = []
    for _ in range(repeats):
        start = perf_counter()
        result = compare_fn(left, right)
        samples.append((perf_counter() - start) * 1000)
        assert len(result.changes) == len(reference.changes)
    tracemalloc.start()
    try:
        compare_fn(left, right)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    ordered = sorted(samples)
    return {"blocks": lines_count, "characters": len(left.text),
            "changes": len(reference.changes), "coarse": reference.used_coarse_matching,
            "repeats": repeats, "median_ms": round(median(samples), 3),
            "p95_ms": round(ordered[ceil(.95 * repeats) - 1], 3),
            "peak_python_heap_mib": round(peak / (1024 * 1024), 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sizes", default="300,1000,3000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]
    if args.repeats < 1 or any(s < 3 for s in sizes):
        parser.error("repeats must be >= 1 and each size must be >= 3")
    report = {"accuracy": accuracy(),
              "performance": [performance(n, args.repeats) for n in sizes],
              "method": "Python perf_counter; compare-only latency; tracemalloc peak is Python allocations; "
                        "environment-dependent; not a strict performance acceptance gate."}
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    if report["accuracy"]["failed_cases"]:
        raise SystemExit("Accuracy regression detected: " + ", ".join(report["accuracy"]["failed_cases"]))


if __name__ == "__main__":
    main()
