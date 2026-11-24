import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Dialog {
    id: root
    required property QtObject backend
    title: "多文档研究 · " + backend.name + (backend.dirty ? " *" : "")
    modal: true
    standardButtons: Dialog.Close
    property string noteId: ""
    property string pendingAction: ""
    function requestAction(action) {
        if (backend.dirty) { pendingAction = action; discard.open(); }
        else execute(action);
    }
    function execute(action) {
        if (action === "new") { backend.newProject(projectName.text); noteId = ""; noteText.text = ""; }
        else openPicker.open();
    }
    Dialog {
        id: discard
        title: "放弃当前项目未保存的修改？"
        modal: true
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: root.execute(root.pendingAction)
    }
    FileDialog {
        id: importPicker
        title: "批量导入研究文档"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["文档 (*.pdf *.docx *.txt *.md *.markdown)"]
        onAccepted: root.backend.importFiles(selectedFiles)
    }
    FileDialog {
        id: openPicker
        title: "打开项目或重导入共享包"
        nameFilters: ["研究项目 / 共享包 (*.json *.zip)"]
        onAccepted: { root.noteId = ""; noteText.text = ""; root.backend.openProject(selectedFile); }
    }
    FileDialog {
        id: savePicker
        fileMode: FileDialog.SaveFile
        nameFilters: ["研究项目 (*.json)"]
        defaultSuffix: "json"
        onAccepted: root.backend.saveProject(selectedFile)
    }
    FileDialog {
        id: markdownPicker
        fileMode: FileDialog.SaveFile
        nameFilters: ["Markdown (*.md)"]
        defaultSuffix: "md"
        onAccepted: root.backend.exportMarkdown(selectedFile)
    }
    FileDialog {
        id: sharePicker
        fileMode: FileDialog.SaveFile
        nameFilters: ["离线共享包 (*.zip)"]
        defaultSuffix: "zip"
        onAccepted: root.backend.exportBundle(selectedFile, includeOriginals.checked)
    }
    Connections {
        target: root.backend
        function onNoteSaved(identifier) { root.noteId = identifier; }
        function onJumpRequested(start, end) {
            sourceText.forceActiveFocus();
            sourceText.cursorPosition = start;
            sourceText.select(start, end);
            var rect = sourceText.positionToRectangle(start);
            sourceScroll.contentItem.contentY = Math.max(0, Math.min(rect.y - 40,
                sourceScroll.contentItem.contentHeight - sourceScroll.height));
        }
    }
    contentItem: ColumnLayout {
        spacing: 8
        RowLayout {
            enabled: !root.backend.busy
            TextField { id: projectName; placeholderText: "新项目名称"; Layout.preferredWidth: 160 }
            Button { text: "新建"; onClicked: root.requestAction("new") }
            Button { text: "打开 / 重导入"; onClicked: root.requestAction("open") }
            Button { text: "保存项目"; onClicked: savePicker.open() }
            Button { text: "批量导入"; objectName: "researchImport"; onClicked: importPicker.open() }
            Button { text: "导出 Markdown"; onClicked: markdownPicker.open() }
            Button { text: "导出共享包"; onClicked: sharePicker.open() }
        }
        RowLayout {
            CheckBox { id: includeOriginals; text: "共享包附带原始文件"; enabled: !root.backend.busy }
            Label { text: "不附原文仍含提取正文、证据和笔记，请确认可共享。"; wrapMode: Text.Wrap; Layout.fillWidth: true; color: "#8b4b16" }
        }
        Label { text: root.backend.status; wrapMode: Text.Wrap; Layout.fillWidth: true; color: "#245744" }
        ScrollView {
            visible: root.backend.issues.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 48 : 0
            TextArea { text: root.backend.issues.join("\n"); readOnly: true; wrapMode: TextEdit.Wrap; font.pixelSize: 12 }
        }
        Label { text: "使用线索需核对 · 词典外项不识别 · 未发现 ≠ 不存在 · 点击单元格查看全部证据"; wrapMode: Text.Wrap; Layout.fillWidth: true }
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            enabled: !root.backend.busy
            orientation: Qt.Horizontal
            ColumnLayout {
                SplitView.preferredWidth: 560
                SplitView.minimumWidth: 280
                TabBar {
                    id: tabs
                    Layout.fillWidth: true
                    TabButton { text: "对照矩阵" }
                    TabButton { text: "文档与目录" }
                    TabButton { text: "笔记" }
                }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: tabs.currentIndex
                    ScrollView {
                        clip: true
                        Column {
                            spacing: 3
                            Row {
                                spacing: 3
                                Label { text: "共同项 / 类别"; width: 160; height: 46; verticalAlignment: Text.AlignVCenter }
                                Repeater { model: root.backend.documents; Label { required property var modelData; width: 160; height: 46; text: modelData.name; wrapMode: Text.Wrap; elide: Text.ElideRight } }
                            }
                            Repeater {
                                model: root.backend.matrix
                                Row {
                                    id: matrixRow
                                    required property var modelData
                                    spacing: 3
                                    Label { width: 160; height: 48; text: (matrixRow.modelData.common ? "● " : "") + matrixRow.modelData.term + "\n" + matrixRow.modelData.kind; color: matrixRow.modelData.common ? "#176345" : "#444444" }
                                    Repeater {
                                        model: matrixRow.modelData.cells
                                        Button {
                                            required property var modelData
                                            width: 160; height: 48
                                            text: modelData.state + " (" + modelData.count + ")"
                                            onClicked: root.backend.selectCell(matrixRow.modelData.term, modelData.document)
                                        }
                                    }
                                }
                            }
                            Label { visible: root.backend.matrix.length === 0; text: "导入文档后显示词典命中项。" }
                        }
                    }
                    ColumnLayout {
                        ListView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 160
                            clip: true
                            model: root.backend.documents
                            delegate: RowLayout {
                                required property var modelData
                                width: ListView.view.width
                                Button { text: modelData.name; Layout.fillWidth: true; onClicked: root.backend.selectDocument(modelData.id) }
                                Button { text: "移除"; onClicked: root.backend.removeDocument(modelData.id) }
                            }
                        }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            TextArea {
                                text: root.backend.outline || "此文档未识别到章节标题。"
                                readOnly: true
                                textFormat: TextEdit.MarkdownText
                                wrapMode: TextEdit.Wrap
                                onLinkActivated: function(link) { root.backend.jumpHeading(parseInt(link.split(":")[1])); }
                            }
                        }
                    }
                    ColumnLayout {
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: root.backend.notes
                            delegate: ColumnLayout {
                                required property var modelData
                                width: ListView.view.width
                                Label { text: modelData.text; wrapMode: Text.Wrap; Layout.fillWidth: true; textFormat: Text.PlainText }
                                RowLayout {
                                    Button { text: "编辑"; onClicked: { root.noteId = modelData.id; noteText.text = modelData.text; linkEvidence.checked = !!modelData.evidence; if (modelData.evidence) root.backend.selectEvidence(modelData.evidence); } }
                                    Button { text: "证据"; enabled: !!modelData.evidence; onClicked: root.backend.selectEvidence(modelData.evidence) }
                                    Button { text: "删除"; onClicked: { root.backend.deleteNote(modelData.id); root.noteId = ""; noteText.text = ""; } }
                                }
                            }
                        }
                        TextArea { id: noteText; Layout.fillWidth: true; Layout.preferredHeight: 90; placeholderText: "记录比对笔记"; wrapMode: TextEdit.Wrap }
                        CheckBox { id: linkEvidence; text: "关联当前选中证据"; enabled: !!root.backend.selectedEvidence }
                        Label { visible: !!root.backend.selectedEvidence; text: "已选中一条证据，可关联笔记"; color: "#245744" }
                        RowLayout {
                            Button { text: root.noteId ? "更新笔记" : "新增笔记"; onClicked: root.backend.saveNote(root.noteId, noteText.text, linkEvidence.checked && linkEvidence.enabled) }
                            Button { text: "清空编辑框"; onClicked: { root.noteId = ""; noteText.text = ""; } }
                        }
                    }
                }
                Label { text: "证据（点击跳转并选中原文）" }
                ListView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    clip: true
                    model: root.backend.evidenceRows
                    delegate: ItemDelegate {
                        required property var modelData
                        width: ListView.view.width
                        text: modelData.state + " · " + modelData.location + " · " + modelData.section + "\n" + modelData.context
                        highlighted: root.backend.selectedEvidence === modelData.id
                        onClicked: root.backend.selectEvidence(modelData.id)
                        ToolTip.visible: hovered
                        ToolTip.text: modelData.context
                    }
                }
            }
            ColumnLayout {
                SplitView.fillWidth: true
                SplitView.minimumWidth: 240
                Label { text: root.backend.previewName; font.bold: true; Layout.fillWidth: true; elide: Text.ElideMiddle }
                ScrollView {
                    id: sourceScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    TextArea {
                        id: sourceText
                        objectName: "researchText"
                        text: root.backend.previewText
                        textFormat: TextEdit.PlainText
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        wrapMode: TextEdit.Wrap
                        font.pixelSize: 15
                        selectionColor: "#e7c65e"
                        selectedTextColor: "#142d24"
                    }
                }
            }
        }
    }
}
