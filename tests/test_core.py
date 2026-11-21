from copy import deepcopy
from hashlib import sha256
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import pytest

from doclens.documents import DocumentError, read_document
from doclens.diff import compare


def pair(tmp_path, old, new):
    paths = [tmp_path / "原文.txt", tmp_path / "新版.txt"]
    for path, text in zip(paths, (old, new)):
        path.write_bytes(text.encode("utf-8"))
    return [read_document(path) for path in paths]


def snippets(document, spans):
    return [document.text[span.start:span.end] for span in spans]


def test_txt_keeps_original_bytes_and_line_offsets(tmp_path):
    path = tmp_path / "原文.TXT"
    data = "\ufeff甲😀乙\r\n\r\n金额1000\r末尾\n".encode()
    path.write_bytes(data)
    doc = read_document(path)
    assert doc.text == "甲😀乙\n\n金额1000\n末尾\n"
    assert doc.sha256 == sha256(data).hexdigest()
    assert [b.location for b in doc.blocks] == [f"第 {i} 行" for i in range(1, 6)]
    assert [doc.text[b.span.start:b.span.end] for b in doc.blocks] == doc.text.split("\n")
    assert path.read_bytes() == data


def test_encoding_is_explicit(tmp_path):
    path = tmp_path / "旧格式.txt"
    path.write_bytes("金额与期限".encode("gb18030"))
    with pytest.raises(DocumentError, match="GB18030") as error:
        read_document(path)
    assert error.value.code == "encoding"
    assert read_document(path, encoding="gb18030").text == "金额与期限"


def test_docx_order_nested_tables_and_merged_cells(tmp_path):
    path = tmp_path / "条款.docx"
    document = Document()
    heading = document.add_paragraph("正文：")
    hyperlink = OxmlElement("w:hyperlink")
    run = OxmlElement("w:r")
    label = OxmlElement("w:t")
    label.text = "可见链接"
    run.append(label)
    hyperlink.append(run)
    heading._p.append(hyperlink)
    table = document.add_table(rows=1, cols=2)
    cell = table.cell(0, 0).merge(table.cell(0, 1))
    cell.text = "合并内容"
    cell.add_table(rows=1, cols=1).cell(0, 0).text = "内层内容"
    document.add_paragraph("后续正文")
    document.save(path)
    result = read_document(path)
    assert [b.text for b in result.blocks if b.text] == ["正文：可见链接", "合并内容", "内层内容", "后续正文"]
    assert "表 1" in next(b.location for b in result.blocks if b.text == "内层内容")


def test_docx_revisions_rejected_and_omitted_headers_warned(tmp_path):
    path = tmp_path / "修订.docx"
    document = Document()
    document.sections[0].header.paragraphs[0].text = "页眉"
    paragraph = document.add_paragraph("正文")
    document.save(path)
    assert read_document(path).warnings
    revision = OxmlElement("w:ins")
    revision.set(qn("w:id"), "1")
    paragraph._p.append(revision)
    document.save(path)
    with pytest.raises(DocumentError) as error:
        read_document(path)
    assert error.value.code == "tracked_changes"


def test_unextracted_word_field_is_reported(tmp_path):
    path = tmp_path / "含域的条款.docx"
    document = Document()
    paragraph = document.add_paragraph("金额：")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), " REF amount ")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "100"
    run.append(text)
    field.append(run)
    paragraph._p.append(field)
    document.save(path)
    snapshot = read_document(path)
    assert "100" in snapshot.text or snapshot.warnings


def test_long_vertical_merge_does_not_repeat_or_lose_text(tmp_path):
    path = tmp_path / "纵向合并.docx"
    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "合并条款"
    table.cell(1, 1).text = "右列"
    first, following = table.rows
    first._tr.tc_lst[0].vMerge = "restart"
    following._tr.tc_lst[0].vMerge = "continue"
    for _ in range(1100):
        table._tbl.append(deepcopy(following._tr))
    document.save(path)
    result = read_document(path)
    assert result.text.count("合并条款") == 1
    assert result.text.count("右列") == 1101
    assert "第 1102 行第 2 列" in result.blocks[-1].location


@pytest.mark.parametrize("name, data, code", [
    ("broken.docx", b"not a zip", "invalid_docx"),
    ("unsupported.pdf", b"%PDF", "unsupported"),
    ("large.txt", b"a" * 100_001, "text_limit"),
])
def test_invalid_files(tmp_path, name, data, code):
    path = tmp_path / name
    path.write_bytes(data)
    with pytest.raises(DocumentError) as error:
        read_document(path)
    assert error.value.code == code


def test_docx_zip_size_limit(tmp_path):
    path = tmp_path / "huge.docx"
    from zipfile import ZIP_DEFLATED
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"a" * (33 * 1024 * 1024))
    with pytest.raises(DocumentError) as error:
        read_document(path)
    assert error.value.code == "archive_limit"


def test_diff_evidence_preserves_unicode_numbers_and_adjacent_edits(tmp_path):
    left, right = pair(tmp_path, "标题\n甲😀乙：7天\n保留\n删除条款\n尾部", "标题\n甲😀乙：3天\n保留\n尾部\n新增条款")
    result = compare(left, right)
    assert [change.kind for change in result.changes] == ["replace", "delete", "insert"]
    first = result.changes[0]
    assert snippets(left, first.left_edits) == ["7"]
    assert snippets(right, first.right_edits) == ["3"]
    assert snippets(left, [result.changes[1].left]) == ["删除条款"]
    assert snippets(right, [result.changes[2].right]) == ["新增条款"]
    for change in result.changes:
        assert 0 <= change.left.start <= change.left.end <= len(left.text)
        assert 0 <= change.right.start <= change.right.end <= len(right.text)


@pytest.mark.parametrize("old,new,kinds", [
    ("", "", []), ("", "新增", ["insert"]), ("删除", "", ["delete"]),
    ("甲\n", "甲", ["delete"]), ("甲\n条款内容\n乙", "甲\n条款\n内容\n乙", ["replace"]),
    ("原文\n内容", "原文\n内容", []),
    ("重复\n换位甲\n重复\n换位乙", "重复\n换位乙\n重复\n换位甲", ["insert", "delete"]),
])
def test_empty_identical_split_and_reordered_text(tmp_path, old, new, kinds):
    assert [c.kind for c in compare(*pair(tmp_path, old, new)).changes] == kinds


def test_large_replace_uses_exact_common_edges(tmp_path):
    left, right = pair(tmp_path, "甲" * 49_000 + "7" + "乙" * 49_000,
                       "甲" * 49_000 + "3" + "乙" * 49_000)
    change, = compare(left, right).changes
    assert snippets(left, change.left_edits) == ["7"]
    assert snippets(right, change.right_edits) == ["3"]


def test_comparison_checks_cancel_before_work(tmp_path):
    left, right = pair(tmp_path, "原文", "新版")
    def stop():
        raise InterruptedError
    with pytest.raises(InterruptedError):
        compare(left, right, check_cancelled=stop)
