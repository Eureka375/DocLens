"""Evidence-validation regressions independent of a live model provider."""

import json

import pytest

from doclens.analysis import AnalysisError, parse_analysis, prepare_analysis
from doclens.diff import compare
from doclens.documents import read_document


ENDPOINT = "https://example.org/v1/chat/completions"


def _make_draft(tmp_path):
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("标题\n交付期限为30天。\n分隔\n付款金额为100元。\n尾部", encoding="utf-8")
    new.write_text("标题\n交付期限为15天。\n分隔\n付款金额为200元。\n尾部", encoding="utf-8")
    a, b = read_document(old), read_document(new)
    return prepare_analysis(a, b, compare(a, b), 1, 2, ENDPOINT, "test")


def _response(ids):
    finding = {"category": "time", "summary": "交付期限变化", "impact": "可能影响排期", "evidence_ids": ids}
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps({"findings": [finding]}, ensure_ascii=False)
    }}]}, ensure_ascii=False).encode("utf-8")


def test_comparative_findings_require_both_original_and_new_evidence(tmp_path):
    draft = _make_draft(tmp_path)
    first, second = (e.id for e in draft.evidence[:2])
    assert [e.side for e in draft.evidence[:2]] == ["原文", "新版"]
    with pytest.raises(AnalysisError, match="证据引用"):
        parse_analysis(_response([first]), draft)
    report = parse_analysis(_response([first, second]), draft)
    assert report[0].evidence[0].text == "交付期限为30天。"
    assert report[0].evidence[1].text == "交付期限为15天。"


def test_multi_group_references_cannot_omit_one_side(tmp_path):
    draft = _make_draft(tmp_path)
    ids = [e.id for e in draft.evidence]
    assert len(ids) == 4
    with pytest.raises(AnalysisError, match="证据引用"):
        parse_analysis(_response(ids[:3]), draft)
    result = parse_analysis(_response(ids), draft)
    assert len(result[0].evidence) == 4
    assert {e.change_index for e in result[0].evidence} == {0, 1}


def test_unknown_evidence_id_is_rejected(tmp_path):
    draft = _make_draft(tmp_path)
    with pytest.raises(AnalysisError, match="证据引用"):
        parse_analysis(_response(["D99-OLD"]), draft)


def _custom_response(finding):
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps({"findings": [finding]}, ensure_ascii=False)
    }}]}, ensure_ascii=False).encode("utf-8")


def test_literal_quotes_are_checked_against_the_exact_snapshot(tmp_path):
    draft = _make_draft(tmp_path)
    old, new = (e.id for e in draft.evidence[:2])
    entry = {
        "category": "time", "summary": "交付期限缩短",
        "impact": "可能影响项目安排", "evidence_ids": [old, new],
        "quotes": [{"id": old, "text": "30天"}, {"id": new, "text": "15天"}],
    }
    finding, = parse_analysis(_custom_response(entry), draft)
    assert finding.quotes == ((old, "30天"), (new, "15天"))
    assert "原文摘录已核对" in finding.verification

    invalid = {**entry, "quotes": [{"id": old, "text": "90天"}, {"id": new, "text": "15天"}]}
    with pytest.raises(AnalysisError, match="证据引用"):
        parse_analysis(_custom_response(invalid), draft)
    invalid = {**entry, "quotes": [{"id": old, "text": "30天"}]}
    with pytest.raises(AnalysisError):
        parse_analysis(_custom_response(invalid), draft)


def test_numeric_direction_contradiction_is_rejected(tmp_path):
    draft = _make_draft(tmp_path)
    old, new = (e.id for e in draft.evidence[:2])
    entry = {
        "category": "time", "summary": "交付期限延长",
        "impact": "可能延后项目", "evidence_ids": [old, new],
        "quotes": [{"id": old, "text": "30天"}, {"id": new, "text": "15天"}],
    }
    with pytest.raises(AnalysisError, match="证据引用"):
        parse_analysis(_custom_response(entry), draft)
    entry["summary"] = "交付期限缩短"
    assert parse_analysis(_custom_response(entry), draft)[0].quotes


def test_backward_compatible_model_without_quotes_is_flagged_unverified(tmp_path):
    draft = _make_draft(tmp_path)
    old, new = (e.id for e in draft.evidence[:2])
    finding, = parse_analysis(_response([old, new]), draft)
    assert "需人工核对" in finding.verification
    assert not finding.quotes
