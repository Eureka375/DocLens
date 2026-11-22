from hashlib import sha256

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject
import pytest

from doclens.analysis import prepare_analysis
from doclens.diff import compare
from doclens.documents import DocumentError, read_document
from doclens.workspace import WorkspaceIndex


def write_pdf(path, pages, *, rotate_page=None, password=None, repeated_forms=0):
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for index, lines in enumerate(pages):
        page = writer.add_blank_page(width=612, height=792)
        if index == rotate_page:
            page.rotate(90)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        if repeated_forms:
            form = DecodedStreamObject()
            form.update({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Form"),
                NameObject("/BBox"): ArrayObject([NumberObject(n) for n in (0, 0, 200, 50)]),
                NameObject("/Resources"): page["/Resources"],
            })
            form.set_data(b"BT /F1 10 Tf 0 30 Td (Repeated) Tj ET")
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/XObject"): DictionaryObject({NameObject("/F"): writer._add_object(form)}),
            })
            stream = b"/F Do\n" * repeated_forms
        elif isinstance(lines, bytes):
            stream = lines
        elif lines is None:
            # A tiny image-only page has no extractable text.
            stream = b"q 50 0 0 50 72 650 cm BI /W 1 /H 1 /CS /RGB /BPC 8 ID \x12\x34\x56 EI Q"
        else:
            drawn = [f"1 0 0 1 72 {730 - row * 25} Tm ({line}) Tj"
                     for row, line in enumerate(lines)]
            stream = ("BT /F1 14 Tf " + "\n".join(drawn) + " ET").encode("ascii")
        content = DecodedStreamObject()
        content.set_data(stream)
        page[NameObject("/Contents")] = writer._add_object(content)
    if password is not None:
        writer.encrypt(password, algorithm="RC4-128")
    writer.write(str(path))


@pytest.mark.parametrize("old_format", ["txt", "docx", "pdf"])
@pytest.mark.parametrize("new_format", ["txt", "docx", "pdf"])
def test_academic_pipeline_across_all_supported_format_pairs(tmp_path, old_format, new_format):
    from docx import Document
    from doclens.analysis import parse_analysis
    import json
    snapshots = []
    for name, suffix, count in (("old", old_format, 30), ("new", new_format, 60)):
        path = tmp_path / f"{name}.{suffix}"
        lines = ["2 Methods", "2.1 Dataset", f"We use {count} samples."]
        if suffix == "pdf":
            write_pdf(path, [lines])
        elif suffix == "docx":
            document = Document()
            document.add_heading(lines[0], 1)
            document.add_heading(lines[1], 2)
            document.add_paragraph(lines[2])
            document.save(path)
        else:
            path.write_text("\n".join(lines), encoding="utf-8")
        original = path.read_bytes()
        snapshots.append(read_document(path))
        assert path.read_bytes() == original
    left, right = snapshots
    comparison = compare(left, right)
    change, = comparison.changes
    assert left.text[change.left_word_edits[0].start:change.left_word_edits[0].end] == "30"
    assert right.text[change.right_word_edits[0].start:change.right_word_edits[0].end] == "60"
    draft = prepare_analysis(left, right, comparison, 1, 1,
                             "https://models.example/chat/completions", "model", "json")
    assert all(e.section_path == ("2 Methods", "2.1 Dataset") for e in draft.evidence)
    finding = {"category": "data", "summary": "样本数由30变为60", "impact": "需核对实验设置",
               "evidence_ids": [e.id for e in draft.evidence]}
    response = json.dumps({"choices": [{"message": {"content": json.dumps({"findings": [finding]})}}]}).encode()
    report, = parse_analysis(response, draft)
    for snapshot, evidence in zip(snapshots, report.evidence):
        assert snapshot.text[evidence.span.start:evidence.span.end] == evidence.text


def test_pdf_pages_and_text_offsets_survive_rotation_and_missing_text(tmp_path):
    path = tmp_path / "报告.PDF"
    write_pdf(path, [("Equipment request", "Owner: Lab"), None, ("Deadline: 14 days",)],
              rotate_page=2)
    original = path.read_bytes()
    doc = read_document(path)
    assert doc.sha256 == sha256(original).hexdigest()
    assert path.read_bytes() == original
    assert doc.text == "Equipment request\nOwner: Lab\nDeadline: 14 days"
    assert [b.location for b in doc.blocks] == ["第 1 页 / 第 1 行", "第 1 页 / 第 2 行", "第 3 页 / 第 1 行"]
    assert [b.page for b in doc.blocks] == [1, 1, 3]
    assert all(doc.text[b.span.start:b.span.end] == b.text for b in doc.blocks)
    assert any("第 2 页" in warning for warning in doc.warnings)


def test_pdf_compares_against_txt_and_can_prepare_evidence(tmp_path):
    old, new = tmp_path / "初稿.pdf", tmp_path / "新版.txt"
    write_pdf(old, [("Equipment request",), ("Deadline: 14 days",)])
    new.write_text("Equipment request\nDeadline: 7 days", encoding="utf-8")
    left, right = read_document(old), read_document(new)
    result = compare(left, right)
    change, = result.changes
    assert change.left_location == "第 2 页 / 第 1 行"
    assert left.text[change.left_edits[0].start:change.left_edits[0].end] == "14"
    draft = prepare_analysis(left, right, result, 1, 1, "https://api.deepseek.com/chat/completions", "deepseek-flash")
    assert [e.text for e in draft.evidence] == ["Deadline: 14 days", "Deadline: 7 days"]


@pytest.mark.parametrize("kind,expected", [
    ("scan", "pdf_no_text"), ("locked", "pdf_encrypted"), ("malformed", "invalid_pdf"),
])
def test_pdf_errors_are_distinguished(tmp_path, kind, expected):
    path = tmp_path / f"{kind}.pdf"
    if kind == "malformed":
        path.write_bytes(b"%PDF-1.7\ninvalid")
    elif kind == "locked":
        write_pdf(path, [("Private text",)], password="password")
    else:
        write_pdf(path, [None])
    with pytest.raises(DocumentError) as error:
        read_document(path)
    assert error.value.code == expected


def test_pdf_page_limit_has_an_explicit_error(tmp_path, monkeypatch):
    from doclens import documents
    monkeypatch.setattr(documents, "MAX_PDF_PAGES", 1)
    path = tmp_path / "multi.pdf"
    write_pdf(path, [("First",), ("Second",)])
    with pytest.raises(DocumentError) as error:
        read_document(path)
    assert error.value.code == "pdf_limit"


def test_pdf_form_limit_cannot_silently_drop_text(tmp_path):
    path = tmp_path / "many-forms.pdf"
    write_pdf(path, [None], repeated_forms=1001)
    with pytest.raises(DocumentError) as error:
        read_document(path)
    assert error.value.code == "pdf_limit"
    assert "第 1 页" in str(error.value)


def test_workspace_searches_pdf_and_reports_image_only_file(tmp_path):
    folder = tmp_path / "reports"
    folder.mkdir()
    write_pdf(folder / "会议记录.pdf", [("March Report",), ("Approved budget",)])
    write_pdf(folder / "扫描件.pdf", [None])
    write_pdf(folder / "部分扫描.pdf", [("Readable page",), None, None])
    broken_image = b"BT /F1 14 Tf 72 730 Td (before) Tj ET 1 BI /W 1 /H 1 /CS /RGB /BPC 8 ID \x12\x34\x56 EI"
    write_pdf(folder / "损坏内容.pdf", [broken_image])
    index = WorkspaceIndex(folder, tmp_path / "index.sqlite3")
    result = index.scan()
    assert result.count == 2
    assert any("扫描件.pdf" in notice and "OCR" in notice for notice in result.issues)
    assert any("损坏内容.pdf" in notice and "结构" in notice for notice in result.issues)
    recheck = index.scan()
    assert recheck.reused == 2
    assert any("部分扫描.pdf" in notice and "第 2–3 页" in notice for notice in recheck.issues)
    hit, = index.search("budget").hits
    assert hit.location == "第 2 页 / 第 1 行"
    assert index.preview(hit)[hit.span.start:hit.span.end] == "budget"
