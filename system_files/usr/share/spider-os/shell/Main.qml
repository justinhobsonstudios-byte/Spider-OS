import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    visible: true
    width: 1180
    height: 760
    minimumWidth: 760
    minimumHeight: 520
    title: "The Web — Spider OS"
    color: "#09090b"

    property string statusText: "Connecting to Spider Core…"
    property bool coreReady: false

    function refresh() {
        const request = new XMLHttpRequest()
        request.open("GET", "http://127.0.0.1:8765/api/health")
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) return
            coreReady = request.status === 200
            statusText = coreReady ? "Webbie is resident and Spider Core is ready" : "Spider Core is starting"
        }
        request.send()
    }

    Component.onCompleted: refresh()
    Timer { interval: 3000; running: true; repeat: true; onTriggered: root.refresh() }

    header: ToolBar {
        background: Rectangle { color: "#121216"; border.color: "#6e0f1d" }
        RowLayout {
            anchors.fill: parent
            anchors.margins: 12
            Label { text: "SPIDER OS"; color: "#f3eadf"; font.pixelSize: 23; font.bold: true }
            Item { Layout.fillWidth: true }
            Rectangle { width: 10; height: 10; radius: 5; color: root.coreReady ? "#36c98f" : "#a30f2d" }
            Label { text: root.statusText; color: "#c8c1b8" }
        }
    }

    SplitView {
        anchors.fill: parent
        Rectangle {
            SplitView.preferredWidth: 250
            color: "#101014"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 12
                Label { text: "THE WEB"; color: "#a30f2d"; font.pixelSize: 28; font.bold: true }
                Repeater {
                    model: ["Today", "Anchors", "Threads", "Personal Knowledge Web", "Research Web", "Approvals", "Kali Bay"]
                    delegate: Button { required property string modelData; text: modelData; Layout.fillWidth: true }
                }
                Item { Layout.fillHeight: true }
                Label { text: "YOUR LIFE. ONE WEB."; color: "#817a73"; wrapMode: Text.WordWrap }
            }
        }
        Rectangle {
            color: "#09090b"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 34; spacing: 20
                Label { text: "Good to see you, Cory."; color: "#f3eadf"; font.pixelSize: 34; font.bold: true }
                Label { text: "Webbie is running as part of your KDE session—not squatting in a browser tab."; color: "#bbb3aa"; font.pixelSize: 17; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Frame {
                    Layout.fillWidth: true; Layout.preferredHeight: 180
                    background: Rectangle { color: "#15151a"; radius: 12; border.color: "#361019" }
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 20
                        Label { text: "WEBBIE"; color: "#a30f2d"; font.pixelSize: 22; font.bold: true }
                        Label { text: root.statusText; color: "#f3eadf"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        Label { text: "Wake phrases: Hey Webbie · Webbie · Hey Web · Web"; color: "#9c958e" }
                    }
                }
                Frame {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    background: Rectangle { color: "#111115"; radius: 12; border.color: "#292930" }
                    Label { anchors.centerIn: parent; text: "Native Anchor and Thread views connect here through Spider Core's local API."; color: "#8f8881"; wrapMode: Text.WordWrap }
                }
            }
        }
    }
}

