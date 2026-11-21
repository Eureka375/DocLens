from collections.abc import Callable, Iterator
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import os
from zipfile import BadZipFile, ZipFile
from zlib import error as CompressionError

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError

from .models import Snapshot, Span, TextBlock

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2048
MAX_TEXT_LENGTH = 100_000
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


def _read_bytes(path: Path) -> bytes:
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


def _paragraphs(container, prefix: str, check_cancelled: Callable[[], None], depth: int = 0) -> Iterator[tuple[str, str]]:
    if depth > 32:
        raise DocumentError("table_depth", "DOCX 表格嵌套超过 32 层。")
    paragraph_no = table_no = 0
    for item in container.iter_inner_content():
        check_cancelled()
        if isinstance(item, Paragraph):
            paragraph_no += 1
            location = f"{prefix}第 {paragraph_no} 段"
            yield item.text, location
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
                yield from _paragraphs(cell, location, check_cancelled, depth + 1)


def _docx_blocks(data: bytes, check_cancelled: Callable[[], None]) -> tuple[list[tuple[str, str]], tuple[str, ...]]:
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
        for text, location in _paragraphs(document, "", check_cancelled):
            text = _canonical_newlines(text)
            size += len(text) + bool(rows)
            if size > MAX_TEXT_LENGTH:
                raise DocumentError("text_limit", "正文超过 100,000 字符的比对上限。")
            rows.append((text, location))
        return rows, warnings
    except InterruptedError:
        raise
    except (BadZipFile, XMLSyntaxError, PackageNotFoundError, CompressionError,
            KeyError, ValueError, TypeError, RuntimeError, OSError, AttributeError) as exc:
        raise DocumentError("invalid_docx", "DOCX 已损坏、加密或结构不受支持。请尝试另存为新的 DOCX。") from exc


def read_document(path: Path, encoding: str = "utf-8", check_cancelled: Callable[[], None] = no_cancel) -> Snapshot:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in (".txt", ".docx"):
        raise DocumentError("unsupported", "请选择 TXT 或 DOCX 文件。")
    check_cancelled()
    data = _read_bytes(path)
    check_cancelled()
    warnings = ()
    if suffix == ".docx":
        rows, warnings = _docx_blocks(data, check_cancelled)
    else:
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
        rows = [(line, f"第 {i} 行") for i, line in enumerate(text.split("\n"), 1)] if text else []
    blocks = []
    cursor = 0
    for text, location in rows:
        blocks.append(TextBlock(text, Span(cursor, cursor + len(text)), location))
        cursor += len(text) + 1
    check_cancelled()
    return Snapshot(path, sha256(data).hexdigest(), "\n".join(row[0] for row in rows), tuple(blocks), warnings)
