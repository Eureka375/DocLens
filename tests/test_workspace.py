from pathlib import Path

from docx import Document
import pytest

from doclens.workspace import WorkspaceIndex


def files(tmp_path):
    folder = tmp_path / "资料"
    folder.mkdir()
    (folder / "中文.txt").write_text('责任在申请人；总额100%，编号a_b。"引号" ABC\n第二行有责任。', encoding="utf-8")
    sub = folder / "子目录"
    sub.mkdir()
    word = Document()
    word.add_paragraph("补充规定")
    word.add_table(rows=1, cols=1).cell(0, 0).text = "金额与责任"
    word.save(sub / "规定.docx")
    (folder / "坏文件.docx").write_bytes(b"not zip")
    return folder


def test_folder_scope_literal_short_queries_and_exact_preview(tmp_path):
    folder = files(tmp_path)
    workspace = WorkspaceIndex(folder, tmp_path / "index.sqlite3")
    summary = workspace.scan()
    assert summary.count == 1 and len(summary.issues) == 1
    for term in ("责", "责任", "100%", "a_b", '"引号"', "ABC"):
        page = workspace.search(term)
        assert page.hits
        for hit in page.hits:
            text = workspace.preview(hit)
            assert text[hit.span.start:hit.span.end] == term
    assert not workspace.search("abc").hits
    assert not workspace.search("不存在").hits
    assert [hit.relative_path for hit in workspace.search("责任").hits] == ["中文.txt", "中文.txt"]
    assert workspace.scan(recursive=True).count == 2
    assert workspace.search("金额").hits[0].relative_path == "子目录/规定.docx"


def test_cache_reuse_refresh_and_cancellation_are_atomic(tmp_path):
    folder = files(tmp_path)
    db = tmp_path / "index.sqlite3"
    index = WorkspaceIndex(folder, db)
    index.scan()
    assert WorkspaceIndex(folder, db).scan().reused == 1
    old_hit = index.search("责任").hits[0]
    (folder / "中文.txt").write_text("改为审批人留存。", encoding="utf-8")
    checks = 0

    def cancel():
        nonlocal checks
        checks += 1
        if checks >= 5:
            raise InterruptedError

    with pytest.raises(InterruptedError):
        index.scan(check_cancelled=cancel)
    assert index.search("责任").hits
    assert not index.search("审批人").hits
    assert index.scan().reused == 0
    assert index.search("审批人").hits
    assert not index.search("责任").hits
    with pytest.raises(ValueError, match="重新搜索"):
        index.preview(old_hit)
    (folder / "中文.txt").unlink()
    assert index.scan().count == 0
    assert not index.search("审批人").hits


def test_gb18030_fallback_only_after_utf8_failure(tmp_path):
    folder = tmp_path / "扫描"
    folder.mkdir()
    (folder / "旧文.txt").write_bytes("期限".encode("gb18030"))
    (folder / "新文.txt").write_text("文档", encoding="utf-8")
    index = WorkspaceIndex(folder, tmp_path / "index.sqlite3")
    assert index.scan().count == 1
    assert index.scan(legacy_txt=True).count == 2
    assert index.search("期限").hits
    assert index.search("文档").hits
