import json
from pathlib import Path
from threading import Event

from docx import Document
from PySide6.QtCore import QEventLoop, QObject, QPointF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
import pytest

from doclens.app import create_window


@pytest.fixture(scope="module")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture(autouse=True)
def isolated_ai_settings(tmp_path, monkeypatch):
    # Every test uses its own encrypted fixture; never access the user's settings.
    monkeypatch.setattr("doclens.settings.default_settings_path", lambda: tmp_path / "ai-settings.bin")


def wait_for(predicate):
    loop = QEventLoop()
    for _ in range(200):
        if predicate():
            return
        QTimer.singleShot(20, loop.quit)
        loop.exec()
    pytest.fail("Qt did not reach the expected state")


def test_original_pdf_preview_switch_and_navigation(app, tmp_path):
    from test_pdf import write_pdf
    left, right = tmp_path / 'left.pdf', tmp_path / 'right.pdf'
    write_pdf(left, [('Deadline 14 days',), ('Amount 100',)])
    write_pdf(right, [('Deadline 7 days',), ('Amount 200',)])
    engine, window, controller = create_window()
    try:
        controller.selectFile('left', QUrl.fromLocalFile(str(left)))
        controller.selectFile('right', QUrl.fromLocalFile(str(right)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert len(controller.leftPreview) == len(controller.rightPreview) == 2
        assert controller.changeCount == 2
        pages = control(window, 'leftPagePreview')
        assert pages.property('visible')
        controller.jumpToChange(1)
        wait_for(lambda: pages.property('contentY') > 0)
        click(window, 'leftTextView')
        assert not pages.property('visible')
        assert control(window, 'leftText').property('selectedText') == '1'
        click(window, 'leftOriginalView')
        assert pages.property('visible')
        preview_folder = controller._preview_directory.name
        controller._reset()
        assert not Path(preview_folder).exists()
    finally:
        window.close()
        engine.deleteLater()


@pytest.mark.parametrize('reverse', [False, True])
def test_original_preview_insert_delete_scrolls_both_sides(app, tmp_path, reverse):
    from test_pdf import write_pdf
    paths = [tmp_path / 'a.pdf', tmp_path / 'b.pdf']
    write_pdf(paths[0], [('Deadline 14 days',), ('Tail stable',)])
    write_pdf(paths[1], [('Deadline 7 days',), ('Tail stable', 'Inserted clause')])
    if reverse:
        paths.reverse()
    engine, window, controller = create_window()
    try:
        for side, path in zip(('left', 'right'), paths):
            controller.selectFile(side, QUrl.fromLocalFile(str(path)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert controller.changeCount == 2
        controller.jumpToChange(1)
        wait_for(lambda: all(control(window, side + 'PagePreview').property('contentY') > 0
                             for side in ('left', 'right')))
    finally:
        controller.clear_previews()
        window.close()
        engine.deleteLater()


def control(window, name):
    return window.findChild(QObject, name)


def click(window, name):
    item = control(window, name)
    assert item.property("enabled")
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())


def test_real_txt_docx_workflow(app, tmp_path):
    original = tmp_path / "原 文.txt"
    original.write_bytes("标题\r\n甲😀乙：7天\r\n保留\r\n删除条款\r\n尾部".encode())
    modified = tmp_path / "新 版.docx"
    doc = Document()
    for line in ["标题", "甲😀乙：3天", "保留", "尾部", "新增条款"]:
        doc.add_paragraph(line)
    doc.save(modified)

    engine, window, controller = create_window(original_preview=False)
    try:
        assert not controller.canCompare
        controller.selectFile("left", QUrl.fromLocalFile(str(original)))
        controller.selectFile("right", QUrl.fromLocalFile(str(modified)))
        assert controller.canCompare
        QTest.qWait(30)
        click(window, "startComparison")
        wait_for(lambda: not controller.busy)
        assert controller.changeCount == 3, controller.status
        left = control(window, "leftText")
        right = control(window, "rightText")
        assert left.property("text") == "标题\n甲😀乙：7天\n保留\n删除条款\n尾部"
        assert right.property("text").endswith("新增条款")
        assert left.property("selectedText") == "7"
        assert right.property("selectedText") == "3"
        wrapper = left.property("textDocument")
        block = wrapper.textDocument().findBlockByNumber(1)
        assert any(f.start == 5 and f.length == 1 for f in block.layout().formats())

        click(window, "nextChange")
        assert left.property("selectedText") == "删除条款"
        assert right.property("selectedText") == ""
        click(window, "nextChange")
        assert right.property("selectedText") == "新增条款"

        broken = tmp_path / "坏文件.docx"
        broken.write_bytes(b"broken")
        controller.selectFile("right", QUrl.fromLocalFile(str(broken)))
        assert controller.changeCount == 0
        assert right.property("text") == ""
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert "坏文件.docx" in controller.status
        assert "损坏" in controller.status
        controller.selectFile("right", QUrl.fromLocalFile(str(original)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert "无文字差异" in controller.status
        assert control(window,"nextChange").property("enabled") is False
        assert not window.grabWindow().isNull()
    finally:
        window.close()


def test_navigation_scrolls_to_a_change_far_below_the_viewport(app, tmp_path):
    old, new = (tmp_path / name for name in ("初稿.txt", "新版.txt"))
    lines = ["开始 7 天"] + [f"第 {i} 条相同文字" for i in range(350)] + ["结束 2 天"]
    old.write_text("\n".join(lines), encoding="utf-8")
    lines[0], lines[-1] = "开始 3 天", "结束 4 天"
    new.write_text("\n".join(lines), encoding="utf-8")
    engine, window, controller = create_window(original_preview=False)
    try:
        for side, path in (("left", old), ("right", new)):
            controller.selectFile(side, QUrl.fromLocalFile(str(path)))
        QTest.qWait(30)
        click(window, "startComparison")
        wait_for(lambda: not controller.busy)
        assert controller.changeCount == 2
        click(window, "nextChange")
        for side, digit in (("left", "2"), ("right", "4")):
            assert control(window, side + "Text").property("selectedText") == digit
            viewport = control(window, side + "Viewport")
            assert viewport.property("contentY") > 1000
        click(window, "previousChange")
        assert control(window, "leftViewport").property("contentY") < 100
    finally:
        window.close()


def test_jump_picker_selects_nonadjacent_changes_in_the_delivered_example(app):
    sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
    engine, window, controller = create_window(original_preview=False)
    try:
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        QTest.qWait(30)
        click(window, "startComparison")
        wait_for(lambda: not controller.busy)
        assert controller.changeCount == 5
        picker = control(window, "jumpToChange")
        assert picker.property("count") == 5
        assert picker.property("currentIndex") == 0

        # Re-select the active entry after moving away from it.
        left_view = control(window, "leftViewport")
        left_view.setProperty("contentY", 1200)
        assert left_view.property("contentY") > 1000
        click(window, "jumpToChange")
        QTest.keyClick(window, Qt.Key_Home)
        QTest.keyClick(window, Qt.Key_Return)
        assert left_view.property("contentY") < 100

        click(window, "jumpToChange")
        QTest.keyClick(window, Qt.Key_End)
        QTest.keyClick(window, Qt.Key_Return)
        wait_for(lambda: controller.changeIndex == 4)
        assert control(window, "leftText").property("selectedText") == "45"
        assert control(window, "rightText").property("selectedText") == "90"
        assert all(control(window, side + "Viewport").property("contentY") > 1000
                   for side in ("left", "right"))

        click(window, "jumpToChange")
        QTest.keyClick(window, Qt.Key_Home)
        QTest.keyClick(window, Qt.Key_Down)
        QTest.keyClick(window, Qt.Key_Return)
        wait_for(lambda: controller.changeIndex == 1)
        assert control(window, "leftText").property("selectedText") == "20"
        assert control(window, "rightText").property("selectedText") == "35"

        click(window, "previousChange")
        assert picker.property("currentIndex") == 0
        assert control(window, "leftText").property("selectedText") == "7"
        assert control(window, "rightText").property("selectedText") == "3"
        assert left_view.property("contentY") < 100

        click(window, "nextChange")
        assert picker.property("currentIndex") == 1
        controller.selectFile("right", QUrl.fromLocalFile(str(sample / "原版.txt")))
        assert picker.property("count") == 0
        assert not picker.property("enabled")
    finally:
        window.close()


def test_pdf_move_jumps_to_both_pages_and_previews_local_evidence(app):
    sample = Path(__file__).resolve().parents[1] / "examples" / "PDF比对"
    engine, window, controller = create_window(original_preview=False)
    try:
        for side, name in (("left", "原版.pdf"), ("right", "新版.pdf")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        QTest.qWait(30)
        click(window, "startComparison")
        wait_for(lambda: not controller.busy)
        assert controller.changeCount == 2, controller.status
        assert "移动 1" in controller.status
        assert controller.currentLocation == "移动 · 原文 第 1 页 / 第 3 行 / 新版 第 2 页 / 第 7 行"
        left, right = (control(window, side + "Text") for side in ("left", "right"))
        moved = "归还设备时须提交运行记录。"
        assert left.property("selectedText") == right.property("selectedText") == moved
        # The moved text appears after the numeric edit on the right.
        for editor, block_number in ((left, 2), (right, 12)):
            document = editor.property("textDocument").textDocument()
            block = document.findBlockByNumber(block_number)
            assert {fmt.format.background().color().name() for fmt in block.layout().formats()} == {"#d5e6ff"}

        click(window, "jumpToChange")
        QTest.keyClick(window, Qt.Key_End)
        QTest.keyClick(window, Qt.Key_Return)
        wait_for(lambda: controller.changeIndex == 1)
        assert left.property("selectedText") == "14"
        assert right.property("selectedText") == "7"
        click(window, "previousChange")
        assert left.property("selectedText") == right.property("selectedText") == moved
        ai = controller.analysis
        assert ai.prepare(1, 1, "https://models.example/v1/chat/completions", "fixture-model")
        assert moved in ai.preview and "第 2 页 / 第 7 行" in ai.preview
    finally:
        window.close()


def test_cancel_discards_pending_comparison(app, tmp_path, monkeypatch):
    import doclens.app as module
    selected = tmp_path / "原文.txt"
    selected.write_text("原文", encoding="utf-8")
    entered = Event()
    release = Event()
    real_read = module.read_document

    def delayed_read(path, encoding, check_cancelled):
        entered.set()
        release.wait(5)
        check_cancelled()
        return real_read(path, encoding, check_cancelled)

    monkeypatch.setattr(module, "read_document", delayed_read)
    engine, window, controller = create_window(original_preview=False)
    try:
        for side in ("left", "right"):
            controller.selectFile(side, QUrl.fromLocalFile(str(selected)))
        controller.startComparison()
        wait_for(entered.is_set)
        controller.cancel()
        assert "正在取消" in controller.status
        release.set()
        wait_for(lambda: not controller.busy)
        assert controller.status == "已取消比对。"
        assert controller.changeCount == 0
        assert controller.canCompare
    finally:
        release.set()
        wait_for(lambda: not controller.busy)
        window.close()


def test_replacing_txt_restores_default_encoding(app, tmp_path):
    old = tmp_path / "GB18030.txt"
    new = tmp_path / "UTF8.txt"
    old.write_bytes("文档".encode("gb18030"))
    new.write_bytes("文档".encode("utf-8"))
    engine, window, controller = create_window(original_preview=False)
    try:
        controller.selectFile("left", QUrl.fromLocalFile(str(old)))
        controller.setEncoding("left", "gb18030")
        controller.selectFile("left", QUrl.fromLocalFile(str(new)))
        controller.selectFile("right", QUrl.fromLocalFile(str(new)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert control(window, "leftText").property("text") == "文档"
        assert control(window, "leftEncoding").property("currentIndex") == 0
        assert controller.changeCount == 0
    finally:
        window.close()


def click_list_item(window, view, index, child_name=None):
    target = "row" if child_name is None else (
        "function find(item) { if (item.objectName === " + json.dumps(child_name) +
        ") return item; for (const child of item.children) { const match = find(child); if (match) return match; } } "
        "const match = find(row);"
    )
    script = ("(function() { const row = itemAtIndex(" + str(index) + "); " +
              ("const match = row;" if child_name is None else target) +
              " return match.mapToItem(null, match.width / 2, match.height / 2); })()")
    expression = QQmlExpression(QQmlEngine.contextForObject(view), view, script)
    point, undefined = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    assert not undefined
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())


def test_folder_search_opens_the_actual_match_in_a_long_file(app, tmp_path):
    folder = tmp_path / "材料"
    folder.mkdir()
    path = folder / "项目.txt"
    path.write_text(("普通内容\n" * 120) + "😀申请责任在负责人。\n归档", encoding="utf-8")
    (folder / "坏文件.docx").write_bytes(b"broken")
    engine, window, controller = create_window(original_preview=False, cache_root=tmp_path / "cache")
    workspace = controller.workspace
    try:
        QTest.qWait(30)
        click(window, "openWorkspace")
        wait_for(lambda: control(window, "workspaceDialog").property("opened"))
        workspace.chooseFolder(QUrl.fromLocalFile(str(folder)), False, False)
        wait_for(lambda: not workspace.busy)
        assert workspace.ready and len(workspace.issues) == 1
        assert [entry["path"] for entry in workspace.documents] == ["项目.txt"]
        view = control(window, "workspaceHits")
        wait_for(lambda: view.property("count") == 1)
        QTest.qWait(30)
        click_list_item(window, view, 0)
        wait_for(lambda: not workspace.busy)
        assert workspace.previewText.startswith("普通内容")
        control(window, "workspaceQuery").setProperty("text", "责任")
        click(window, "workspaceSearch")
        wait_for(lambda: not workspace.busy)
        wait_for(lambda: view.property("count") == 1)
        QTest.qWait(30)
        click_list_item(window, view, 0)
        wait_for(lambda: workspace.activeHit == 0)
        preview = control(window, "workspacePreview")
        wait_for(lambda: preview.property("selectedText") == "责任")
        assert control(window, "workspacePreviewView").property("contentY") > 1000
        workspace.clearCache()
        wait_for(lambda: not workspace.busy)
        assert not workspace.ready and not workspace.hits and not workspace.previewText
        assert path.read_text(encoding="utf-8").endswith("😀申请责任在负责人。\n归档")
    finally:
        wait_for(lambda: not workspace.busy)
        window.close()


class FixtureReply(QObject):
    readyRead = Signal()
    finished = Signal()

    def __init__(self, code, data, parent):
        super().__init__(parent)
        self.code = code
        self.data = data
        self.cancelled = False
        QTimer.singleShot(30, self.deliver)

    def deliver(self):
        if not self.cancelled:
            self.readyRead.emit()
            if not self.cancelled:
                self.finished.emit()

    def read(self, size):
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk

    def attribute(self, attribute):
        assert attribute == QNetworkRequest.Attribute.HttpStatusCodeAttribute
        return self.code

    def error(self):
        return QNetworkReply.NetworkError.NoError

    def abort(self):
        self.cancelled = True
        self.finished.emit()


class FixtureNetwork(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.calls = []
        self.code = 200

    def post(self, request, body):
        self.calls.append((request, body))
        evidence = json.loads(json.loads(body)["messages"][1]["content"])
        findings = [{"category": "time", "summary": "撤回期限缩短", "impact": "申请人应提前提交撤回。",
                     "evidence_ids": [item["id"] for item in evidence]}]
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"findings": findings})}}]}
        return FixtureReply(self.code, json.dumps(response).encode(), self)


def test_ai_preview_approval_cache_and_clickable_local_evidence(app):
    sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
    service = FixtureNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    endpoint = "https://models.example/v1/chat/completions"
    try:
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        ai.approveAndSend("fixture-key")
        assert not service.calls
        click(window, "openAnalysis")
        wait_for(lambda: control(window, "analysisDialog").property("opened"))
        key_input = control(window, "aiKey")
        key_input.setProperty("text", "another-service-key")
        control(window, "aiEndpoint").setProperty("text", endpoint)
        assert key_input.property("text") == ""
        for field, value in (("aiEndpoint", endpoint), ("aiModel", "fixture-model"), ("aiKey", "fixture-key")):
            control(window, field).setProperty("text", value)
        click(window, "aiPrepare")
        confirmation = control(window, "aiConfirmation")
        wait_for(lambda: confirmation.property("opened"))
        assert "7 天内完成登记" in control(window, "aiPreview").property("text")
        assert "记录 001" not in ai.preview and not service.calls
        click(window, "aiDecline")
        wait_for(lambda: not confirmation.property("visible"))
        assert not service.calls
        click(window, "aiPrepare")
        wait_for(lambda: confirmation.property("opened"))
        click(window, "aiSend")
        wait_for(lambda: not ai.busy and bool(ai.report))
        assert len(service.calls) == 1
        request, body = service.calls[0]
        assert request.url().toString() == endpoint
        assert request.rawHeader("Authorization") == b"Bearer fixture-key"
        assert request.attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute) == QNetworkRequest.RedirectPolicy.ManualRedirectPolicy
        assert b"fixture-key" not in body
        assert ai.prepare(1, 1, endpoint, "fixture-model")
        ai.approveAndSend("")
        assert len(service.calls) == 1 and "缓存" in ai.status
        view = control(window, "aiFindings")
        wait_for(lambda: view.property("count") == 1)
        QTest.qWait(40)
        click_list_item(window, view, 0, "aiEvidence0_1")
        wait_for(lambda: not control(window, "analysisDialog").property("visible"))
        assert control(window, "rightText").property("selectedText") == "系统应在 3 天内完成登记。"
        assert controller.changeIndex == 0
        assert ai.prepare(1, 1, endpoint, "fixture-model")
        controller.selectFile("right", QUrl.fromLocalFile(str(sample / "原版.txt")))
        ai.approveAndSend("fixture-key")
        assert not ai.report and len(service.calls) == 1
    finally:
        ai.cancel()
        window.close()


@pytest.mark.parametrize("code, expected_status", [(401, "身份验证"), (402, "余额"), (429, "限流"),
                                                   (302, "重定向"), (500, "HTTP 500")])
def test_model_service_error_keeps_local_comparison_available(app, code, expected_status):
    sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
    service = FixtureNetwork()
    service.code = code
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert ai.prepare(1, 1, "https://models.example/v1/chat/completions", "fixture-model")
        ai.approveAndSend("fixture-key")
        wait_for(lambda: not ai.busy)
        assert expected_status in ai.status and not ai.report
        assert controller.changeCount == 5
        controller.jumpToChange(4)
        assert control(window, "rightText").property("selectedText") == "90"
    finally:
        ai.cancel()
        window.close()


def test_ai_provider_selection_reaches_request_and_invalid_citations_fall_back(app):
    sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
    class OneSidedNetwork(FixtureNetwork):
        def post(self, request, body):
            self.calls.append((request, body))
            content = {"findings": [{"category": "method", "summary": "变更说明", "impact": "",
                                     "evidence_ids": ["D1-OLD"]}]}
            response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}
            return FixtureReply(200, json.dumps(response).encode(), self)
    service = OneSidedNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        click(window, "openAnalysis")
        wait_for(lambda: control(window, "analysisDialog").property("opened"))
        control(window, "aiEndpoint").setProperty("text", "https://models.example/chat/completions")
        control(window, "aiModel").setProperty("text", "fixture-model")
        control(window, "aiProvider").setProperty("currentIndex", 2)
        control(window, "aiKey").setProperty("text", "fixture-key")
        click(window, "aiPrepare")
        wait_for(lambda: control(window, "aiConfirmation").property("opened"))
        assert "json" in ai.scope
        click(window, "aiSend")
        wait_for(lambda: not ai.busy)
        assert json.loads(service.calls[0][1])["response_format"] == {"type": "json_object"}
        assert not ai.report and "本地差异" in ai.status
        assert controller.changeCount == 5
        controller.jumpToChange(4)
        assert control(window, "rightText").property("selectedText") == "90"
    finally:
        ai.cancel()
        window.close()


def test_saved_ai_configuration_restores_and_reuses_key_after_restart(app):
    from doclens.settings import AISettingsStore
    endpoint = "https://models.example/chat/completions"
    engine, window, controller = create_window(original_preview=False)
    try:
        assert controller.analysis.saveSettings(endpoint, "saved-model", "fictional-saved-key", "json")
        assert controller.analysis.savedKeyAvailable
    finally:
        window.close()
    service = FixtureNetwork()
    engine2, window2, controller2 = create_window(original_preview=False, analysis_network=service)
    ai = controller2.analysis
    try:
        assert control(window2, "aiEndpoint").property("text") == endpoint
        assert control(window2, "aiModel").property("text") == "saved-model"
        assert control(window2, "aiProvider").property("currentIndex") == 2
        assert control(window2, "aiKey").property("text") == ""
        assert "已保存" in control(window2, "aiKey").property("placeholderText")
        sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller2.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller2.startComparison()
        wait_for(lambda: not controller2.busy)
        assert ai.prepare(1, 1, endpoint, "saved-model", "json")
        ai.approveAndSend("")
        wait_for(lambda: not ai.busy)
        assert service.calls[0][0].rawHeader("Authorization") == b"Bearer fictional-saved-key"
        assert b"fictional-saved-key" not in service.calls[0][1]
        assert ai.report
        # A different endpoint must never receive the remembered key.
        assert ai.prepare(1, 1, "https://other.example/chat/completions", "saved-model")
        ai.approveAndSend("")
        assert len(service.calls) == 1 and "API Key" in ai.status
        assert ai.clearSavedSettings()
        assert not ai.savedKeyAvailable and not ai.report
        assert AISettingsStore().load() is None
    finally:
        ai.cancel()
        window2.close()


def test_key_is_remembered_on_send_and_can_be_replaced(app):
    from doclens.settings import AISettingsStore
    service = FixtureNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    endpoint = "https://models.example/chat/completions"
    try:
        sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert ai.prepare(1, 1, endpoint, "saved-model")
        ai.approveAndSend("fictional-first-key")
        wait_for(lambda: not ai.busy)
        assert AISettingsStore().load().api_key == "fictional-first-key"
        assert ai.saveSettings(endpoint, "saved-model", "fictional-replacement", "auto")
        assert ai.prepare(1, 1, endpoint, "saved-model")
        ai.approveAndSend("")
        wait_for(lambda: not ai.busy)
        assert len(service.calls) == 2  # Replacing a key invalidates the old cache.
        assert service.calls[-1][0].rawHeader("Authorization") == b"Bearer fictional-replacement"
        assert ai.clearSavedSettings()
        assert ai.prepare(1, 1, endpoint, "saved-model")
        ai.approveAndSend("")
        assert len(service.calls) == 2
    finally:
        ai.cancel()
        window.close()


def test_settings_buttons_save_and_clear_without_sending(app):
    service = FixtureNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        click(window, "openAnalysis")
        wait_for(lambda: control(window, "analysisDialog").property("opened"))
        for field, value in (("aiEndpoint", "https://models.example/chat/completions"),
                             ("aiModel", "saved-model"), ("aiKey", "fictional-key")):
            control(window, field).setProperty("text", value)
        click(window, "aiSaveSettings")
        assert ai.savedKeyAvailable and not service.calls
        assert control(window, "aiKey").property("text") == ""
        click(window, "aiClearSettings")
        assert not ai.savedKeyAvailable
        assert control(window, "aiEndpoint").property("text") == ""
        assert control(window, "aiModel").property("text") == ""
    finally:
        window.close()


def test_failed_remember_keeps_new_key_input_and_sends_only_explicit_key(app, monkeypatch):
    from doclens.settings import SettingsError
    service = FixtureNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        endpoint = "https://models.example/chat/completions"
        assert ai.saveSettings(endpoint, "model", "fictional-old-key", "auto")
        def fail(config):
            raise SettingsError("测试：未能安全保存")
        monkeypatch.setattr(ai._settings_store, "save", fail)
        sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        click(window, "openAnalysis")
        wait_for(lambda: control(window, "analysisDialog").property("opened"))
        for field, value in (("aiEndpoint", endpoint), ("aiModel", "model"), ("aiKey", "fictional-new-key")):
            control(window, field).setProperty("text", value)
        click(window, "aiPrepare")
        wait_for(lambda: control(window, "aiConfirmation").property("opened"))
        click(window, "aiSend")
        wait_for(lambda: not ai.busy)
        assert service.calls[0][0].rawHeader("Authorization") == b"Bearer fictional-new-key"
        assert "未能安全保存" in ai.settingsStatus
        assert control(window, "aiKey").property("text") == "fictional-new-key"
    finally:
        ai.cancel()
        window.close()


def test_corrupt_settings_do_not_prevent_window_start(app):
    from doclens.settings import AISettingsStore
    AISettingsStore().path.write_bytes(b"invalid protected settings")
    engine, window, controller = create_window(original_preview=False)
    try:
        assert not controller.analysis.savedKeyAvailable
        assert "无法读取" in controller.analysis.settingsStatus
        assert controller.analysis.clearSavedSettings()
    finally:
        window.close()


@pytest.mark.parametrize("finish", ["timeout", "cancel"])
def test_ai_allows_two_minutes_and_releases_pending_request(app, finish):
    class PendingReply(FixtureReply):
        def deliver(self):
            pass  # No server result: exercise the real controller timer/cancel.
    class PendingNetwork(FixtureNetwork):
        def post(self, request, body):
            self.calls.append((request, body))
            self.pending = PendingReply(200, b"", self)
            return self.pending
    service = PendingNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert ai.prepare(1, 1, "https://api.deepseek.com/chat/completions", "deepseek-flash", "deepseek")
        ai.approveAndSend("fictional-key")
        assert ai.busy and ai._timer.isActive()
        assert ai._timer.interval() == 120_000
        assert "120 秒" in ai.status
        QTest.qWait(60)
        assert ai.busy and not service.pending.cancelled
        if finish == "timeout":
            ai._timer.start(1)  # Test expiry without waiting two actual minutes.
        else:
            ai.cancel()
        wait_for(lambda: not ai.busy)
        assert service.pending.cancelled and not ai._timer.isActive()
        assert ("超过 120 秒" if finish == "timeout" else "已取消") in ai.status
        assert not ai.report and "本地差异" in ai.status
        assert controller.changeCount == 5
        controller.jumpToChange(4)
        assert control(window, "rightText").property("selectedText") == "90"
        assert len(service.calls) == 1  # Timeout/cancel never silently resends.
    finally:
        ai.cancel()
        window.close()


def test_review_filters_annotation_export_and_word_navigation(app, tmp_path):
    sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
    engine, window, controller = create_window(original_preview=False)
    try:
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        assert len(controller.reviewRows) == 5
        controller.setReviewed(4, True)
        controller.setReviewNote(4, "最后期限已核对 <script>bad</script>")
        controller.setReviewFilter("all", "reviewed", "最后期限")
        assert [r["index"] for r in controller.reviewRows] == [4]
        controller.jumpToChange(controller.reviewRows[0]["index"])
        assert control(window, "rightText").property("selectedText") == "90"
        controller.setWordMode(True)
        assert controller.wordMode
        assert control(window, "rightText").property("selectedText") == "90"
        report = tmp_path / "comparison.html"
        assert controller.exportReport(QUrl.fromLocalFile(str(report)))
        html = report.read_text(encoding="utf-8")
        assert "第1组" in html and "第5组" in html  # Export is not limited by filters.
        assert "最后期限已核对 &lt;script&gt;bad&lt;/script&gt;" in html
        assert "格式、图片、公式" in controller.coverageNotice
        controller.selectFile("right", QUrl.fromLocalFile(str(sample / "原版.txt")))
        assert not controller.reviewRows
    finally:
        window.close()


def test_ai_batches_preserve_success_and_retry_only_missing_with_new_approval(app, tmp_path):
    class PartialNetwork(FixtureNetwork):
        fail_second = True
        def post(self, request, body):
            reply = super().post(request, body)
            if len(self.calls) == 2 and self.fail_second:
                reply.code = 500
            return reply
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, count in zip(paths, (30, 60)):
        path.write_text("\n".join(f"# Section {i}\nSamples {count}." for i in range(9)), encoding="utf-8")
    service = PartialNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        for side, path in zip(("left", "right"), paths):
            controller.selectFile(side, QUrl.fromLocalFile(str(path)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        endpoint = "https://models.example/chat/completions"
        assert ai.prepare(1, 9, endpoint, "model")
        assert "3 批" in ai.scope and not service.calls
        ai.approveAndSend("fictional-key")
        wait_for(lambda: not ai.busy)
        assert len(service.calls) == 2  # Failure prevents the third request.
        assert ai.report and all(ai.coverage_states[i] == "已解释" for i in range(4))
        assert all(ai.coverage_states[i] == "失败" for i in range(4, 8))
        assert ai.coverage_states[8] == "未发送"
        service.fail_second = False
        assert ai.prepareMissing(1, 9, endpoint, "model", "auto")
        assert len(service.calls) == 2
        assert "D1-OLD" not in ai.preview and "D5-OLD" in ai.preview
        ai.approveAndSend("")
        wait_for(lambda: not ai.busy)
        assert len(service.calls) == 4
        assert all(value == "已解释" for value in ai.coverage_states.values())
        assert len(ai.report) == 3
        controller.setCategoryFilter("time")
        assert len(controller.reviewRows) == 9
        controller.setCategoryFilter("data")
        assert not controller.reviewRows
        controller.setCategoryFilter("all")
        previous = ai.report
        service.code = 500
        assert ai.prepare(1, 9, endpoint, "replacement-model")
        ai.approveAndSend("")
        wait_for(lambda: not ai.busy)
        assert ai.report == previous  # A failed rerun must preserve all prior explanations.
    finally:
        ai.cancel()
        window.close()


def test_ai_valid_partial_response_marks_uncovered_and_cancel_discards_queue(app, tmp_path):
    class OmitNetwork(FixtureNetwork):
        def post(self, request, body):
            self.calls.append((request, body))
            ids = [e["id"] for e in json.loads(json.loads(body)["messages"][1]["content"])][:2]
            content = {"findings": [{"category": "data", "summary": "样本变化", "impact": "需核对",
                                     "evidence_ids": ids}]}
            return FixtureReply(200, json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode(), self)
    paths = [tmp_path / "old.txt", tmp_path / "new.txt"]
    for path, count in zip(paths, (30, 60)):
        path.write_text("\n".join(f"# S{i}\nSamples {count}." for i in range(5)), encoding="utf-8")
    service = OmitNetwork()
    engine, window, controller = create_window(original_preview=False, analysis_network=service)
    ai = controller.analysis
    try:
        for side, path in zip(("left", "right"), paths):
            controller.selectFile(side, QUrl.fromLocalFile(str(path)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        endpoint = "https://models.example/chat/completions"
        assert ai.prepare(1, 4, endpoint, "model")
        ai.approveAndSend("fictional-key")
        wait_for(lambda: not ai.busy)
        assert ai.coverage_states[0] == "已解释" and ai.coverage_states[1] == "未覆盖"
        assert "未覆盖" in ai.status
        assert ai.prepareMissing(1, 5, endpoint, "model", "auto")
        ai.approveAndSend("")
        ai.cancel()
        wait_for(lambda: not ai.busy)
        QTest.qWait(60)
        assert len(service.calls) == 2
        assert ai.coverage_states[0] == "已解释" and ai.report
        assert any(state == "已取消" for state in ai.coverage_states.values())
    finally:
        ai.cancel()
        window.close()


def test_review_panel_edits_and_filters_through_real_controls(app):
    sample = Path(__file__).resolve().parents[1] / "examples" / "跳转测试"
    engine, window, controller = create_window(original_preview=False)
    try:
        for side, name in (("left", "原版.txt"), ("right", "新版.txt")):
            controller.selectFile(side, QUrl.fromLocalFile(str(sample / name)))
        controller.startComparison()
        wait_for(lambda: not controller.busy)
        view = control(window, "reviewList")
        wait_for(lambda: view.property("count") == 5)
        QTest.qWait(40)
        click_list_item(window, view, 0, "reviewNote0")
        for character in "reviewed sample note":
            QTest.keyClick(window, Qt.Key(ord(character.upper())))
        # Clicking directly must save the note without destroying the checkbox click.
        click_list_item(window, view, 0, "reviewChecked0")
        wait_for(lambda: controller.reviewRows[0]["reviewed"])
        assert controller.reviewRows[0]["note"] == "reviewed sample note"
        control(window, "reviewQuery").setProperty("text", "reviewed sample note")
        wait_for(lambda: view.property("count") == 1)
        click_list_item(window, view, 0, "reviewJump0")
        assert controller.changeIndex == 0
    finally:
        window.close()
