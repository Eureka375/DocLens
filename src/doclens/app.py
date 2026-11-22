import argparse
from bisect import bisect_right
from collections import Counter
import logging
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import Property, Q_ARG, QMetaObject, QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from .analysis_ui import AnalysisController
from .analysis import CATEGORIES
from .diff import compare
from .documents import DocumentError, read_document
from .models import Change, Span
from .workspace_ui import WorkspaceController
from .preview import PreviewError, build_preview
from .review import COVERAGE_NOTICE, ReviewSession

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
    def __init__(self, paths: tuple[Path, Path], encodings: tuple[str, str], parent: QObject,
                 original_preview: bool = True):
        super().__init__(parent)
        self.paths = paths
        self.encodings = encodings
        self.outcome = None
        self.error = ""
        self.original_preview = original_preview
        self.preview_directory = None

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
            previews = {}
            if self.original_preview:
                self.preview_directory = TemporaryDirectory(prefix='DocLens-preview-')
                for side, snapshot in zip(('left', 'right'), snapshots):
                    try:
                        previews[side] = build_preview(snapshot, comparison.changes, side,
                            Path(self.preview_directory.name) / side, self.check_cancelled)
                    except InterruptedError:
                        raise
                    except PreviewError as exc:
                        previews[side] = {'pages': [], 'warning': str(exc)}
                    except (OSError, ValueError, RuntimeError):
                        previews[side] = {'pages': [], 'warning': '原貌预览未完成，可使用文字视图。请确认 Word 已安装并激活，或重新比对。'}
            self.outcome = (*snapshots, comparison, previews)
        except InterruptedError:
            return
        except Exception:
            logging.error("Comparison failed unexpectedly")
            self.error = "比对未完成。请检查文件，重新选择后重试。"


class CompareController(QObject):
    changed = Signal()
    busyChanged = Signal()
    changeEntriesChanged = Signal()
    reviewChanged = Signal()
    reviewAnalysisChanged = Signal()

    def __init__(self, cache_root=None, analysis_network=None, original_preview=True):
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
        self._original_preview = original_preview
        self._previews = {}
        self._preview_directory = None
        self._review = None
        self._review_filter = ("all", "all", "")
        self._category_filter = "all"
        self._word_mode = False
        self._snapshots = None
        self._analysis_signature = None
        self.analysis.reportChanged.connect(self._sync_review_analysis)
        self.analysis.changed.connect(self._sync_review_analysis)

    @Slot()
    def _sync_review_analysis(self):
        signature = (tuple(sorted(self.analysis.coverage_states.items())), self.analysis.findings_for_export())
        if signature == self._analysis_signature:
            return
        self._analysis_signature = signature
        self.reviewAnalysisChanged.emit()
        if self._category_filter != "all":
            self.reviewChanged.emit()

    @Property("QVariantMap", notify=reviewAnalysisChanged)
    def reviewAnalysis(self):
        result = {}
        if not self._review:
            return result
        for index, status in self.analysis.coverage_states.items():
            if 0 <= index < len(self._changes):
                result[str(index)] = {"aiStatus": status, "aiFindings": [], "categoryIds": []}
        for finding_index, finding in enumerate(self.analysis.findings_for_export()):
            groups = sorted({e.change_index for e in finding.evidence})
            for group in groups:
                if not 0 <= group < len(self._changes):
                    continue
                entry = result.setdefault(str(group), {"aiStatus": "未分析", "aiFindings": [], "categoryIds": []})
                if finding.category not in entry["categoryIds"]:
                    entry["categoryIds"].append(finding.category)
                entry["aiFindings"].append({
                    "index": finding_index, "category": CATEGORIES[finding.category],
                    "summary": finding.summary, "impact": finding.impact,
                    "groups": [i + 1 for i in groups],
                    "evidence": [{"index": i, "side": e.side, "id": e.id}
                                 for i, e in enumerate(finding.evidence) if e.change_index == group],
                })
        for entry in result.values():
            entry["category"] = "、".join(CATEGORIES[c] for c in entry["categoryIds"]) or "未分类"
        return result

    @Slot(int, int)
    def openAnalysisEvidence(self, finding_index, evidence_index):
        self.analysis.openEvidence(finding_index, evidence_index)

    @Property(str, constant=True)
    def coverageNotice(self):
        return COVERAGE_NOTICE

    @Property("QVariantList", notify=reviewChanged)
    def reviewRows(self):
        if not self._review:
            return []
        analysis = self.reviewAnalysis
        rows = []
        for row in self._review.rows(*self._review_filter):
            entry = analysis.get(str(row["index"]), {"aiStatus": "未分析", "aiFindings": [],
                                                     "categoryIds": [], "category": "未分类"})
            assigned = entry["categoryIds"]
            if self._category_filter == "unclassified" and assigned:
                continue
            if self._category_filter not in ("all", "unclassified") and self._category_filter not in assigned:
                continue
            row.update(entry)
            rows.append(row)
        return rows

    @Slot(str)
    def setCategoryFilter(self, category):
        if category in ("all", "unclassified", *CATEGORIES):
            self._category_filter = category
            self.reviewChanged.emit()

    @Property(str, notify=reviewChanged)
    def reviewSummary(self):
        if not self._review:
            return "比对后可核对并导出报告。"
        done = sum(a["reviewed"] for a in self._review.annotations)
        return f"已核对 {done} / {len(self._changes)} 组"

    @Slot(str, str, str)
    def setReviewFilter(self, kind, state, query):
        if kind in ("all", *CHANGE_LABEL) and state in ("all", "pending", "reviewed"):
            self._review_filter = kind, state, query
            self.reviewChanged.emit()

    @Slot(int, bool)
    def setReviewed(self, index, reviewed):
        if self._review and 0 <= index < len(self._changes):
            self._review.update(index, reviewed=reviewed)
            self.reviewChanged.emit()

    @Slot(int, str)
    def setReviewNote(self, index, note):
        if self._review and 0 <= index < len(self._changes):
            if self._review.annotations[index]["note"] == note:
                return
            try:
                self._review.update(index, note=note)
            except ValueError as exc:
                self._status = str(exc)
                self.changed.emit()
            # The editor already displays this text. Resetting its ListView on
            # focus loss would destroy the checkbox receiving the next click.

    @Slot(QUrl, result=bool)
    def exportReport(self, url):
        if self.busy or self.analysis.busy or self._review is None or not url.isLocalFile():
            return False
        try:
            self._review.export_html(Path(url.toLocalFile()), self.analysis.findings_for_export(),
                                     getattr(self.analysis, "coverage_states", {}))
            self._status = "审阅报告已导出，包含全部差异和已保存备注。"
        except (OSError, ValueError):
            self._status = "报告未能导出，请选择可写的HTML文件，不能覆盖输入文档。"
            self.changed.emit()
            return False
        self.changed.emit()
        return True

    @Property(bool, notify=changed)
    def wordMode(self):
        return self._word_mode

    @Slot(bool)
    def setWordMode(self, enabled):
        self._word_mode = enabled
        if self._snapshots:
            self._highlight_comparison()
            if self._index >= 0:
                self.jumpToChange(self._index)
        self.changed.emit()

    def _highlight_comparison(self):
        for highlighter in self._highlighters:
            highlighter.setDocument(None)
        self._highlighters.clear()
        for side, snapshot, color in (("left", self._snapshots[0], "#fbded9"),
                                       ("right", self._snapshots[1], "#d4eddc")):
            offsets = self._offsets[side]
            field = side + ("_word_edits" if self._word_mode else "_edits")
            spans = []
            for c in self._changes:
                edits = getattr(c, field)
                if c.kind == "move_replace":
                    whole = getattr(c, side)
                    cursor = whole.start
                    for edit in sorted(edits, key=lambda part: part.start):
                        if cursor < edit.start:
                            spans.append((offsets[cursor], offsets[edit.start], MOVE_COLOR))
                        spans.append((offsets[edit.start], offsets[edit.end], color))
                        cursor = edit.end
                    if cursor < whole.end:
                        spans.append((offsets[cursor], offsets[whole.end], MOVE_COLOR))
                else:
                    spans.extend((offsets[s.start], offsets[s.end],
                                  MOVE_COLOR if c.kind == "move" else color)
                                 for s in edits)
            spans.sort(key=lambda item: (item[0], item[1]))
            if spans:
                self._highlighters.append(EvidenceHighlighter(self._wrappers[side].textDocument(), spans))

    @Property('QVariantList', notify=changed)
    def leftPreview(self):
        return self._previews.get('left', {}).get('pages', [])

    @Property('QVariantList', notify=changed)
    def rightPreview(self):
        return self._previews.get('right', {}).get('pages', [])

    def clear_previews(self):
        self._previews = {}
        self.changed.emit()
        if self._preview_directory is not None:
            self._preview_directory.cleanup()
            self._preview_directory = None

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
        self.clear_previews()
        self.analysis.invalidate()
        for highlighter in self._highlighters:
            highlighter.setDocument(None)
        self._highlighters.clear()
        self._changes = ()
        self._index = -1
        self._warning = ""
        self._offsets.clear()
        self._review = None
        self._snapshots = None
        self.reviewChanged.emit()
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
        self._status = "正在计算差异并生成原貌预览…" if self._original_preview else "正在读取文档并计算差异…"
        self._thread = CompareThread(tuple(self._paths.values()), tuple(self._encodings.values()), self,
                                     self._original_preview)
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
                self._preview_directory = thread.preview_directory
                thread.preview_directory = None
                self._show_comparison(*thread.outcome)
        finally:
            if thread.preview_directory is not None:
                thread.preview_directory.cleanup()
            self._thread = None
            thread.deleteLater()
            self.busyChanged.emit()
            self.changed.emit()

    def _show_comparison(self, left, right, comparison, previews=None) -> None:
        self._changes = comparison.changes
        self._snapshots = left, right
        self._review = ReviewSession(left, right, comparison)
        self.reviewChanged.emit()
        self._previews = previews or {}
        warnings = [f"「{snapshot.path.name}」{warning}"
                    for snapshot in (left, right) for warning in snapshot.warnings]
        if comparison.used_coarse_matching:
            warnings.append("部分差异范围较大，按整段显示。")
        warnings.extend(f"{'原文' if side == 'left' else '新版'}：{preview['warning']}"
                        for side, preview in self._previews.items() if preview.get('warning'))
        self._warning = "\n".join(warnings)
        for side, snapshot, color in (("left", left, "#fbded9"), ("right", right, "#d4eddc")):
            editor = self._editors[side]
            editor.setProperty("text", snapshot.text)
            offsets = self._offsets[side] = utf16_offsets(snapshot.text)
        self._highlight_comparison()
        self.changeEntriesChanged.emit()
        self.changed.emit()
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
        if self._previews:
            QMetaObject.invokeMethod(self._root, "jumpPreview", Qt.DirectConnection,
                                     Q_ARG(str, side), Q_ARG(int, self._index))

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
            if self._word_mode:
                edits = getattr(change, side + "_word_edits")
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


def create_window(*, cache_root=None, analysis_network=None, original_preview=True) -> tuple[QQmlApplicationEngine, QQuickWindow, CompareController]:
    controller = CompareController(cache_root, analysis_network, original_preview)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller, "workspace": controller.workspace,
                                 "analysis": controller.analysis})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("ui") / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("DocLens could not load its QML window")
    window = engine.rootObjects()[0]
    controller.attach(window)
    app = QGuiApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(controller.clear_previews)
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
