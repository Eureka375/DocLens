"""Version diff contract cases with independently labeled expected spans."""

import json
from pathlib import Path

import pytest

from doclens.diff import compare
from doclens.documents import read_document


CASES = json.loads((Path(__file__).parent / "fixtures" / "diff_cases.json").read_text(encoding="utf-8"))


def _case_snapshot(tmp_path, stem, text):
    path = tmp_path / f"{stem}.txt"
    path.write_text(text, encoding="utf-8")
    return read_document(path)


def _excerpt(document, span):
    return document.text[span.start:span.end]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_labeled_diff_cases(tmp_path, case):
    old = _case_snapshot(tmp_path, "old", case["old"])
    new = _case_snapshot(tmp_path, "new", case["new"])
    result = compare(old, new)
    actual = [
        {
            "kind": change.kind,
            "left": _excerpt(old, change.left),
            "right": _excerpt(new, change.right),
        }
        for change in result.changes
    ]
    expected = case["expected"]
    if case.get("unordered"):
        key = lambda item: (item["kind"], item["left"], item["right"])
        actual, expected = sorted(actual, key=key), sorted(expected, key=key)
    assert actual == expected, case["description"]
    assert not result.used_coarse_matching
    for change in result.changes:
        assert 0 <= change.left.start <= change.left.end <= len(old.text)
        assert 0 <= change.right.start <= change.right.end <= len(new.text)
        assert change.left_location and change.right_location
        for span in change.left_edits:
            assert change.left.start <= span.start < span.end <= change.left.end
        for span in change.right_edits:
            assert change.right.start <= span.start < span.end <= change.right.end
        if change.kind == "move":
            assert _excerpt(old, change.left) == _excerpt(new, change.right)
    if "edits" in case:
        matched = next(change for change in result.changes if change.kind == "replace")
        assert [_excerpt(old, s) for s in matched.left_edits] == case["edits"]["left"]
        assert [_excerpt(new, s) for s in matched.right_edits] == case["edits"]["right"]


def test_similar_adjacent_paragraphs_keep_two_independent_evidence_ranges(tmp_path):
    old = _case_snapshot(tmp_path, "old", "标题\n采购金额为100元。\n运输期限为30天。\n结束")
    new = _case_snapshot(tmp_path, "new", "标题\n采购金额为200元。\n运输期限为15天。\n结束")
    result = compare(old, new)
    assert [_excerpt(old, c.left) for c in result.changes] == [
        "采购金额为100元。", "运输期限为30天。"
    ]
    assert [_excerpt(new, c.right) for c in result.changes] == [
        "采购金额为200元。", "运输期限为15天。"
    ]


def test_large_ambiguous_alignment_remains_bounded(tmp_path):
    old = _case_snapshot(tmp_path, "old", "\n".join(f"原有条款{n:04d}" for n in range(300)))
    new = _case_snapshot(tmp_path, "new", "\n".join(f"新的条款{n:04d}" for n in range(300)))
    result = compare(old, new)
    assert len(result.changes) >= 1
    assert all(c.left_location and c.right_location for c in result.changes)
