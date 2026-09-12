import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    property bool online: false
    property string detail: "Starting"
    toolTipMainText: "Webbie"
    toolTipSubText: detail

    function poll() {
        const request = new XMLHttpRequest()
        request.open("GET", "http://127.0.0.1:8765/api/resident")
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) return
            online = request.status === 200
            detail = online ? "Resident in KDE" : "Waiting for Spider Core"
        }
        request.send()
    }

    compactRepresentation: PlasmaComponents.Label {
        text: root.online ? "🕷" : "○"
        color: root.online ? "#a30f2d" : "#8a8a8a"
        font.pixelSize: 22
    }
    fullRepresentation: PlasmaComponents.Label { text: "Webbie: " + root.detail }
    Component.onCompleted: poll()
    Timer { interval: 5000; running: true; repeat: true; onTriggered: root.poll() }
}
