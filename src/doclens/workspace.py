from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
from stat import FILE_ATTRIBUTE_HIDDEN, FILE_ATTRIBUTE_REPARSE_POINT

from .documents import SUPPORTED_EXTENSIONS, DocumentError, no_cancel, parse_snapshot, read_document_bytes
from .models import Span

# Change the database filename when snapshot extraction or the schema changes.
INDEX_VERSION = "v2"
MAX_FILES = 500
MAX_TEXT = 5_000_000
MAX_BLOCKS = 100_000
RESULT_LIMIT = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    cache_key TEXT NOT NULL,
    text TEXT NOT NULL,
    block_count INTEGER NOT NULL,
    partial INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS block (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    start INTEGER NOT NULL,
    location TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS block_document ON block(document_id);
CREATE TABLE IF NOT EXISTS document_warning (
    document_id INTEGER PRIMARY KEY REFERENCES document(id) ON DELETE CASCADE,
    message TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class IndexedDocument:
    relative_path: str
    cache_key: str
    source_bytes: int
    block_count: int
    partial: bool


@dataclass(frozen=True, slots=True)
class ScanSummary:
    documents: tuple[IndexedDocument, ...]
    reused: int
    issues: tuple[str, ...]
    fts_available: bool

    @property
    def count(self) -> int:
        return len(self.documents)


@dataclass(frozen=True, slots=True)
class SearchHit:
    relative_path: str
    cache_key: str
    location: str
    span: Span
    snippet: str


@dataclass(frozen=True, slots=True)
class SearchPage:
    hits: tuple[SearchHit, ...]
    matches: int
    documents: int


def _visible(path: Path) -> bool:
    status = path.lstat()
    attrs = getattr(status, "st_file_attributes", 0)
    return not (path.name.startswith((".", "~$")) or path.is_symlink()
                or attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_REPARSE_POINT))


def _paths(folder: Path, recursive: bool, issues: list[str],
           check_cancelled: Callable[[], None]) -> Iterator[Path]:
    def inaccessible(exc: OSError) -> None:
        issues.append(f"{Path(exc.filename or folder).name}：无法读取文件夹。")

    def visible(path: Path) -> bool:
        check_cancelled()
        try:
            return _visible(path)
        except OSError:
            issues.append(f"{path.relative_to(folder).as_posix()}：无法读取文件信息。")
            return False

    for base, directories, names in os.walk(folder, topdown=True, onerror=inaccessible):
        check_cancelled()
        parent = Path(base)
        directories[:] = sorted((d for d in directories if recursive and visible(parent / d)), key=str.casefold)
        for name in sorted(names, key=str.casefold):
            check_cancelled()
            path = parent / name
            if path.suffix.lower() in SUPPORTED_EXTENSIONS and visible(path) and path.is_file():
                yield path


class WorkspaceIndex:
    def __init__(self, folder: Path, database: Path):
        self.folder = folder
        self.database = database

    @classmethod
    def for_folder(cls, folder: Path, cache_root: Path):
        key = sha256(os.path.normcase(str(folder.absolute())).encode("utf-8")).hexdigest()
        return cls(folder, cache_root / f"{INDEX_VERSION}-{key}.sqlite3")

    def _connect(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=2)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA secure_delete = ON")
            connection.executescript(SCHEMA)
            return connection
        except BaseException:
            connection.close()
            raise

    def scan(self, recursive: bool = False, legacy_txt: bool = False,
             check_cancelled: Callable[[], None] = no_cancel,
             progress: Callable[[int], None] = lambda _: None) -> ScanSummary:
        if not self.folder.is_dir():
            raise ValueError("文件夹不存在或无法读取。")
        issues: list[str] = []
        retained: set[str] = set()
        catalog = []
        reused = text_length = block_count = 0
        with closing(self._connect()) as db, db:
            # The cache and the FTS snapshot move together at commit time.
            db.execute("BEGIN IMMEDIATE")
            old = {row[0]: row[1:] for row in db.execute(
                "SELECT path, cache_key, length(text), block_count, partial, message FROM document "
                "LEFT JOIN document_warning ON document_warning.document_id = document.id")}
            for number, path in enumerate(_paths(self.folder, recursive, issues, check_cancelled), 1):
                if number > MAX_FILES:
                    issues.append(f"只扫描前 {MAX_FILES} 份支持的文档。")
                    break
                progress(number)
                relative = path.relative_to(self.folder).as_posix()
                try:
                    data = read_document_bytes(path)
                    check_cancelled()
                    key = f"{sha256(data).hexdigest()}:{int(legacy_txt)}"
                    cached = old.get(relative)
                    if cached and cached[0] == key:
                        size, blocks, partial, warning = cached[1:]
                        snapshot = None
                    else:
                        try:
                            snapshot = parse_snapshot(path, data, "utf-8", check_cancelled)
                        except DocumentError as exc:
                            if not legacy_txt or exc.code != "encoding":
                                raise
                            snapshot = parse_snapshot(path, data, "gb18030", check_cancelled)
                        size, blocks = len(snapshot.text), len(snapshot.blocks)
                        warning = "；".join(snapshot.warnings)
                        partial = bool(warning)
                except DocumentError as exc:
                    issues.append(f"{relative}：{exc}")
                    continue
                if text_length + size > MAX_TEXT or block_count + blocks > MAX_BLOCKS:
                    issues.append(f"{relative}：达到工作空间正文或段落总量上限，未编入索引。")
                    continue
                text_length += size
                block_count += blocks
                retained.add(relative)
                catalog.append(IndexedDocument(relative, key, len(data), blocks, bool(partial)))
                if partial:
                    issues.append(f"{relative}：{warning or '含未提取结构，仅索引可读取的正文。'}")
                if snapshot is None:
                    reused += 1
                    continue
                db.execute("DELETE FROM document WHERE path = ?", (relative,))
                document_id = db.execute(
                    "INSERT INTO document(path, cache_key, text, block_count, partial) VALUES (?, ?, ?, ?, ?)",
                    (relative, key, snapshot.text, blocks, int(partial)),
                ).lastrowid
                if warning:
                    db.execute("INSERT INTO document_warning(document_id, message) VALUES (?, ?)",
                               (document_id, warning))
                db.executemany("INSERT INTO block(document_id, start, location, text) VALUES (?, ?, ?, ?)",
                               ((document_id, b.span.start, b.location, b.text) for b in snapshot.blocks))
            db.executemany("DELETE FROM document WHERE path = ?", ((p,) for p in old.keys() - retained))
            check_cancelled()
            fts_available = _create_fts(db)
            if fts_available:
                try:
                    db.set_progress_handler(lambda: _interrupted(check_cancelled), 2000)
                    db.execute("INSERT INTO block_fts(block_fts) VALUES ('rebuild')")
                except sqlite3.OperationalError:
                    check_cancelled()
                    raise
                finally:
                    db.set_progress_handler(None, 0)
            check_cancelled()
        return ScanSummary(tuple(catalog), reused, tuple(issues), fts_available)

    def search(self, query: str, check_cancelled: Callable[[], None] = no_cancel) -> SearchPage:
        if not query or not query.strip() or "\0" in query or len(query) > 200:
            raise ValueError("请输入 1 至 200 个字符的关键词。")
        with closing(self._connect()) as db:
            indexed = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='block_fts'").fetchone()
            if indexed and len(query) >= 3:
                try:
                    rows = db.execute(
                        """SELECT d.path, d.cache_key, b.start, b.location, b.text
                           FROM block_fts f JOIN block b ON f.rowid = b.id JOIN document d ON d.id = b.document_id
                           WHERE block_fts MATCH ? AND instr(b.text, ?) > 0""",
                        ('"' + query.replace('"', '""') + '"', query),
                    )
                except sqlite3.OperationalError:
                    rows = _literal_rows(db, query)
            else:
                rows = _literal_rows(db, query)
            counts: Counter[str] = Counter()
            hits = []
            for relative, key, start, location, text in rows:
                check_cancelled()
                offset = text.index(query)
                counts[relative] += text.count(query)
                lo, hi = max(0, offset - 35), min(len(text), offset + len(query) + 60)
                snippet = ("…" if lo else "") + " ".join(text[lo:hi].split()) + ("…" if hi < len(text) else "")
                hits.append(SearchHit(relative, key, location, Span(start + offset, start + offset + len(query)), snippet))
        hits.sort(key=lambda hit: (Path(hit.relative_path).stem != query, -counts[hit.relative_path],
                                   hit.relative_path.casefold(), hit.relative_path, hit.span.start))
        return SearchPage(tuple(hits[:RESULT_LIMIT]), len(hits), len(counts))

    def preview(self, hit: SearchHit | IndexedDocument) -> str:
        with closing(self._connect()) as db:
            row = db.execute("SELECT text FROM document WHERE path=? AND cache_key=?",
                             (hit.relative_path, hit.cache_key)).fetchone()
        if row is None:
            raise ValueError("索引已更新，请重新搜索。")
        return row[0]

    def clear(self) -> None:
        if not self.database.exists():
            return
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DROP TABLE IF EXISTS block_fts")
            db.execute("DELETE FROM document")
        # Reclaim space; a future scan will recreate the full-text index.
        with closing(self._connect()) as db:
            db.execute("VACUUM")


def _create_fts(db: sqlite3.Connection) -> bool:
    try:
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS block_fts USING fts5(
            text, content='block', content_rowid='id', tokenize='trigram')""")
        return True
    except sqlite3.OperationalError as exc:
        if "no such module: fts5" in str(exc) or "no such tokenizer" in str(exc):
            return False
        raise


def _literal_rows(db: sqlite3.Connection, query: str):
    return db.execute(
        """SELECT d.path, d.cache_key, b.start, b.location, b.text
           FROM block b JOIN document d ON d.id = b.document_id WHERE instr(b.text, ?) > 0""",
        (query,),
    )


def _interrupted(check_cancelled: Callable[[], None]) -> int:
    try:
        check_cancelled()
    except InterruptedError:
        return 1
    return 0
