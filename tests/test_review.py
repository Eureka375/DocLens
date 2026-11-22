from pathlib import Path

import pytest

from doclens.diff import compare
from doclens.documents import read_document
from doclens.review import ReviewSession


def session(tmp_path):
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, text in zip(paths, ("# Methods\nSamples 30.\n# Results\nValue 10.",
                                  "# Methods\nSamples 60.\n# Results\nValue 20.")):
        path.write_text(text, encoding="utf-8")
    left, right = map(read_document, paths)
    return ReviewSession(left, right, compare(left, right))


def test_review_filters_preserve_original_group_ids_and_notes(tmp_path):
    review = session(tmp_path)
    review.update(1, reviewed=True, note="核对结果 <script>alert(1)</script>")
    assert [r["index"] for r in review.rows(query="Results")] == [1]
    assert [r["index"] for r in review.rows(state="reviewed")] == [1]
    assert [r["index"] for r in review.rows(state="pending")] == [0]
    assert review.rows(kind="insert") == []
    assert review.rows(query="核对结果")[0]["note"].startswith("核对结果")
    assert review.rows()[0]["numbersChanged"]
    with pytest.raises(ValueError):
        review.update(20, reviewed=True)


def test_report_exports_all_groups_and_escapes_content(tmp_path):
    review = session(tmp_path)
    review.update(0, reviewed=True, note='<img src=x onerror="alert(1)">')
    destination = tmp_path / "report.html"
    review.export_html(destination, (), {0: "未覆盖"})
    html = destination.read_text(encoding="utf-8")
    assert "Samples 30." in html and "Samples 60." in html and "Value 20." in html
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in html
    assert '<img src=x' not in html
    assert "已核对" in html and "未覆盖" in html
    assert "格式、图片、公式" in html
    assert str(tmp_path) not in html
    assert review.left.path.read_text(encoding="utf-8").startswith("# Methods")


def test_report_does_not_overwrite_source_and_atomic_failure_preserves_report(tmp_path, monkeypatch):
    import doclens.review as module
    review = session(tmp_path)
    with pytest.raises(ValueError):
        review.export_html(review.left.path, (), {})
    target = tmp_path / "report.html"
    target.write_text("previous report", encoding="utf-8")
    def fail(*args):
        raise OSError("write failed")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        review.export_html(target, (), {})
    assert target.read_text(encoding="utf-8") == "previous report"
    assert not list(tmp_path.glob("doclens-report-*"))
