from collections.abc import Callable
from pathlib import Path
import sqlite3

from PySide6.QtCore import QObject, Property, QStandardPaths, QThread, QUrl, Signal, Slot

from .workspace import ScanSummary, SearchPage, WorkspaceIndex


class WorkspaceTask(QThread):
    progress = Signal(int)

    def __init__(self, action: Callable, parent: QObject):
        super().__init__(parent)
        self.action = action
        self.result = None
        self.error = ""

    def check_cancelled(self):
        if self.isInterruptionRequested():
            raise InterruptedError

    def run(self):
        try:
            self.result = self.action(self.check_cancelled, self.progress.emit)
        except InterruptedError:
            return
        except ValueError as exc:
            self.error = str(exc)
        except (OSError, sqlite3.Error):
            self.error = "无法访问文件夹或本地索引。请检查目录权限并重试。"
        except Exception:
            self.error = "无法完成文件夹任务，请重试。"


class WorkspaceController(QObject):
    changed = Signal()
    busyChanged = Signal()
    hitsChanged = Signal()
    documentsChanged = Signal()
    previewChanged = Signal()

    def __init__(self, parent: QObject, cache_root: Path | None = None):
        super().__init__(parent)
        default = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
        self._cache_root = cache_root if cache_root is not None else Path(default) / "workspaces"
        self._workspace: WorkspaceIndex | None = None
        self._summary: ScanSummary | None = None
        self._task = None
        self._job = ""
        self._cancelled = False
        self._status = "选择包含 TXT、DOCX 或 PDF 的文件夹。"
        self._hits = ()
        self._preview = ""
        self._source = ""
        self._selection = (0, 0)
        self._active_hit = -1
        self._scanned = 0

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._task is not None

    @Property(str, notify=changed)
    def folder(self) -> str:
        return str(self._workspace.folder) if self._workspace else ""

    @Property(bool, notify=changed)
    def ready(self) -> bool:
        return self._summary is not None and not self.busy

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Property("QStringList", notify=changed)
    def issues(self) -> list[str]:
        return list(self._summary.issues) if self._summary else []

    @Property("QVariantList", notify=hitsChanged)
    def hits(self) -> list[dict]:
        return [{"path": hit.relative_path, "location": hit.location, "snippet": hit.snippet}
                for hit in self._hits]

    @Property("QVariantList", notify=documentsChanged)
    def documents(self) -> list[dict]:
        if self._summary is None:
            return []
        return [{"path": doc.relative_path,
                 "detail": f"{doc.source_bytes / 1024:.1f} KiB · {doc.block_count} 个文本块"
                           + (" · 仅提取部分正文" if doc.partial else "")}
                for doc in self._summary.documents]

    @Property(str, notify=previewChanged)
    def previewText(self) -> str:
        return self._preview

    @Property(str, notify=previewChanged)
    def previewSource(self) -> str:
        return self._source

    @Property(int, notify=previewChanged)
    def previewStart(self) -> int:
        return self._selection[0]

    @Property(int, notify=previewChanged)
    def previewEnd(self) -> int:
        return self._selection[1]

    @Property(int, notify=previewChanged)
    def activeHit(self) -> int:
        return self._active_hit

    def _clear_preview(self) -> None:
        self._preview = self._source = ""
        self._selection = (0, 0)
        self._active_hit = -1
        self.previewChanged.emit()

    def _clear_results(self) -> None:
        self._hits = ()
        self.hitsChanged.emit()
        self._clear_preview()

    @Slot(QUrl, bool, bool)
    def chooseFolder(self, url: QUrl, recursive: bool, legacy: bool) -> None:
        if self.busy or not url.isLocalFile():
            return
        self._workspace = WorkspaceIndex.for_folder(Path(url.toLocalFile()), self._cache_root)
        self._summary = None
        self.documentsChanged.emit()
        self.rescan(recursive, legacy)

    @Slot(bool, bool)
    def rescan(self, recursive: bool, legacy: bool) -> None:
        if self.busy or self._workspace is None:
            return
        workspace = self._workspace
        self._clear_results()
        self._scanned = 0
        self._start("scan", "正在扫描文件夹…",
                    lambda check, progress: workspace.scan(recursive, legacy, check, progress))

    @Slot(str)
    def search(self, query: str) -> None:
        if not self.ready:
            return
        workspace = self._workspace
        self._clear_results()
        self._start("search", "正在搜索正文…", lambda check, _: workspace.search(query.strip(), check))

    @Slot(int)
    def openHit(self, index: int) -> None:
        if self.busy or not 0 <= index < len(self._hits):
            return
        workspace, hit = self._workspace, self._hits[index]
        self._clear_preview()
        self._start("preview", "正在打开匹配原文…", lambda _, __: (index, hit, workspace.preview(hit)))

    @Slot(int)
    def openDocument(self, index: int) -> None:
        if not self.ready or not 0 <= index < len(self._summary.documents):
            return
        workspace, document = self._workspace, self._summary.documents[index]
        self._clear_preview()
        self._start("document", "正在打开扫描快照…",
                    lambda _, __: (document.relative_path, workspace.preview(document)))

    @Slot()
    def clearCache(self) -> None:
        if self.busy or self._workspace is None:
            return
        workspace = self._workspace
        self._summary = None
        self.documentsChanged.emit()
        self._clear_results()
        self._start("clear", "正在清除当前文件夹的本地缓存…", lambda _, __: workspace.clear())

    def _start(self, job: str, status: str, action: Callable) -> None:
        self._job = job
        self._status = status
        self._cancelled = False
        self._task = WorkspaceTask(action, self)
        self._task.progress.connect(self._progress)
        self._task.finished.connect(self._complete)
        self._task.start()
        self.busyChanged.emit()
        self.changed.emit()

    @Slot(int)
    def _progress(self, count: int) -> None:
        if self._job == "scan" and not self._cancelled:
            self._scanned = count
            self._status = f"正在扫描第 {self._scanned} 份文档…"
            self.changed.emit()

    @Slot()
    def cancel(self) -> None:
        if self._task is not None and self._job != "clear":
            self._cancelled = True
            self._task.requestInterruption()
            self._status = "正在取消文件夹任务…"
            self.changed.emit()

    @Slot()
    def _complete(self) -> None:
        task, self._task = self._task, None
        try:
            if task.error:
                self._status = task.error
            elif self._cancelled and task.result is None:
                self._status = "文件夹任务已取消。" if not self._summary else "任务已取消。上次扫描结果仍可搜索。"
            elif self._job == "clear":
                self._status = "本地索引缓存已清除。重新扫描后可搜索。"
            elif isinstance(task.result, ScanSummary):
                self._summary = task.result
                self.documentsChanged.emit()
                self._status = f"扫描完成 · 已索引 {task.result.count} 份文档 · 复用 {task.result.reused} 份"
                if not task.result.fts_available:
                    self._status += " · 当前环境使用字面扫描"
            elif isinstance(task.result, SearchPage) and not self._cancelled:
                page = task.result
                self._hits = page.hits
                self.hitsChanged.emit()
                self._status = f"匹配 {page.documents} 份文档、{page.matches} 个段落"
                if page.matches > len(page.hits):
                    self._status += f" · 显示前 {len(page.hits)} 个"
            elif self._job == "preview" and not self._cancelled and task.result:
                index, hit, text = task.result
                self._active_hit = index
                self._source = f"{hit.relative_path} · {hit.location} · 扫描快照"
                self._preview = text
                self._selection = (len(text[:hit.span.start].encode("utf-16-le")) // 2,
                                   len(text[:hit.span.end].encode("utf-16-le")) // 2)
                self.previewChanged.emit()
                self._status = f"已显示第 {index + 1} 条匹配。"
            elif self._job == "document" and not self._cancelled and task.result:
                name, self._preview = task.result
                self._source = f"{name} · 扫描快照"
                self.previewChanged.emit()
                self._status = "已打开文档的扫描快照。"
            else:
                self._status = "文件夹任务已取消。"
        finally:
            self._job = ""
            task.deleteLater()
            self.busyChanged.emit()
            self.changed.emit()
