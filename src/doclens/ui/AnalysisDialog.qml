import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: analysis
    required property QtObject backend
    required property int changeCount
    required property int activeGroup
    anchors.centerIn: parent
    title: "AI 差异分析"
    modal: true
    standardButtons: Dialog.Close
    closePolicy: Popup.CloseOnEscape
    onOpened: {
        if (backend.report.length === 0 && !backend.busy) {
            first.value = activeGroup;
            last.value = activeGroup;
        }
    }

    Connections {
        target: analysis.backend
        function onEvidenceRequested() { analysis.close(); }
    }

    contentItem: ColumnLayout {
        spacing: 10
        GridLayout {
            columns: 2
            Layout.fillWidth: true
            enabled: !analysis.backend.busy
            Label { text: "服务地址" }
            TextField {
                id: endpoint
                objectName: "aiEndpoint"
                Layout.fillWidth: true
                placeholderText: "https://服务地址/v1/chat/completions"
                maximumLength: 500
                selectByMouse: true
                onTextChanged: if (key) key.clear()
            }
            Label { text: "模型名称" }
            TextField {
                id: modelName
                objectName: "aiModel"
                Layout.fillWidth: true
                placeholderText: "输入服务提供的模型名称"
                maximumLength: 160
            }
            Label { text: "API Key" }
            TextField {
                id: key
                objectName: "aiKey"
                Layout.fillWidth: true
                placeholderText: "仅在本次应用会话中使用"
                echoMode: TextInput.Password
                maximumLength: 4096
            }
            Label { text: "请求格式" }
            ComboBox {
                id: provider
                objectName: "aiProvider"
                Layout.fillWidth: true
                textRole: "label"
                valueRole: "profile"
                model: [
                    {label: "自动识别（兼容现有设置）", profile: "auto"},
                    {label: "通用 Chat Completions", profile: "compatible"},
                    {label: "Chat Completions + JSON 模式", profile: "json"},
                    {label: "DeepSeek 请求格式", profile: "deepseek"}
                ]
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Label { text: "分析第" }
            SpinBox {
                id: first
                objectName: "aiFirst"
                from: 1
                to: Math.max(1, analysis.changeCount)
                editable: true
                enabled: !analysis.backend.busy
                Accessible.name: "开始差异编号"
            }
            Label { text: "至" }
            SpinBox {
                id: last
                objectName: "aiLast"
                from: 1
                to: Math.max(1, analysis.changeCount)
                editable: true
                enabled: !analysis.backend.busy
                Accessible.name: "结束差异编号"
            }
            Label { text: "组" }
            Item { Layout.fillWidth: true }
            Button {
                text: "清除分析缓存"
                enabled: !analysis.backend.busy
                onClicked: analysis.backend.clearCache()
            }
            Button {
                text: "取消等待"
                visible: analysis.backend.busy
                onClicked: analysis.backend.cancel()
            }
            Button {
                objectName: "aiPrepare"
                text: "预览待发送内容"
                highlighted: true
                enabled: analysis.changeCount > 0 && !analysis.backend.busy
                onClicked: {
                    if (analysis.backend.prepare(first.value, last.value, endpoint.text, modelName.text, provider.currentValue))
                        confirmation.open();
                }
            }
        }

        Label {
            Layout.fillWidth: true
            text: analysis.backend.status
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            color: "#25483d"
        }
        Label {
            Layout.fillWidth: true
            visible: analysis.backend.report.length > 0
            text: "点击证据可回到对应原文。请以原文核对模型解释。"
            color: "#53675f"
            font.pixelSize: 12
        }
        ListView {
            id: findings
            objectName: "aiFindings"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: analysis.backend.report
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: card
                required property var modelData
                required property int index
                width: findings.width - 14
                height: findingContent.implicitHeight + 24
                color: "#f4f8f5"
                border.color: "#d7e3db"
                radius: 5
                ColumnLayout {
                    id: findingContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 12
                    spacing: 6
                    Label {
                        Layout.fillWidth: true
                        text: card.modelData.category + " · " + card.modelData.summary
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        font.bold: true
                        color: "#244339"
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: !!card.modelData.impact
                        text: card.modelData.impact
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: "#415c51"
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.preferredHeight: implicitHeight
                        spacing: 6
                        Repeater {
                            model: card.modelData.evidence
                            delegate: Button {
                                required property string modelData
                                required property int index
                                objectName: "aiEvidence" + card.index + "_" + index
                                text: modelData
                                onClicked: analysis.backend.openEvidence(card.index, index)
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: confirmation
        objectName: "aiConfirmation"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(analysis.width - 24, 790)
        height: Math.min(analysis.height - 24, 540)
        title: "确认发送差异片段"
        modal: true
        closePolicy: Popup.CloseOnEscape
        onClosed: analysis.backend.discardPreview()

        contentItem: ColumnLayout {
            spacing: 8
            Label {
                Layout.fillWidth: true
                text: analysis.backend.previewDestination
                textFormat: Text.PlainText
                wrapMode: Text.WrapAnywhere
                font.bold: true
                color: "#244339"
            }
            Label {
                Layout.fillWidth: true
                text: analysis.backend.scope
                wrapMode: Text.Wrap
                color: "#53675f"
            }
            ScrollView {
                Layout.fillHeight: true
                Layout.fillWidth: true
                TextArea {
                    objectName: "aiPreview"
                    text: analysis.backend.preview
                    textFormat: TextEdit.PlainText
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.Wrap
                }
            }
            RowLayout {
                Item { Layout.fillWidth: true }
                Button {
                    objectName: "aiDecline"
                    text: "返回"
                    onClicked: confirmation.close()
                }
                Button {
                    objectName: "aiSend"
                    text: "确认发送"
                    highlighted: true
                    onClicked: {
                        analysis.backend.approveAndSend(key.text);
                        confirmation.close();
                    }
                }
            }
        }
    }
}
