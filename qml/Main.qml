import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: root
    width: 1440
    height: 900
    minimumWidth: 800
    minimumHeight: 600
    visible: true
    title: "FRONDA Cover Maker"
    color: "#0D0B0A"
    // desktopAvailable* is logical pixels. Convert it back to physical pixels
    // before using pixel density, otherwise a 4K TV at 300% is misidentified
    // as a small monitor.
    property real physicalDiagonal: Screen.pixelDensity > 0
                                  ? Math.sqrt(Math.pow(Screen.desktopAvailableWidth * Screen.devicePixelRatio / Screen.pixelDensity, 2) + Math.pow(Screen.desktopAvailableHeight * Screen.devicePixelRatio / Screen.pixelDensity, 2)) / 25.4
                                  : 0
    property var layout: appController.layoutFor(width, height, contentItem.width, contentItem.height, visibility === Window.Maximized, visibility === Window.FullScreen, physicalDiagonal, Screen.devicePixelRatio)
    property bool compact: layout.layout_mode === "Compact"
    property bool medium: layout.layout_mode === "Medium"
    property bool reduced: appController.reduceMotion
    property color gold: "#D7A64A"
    property color bronze: "#A66A2C"
    property color red: "#E21B23"
    property color parchment: "#D8C6A0"
    property string toastText: ""
    property bool pageEntered: false
    function openTemplateDialog() { templateDialog.open() }
    function openExportDialog() { exportDialog.open() }
    function openImageDialog() { imageDialog.open() }
    function updateScreenProfile() {
        appController.setScreenKey(Screen.name + "|" + Screen.desktopAvailableWidth + "x" + Screen.desktopAvailableHeight + "|" + Screen.devicePixelRatio)
    }
    Component.onCompleted: { pageEntered = true; updateScreenProfile() }
    onScreenChanged: updateScreenProfile()

    FileDialog {
        id: templateDialog
        title: "Выберите PSD-шаблон"
        nameFilters: ["PSD-файлы (*.psd)"]
        onAccepted: appController.setTemplatePath(selectedFile)
    }
    FolderDialog {
        id: exportDialog
        title: "Выберите папку экспорта"
        onAccepted: appController.setExportPath(selectedFolder)
    }
    FileDialog {
        id: imageDialog
        title: "Выберите изображение для обложки"
        nameFilters: ["Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"]
        onAccepted: appController.setImagePath(selectedFile)
    }
    background: Rectangle {
        color: root.color
        Rectangle {
            anchors.fill: parent
            opacity: 0.35
            gradient: Gradient {
                GradientStop { position: 0
color: "#21130d" }
                GradientStop { position: 0.52
color: "#0D0B0A" }
                GradientStop { position: 1
color: "#160e0a" }
            }
        }
        Image {
            source: "../resources/images/ornament_cc0.svg"
            anchors.left: parent.left
            anchors.top: parent.top
            width: 150
            height: 150
            opacity: 0.055
        }
        Rectangle {
            width: parent.width
            height: 2
            y: 0
            color: root.gold
            opacity: root.reduced ? 0.2 : 0.75
            SequentialAnimation on x {
                running: !root.reduced
                loops: Animation.Infinite
                NumberAnimation { from: -root.width; to: root.width; duration: 4200; easing.type: Easing.InOutSine }
            }
        }
        Image {
            source: "../resources/images/ornament_cc0.svg"
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: 170
            height: 170
            opacity: 0.055
            rotation: 180
        }
    }
    header: ToolBar {
        height: 72 * root.layout.ui_scale
        background: Rectangle {
            color: "#171310"
            border.color: "#5A3B1D"
            border.width: 1
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            spacing: 16
            Image {
                source: "../resources/images/fronda_logo.png"
                Layout.preferredWidth: 180
                Layout.preferredHeight: 46
                fillMode: Image.PreserveAspectFit
            }
            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                Layout.topMargin: 16
                Layout.bottomMargin: 16
                color: root.bronze
            }
            Label {
                text: "COVER MAKER"
                color: root.parchment
                font.pixelSize: 18 * root.layout.ui_scale
                font.letterSpacing: 2
                Layout.fillWidth: true
            }
            ComboBox {
                model: ["Auto", "Monitor", "Television", "CompactWindow"]
                currentIndex: model.indexOf(appController.displayProfile)
                onActivated: appController.setDisplayProfile(currentText)
                Layout.preferredWidth: 175
            }
            ToolButton { text: "⚙"
onClicked: settingsPopup.open() }
        }
    }
    Popup {
        id: settingsPopup
        modal: true
        anchors.centerIn: Overlay.overlay
        width: 340
        padding: 22
        background: Rectangle { color: "#211A14"
border.color: root.bronze }
        contentItem: ColumnLayout {
            spacing: 16
            Label { text: "Настройки движения"
color: root.parchment
font.bold: true }
            Switch { text: "Уменьшить анимации"
checked: appController.reduceMotion
onToggled: appController.setReduceMotion(checked) }
            Label { text: "Остаются только короткие плавные переходы."
color: "#A99C89"
wrapMode: Text.Wrap
Layout.fillWidth: true }
        }
    }
    component FrondaButton: Button {
        id: button
        property bool primary: false
        implicitHeight: root.layout.touch_target
        font.pixelSize: 14 * root.layout.ui_scale
        font.bold: primary
        contentItem: Label {
            text: button.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: button.primary ? "#FFF6E5" : root.parchment
            font: button.font
        }
        background: Rectangle {
            radius: 2
            color: button.primary ? root.red : "#2B1B12"
            border.color: button.primary ? "#FF7A69" : root.bronze
            border.width: 1
            Behavior on color { ColorAnimation { duration: root.reduced ? 90 : 150 } }
        }
        scale: pressed ? 0.985 : 1
        Behavior on scale { NumberAnimation { duration: root.reduced ? 80 : 140
easing.type: Easing.OutCubic } }
    }
    component SectionLabel: Label {
        color: root.gold
        font.pixelSize: 12 * root.layout.ui_scale
        font.letterSpacing: 1.2
        topPadding: 8
    }
    component ModeButton: Button {
        id: modeButton
        property bool active: false
        implicitHeight: 38
        font.pixelSize: 12 * root.layout.ui_scale
        contentItem: Label { text: modeButton.text; color: modeButton.active ? "#FFF6E5" : root.parchment; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font: modeButton.font }
        background: Rectangle {
            color: modeButton.active ? root.red : "#2B1B12"
            border.color: modeButton.active ? "#FF7A69" : root.bronze
            border.width: 1
            Behavior on color { ColorAnimation { duration: root.reduced ? 70 : 180 } }
        }
        scale: pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }
    component ControlsPanel: ScrollView {
        id: controlsScroll
        clip: true
        contentWidth: availableWidth
        contentHeight: controlsColumn.implicitHeight + 40
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        ColumnLayout {
            id: controlsColumn
            x: 20
            width: Math.max(0, parent.width - 40)
            spacing: root.layout.base_spacing
            y: 20
            Label { text: "МАСТЕРСКАЯ ОБЛОЖЕК"
color: root.gold
font.letterSpacing: 2 }
            Label { text: appController.status
color: appController.readyToExport ? "#9DA86B" : "#C6B8A2"
wrapMode: Text.Wrap
Layout.fillWidth: true }
            SectionLabel { text: "Источник шаблона" }
            RowLayout {
                Layout.fillWidth: true
                ModeButton { text: "Встроенный"; active: appController.templateMode === "Builtin"; Layout.fillWidth: true; onClicked: appController.setTemplateMode("Builtin") }
                ModeButton { text: "Другой PSD"; active: appController.templateMode === "Custom"; Layout.fillWidth: true; onClicked: appController.setTemplateMode("Custom") }
            }
            Label {
                visible: appController.templateMode === "Builtin"
                text: "FRONDA Prevyu · 1920 × 1080 · уже включён в программу"
                color: "#9DA86B"
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            SectionLabel { text: "Другой PSD-шаблон"; visible: appController.templateMode === "Custom" }
            RowLayout {
                visible: appController.templateMode === "Custom"
                Layout.fillWidth: true
                TextField { text: appController.templatePath
placeholderText: "Путь к Prevyu.psd"
readOnly: true
Layout.fillWidth: true }
                FrondaButton { text: "Выбрать"
onClicked: root.openTemplateDialog() }
            }
            FrondaButton { visible: appController.templateMode === "Custom"; text: "Проверить шаблон"
Layout.fillWidth: true
onClicked: appController.analyzeTemplate() }
            SectionLabel { text: "Название релиза" }
            TextArea { text: appController.title
placeholderText: "Введите название"
wrapMode: TextEdit.NoWrap
Layout.fillWidth: true
Layout.preferredHeight: 74
leftPadding: 10
rightPadding: 10
// For a one-line title keep the typing line centred vertically in the
// control; once it becomes multi-line the usual top padding is retained.
topPadding: text.indexOf("\n") === -1 ? Math.max(10, (height - font.pixelSize) / 2) : 10
onTextChanged: appController.setTitle(text) }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Выравнивание"; color: "#A99C89" }
                ComboBox {
                    model: ["Слева", "По центру"]
                    currentIndex: appController.titleAlignment === "center" ? 1 : 0
                    Layout.fillWidth: true
                    onActivated: appController.setTitleAlignment(currentIndex === 1 ? "center" : "left")
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Тип выпуска"; color: "#A99C89" }
                ModeButton { text: "Серии"; active: appController.releaseType === "Episode"; Layout.fillWidth: true; onClicked: appController.setReleaseType("Episode") }
                ModeButton { text: "Фильм"; active: appController.releaseType === "Film"; Layout.fillWidth: true; onClicked: appController.setReleaseType("Film") }
            }
            RowLayout {
                Layout.fillWidth: true
                visible: appController.releaseType === "Episode"
                Label { text: "Обложки"; color: "#A99C89" }
                ModeButton { text: "Одна за всех"; active: appController.artworkMode === "Shared"; Layout.fillWidth: true; onClicked: appController.setArtworkMode("Shared") }
                ModeButton { text: "Разная для каждой"; active: appController.artworkMode === "PerEpisode"; Layout.fillWidth: true; onClicked: appController.setArtworkMode("PerEpisode") }
            }
            Label { text: "Символов: " + appController.title.length
color: "#A99C89" }
            SectionLabel { text: "Серии"; visible: appController.releaseType === "Episode" }
            RowLayout {
                visible: appController.releaseType === "Episode"
                Layout.fillWidth: true
                SpinBox { from: 0
to: 9999
value: appController.startEpisode
onValueModified: appController.setStartEpisode(value)
Layout.fillWidth: true }
                Label { text: "до"
color: root.parchment }
                SpinBox { from: appController.startEpisode
to: 9999
value: appController.endEpisode
onValueModified: appController.setEndEpisode(value)
Layout.fillWidth: true }
            }
            Label {
                visible: appController.releaseType === "Episode"
                text: (appController.releaseType === "Film" ? "Обложка фильма" : "Настраиваем обложку серии " + appController.previewEpisode) + "  •  к экспорту: " + (appController.endEpisode - appController.startEpisode + 1)
                color: root.parchment
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            SpinBox {
                visible: appController.releaseType === "Episode" && appController.artworkMode === "PerEpisode"
                from: appController.startEpisode
                to: appController.endEpisode
                value: appController.previewEpisode
                Layout.fillWidth: true
                onValueModified: appController.setPreviewEpisode(value)
            }
            SectionLabel { text: "Изображение" }
            RowLayout {
                Layout.fillWidth: true
                FrondaButton { text: "Выбрать файл"; Layout.fillWidth: true; onClicked: root.openImageDialog() }
            FrondaButton {
                text: appController.releaseType === "Film"
                      ? (appController.hasImage ? "Заменить обложку фильма" : "Из буфера для фильма")
                      : appController.artworkMode === "Shared"
                        ? (appController.hasImage ? "Заменить общую" : "Из буфера для всех")
                        : (appController.hasImage ? "Заменить для серии " + appController.previewEpisode : "Из буфера для серии " + appController.previewEpisode)
                Layout.fillWidth: true
                onClicked: appController.pasteImage()
            }
            }
            SectionLabel { text: "Экспорт" }
            RowLayout {
                Layout.fillWidth: true
                TextField { text: appController.exportPath
placeholderText: "Папка экспорта"
readOnly: true
Layout.fillWidth: true }
                FrondaButton { text: "Папка"
onClicked: root.openExportDialog() }
            }
            FrondaButton { text: "Создать обложки"
primary: true
enabled: !appController.exporting
Layout.fillWidth: true
onClicked: appController.exportCovers() }
            ColumnLayout {
                visible: appController.exporting
                Layout.fillWidth: true
                spacing: 6
                Label { text: "Экспорт: " + appController.exportProgress + " / " + appController.exportTotal; color: root.parchment }
                ProgressBar { from: 0; to: Math.max(1, appController.exportTotal); value: appController.exportProgress; Layout.fillWidth: true }
                FrondaButton { text: "Отменить экспорт"; Layout.fillWidth: true; onClicked: appController.cancelExport() }
            }
        }
    }
    component PreviewPanel: Item {
        opacity: root.pageEntered ? 1 : 0
        scale: root.pageEntered ? 1 : 0.985
        Behavior on opacity { NumberAnimation { duration: root.reduced ? 100 : 420; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: root.reduced ? 100 : 520; easing.type: Easing.OutCubic } }
        Rectangle { anchors.fill: parent
color: "#171310"
border.color: "#5A3B1D"
border.width: 1 }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                Label { text: "ПРЕДПРОСМОТР"
color: root.gold
font.letterSpacing: 2
Layout.fillWidth: true }
                Label { text: "1920 × 1080"
color: "#A99C89" }
            }
            Rectangle {
                color: "#0A0908"
                border.color: root.bronze
                border.width: 1
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 240
                Image { anchors.centerIn: parent
width: Math.min(parent.width - 20, parent.height * 16 / 9)
height: width * 9 / 16
source: appController.previewUrl
fillMode: Image.PreserveAspectFit
asynchronous: true
visible: source !== "" }
                Column {
                    anchors.centerIn: parent
                    visible: appController.previewUrl === ""
                    Label { text: "✦"
color: root.bronze
font.pixelSize: 38
anchors.horizontalCenter: parent.horizontalCenter }
                    Label { text: "Предпросмотр появится после\nпроверки шаблона и вставки изображения"
color: "#A99C89"
horizontalAlignment: Text.AlignHCenter }
                }
                SequentialAnimation on opacity {
                    running: !root.reduced && appController.previewUrl === ""
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.42; to: 1; duration: 1050; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1; to: 0.42; duration: 1050; easing.type: Easing.InOutSine }
                }
            }
        }
    }
    Drawer {
        id: compactDrawer
        width: Math.min(390, root.width * 0.9)
        height: root.height
        edge: Qt.LeftEdge
        background: Rectangle { color: "#171310"
border.color: root.bronze }
        Loader { anchors.fill: parent
sourceComponent: controlsComponent }
    }
    Component { id: controlsComponent
ControlsPanel {} }
    Component { id: previewComponent
PreviewPanel {} }
    Item {
        anchors.fill: parent
        RowLayout {
            anchors.fill: parent
            anchors.margins: root.layout.safe_margin
            spacing: root.layout.base_spacing
            visible: !root.compact && !root.medium
            Loader { Layout.preferredWidth: root.layout.layout_mode === "Wide" ? 390 : 340
Layout.fillHeight: true
sourceComponent: controlsComponent }
            Loader { Layout.fillWidth: true
Layout.fillHeight: true
sourceComponent: previewComponent }
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.layout.safe_margin
            spacing: root.layout.base_spacing
            visible: root.compact || root.medium
            RowLayout {
                Layout.fillWidth: true
                visible: root.compact
                FrondaButton { text: "☰ Параметры"
onClicked: compactDrawer.open() }
                Item { Layout.fillWidth: true }
                Label { text: appController.status
color: root.parchment
elide: Text.ElideRight
Layout.maximumWidth: 300 }
            }
            Loader { Layout.fillWidth: true
Layout.fillHeight: true
sourceComponent: previewComponent }
            Loader { visible: root.medium
Layout.fillWidth: true
Layout.preferredHeight: 460
sourceComponent: controlsComponent }
        }
    }
    Popup {
        id: toastPopup
        parent: Overlay.overlay
        x: Math.max(16, (parent.width - width) / 2)
        y: 88
        width: 340
        height: 76
        padding: 14
        property string toastKind: "success"
        background: Rectangle { color: toastPopup.toastKind === "error" ? "#4A1512" : "#25301A"
border.color: toastPopup.toastKind === "error" ? root.red : root.gold }
        contentItem: RowLayout {
            Label { text: toastPopup.toastKind === "error" ? "!" : "✓"
color: root.gold
font.pixelSize: 24 }
            Label { text: root.toastText
color: "#FFF6E5"
wrapMode: Text.Wrap
Layout.fillWidth: true }
        }
        Timer { id: toastTimer
interval: 3200
onTriggered: toastPopup.close() }
    }
    Connections {
        target: appController
        function onToast(message, kind) {
            root.toastText = message
            toastPopup.toastKind = kind
            toastPopup.open()
            toastTimer.restart()
        }
        function onErrorOccurred(message) {
            errorText.text = message
            errorPopup.open()
        }
    }
    Popup {
        id: errorPopup
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 680)
        height: Math.min(root.height - 48, 410)
        padding: 22
        background: Rectangle { color: "#25110F"; border.color: root.red; border.width: 1 }
        contentItem: ColumnLayout {
            spacing: 14
            Label { text: "ОШИБКА"; color: "#FF8075"; font.bold: true; font.letterSpacing: 1.5 }
            ScrollView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                TextArea { id: errorText; readOnly: true; wrapMode: TextEdit.Wrap; color: "#FFF0E8"; background: null }
            }
            RowLayout {
                Layout.fillWidth: true
                FrondaButton { text: "Копировать текст"; onClicked: appController.copyLastError() }
                Item { Layout.fillWidth: true }
                FrondaButton { text: "Закрыть"; primary: true; onClicked: errorPopup.close() }
            }
        }
    }
}

