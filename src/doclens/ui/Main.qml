import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    required property QtObject controller
    width: 1120
    height: 720
    minimumWidth: 760
    minimumHeight: 480
    visible: true
    title: "DocLens"
    color: "#edf2ef"
    font.family: "Microsoft YaHei UI"

    function jump(side: string, start: int, end: int) {
        (side === "left" ? leftPane : rightPane).jump(start, end);
    }

    onClosing: function(event) {
        if (controller.busy) {
            event.accepted = false;
            controller.cancel();
            closeWhenIdle = true;
        }
    }
    property bool closeWhenIdle: false
    Connections {
        target: window.controller
        function onBusyChanged() {
            if (window.closeWhenIdle && !window.controller.busy)
                Qt.callLater(window.close);
        }
    }

    FileDialog {
        id: picker
        property string side: "left"
        title: side === "left" ? "选择原文档" : "选择新版文档"
        nameFilters: ["文本文档 (*.txt *.docx)"]
        onAccepted: window.controller.selectFile(side, selectedFile)
    }

    Shortcut {
        sequence: "Ctrl+Return"
        enabled: window.controller.canCompare
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
            Layout.fillHeight: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            uniformCellSizes: true
            spacing: 12
            DocumentPane {
                id: leftPane
                Layout.fillWidth: true
                Layout.fillHeight: true
                side: "left"
                title: "原文档"
                documentName: window.controller.leftName
                textEncoding: window.controller.leftEncoding
                busy: window.controller.busy
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
                onPickFile: { picker.side = side; picker.open(); }
                onEncodingChangedByUser: value => window.controller.setEncoding(side, value)
            }
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
            text: window.controller.currentLocation || "支持 TXT 和 DOCX 正文。"
            wrapMode: Text.Wrap
            color: "#4a6259"
            font.pixelSize: 12
        }
    }
}
