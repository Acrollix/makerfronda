from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

# Absolute imports are required because PyInstaller runs this file as the
# top-level `main` script rather than as `fronda.main`.
from fronda.controller import AppController
from fronda.paths import application_dir, resource_path


def main() -> int:
    QCoreApplication.setOrganizationName("FRONDA")
    QCoreApplication.setApplicationName("CoverMaker")
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    application_icon = QIcon(str(resource_path("images", "fronda.ico")))
    app.setWindowIcon(application_icon)
    engine = QQmlApplicationEngine()
    controller = AppController()
    engine.rootContext().setContextProperty("appController", controller)
    qml = application_dir() / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        return 1
    # Qt may restore a position on a disconnected display. Always place the
    # first window inside the current primary work area.
    window = engine.rootObjects()[0]
    # Explicitly assign the icon to the native QQuickWindow as well. This
    # avoids Windows showing the generic Qt/launcher glyph in the taskbar.
    window.setIcon(application_icon)
    screen = app.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        # On a 4K TV at 300% Windows exposes roughly 1280×720 logical
        # pixels. The desktop default (1440×900) would otherwise open beyond
        # the work area and put the native close button outside the screen.
        # Maximise instead of allowing a partially visible window.
        if window.width() > available.width() or window.height() > available.height():
            window.showMaximized()
        else:
            x = available.x() + max(0, (available.width() - window.width()) // 2)
            y = available.y() + max(0, (available.height() - window.height()) // 2)
            window.setPosition(x, y)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
