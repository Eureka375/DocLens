import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Dialog {
    id: workspace
    required property QtObject backend
    anchors.centerIn: parent
    title: "文件夹检索"
    modal: true
    standardButtons: Dialog.Close
    closePolicy: Popup.CloseOnEscape

    FolderDialog {
        id: folderPicker
        title: "选择文档文件夹"
        onAccepted: {
            viewMode.currentIndex = 0;
            workspace.backend.chooseFolder(selectedFolder, recursive.checked, legacy.checked);
        }
    }

    Connections {
        target: workspace.backend
        function onPreviewChanged() {
            Qt.callLater(function() {
                const start = workspace.backend.previewStart;
                preview.select(start, workspace.backend.previewEnd);
                const y = preview.positionToRectangle(start).y;
                previewView.contentY = Math.max(0, Math.min(y - previewView.height / 3,
                                                           previewView.contentHeight - previewView.height));
            });
        }
    }

    contentItem: ColumnLayout {
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Button {
                text: "选择文件夹…"
                enabled: !workspace.backend.busy
                onClicked: folderPicker.open()
            }
            Label {
                Layout.fillWidth: true
                text: workspace.backend.folder || "未选择文件夹"
                textFormat: Text.PlainText
                elide: Text.ElideMiddle
                color: "#365448"
            }
            Button {
                text: "重新扫描"
                enabled: !!workspace.backend.folder && !workspace.backend.busy
                onClicked: {
                    viewMode.currentIndex = 0;
                    workspace.backend.rescan(recursive.checked, legacy.checked);
                }
            }
            Button {
                text: "清除缓存"
                enabled: !!workspace.backend.folder && !workspace.backend.busy
                onClicked: workspace.backend.clearCache()
            }
        }
        RowLayout {
            CheckBox { id: recursive; text: "包含子文件夹"; enabled: !workspace.backend.busy }
            CheckBox { id: legacy; text: "旧 TXT 尝试 GB18030"; enabled: !workspace.backend.busy }
            Item { Layout.fillWidth: true }
            Button {
                text: "取消任务"
                enabled: workspace.backend.busy
                onClicked: workspace.backend.cancel()
            }
        }
        RowLayout {
            TextField {
                id: query
                objectName: "workspaceQuery"
                Layout.fillWidth: true
                maximumLength: 200
                placeholderText: "在文档正文中查找关键词或短语"
                enabled: workspace.backend.ready
                onAccepted: searchButton.clicked()
            }
            Button {
                id: searchButton
                objectName: "workspaceSearch"
                text: "搜索"
                highlighted: true
                enabled: workspace.backend.ready && !!query.text.trim()
                onClicked: {
                    viewMode.currentIndex = 1;
                    workspace.backend.search(query.text);
                }
            }
        }
        RowLayout {
            Label {
                Layout.fillWidth: true
                text: workspace.backend.status
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: "#25483d"
            }
            Button {
                text: "扫描提示 (" + workspace.backend.issues.length + ")"
                visible: workspace.backend.issues.length > 0
                onClicked: issuesDialog.open()
            }
        }
        TabBar {
            id: viewMode
            Layout.preferredWidth: 295
            TabButton { text: "已扫描文档" }
            TabButton { text: "搜索结果" }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10
            Rectangle {
                Layout.preferredWidth: Math.min(330, workspace.width * 0.37)
                Layout.fillHeight: true
                radius: 5
                border.color: "#d5dedb"
                color: "#f6f9f7"

                ListView {
                    id: results
                    objectName: "workspaceHits"
                    anchors.fill: parent
                    anchors.margins: 1
                    clip: true
                    model: viewMode.currentIndex === 0 ? workspace.backend.documents : workspace.backend.hits
                    currentIndex: viewMode.currentIndex === 0 ? -1 : workspace.backend.activeHit
                    ScrollBar.vertical: ScrollBar {}
                    delegate: ItemDelegate {
                        id: hitRow
                        required property var modelData
                        required property int index
                        objectName: "workspaceHit" + index
                        width: results.width
                        highlighted: index === results.currentIndex
                        enabled: !workspace.backend.busy
                        onClicked: {
                            if (viewMode.currentIndex === 0)
                                workspace.backend.openDocument(index);
                            else
                                workspace.backend.openHit(index);
                        }
                        contentItem: ColumnLayout {
                            spacing: 4
                            Label {
                                Layout.fillWidth: true
                                text: hitRow.modelData.path
                                textFormat: Text.PlainText
                                elide: Text.ElideMiddle
                                color: "#244339"
                                font.bold: true
                            }
                            Label {
                                Layout.fillWidth: true
                                text: viewMode.currentIndex === 0 ? hitRow.modelData.detail :
                                      hitRow.modelData.location + " · " + hitRow.modelData.snippet
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                font.pixelSize: 12
                                color: "#52665d"
                            }
                        }
                    }
                }
                Label {
                    anchors.centerIn: parent
                    visible: results.count === 0
                    text: viewMode.currentIndex === 0 ? "暂无已扫描文档" : "暂无搜索结果"
                    color: "#52665d"
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 5
                border.color: "#d5dedb"
                color: "white"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 1
                    Label {
                        Layout.fillWidth: true
                        padding: 10
                        text: workspace.backend.previewSource || "从搜索结果打开匹配原文"
                        textFormat: Text.PlainText
                        elide: Text.ElideMiddle
                        color: "#244339"
                        font.bold: true
                    }
                    Flickable {
                        id: previewView
                        objectName: "workspacePreviewView"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: width
                        contentHeight: preview.height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar {}
                        TextArea {
                            id: preview
                            objectName: "workspacePreview"
                            width: previewView.width
                            height: Math.max(implicitHeight, previewView.height)
                            text: workspace.backend.previewText
                            textFormat: TextEdit.PlainText
                            readOnly: true
                            selectByMouse: true
                            persistentSelection: true
                            wrapMode: TextEdit.Wrap
                            padding: 12
                            background: null
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: issuesDialog
        anchors.centerIn: parent
        width: Math.min(620, workspace.width - 24)
        height: Math.min(330, workspace.height - 24)
        title: "扫描提示"
        modal: true
        standardButtons: Dialog.Close
        contentItem: ScrollView {
            TextArea {
                text: workspace.backend.issues.join("\n\n")
                textFormat: TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
            }
        }
    }
}
