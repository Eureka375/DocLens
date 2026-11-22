import json

import pytest

from doclens.analysis import AnalysisError, prepare_analysis, parse_analysis
from doclens.diff import compare
from doclens.documents import read_document


@pytest.fixture
def comparison(tmp_path):
    left, right = tmp_path / "私密原稿.txt", tmp_path / "私密新版.txt"
    left.write_text("内部标识 SECRET\n用户可以在 7 天内撤回。\n金额100元。", encoding="utf-8")
    right.write_text("内部标识 SECRET\n用户可以在 3 天内撤回。\n金额200元。", encoding="utf-8")
    snapshots = read_document(left), read_document(right)
    return (*snapshots, compare(*snapshots))


def fake_response(ids, **updates):
    finding = {"category": "time", "summary": "撤回期限缩短", "impact": "用户少了4天", "evidence_ids": ids}
    finding.update(updates)
    content = json.dumps({"findings": [finding]}, ensure_ascii=False)
    return json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}).encode()


def test_draft_sends_only_selected_text_and_validates_references(comparison):
    draft = prepare_analysis(*comparison, 1, 1, "https://models.example/v1/chat/completions", "example")
    assert "7 天内撤回" in draft.preview and "3 天内撤回" in draft.preview
    assert "SECRET" not in draft.preview and "私密" not in draft.preview
    body = json.loads(draft.body)
    assert body["model"] == "example" and body["stream"] is False
    assert body["max_completion_tokens"] == 1400
    assert "max_tokens" not in body
    evidence = json.loads(body["messages"][1]["content"])
    assert [e["text"] for e in evidence] == [e.text for e in draft.evidence]
    ids = [e.id for e in draft.evidence]
    assert len(ids) == 2
    report = parse_analysis(fake_response(ids), draft)
    assert report[0].impact == "用户少了4天"
    assert report[0].evidence[1].change_index == 0
    for invalid in (["fake"], [], ids + ids, [1]):
        with pytest.raises(AnalysisError):
            parse_analysis(fake_response(invalid), draft)
    with pytest.raises(AnalysisError):
        parse_analysis(fake_response(ids, impact={"unsafe": True}), draft)


def test_official_deepseek_endpoint_uses_its_documented_request_format(comparison):
    endpoint = "https://api.deepseek.com/chat/completions"
    draft = prepare_analysis(*comparison, 1, 1, endpoint, "deepseek-flash")
    body = json.loads(draft.body)
    assert body["model"] == "deepseek-flash"
    assert body["max_tokens"] == 1400
    assert "max_completion_tokens" not in body
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    ids = [e.id for e in draft.evidence]
    assert parse_analysis(fake_response(ids), draft)[0].evidence[0].id == ids[0]


def test_deepseek_parameters_only_apply_to_the_exact_api_hostname(comparison):
    draft = prepare_analysis(*comparison, 1, 1,
                             "https://api.deepseek.com.example/chat/completions", "deepseek-flash")
    body = json.loads(draft.body)
    assert body["max_completion_tokens"] == 1400
    assert not {"max_tokens", "thinking", "response_format"}.intersection(body)


def test_endpoint_and_budget_validated_before_request(comparison, tmp_path):
    for endpoint in ("http://models.example/chat/completions", "https://u:p@models.example/chat/completions",
                     "https://models.example/chat/completions?key=secret", "file:///chat/completions"):
        with pytest.raises(AnalysisError):
            prepare_analysis(*comparison, 1, 1, endpoint, "model")
    left_path, right_path = tmp_path / "long-a.txt", tmp_path / "long-b.txt"
    left_path.write_text("甲" * 13_000, encoding="utf-8")
    right_path.write_text("乙" * 13_000, encoding="utf-8")
    left, right = read_document(left_path), read_document(right_path)
    with pytest.raises(AnalysisError, match="缩小"):
        prepare_analysis(left, right, compare(left, right), 1, 1,
                         "https://models.example/v1/chat/completions", "model")


def test_cached_evidence_is_bound_to_offsets_in_the_decoded_snapshots(tmp_path):
    paths = [tmp_path / "旧.txt", tmp_path / "新.txt"]
    for path, text in zip(paths, ["文档\nABC", "文档\nXYZ"]):
        path.write_text(text, encoding="utf-8")
    drafts = []
    for encoding in ("utf-8", "gb18030"):
        old, new = (read_document(path, encoding) for path in paths)
        drafts.append(prepare_analysis(old, new, compare(old, new), 1, 1,
                                       "https://models.example/v1/chat/completions", "model"))
    assert drafts[0].body == drafts[1].body
    assert drafts[0].evidence[1].span != drafts[1].evidence[1].span
    assert drafts[0].fingerprint != drafts[1].fingerprint


@pytest.mark.parametrize("provider,token,json_mode", [
    ("compatible", "max_completion_tokens", False),
    ("json", "max_completion_tokens", True), ("deepseek", "max_tokens", True),
])
def test_explicit_provider_request_formats(comparison, provider, token, json_mode):
    draft = prepare_analysis(*comparison, 1, 1, "https://models.example/v1/chat/completions", "model", provider)
    body = json.loads(draft.body)
    assert body[token] == 1400
    assert (body.get("response_format") == {"type": "json_object"}) == json_mode
    assert provider in draft.scope


def test_invalid_provider_and_cache_separation(comparison):
    args = (*comparison, 1, 1, "https://models.example/v1/chat/completions", "model")
    with pytest.raises(AnalysisError):
        prepare_analysis(*args, "unknown")
    assert prepare_analysis(*args, "json").fingerprint != prepare_analysis(*args).fingerprint


def test_analysis_rejects_one_sided_comparisons_and_accepts_academic_categories(comparison):
    draft = prepare_analysis(*comparison, 1, 1, "https://models.example/chat/completions", "model")
    ids = [e.id for e in draft.evidence]
    with pytest.raises(AnalysisError):
        parse_analysis(fake_response(ids[:1]), draft)
    for category in ("research_question", "method", "data", "result", "conclusion", "citation"):
        assert parse_analysis(fake_response(ids, category=category), draft)[0].category == category


@pytest.mark.parametrize("old,new", [("", "新增实验说明"), ("删除实验说明", "")])
def test_single_sided_insert_delete_evidence_is_valid(tmp_path, old, new):
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, text in zip(paths, (old, new)):
        path.write_text(text, encoding="utf-8")
    left, right = map(read_document, paths)
    draft = prepare_analysis(left, right, compare(left, right), 1, 1,
                             "https://models.example/chat/completions", "model")
    assert len(parse_analysis(fake_response([e.id for e in draft.evidence]), draft)) == 1


def test_academic_evidence_includes_heading_context_without_unchanged_body(tmp_path):
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, count in zip(paths, (30, 60)):
        path.write_text(f"2 Methods\n2.1 Dataset\nWe use {count} samples.\nUNSELECTED BODY", encoding="utf-8")
    left, right = map(read_document, paths)
    draft = prepare_analysis(left, right, compare(left, right), 1, 1,
                             "https://models.example/chat/completions", "model")
    payload = json.loads(json.loads(draft.body)["messages"][1]["content"])
    assert payload[0]["section_path"] == ["2 Methods", "2.1 Dataset"]
    assert "2 Methods / 2.1 Dataset" in draft.preview
    assert "UNSELECTED BODY" not in draft.body.decode()


def test_batch_plans_cover_every_group_with_small_requests(tmp_path):
    from doclens.analysis import prepare_batches
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, value in zip(paths, (30, 60)):
        path.write_text("\n".join(f"# Section {i}\nSamples {value}." for i in range(9)), encoding="utf-8")
    left, right = map(read_document, paths)
    comparison = compare(left, right)
    assert len(comparison.changes) == 9
    batches = prepare_batches(left, right, comparison, 1, 9, "https://models.example/chat/completions", "model")
    groups = [{e.change_index for e in b.evidence} for b in batches]
    assert [len(g) for g in groups] == [4, 4, 1]
    assert set.union(*groups) == set(range(9))
    assert len(set.intersection(groups[0], groups[1])) == 0
    assert all(len(json.loads(b.body)["messages"][1]["content"]) <= 12_000 for b in batches)
    missing = prepare_batches(left, right, comparison, 1, 9, "https://models.example/chat/completions", "model",
                              only={1, 7})
    assert {e.change_index for b in missing for e in b.evidence} == {1, 7}


def test_batch_budget_splits_before_send_and_rejects_oversized_task(tmp_path, monkeypatch):
    import doclens.analysis as analysis
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, value in zip(paths, ("old", "new")):
        path.write_text("\n".join(f"# Section {i}\n" + value + "x" * 3500 for i in range(4)), encoding="utf-8")
    left, right = map(read_document, paths)
    args = (left, right, compare(left, right), 1, 4, "https://models.example/chat/completions", "model")
    assert len(analysis.prepare_batches(*args)) == 4
    monkeypatch.setattr(analysis, "MAX_TASK_CHARS", 10_000)
    with pytest.raises(AnalysisError, match="总"):
        analysis.prepare_batches(*args)
