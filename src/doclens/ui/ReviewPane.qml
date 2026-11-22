import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: review
    required property QtObject backend
    color: "#ffffff"
    border.color: "#d5dedb"
    radius: 7
    function applyFilter() {
        backend.setReviewFilter(["all", "insert", "delete", "replace", "move"][kind.currentIndex],
                                ["all", "pending", "reviewed"][state.currentIndex], query.text);
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6
        Label { text: "差异审阅"; font.bold: true; color: "#244339" }
        Label { text: review.backend.reviewSummary; color: "#53675f" }
        RowLayout {
            Layout.fillWidth: true
            ComboBox { id: kind; objectName: "reviewKind"; Layout.fillWidth: true; model: ["全部类型", "新增", "删除", "修改", "移动"]; onActivated: review.applyFilter() }
            ComboBox { id: state; objectName: "reviewState"; Layout.fillWidth: true; model: ["全部状态", "待核对", "已核对"]; onActivated: review.applyFilter() }
        }
        ComboBox {
            Layout.fillWidth: true
            objectName: "reviewCategory"
            model: ["全部AI类别", "未分类", "研究问题", "方法", "数据", "结果", "结论", "引用文献", "时间", "金额", "权限", "责任", "要求与限制", "表述", "其他"]
            onActivated: review.backend.setCategoryFilter(["all", "unclassified", "research_question", "method", "data", "result", "conclusion", "citation", "time", "amount", "permission", "responsibility", "requirement", "editorial", "other"][currentIndex])
        }
        TextField {
            id: query
            objectName: "reviewQuery"
            Layout.fillWidth: true
            placeholderText: "搜索章节、正文或备注"
            onTextChanged: review.applyFilter()
        }
        ListView {
            id: rows
            objectName: "reviewList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            model: review.backend.reviewRows
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: card
                required property var modelData
                width: rows.width - 12
                height: contents.implicitHeight + 16
                color: review.backend.changeIndex === modelData.index ? "#e5f1eb" : "#f5f7f6"
                radius: 4
                ColumnLayout {
                    id: contents
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 8
                    spacing: 4
                    Button {
                        objectName: "reviewJump" + card.modelData.index
                        Layout.fillWidth: true
                        text: "第 " + (card.modelData.index + 1) + " 组 · " + card.modelData.label + (card.modelData.numbersChanged ? " · 数字变化" : "")
                        onClicked: review.backend.jumpToChange(card.modelData.index)
                    }
                    Label { Layout.fillWidth: true; text: card.modelData.section + " · " + card.modelData.category; textFormat: Text.PlainText; elide: Text.ElideRight; color: "#53675f" }
                    Label { Layout.fillWidth: true; text: (card.modelData.old || "（空）").slice(0, 65) + " → " + (card.modelData.new || "（空）").slice(0, 65); textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                    CheckBox {
                        objectName: "reviewChecked" + card.modelData.index
                        text: "已核对"
                        checked: card.modelData.reviewed
                        onClicked: review.backend.setReviewed(card.modelData.index, checked)
                    }
                    TextField {
                        objectName: "reviewNote" + card.modelData.index
                        Layout.fillWidth: true
                        text: card.modelData.note
                        maximumLength: 2000
                        placeholderText: "备注（回车或离开保存）"
                        onEditingFinished: review.backend.setReviewNote(card.modelData.index, text)
                    }
                }
            }
        }
        Label { Layout.fillWidth: true; text: "备注随导出报告留档；重比或换文件后清空。"; wrapMode: Text.Wrap; color: "#53675f"; font.pixelSize: 11 }
    }
}
