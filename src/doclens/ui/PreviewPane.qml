import QtQuick
import QtQuick.Controls

ListView {
    id: preview
    required property var pages
    required property string side
    property int activeGroup: -1
    property real zoom: 1
    readonly property real pageWidth: Math.max(220, width - 36) * zoom
    objectName: side + "PagePreview"
    model: pages
    spacing: 18
    clip: true
    contentWidth: Math.max(width, pageWidth + 36)
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.AutoFlickDirection
    ScrollBar.vertical: ScrollBar {}
    ScrollBar.horizontal: ScrollBar {}

    function jumpGroup(group: int) {
        if (group < 0) return;
        for (let i = 0; i < pages.length; ++i) {
            const marks = pages[i].marks.concat(pages[i].anchors || []);
            for (let j = 0; j < marks.length; ++j) {
                if (marks[j].group !== group) continue;
                const pageIndex = i;
                const y = marks[j].y;
                forceLayout();
                positionViewAtIndex(pageIndex, ListView.Beginning);
                Qt.callLater(function() {
                    if (preview.activeGroup !== group) return;
                    preview.forceLayout();
                    const item = itemAtIndex(pageIndex);
                    if (item) contentY = Math.max(originY, Math.min(item.y + y * item.paperHeight - height / 3,
                                                  originY + contentHeight - height));
                });
                return;
            }
        }
    }

    delegate: Item {
        required property var modelData
        required property int index
        width: preview.contentWidth
        height: paper.height + 30
        property real paperHeight: paper.height
        Rectangle {
            id: paper
            x: Math.max(18, (preview.width - width) / 2)
            width: preview.pageWidth
            height: width * modelData.height / modelData.width
            color: "white"
            border.color: "#bac5c0"
            Image {
                anchors.fill: parent
                source: modelData.source
                fillMode: Image.Stretch
                cache: false
                smooth: true
                sourceSize.width: modelData.width
                sourceSize.height: modelData.height
            }
            Repeater {
                model: modelData.marks
                delegate: Rectangle {
                    required property var modelData
                    x: modelData.x * paper.width
                    y: modelData.y * paper.height
                    width: Math.max(2, modelData.width * paper.width)
                    height: Math.max(3, modelData.height * paper.height)
                    color: modelData.color
                    opacity: modelData.group === preview.activeGroup ? 0.40 : 0.24
                    border.color: modelData.group === preview.activeGroup ? "#253e56" : "transparent"
                    border.width: modelData.group === preview.activeGroup ? 1 : 0
                }
            }
        }
        Label {
            anchors.top: paper.bottom
            anchors.topMargin: 6
            anchors.horizontalCenter: paper.horizontalCenter
            text: "第 " + modelData.page + " 页"
            color: "#52665d"
            font.pixelSize: 12
        }
    }
}
