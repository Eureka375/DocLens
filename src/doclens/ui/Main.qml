import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    required property QtObject controller
    required property QtObject workspace
    required property QtObject analysis
    width: 1440
    height: 840
    minimumWidth: 760
    property bool showReview: true
    minimumHeight: 480
    visible: true
    title: "DocLens"
    color: "#edf2ef"
    font.family: "Microsoft YaHei UI"

    function jump(side: string, start: int, end: int) {
        (side === "left" ? leftPane : rightPane).jump(start, end);
    }
    function jumpPreview(side: string, group: int) {
        (side === "left" ? leftPane : rightPane).jumpPreview(group);
    }

    onClosing: function(event) {
        if (workInProgress) {
            event.accepted = false;
            closeWhenIdle = true;
            controller.cancel();
            workspace.cancel();
            analysis.cancel();
        }
    }
    property bool closeWhenIdle: false
    readonly property bool workInProgress: controller.busy || workspace.busy || analysis.busy
    onWorkInProgressChanged: {
        if (closeWhenIdle && !workInProgress)
            Qt.callLater(window.close);
    }

    WorkspaceDialog {
        id: searchDialog
        objectName: "workspaceDialog"
        parent: Overlay.overlay
        width: Math.min(window.width - 36, 1040)
        height: Math.min(window.height - 36, 680)
        backend: window.workspace
    }
    AnalysisDialog {
        id: analysisDialog
        objectName: "analysisDialog"
        parent: Overlay.overlay
        width: Math.min(window.width - 36, 1120)
        height: Math.min(window.height - 36, 760)
        backend: window.analysis
        changeCount: window.controller.changeCount
        activeGroup: Math.max(1, window.controller.changeIndex + 1)
        onHomeRequested: {
            if (window.width < 1280) homeReviewDrawer.open();
            else window.showReview = true;
        }
    }

    Drawer {
        id: homeReviewDrawer
        objectName: "homeReviewDrawer"
        parent: Overlay.overlay
        edge: Qt.LeftEdge
        width: Math.min(420, window.width - 32)
        height: window.height
        modal: false
        dim: false
        contentItem: ReviewPane {
            backend: window.controller
            listObjectName: "drawerReviewList"
            onEvidenceOpened: homeReviewDrawer.close()
        }
    }

    FileDialog {
        id: reportPicker
        title: "导出完整审阅报告"
        fileMode: FileDialog.SaveFile
        nameFilters: ["HTML 报告 (*.html)"]
        defaultSuffix: "html"
        onAccepted: window.controller.exportReport(selectedFile)
    }

    FileDialog {
        id: picker
        property string side: "left"
        title: side === "left" ? "选择原文档" : "选择新版文档"
        nameFilters: ["文档 (*.txt *.docx *.pdf *.TXT *.DOCX *.PDF)"]
        onAccepted: window.controller.selectFile(side, selectedFile)
    }

    Shortcut {
        sequence: "Ctrl+Return"
        enabled: window.controller.canCompare && !searchDialog.visible && !analysisDialog.visible
        onActivated: window.controller.startComparison()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 79
            color: "#183c34"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: 12
                ColumnLayout {
                    spacing: 1
                    Label { text: "DocLens"; color: "#ffffff"; font.pixelSize: 25; font.bold: true }
                    Label { text: "本地文档比对"; color: "#c8ded5"; font.pixelSize: 12 }
                }
                Item { Layout.fillWidth: true }
                Button {
                    objectName: "openWorkspace"
                    text: "文件夹检索"
                    onClicked: searchDialog.open()
                }
                Button {
                    objectName: "openAnalysis"
                    text: "AI 分析"
                    enabled: window.controller.changeCount > 0 && !window.controller.busy
                    onClicked: analysisDialog.open()
                }
                BusyIndicator {
                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 30
                    running: window.controller.busy
                    visible: running
                }
                Button {
                    objectName: "cancelComparison"
                    text: "取消"
                    visible: window.controller.busy
                    onClicked: window.controller.cancel()
                }
                Button {
                    objectName: "startComparison"
                    text: "开始比对"
                    highlighted: true
                    enabled: window.controller.canCompare
                    onClicked: window.controller.startComparison()
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            Layout.topMargin: 12
            Layout.bottomMargin: 12
            spacing: 8
            Label {
                Layout.fillWidth: true
                objectName: "status"
                text: window.controller.status
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: "#25483d"
                font.bold: true
                font.pixelSize: 14
            }
            Label {
                visible: window.controller.changeCount > 0
                text: (window.controller.changeIndex + 1) + " / " + window.controller.changeCount
                color: "#365448"
            }
            Button {
                objectName: "previousChange"
                text: "上一处"
                enabled: !window.controller.busy && window.controller.changeIndex > 0
                onClicked: window.controller.navigate(-1)
            }
            Button {
                objectName: "nextChange"
                text: "下一处"
                enabled: !window.controller.busy && window.controller.changeIndex + 1 < window.controller.changeCount
                onClicked: window.controller.navigate(1)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            Layout.bottomMargin: 12
            spacing: 10
            visible: jumpPicker.count > 0
            Label {
                text: "跳转到差异"
                color: "#365448"
                font.bold: true
            }
            ComboBox {
                id: jumpPicker
                objectName: "jumpToChange"
                Accessible.name: "跳转到差异"
                Layout.fillWidth: true
                enabled: !window.controller.busy && count > 0
                model: window.controller.changeEntries
                currentIndex: window.controller.changeIndex
                onActivated: index => window.controller.jumpToChange(index)
            }
            CheckBox {
                text: "审阅列表"
                checked: window.width >= 1280 ? window.showReview : homeReviewDrawer.opened
                onClicked: {
                    if (window.width < 1280) {
                        if (homeReviewDrawer.opened) homeReviewDrawer.close();
                        else homeReviewDrawer.open();
                    } else window.showReview = checked;
                }
            }
            CheckBox {
                objectName: "wordHighlight"
                text: "词级高亮"
                checked: window.controller.wordMode
                onClicked: window.controller.setWordMode(checked)
            }
            Button {
                objectName: "exportReport"
                text: "导出报告"
                enabled: !window.workInProgress
                onClicked: reportPicker.open()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            spacing: 12
            ReviewPane {
                Layout.preferredWidth: 360
                Layout.fillHeight: true
                visible: window.controller.changeCount > 0 && window.width >= 1280 && window.showReview
                backend: window.controller
            }
            DocumentPane {
                id: leftPane
                Layout.fillWidth: true
                Layout.fillHeight: true
                side: "left"
                title: "原文档"
                documentName: window.controller.leftName
                textEncoding: window.controller.leftEncoding
                busy: window.controller.busy
                previewPages: window.controller.leftPreview
                activeGroup: window.controller.changeIndex
                onPickFile: { picker.side = side; picker.open(); }
                onEncodingChangedByUser: value => window.controller.setEncoding(side, value)
            }
            DocumentPane {
                id: rightPane
                Layout.fillWidth: true
                Layout.fillHeight: true
                side: "right"
                title: "新版文档"
                documentName: window.controller.rightName
                textEncoding: window.controller.rightEncoding
                busy: window.controller.busy
                previewPages: window.controller.rightPreview
                activeGroup: window.controller.changeIndex
                onPickFile: { picker.side = side; picker.open(); }
                onEncodingChangedByUser: value => window.controller.setEncoding(side, value)
            }
        }
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: 22
            Layout.rightMargin: 22
            Layout.topMargin: 6
            text: window.controller.coverageNotice
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: "#6b562f"
            font.pixelSize: 11
        }
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: 22
            Layout.rightMargin: 22
            Layout.topMargin: 10
            visible: window.controller.warning.length > 0
            text: window.controller.warning
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: "#70471b"
        }
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: 22
            Layout.rightMargin: 22
            Layout.topMargin: 10
            Layout.bottomMargin: 12
            text: window.controller.currentLocation || "支持 TXT、DOCX 和文本型 PDF。"
            wrapMode: Text.Wrap
            color: "#4a6259"
            font.pixelSize: 12
        }
    }
}
