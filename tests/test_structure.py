from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import pytest

from doclens.documents import read_document
from doclens.diff import compare


def test_docx_structure_and_original_offsets(tmp_path):
    path = tmp_path / "structured.docx"
    doc = Document()
    doc.add_heading("服务协议", 1)
    doc.add_heading("交付", 2)
    doc.add_paragraph("提交材料", style="List Bullet")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "合并😀"
    table.cell(0, 0).add_table(rows=1, cols=1).cell(0, 0).text = "内层"
    doc.save(path)
    snapshot = read_document(path)
    assert snapshot.blocks[0].kind == "heading"
    assert snapshot.blocks[1].heading_level == 2
    listed = snapshot.blocks[2]
    assert listed.kind == "list_item"
    assert listed.section_path == ("服务协议", "交付")
    merged = next(b for b in snapshot.blocks if b.text == "合并😀")
    nested = next(b for b in snapshot.blocks if b.text == "内层")
    assert merged.table_path == ((1, 1, 1),)
    assert nested.table_path == ((1, 1, 1), (1, 1, 1))
    assert merged.kind == nested.kind == "table_cell"
    assert all(snapshot.text[b.span.start:b.span.end] == b.text for b in snapshot.blocks)


def snapshots(tmp_path, old, new):
    result = []
    for name, text in (("old.txt", old), ("new.txt", new)):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        result.append(read_document(path))
    return result


def test_txt_heading_hierarchy_is_conservative(tmp_path):
    left, _ = snapshots(tmp_path, "# 总则\n## 交付\n正文😀\n第一章 附则\n结束。", "")
    assert left.blocks[1].heading_level == 2
    assert left.blocks[2].section_path == ("总则", "交付")
    assert left.blocks[3].heading_level == 1
    assert left.blocks[4].kind == "paragraph"


def test_adjacent_modified_paragraphs_have_separate_evidence(tmp_path):
    left, right = snapshots(tmp_path, "# 交付\n期限为7天\n金额为100元", "# 交付\n期限为3天\n金额为200元")
    result = compare(left, right)
    assert len(result.changes) == 2
    assert [left.text[c.left.start:c.left.end] for c in result.changes] == ["期限为7天", "金额为100元"]
    assert [right.text[c.right.start:c.right.end] for c in result.changes] == ["期限为3天", "金额为200元"]


def test_repeated_body_does_not_align_across_sections(tmp_path):
    left, right = snapshots(tmp_path, "# 甲\n共同条款\n# 乙\n乙的原文", "# 甲\n甲的新文\n# 乙\n共同条款")
    result = compare(left, right)
    assert [c.kind for c in result.changes] == ["replace", "replace"]
    assert all("#" not in left.text[c.left.start:c.left.end] for c in result.changes)


def test_unrelated_adjacent_blocks_remain_one_region(tmp_path):
    left, right = snapshots(tmp_path, "# 标题\n甲甲甲\n乙乙乙", "# 标题\n丙丙丙\n丁丁丁")
    assert len(compare(left, right).changes) == 1


def test_custom_inherited_heading_and_body_override(tmp_path):
    from docx.enum.style import WD_STYLE_TYPE
    doc = Document()
    style = doc.styles.add_style("Custom title", WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = doc.styles["Heading 2"]
    doc.add_paragraph("自定义标题", style=style)
    paragraph = doc.add_paragraph("不作为标题", style=style)
    outline = OxmlElement("w:outlineLvl")
    outline.set(qn("w:val"), "9")
    paragraph._p.get_or_add_pPr().append(outline)
    path = tmp_path / "styles.docx"
    doc.save(path)
    snapshot = read_document(path)
    assert snapshot.blocks[0].heading_level == 2
    assert snapshot.blocks[1].kind == "paragraph"
    assert snapshot.blocks[1].section_path == ("自定义标题",)


@pytest.mark.parametrize("old,new", [
    ("# 重复\n甲\n# 重复\n乙", "# 重复\n丙\n# 重复\n丁"),
    ("# 原标题\n期限7天", "# 新标题\n期限3天"),
    ("# 交付\n条款内容", "# 交付\n条款\n内容"),
    ("# 交付\n条款\n内容", "# 交付\n条款内容"),
    ("# 交付\n期限7天\n", "# 交付\n期限3天\n"),
])
def test_fallback_regions_preserve_all_changed_text(tmp_path, old, new):
    left, right = snapshots(tmp_path, old, new)
    result = compare(left, right)
    assert result.changes
    # Removing unchanged gaps and inserting each right span reconstructs the
    # right display text for these monotonic replacement-only cases.
    rebuilt = left.text
    for change in reversed(result.changes):
        assert change.kind == "replace"
        rebuilt = rebuilt[:change.left.start] + right.text[change.right.start:change.right.end] + rebuilt[change.left.end:]
    assert rebuilt == right.text


def test_section_work_budget_and_cancellation(tmp_path, monkeypatch):
    import doclens.diff as diff
    monkeypatch.setattr(diff, "BLOCK_PAIR_LIMIT", 1)
    left, right = snapshots(tmp_path, "# 甲\na\nb\n# 乙\nc\nd", "# 甲\nx\ny\n# 乙\nz\nw")
    assert compare(left, right).used_coarse_matching
    calls = 0
    def stop():
        nonlocal calls
        calls += 1
        if calls == 4:
            raise InterruptedError
    with pytest.raises(InterruptedError):
        compare(left, right, stop)


def test_table_changes_are_split_by_cell(tmp_path):
    snapshots_ = []
    for name, values in (("old", ("金额100元", "期限7天")), ("new", ("金额200元", "期限3天"))):
        doc = Document()
        table = doc.add_table(rows=1, cols=2)
        for cell, value in zip(table.rows[0].cells, values):
            cell.text = value
        path = tmp_path / (name + ".docx")
        doc.save(path)
        snapshots_.append(read_document(path))
    result = compare(*snapshots_)
    assert len(result.changes) == 2
    assert "第 1 行第 1 列" in result.changes[0].left_location
    assert "第 1 行第 2 列" in result.changes[1].left_location


def test_unchanged_section_does_not_spend_matching_budget(tmp_path):
    common = "# 稳定章节\n" + "\n".join(f"不变条款{i}" for i in range(1000))
    left, right = snapshots(tmp_path, common + "\n# 费用\namount100", common + "\n# 费用\namount200")
    result = compare(left, right)
    assert not result.used_coarse_matching
    assert len(result.changes) == 1
