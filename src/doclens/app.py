import argparse
from bisect import bisect_right
from collections import Counter
import logging
from pathlib import Path
import sys

from PySide6.QtCore import Property, Q_ARG, QMetaObject, QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from .analysis_ui import AnalysisController
from .diff import compare
from .documents import DocumentError, read_document
from .models import Change, Span
from .workspace_ui import WorkspaceController

CHANGE_LABEL = {"insert": "新增", "delete": "删除", "replace": "修改", "move": "移动", "move_replace": "移动并修改"}
MOVE_COLOR = "#d5e6ff"


def utf16_offsets(text: str) -> list[int]:
    offsets = [0]
    for ch in text:
        offsets.append(offsets[-1] + (2 if ord(ch) > 0xFFFF else 1))
    return offsets


class EvidenceHighlighter(QSyntaxHighlighter):
    def __init__(self, document, spans: list[tuple[int, int, str]]):
        self._spans = spans
        self._ends = [end for _, end, _ in spans]
        self._formats = {}
        for color in {color for _, _, color in spans}:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(color))
            self._formats[color] = fmt
        super().__init__(document)
        layout_enabled = document.isLayoutEnabled()
        document.setLayoutEnabled(False)
        try:
            self.rehighlight()
        finally:
            document.setLayoutEnabled(layout_enabled)

    def highlightBlock(self, text: str) -> None:
        start = self.currentBlock().position()
        end = start + len(text.encode("utf-16-le")) // 2
        for index in range(bisect_right(self._ends, start), len(self._spans)):
            a, b, color = self._spans[index]
            if a >= end:
                break
            low, high = max(start, a), min(end, b)
            if low < high:
                self.setFormat(low - start, high - low, self._formats[color])


class CompareThread(QThread):
    def __init__(self, paths: tuple[Path, Path], encodings: tuple[str, str], parent: QObject):
        super().__init__(parent)
        self.paths = paths
        self.encodings = encodings
        self.outcome = None
        self.error = ""

    def check_cancelled(self) -> None:
        if self.isInterruptionRequested():
            raise InterruptedError

    def run(self) -> None:
        try:
            snapshots = []
            for path, encoding in zip(self.paths, self.encodings):
                try:
                    snapshots.append(read_document(path, encoding, self.check_cancelled))
                except DocumentError as exc:
                    self.error = f"「{path.name}」{exc}"
                    return
            comparison = compare(*snapshots, check_cancelled=self.check_cancelled)
            self.check_cancelled()
            self.outcome = (*snapshots, comparison)
        except InterruptedError:
            return
        except Exception:
            logging.error("Comparison failed unexpectedly")
            self.error = "比对未完成。请检查文件，重新选择后重试。"


class CompareController(QObject):
    changed = Signal()
    busyChanged = Signal()
    changeEntriesChanged = Signal()

    def __init__(self, cache_root=None, analysis_network=None):
        super().__init__()
        self.workspace = WorkspaceController(self, cache_root)
        self.analysis = AnalysisController(self, analysis_network)
        self.analysis.evidenceRequested.connect(self._jump_evidence)
        self._paths = {"left": None, "right": None}
        self._encodings = {"left": "utf-8", "right": "utf-8"}
        self._thread = None
        self._cancel_requested = False
        self._status = "分别选择原文档和新版文档。"
        self._warning = ""
        self._changes = ()
        self._index = -1
        self._root = None
        self._wrappers = {}
        self._highlighters = []
        self._offsets = {}

    def attach(self, root: QQuickWindow) -> None:
        self._root = root
        self._editors = {side: root.findChild(QObject, side + "Text") for side in self._paths}
        # In PySide6 the QQuickTextDocument wrappers must live with the editor.
        self._wrappers = {side: editor.property("textDocument") for side, editor in self._editors.items()}

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._thread is not None

    @Property(bool, notify=changed)
    def canCompare(self) -> bool:
        return not self.busy and all(self._paths.values())

    @Property(str, notify=changed)
    def leftName(self) -> str:
        return self._paths["left"].name if self._paths["left"] else ""

    @Property(str, notify=changed)
    def rightName(self) -> str:
        return self._paths["right"].name if self._paths["right"] else ""

    @Property(str, notify=changed)
    def leftEncoding(self) -> str:
        return self._encodings["left"]

    @Property(str, notify=changed)
    def rightEncoding(self) -> str:
        return self._encodings["right"]

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Property(str, notify=changed)
    def warning(self) -> str:
        return self._warning

    @Property(int, notify=changed)
    def changeCount(self) -> int:
        return len(self._changes)

    @Property(int, notify=changed)
    def changeIndex(self) -> int:
        return self._index

    @staticmethod
    def _change_location(change: Change) -> str:
        return f"{CHANGE_LABEL[change.kind]} · 原文 {change.left_location} / 新版 {change.right_location}"

    @Property("QStringList", notify=changeEntriesChanged)
    def changeEntries(self) -> list[str]:
        return [f"{index}. {self._change_location(change)}" for index, change in enumerate(self._changes, 1)]

    @Property(str, notify=changed)
    def currentLocation(self) -> str:
        return self._change_location(self._changes[self._index]) if self._index >= 0 else ""

    def _reset(self) -> None:
        self.analysis.invalidate()
        for highlighter in self._highlighters:
            highlighter.setDocument(None)
        self._highlighters.clear()
        self._changes = ()
        self._index = -1
        self._warning = ""
        self._offsets.clear()
        for side, editor in self._editors.items():
            editor.setProperty("text", "")
            self._jump(side, 0, 0)
        self.changeEntriesChanged.emit()

    @Slot(str, QUrl)
    def selectFile(self, side: str, url: QUrl) -> None:
        if self.busy or side not in self._paths or not url.isLocalFile():
            return
        path = Path(url.toLocalFile())
        if path != self._paths[side]:
            self._encodings[side] = "utf-8"
        self._paths[side] = path
        self._reset()
        self._status = "可以开始比对。" if self.canCompare else "请选择另一份文档。"
        self.changed.emit()

    @Slot(str, str)
    def setEncoding(self, side: str, encoding: str) -> None:
        if self.busy or side not in self._paths or encoding not in ("utf-8", "gb18030"):
            return
        if self._encodings[side] == encoding:
            return
        self._encodings[side] = encoding
        self._reset()
        self._status = "已更新 TXT 编码。"
        self.changed.emit()

    @Slot()
    def startComparison(self) -> None:
        if not self.canCompare:
            return
        self._reset()
        self._cancel_requested = False
        self._status = "正在读取文档并计算差异…"
        self._thread = CompareThread(tuple(self._paths.values()), tuple(self._encodings.values()), self)
        self._thread.finished.connect(self._complete)
        self._thread.start()
        self.busyChanged.emit()
        self.changed.emit()

    @Slot()
    def cancel(self) -> None:
        if self._thread is not None:
            self._cancel_requested = True
            self._thread.requestInterruption()
            self._status = "正在取消…"
            self.changed.emit()

    @Slot()
    def _complete(self) -> None:
        thread = self._thread
        try:
            if self._cancel_requested:
                self._status = "已取消比对。"
            elif thread.outcome is None:
                self._status = thread.error or "比对未完成，请重试。"
            else:
                self._show_comparison(*thread.outcome)
        finally:
            self._thread = None
            thread.deleteLater()
            self.busyChanged.emit()
            self.changed.emit()

    def _show_comparison(self, left, right, comparison) -> None:
        self._changes = comparison.changes
        warnings = [f"「{snapshot.path.name}」{warning}"
                    for snapshot in (left, right) for warning in snapshot.warnings]
        if comparison.used_coarse_matching:
            warnings.append("部分差异范围较大，按整段显示。")
        self._warning = "\n".join(warnings)
        for side, snapshot, color in (("left", left, "#fbded9"), ("right", right, "#d4eddc")):
            editor = self._editors[side]
            editor.setProperty("text", snapshot.text)
            offsets = self._offsets[side] = utf16_offsets(snapshot.text)
            spans = []
            for change in self._changes:
                edits = getattr(change, side + "_edits")
                if change.kind == "move_replace":
                    # Non-overlapping highlight ranges: blue marks relocation,
                    # while the changed characters retain red/green emphasis.
                    whole = getattr(change, side)
                    cursor = whole.start
                    for edit in sorted(edits, key=lambda part: part.start):
                        if cursor < edit.start:
                            spans.append((offsets[cursor], offsets[edit.start], MOVE_COLOR))
                        spans.append((offsets[edit.start], offsets[edit.end], color))
                        cursor = edit.end
                    if cursor < whole.end:
                        spans.append((offsets[cursor], offsets[whole.end], MOVE_COLOR))
                else:
                    spans.extend((offsets[span.start], offsets[span.end],
                                  MOVE_COLOR if change.kind == "move" else color)
                                 for span in edits)
            spans.sort(key=lambda item: (item[0], item[1]))
            if spans:
                document = self._wrappers[side].textDocument()
                self._highlighters.append(EvidenceHighlighter(document, spans))
        self.changeEntriesChanged.emit()
        if self._changes:
            self.analysis.set_comparison(left, right, comparison)
            counts = Counter(change.kind for change in self._changes)
            totals = " · ".join(f"{label} {counts[kind]}" for kind, label in CHANGE_LABEL.items())
            self._status = f"{len(self._changes)} 组差异 · {totals}"
            self.jumpToChange(0)
        else:
            self._status = "两份文档提取的正文无文字差异。"

    def _jump(self, side: str, start: int, end: int) -> None:
        QMetaObject.invokeMethod(self._root, "jump", Qt.DirectConnection,
                                 Q_ARG(str, side), Q_ARG(int, start), Q_ARG(int, end))

    @Slot(int)
    def navigate(self, direction: int) -> None:
        if not self._changes:
            return
        self.jumpToChange(max(0, min(self._index + direction, len(self._changes) - 1)))

    @Slot(int)
    def jumpToChange(self, index: int) -> None:
        if not 0 <= index < len(self._changes):
            return
        self._index = index
        change = self._changes[index]
        for side, boundary, edits in (("left", change.left, change.left_edits),
                                      ("right", change.right, change.right_edits)):
            offsets = self._offsets[side]
            target = edits[0] if edits else Span(boundary.start, boundary.start)
            self._jump(side, offsets[target.start], offsets[target.end])
        self.changed.emit()


    @Slot(int, str, int, int)
    def _jump_evidence(self, index: int, side: str, start: int, end: int) -> None:
        if not 0 <= index < len(self._changes) or side not in self._offsets:
            return
        offsets = self._offsets[side]
        if not 0 <= start <= end < len(offsets):
            return
        self.jumpToChange(index)
        self._jump(side, offsets[start], offsets[end])


def create_window(*, cache_root=None, analysis_network=None) -> tuple[QQmlApplicationEngine, QQuickWindow, CompareController]:
    controller = CompareController(cache_root, analysis_network)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller, "workspace": controller.workspace,
                                 "analysis": controller.analysis})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("ui") / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("DocLens could not load its QML window")
    window = engine.rootObjects()[0]
    controller.attach(window)
    return engine, window, controller


def main() -> int:
    parser = argparse.ArgumentParser(prog="doclens")
    parser.add_argument("documents", type=Path, nargs="*")
    args = parser.parse_args()
    if len(args.documents) not in (0, 2):
        parser.error("provide either no files or exactly two files")
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("DocLens")
    engine, window, controller = create_window()
    if args.documents:
        for side, path in zip(("left", "right"), args.documents):
            controller.selectFile(side, QUrl.fromLocalFile(str(path.absolute())))
        controller.startComparison()
    return app.exec()
