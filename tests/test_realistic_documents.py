"""End-to-end regression on representative, structured DOCX and multipage PDF.

Fixtures are deterministic synthetic work documents (not a random benchmark).
They exercise extraction -> paragraph alignment -> source coordinates.
"""

from pathlib import Path

from docx import Document

from doclens.diff import compare
from doclens.documents import read_document


ROOT = Path(__file__).resolve().parents[1]


def _write_report(path: Path, *, updated: bool) -> None:
    document = Document()
    document.add_heading("设备借用管理办法", level=1)
    document.add_paragraph("文件编号 DL-2026 · 使用范围：实验室设备")
    document.add_heading("第一章 总则", level=2)
    moved = ("借用人须在15天内归还设备并提交完整的使用记录。" if updated
             else "借用人须在30天内归还设备并提交完整的使用记录。")
    for number in range(32):
        if not updated and number == 4:
            document.add_paragraph(moved)
        document.add_paragraph(f"第{number + 1:02d}条 设备使用登记应符合实验室标准流程，条款编号{number + 100}。")
        if updated and number == 19:
            document.add_paragraph(moved)
    document.add_heading("第二章 费用与审批", level=2)
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "项目"
    table.cell(0, 1).text = "审批限额"
    table.cell(1, 0).text = "临时租用"
    table.cell(1, 1).text = "1500元" if updated else "1000元"
    document.add_paragraph("附则：本文档仅用于软件测试。")
    document.save(path)


def test_docx_with_headings_table_and_edited_move(tmp_path):
    old_file, new_file = tmp_path / "办法-旧版.docx", tmp_path / "办法-新版.docx"
    _write_report(old_file, updated=False)
    _write_report(new_file, updated=True)
    old, new = read_document(old_file), read_document(new_file)
    comparison = compare(old, new)
    changes = comparison.changes
    assert not comparison.used_coarse_matching
    moved = [c for c in changes if c.kind == "move_replace"]
    assert len(moved) == 1
    change = moved[0]
    assert old.text[change.left.start:change.left.end] == "借用人须在30天内归还设备并提交完整的使用记录。"
    assert new.text[change.right.start:change.right.end] == "借用人须在15天内归还设备并提交完整的使用记录。"
    assert [old.text[s.start:s.end] for s in change.left_edits] == ["30"]
    assert [new.text[s.start:s.end] for s in change.right_edits] == ["15"]
    assert change.left_location != change.right_location
    changes_in_table = [c for c in changes if c.kind == "replace"
                        and "1000元" in old.text[c.left.start:c.left.end]]
    assert len(changes_in_table) == 1
    assert "1500元" in new.text[changes_in_table[0].right.start:changes_in_table[0].right.end]
    assert "表" in changes_in_table[0].left_location


def test_existing_multi_page_pdf_move_and_numeric_edit():
    folder = ROOT / "examples" / "PDF比对"
    old, new = (read_document(folder / name) for name in ("原版.pdf", "新版.pdf"))
    comparison = compare(old, new)
    assert [c.kind for c in comparison.changes] == ["move", "replace"]
    move, edit = comparison.changes
    assert old.text[move.left.start:move.left.end] == new.text[move.right.start:move.right.end]
    assert "第 1 页" in move.left_location and "第 2 页" in move.right_location
    assert [old.text[s.start:s.end] for s in edit.left_edits] == ["14"]
    assert [new.text[s.start:s.end] for s in edit.right_edits] == ["7"]


def test_existing_long_realistic_text_has_five_separately_navigable_changes():
    folder = ROOT / "examples" / "跳转测试"
    old, new = (read_document(folder / name) for name in ("原版.txt", "新版.txt"))
    changes = compare(old, new).changes
    assert len(changes) == 5
    assert all(old.text[c.left.start:c.left.end] or new.text[c.right.start:c.right.end]
               for c in changes)
    assert [old.text[s.start:s.end] for s in changes[-1].left_edits] == ["45"]
    assert [new.text[s.start:s.end] for s in changes[-1].right_edits] == ["90"]


def test_ambiguous_similar_repeated_paragraphs_do_not_force_edited_moves(tmp_path):
    common = "实验室设备借用须提交完整审批表，并保留纸质记录以备审查。"
    old_file, new_file = tmp_path / "a.txt", tmp_path / "b.txt"
    old_file.write_text("起始\n" + common.replace("审批表", "30日审批表")
                        + "\n固定段一\n" + common.replace("审批表", "31日审批表")
                        + "\n固定段二\n结尾", encoding="utf-8")
    new_file.write_text("起始\n固定段一\n固定段二\n"
                        + common.replace("审批表", "15日审批表") + "\n"
                        + common.replace("审批表", "16日审批表") + "\n结尾", encoding="utf-8")
    old, new = read_document(old_file), read_document(new_file)
    assert all(c.kind != "move_replace" for c in compare(old, new).changes)
