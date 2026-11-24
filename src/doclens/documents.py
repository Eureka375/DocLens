from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import logging
from pathlib import Path
import os
from threading import get_ident
from zipfile import BadZipFile, ZipFile
from zlib import error as CompressionError

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from pypdf import PdfReader, apply_configuration
from pypdf.errors import DependencyError, FileNotDecryptedError, LimitReachedError, PyPdfError, WrongPasswordError

from .models import Snapshot, Span, TextBlock
from .structure import annotate

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2048
MAX_TEXT_LENGTH = 100_000
MAX_PDF_PAGES = 300
MAX_PDF_STREAM_BYTES = 4 * 1024 * 1024
MAX_PDF_CONTENT_BYTES = 16 * 1024 * 1024
SUPPORTED_EXTENSIONS = frozenset((".txt", ".docx", ".pdf", ".md", ".markdown"))
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MATH_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
REVISION_TAGS = {
    "ins", "del", "moveFrom", "moveTo", "cellIns", "cellDel", "cellMerge",
    "moveFromRangeStart", "moveToRangeStart", "pPrChange", "rPrChange",
    "sectPrChange", "tblPrChange", "tblGridChange", "trPrChange", "tcPrChange",
    "numberingChange",
}
OMITTED_TAGS = {"drawing", "pict", "txbxContent", "footnoteReference", "endnoteReference",
                "commentReference", "altChunk", "sdt", "object", "fldSimple", "customXml",
                "smartTag", "subDoc"}
ALTERNATE_CONTENT = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"


class DocumentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def no_cancel() -> None:
    pass


def _canonical_newlines(text: str) -> str:
    # Match the text document's paragraph separators before calculating offsets.
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\u2029", "\n")


def _state(stat: os.stat_result) -> tuple[int, ...]:
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def read_document_bytes(path: Path) -> bytes:
    try:
        with path.open("rb") as source:
            before = os.fstat(source.fileno())
            data = source.read(MAX_FILE_BYTES + 1)
            after = os.fstat(source.fileno())
        current = path.stat()
    except OSError as exc:
        raise DocumentError("unreadable", "无法读取文件。请检查文件是否存在及是否有读取权限。") from exc
    if len(data) > MAX_FILE_BYTES:
        raise DocumentError("file_limit", "文件超过 10 MiB 的读取上限。")
    if len(data) != before.st_size or _state(before) != _state(after) or _state(after) != _state(current):
        raise DocumentError("file_changed", "文件在读取期间已变化。请保存文件后重试。")
    return data


def _paragraph_structure(paragraph: Paragraph) -> tuple[str, int | None]:
    # Direct formatting wins over inherited styles; use outlineLvl rather than
    # translated style names so localized and custom Word headings also work.
    properties = [paragraph._p.pPr]
    style = paragraph.style
    visited = set()
    while style is not None and style.style_id not in visited:
        visited.add(style.style_id)
        properties.append(style.element.pPr)
        style = style.base_style
    for props in properties:
        if props is not None and props.outlineLvl is not None:
            level = props.outlineLvl.val
            return ("heading", level + 1) if 0 <= level <= 8 else ("paragraph", None)
    if any(props is not None and props.numPr is not None for props in properties):
        return "list_item", None
    return "paragraph", None


def _paragraphs(container, prefix: str, check_cancelled: Callable[[], None], depth: int = 0,
                table_path: tuple[tuple[int, int, int], ...] = ()) -> Iterator[TextBlock]:
    if depth > 32:
        raise DocumentError("table_depth", "DOCX 表格嵌套超过 32 层。")
    paragraph_no = table_no = 0
    for item in container.iter_inner_content():
        check_cancelled()
        if isinstance(item, Paragraph):
            paragraph_no += 1
            location = f"{prefix}第 {paragraph_no} 段"
            kind, level = _paragraph_structure(item)
            yield TextBlock(item.text, Span(0, 0), location,
                            "table_cell" if table_path else kind, level, table_path=table_path)
            continue
        table_no += 1
        for row_no, row in enumerate(item.rows, 1):
            next_column = row.grid_cols_before + 1
            # Physical cells avoid recursively resolving long vertical merges.
            for cell_element in row._tr.tc_lst:
                check_cancelled()
                col_no = next_column
                next_column += cell_element.grid_span
                if cell_element.vMerge == "continue":
                    continue
                cell = _Cell(cell_element, item)
                location = f"{prefix}表 {table_no} / 第 {row_no} 行第 {col_no} 列 / "
                yield from _paragraphs(cell, location, check_cancelled, depth + 1,
                                       table_path + ((table_no, row_no, col_no),))


def _docx_blocks(data: bytes, check_cancelled: Callable[[], None]) -> tuple[list[TextBlock], tuple[str, ...]]:
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise DocumentError("archive_limit", "DOCX 解压大小或内部文件数超过读取上限。")
            names = {entry.filename for entry in entries}
        check_cancelled()
        document = Document(BytesIO(data))
        tags = {node.tag for node in document.element.body.iter() if isinstance(node.tag, str)}
        if any(WORD_NS + tag in tags for tag in REVISION_TAGS):
            raise DocumentError("tracked_changes", "DOCX 含未处理的修订。请在 Word 中处理修订并另存副本后重试。")
        warnings = ()
        omitted_parts = any(name.startswith(("word/header", "word/footer", "word/footnotes", "word/endnotes"))
                            for name in names)
        if (omitted_parts or ALTERNATE_CONTENT in tags or any(WORD_NS + tag in tags for tag in OMITTED_TAGS)
                or any(tag.startswith(MATH_NS) for tag in tags)):
            warnings = ("检测到未提取的结构，例如 Word 域、页眉、脚注或图形。比对结果可能未覆盖全部可见文字。",)
        rows = []
        size = 0
        for block in _paragraphs(document, "", check_cancelled):
            text = _canonical_newlines(block.text)
            size += len(text) + bool(rows)
            if size > MAX_TEXT_LENGTH:
                raise DocumentError("text_limit", "正文超过 100,000 字符的比对上限。")
            rows.append(replace(block, text=text))
        return rows, warnings
    except InterruptedError:
        raise
    except (BadZipFile, XMLSyntaxError, PackageNotFoundError, CompressionError,
            KeyError, ValueError, TypeError, RuntimeError, OSError, AttributeError) as exc:
        raise DocumentError("invalid_docx", "DOCX 已损坏、加密或结构不受支持。请尝试另存为新的 DOCX。") from exc


class _PdfExtractionWarnings(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.thread = get_ident()
        self.limit_reached = False
        self.form_skipped = False

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self.thread or record.name != "pypdf._page":
            return
        message = record.getMessage()
        # pypdf reports skipped forms through logging while returning the remaining text.
        if "form XObject invocations while extracting text" in message:
            self.limit_reached = True
        elif message.startswith(("Detected cyclic form XObject", "Impossible to decode XFormObject")):
            self.form_skipped = True


@contextmanager
def _pdf_extraction_warnings() -> Iterator[_PdfExtractionWarnings]:
    logger = logging.getLogger("pypdf")
    handler = _PdfExtractionWarnings()
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        handler.close()


def _pdf_blocks(data: bytes, check_cancelled: Callable[[], None]) -> tuple[list[TextBlock], tuple[str, ...]]:
    rows = []
    empty_pages = []
    size = content_bytes = 0
    try:
        with apply_configuration(
            disable_legacy_handling=True,
            maximum_declared_stream_length=MAX_PDF_STREAM_BYTES,
            array_based_stream_maximum_output_length=MAX_PDF_STREAM_BYTES,
            zlib_maximum_output_length=MAX_PDF_STREAM_BYTES,
            lzw_maximum_output_length=MAX_PDF_STREAM_BYTES,
            run_length_maximum_output_length=MAX_PDF_STREAM_BYTES,
            brotli_maximum_output_length=MAX_PDF_STREAM_BYTES,
            stream_decoding_work_maximum_length=MAX_PDF_CONTENT_BYTES,
            stream_parsing_work_maximum_count=100_000,
            page_tree_maximum_page_entries=1024,
            page_tree_maximum_entries=4096,
            xform_maximum_invocations_per_extraction=1000,
        ), _pdf_extraction_warnings() as diagnostics, PdfReader(
            BytesIO(data), root_object_recovery_limit=1000, xref_stream_maximum_entries=100_000
        ) as reader:
            if reader.is_encrypted:
                raise DocumentError("pdf_encrypted", "PDF 已加密。请先用原工具另存为未加密的副本。")
            check_cancelled()
            if len(reader.pages) > MAX_PDF_PAGES:
                raise DocumentError("pdf_limit", f"PDF 超过 {MAX_PDF_PAGES} 页的读取上限。")
            for page_no, page in enumerate(reader.pages, 1):
                check_cancelled()
                contents = page.get_contents()
                if contents is not None:
                    content_bytes += len(contents.get_data())
                    if content_bytes > MAX_PDF_CONTENT_BYTES:
                        raise DocumentError("pdf_limit", "PDF 页面内容超过解析上限。请拆分文件后重试。")
                body = _canonical_newlines(page.extract_text()).replace("\0", "").rstrip("\n")
                if diagnostics.limit_reached:
                    raise DocumentError("pdf_limit", f"PDF 第 {page_no} 页内容超过解析上限。请简化该页后重试。")
                if diagnostics.form_skipped:
                    raise DocumentError("invalid_pdf", f"PDF 第 {page_no} 页含无法提取的结构。请尝试另存为新的 PDF。")
                if not body.strip():
                    empty_pages.append(page_no)
                    continue
                size += len(body) + bool(rows)
                if size > MAX_TEXT_LENGTH:
                    raise DocumentError("text_limit", "正文超过 100,000 字符的比对上限。")
                rows.extend(TextBlock(line, Span(0, 0), f"第 {page_no} 页 / 第 {line_no} 行", page=page_no)
                            for line_no, line in enumerate(body.split("\n"), 1))
    except InterruptedError:
        raise
    except (FileNotDecryptedError, WrongPasswordError, DependencyError) as exc:
        raise DocumentError("pdf_encrypted", "PDF 已加密。请先用原工具另存为未加密的副本。") from exc
    except LimitReachedError as exc:
        raise DocumentError("pdf_limit", "PDF 页面内容超过解析上限。请拆分文件后重试。") from exc
    except (PyPdfError, CompressionError, KeyError, ValueError, TypeError, IndexError, AssertionError,
            RuntimeError, OSError, AttributeError, OverflowError) as exc:
        raise DocumentError("invalid_pdf", "PDF 已损坏或结构不受支持。请尝试另存为新的 PDF。") from exc
    if not rows:
        raise DocumentError("pdf_no_text", "PDF 未提取到可用文字。若为扫描件，请先完成 OCR 再导入。")
    if not empty_pages:
        return rows, ()
    ranges = []
    start = end = empty_pages[0]
    for page_no in empty_pages[1:]:
        if page_no == end + 1:
            end = page_no
            continue
        ranges.append(str(start) if start == end else f"{start}–{end}")
        start = end = page_no
    ranges.append(str(start) if start == end else f"{start}–{end}")
    pages = "、".join(ranges[:8]) + (" 等" if len(ranges) > 8 else "")
    return rows, (f"第 {pages} 页未提取到文字，共 {len(empty_pages)} 页。若为扫描页，请先完成 OCR。",)


def read_document(path: Path, encoding: str = "utf-8", check_cancelled: Callable[[], None] = no_cancel) -> Snapshot:
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise DocumentError("unsupported", "请选择 TXT、Markdown、DOCX 或 PDF 文件。")
    check_cancelled()
    return parse_snapshot(path, read_document_bytes(path), encoding, check_cancelled)


def parse_snapshot(path: Path, data: bytes, encoding: str, check_cancelled: Callable[[], None]) -> Snapshot:
    check_cancelled()
    warnings = ()
    suffix = path.suffix.lower()
    if suffix == ".docx":
        rows, warnings = _docx_blocks(data, check_cancelled)
    elif suffix == ".pdf":
        rows, warnings = _pdf_blocks(data, check_cancelled)
    elif suffix in (".txt", ".md", ".markdown"):
        if encoding not in ("utf-8", "gb18030"):
            raise ValueError(f"Unsupported TXT encoding: {encoding}")
        try:
            text = _canonical_newlines(data.decode("utf-8-sig" if encoding == "utf-8" else encoding))
        except UnicodeDecodeError as exc:
            raise DocumentError("encoding", "无法按所选编码读取 TXT。旧版中文 TXT 可改选 GB18030 后重试。") from exc
        if "\0" in text:
            raise DocumentError("invalid_txt", "TXT 包含无法显示的空字符。请另存为 UTF-8 文本后重试。")
        if len(text) > MAX_TEXT_LENGTH:
            raise DocumentError("text_limit", "正文超过 100,000 字符的比对上限。")
        rows = [TextBlock(line, Span(0, 0), f"第 {i} 行")
                for i, line in enumerate(text.split("\n"), 1)] if text else []
    else:
        raise DocumentError("unsupported", "请选择 TXT、Markdown、DOCX 或 PDF 文件。")
    blocks = []
    cursor = 0
    for block in rows:
        blocks.append(replace(block, span=Span(cursor, cursor + len(block.text))))
        cursor += len(block.text) + 1
    check_cancelled()
    return Snapshot(path, sha256(data).hexdigest(), "\n".join(row.text for row in rows),
                    annotate(blocks, infer_headings=suffix != ".docx"), warnings)
