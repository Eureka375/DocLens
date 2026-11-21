import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: pane
    required property string side
    required property string title
    required property string documentName
    required property string textEncoding
    required property bool busy
    signal pickFile()
    signal encodingChangedByUser(string encoding)
    color: "#ffffff"
    border.color: "#d5dedb"
    radius: 7

    function jump(start: int, end: int) {
        editor.select(start, end);
        const rect = editor.positionToRectangle(start);
        viewport.contentY = Math.max(0, Math.min(rect.y - viewport.height / 3,
                                                  viewport.contentHeight - viewport.height));
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 14
            spacing: 10
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Label {
                    text: pane.title
                    color: "#244339"
                    font.bold: true
                    font.pixelSize: 15
                }
                Label {
                    Layout.fillWidth: true
                    text: pane.documentName || "尚未选择文件"
                    textFormat: Text.PlainText
                    elide: Text.ElideMiddle
                    color: "#52665d"
                    font.pixelSize: 12
                    ToolTip.visible: nameHover.hovered && text.length > 0
                    ToolTip.text: text
                    HoverHandler { id: nameHover }
                }
            }
            Button {
                text: "选择文件…"
                objectName: pane.side + "Browse"
                enabled: !pane.busy
                onClicked: pane.pickFile()
            }
            ComboBox {
                Layout.preferredWidth: 119
                objectName: pane.side + "Encoding"
                Accessible.name: pane.title + "的 TXT 编码"
                model: ["UTF-8", "GB18030"]
                currentIndex: pane.textEncoding === "gb18030" ? 1 : 0
                enabled: !pane.busy && pane.documentName.toLowerCase().endsWith(".txt")
                onActivated: pane.encodingChangedByUser(index === 0 ? "utf-8" : "gb18030")
                ToolTip.visible: hovered
                ToolTip.text: "TXT 文件编码"
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: "#dfe6e2" }
        Flickable {
            id: viewport
            objectName: pane.side + "Viewport"
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: editor.height
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            ScrollBar.vertical: ScrollBar {}

            TextArea {
                id: editor
                objectName: pane.side + "Text"
                Accessible.name: pane.title + "正文"
                width: viewport.width
                height: Math.max(implicitHeight, viewport.height)
                readOnly: true
                selectByMouse: true
                persistentSelection: true
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                font.pixelSize: 16
                color: "#243a32"
                selectionColor: "#bcd7f0"
                selectedTextColor: "#16334b"
                padding: 18
                background: null
            }
        }
    }
}
