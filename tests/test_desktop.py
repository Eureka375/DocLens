from threading import Event

from docx import Document
from PySide6.QtCore import QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
import pytest

from doclens.app import create_window


@pytest.fixture(scope="module")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


def wait_for(predicate):
    for _ in range(200):
        if predicate():
            return
        QTest.qWait(20)
    pytest.fail("Qt did not reach the expected state")


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

    engine, window, controller = create_window()
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
    engine, window, controller = create_window()
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
    engine, window, controller = create_window()
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
    engine, window, controller = create_window()
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
