from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox

# Absolute imports are required because PyInstaller runs this file as the
# top-level `main` script rather than as `fronda.main`.
from fronda.controller import AppController
from fronda.paths import application_dir, resource_path


def _launch_log_path() -> Path:
    """A visible diagnostic location for windowed macOS launches."""
    root = Path.home() / "Library" / "Logs" / "FRONDA Cover Maker" if sys.platform == "darwin" else Path.home() / "AppData" / "Local" / "FRONDA" / "CoverMaker"
    root.mkdir(parents=True, exist_ok=True)
    return root / "launch.log"


def _write_launch_log(message: str) -> None:
    try:
        with _launch_log_path().open("a", encoding="utf-8") as log:
            log.write(message.rstrip() + "\n")
    except OSError:
        pass


def _qt_message_handler(kind: QtMsgType, _context: object, message: str) -> None:
    # QML import errors otherwise disappear when a PyInstaller macOS app is
    # launched by Finder instead of Terminal.
    label = {QtMsgType.QtDebugMsg: "DEBUG", QtMsgType.QtInfoMsg: "INFO", QtMsgType.QtWarningMsg: "WARNING", QtMsgType.QtCriticalMsg: "CRITICAL", QtMsgType.QtFatalMsg: "FATAL"}.get(kind, "QT")
    _write_launch_log(f"{label}: {message}")


def _show_startup_error(detail: str) -> None:
    _write_launch_log(detail)
    path = _launch_log_path()
    try:
        QMessageBox.critical(None, "FRONDA Cover Maker", f"Не удалось открыть приложение.\n\nПодробности сохранены в:\n{path}")
    except Exception:
        pass


def main() -> int:
    _write_launch_log("\n=== FRONDA launch ===")
    qInstallMessageHandler(_qt_message_handler)
    try:
        QCoreApplication.setOrganizationName("FRONDA")
        QCoreApplication.setApplicationName("CoverMaker")
        QQuickStyle.setStyle("Basic")
        app = QApplication(sys.argv)
        application_icon = QIcon(str(resource_path("images", "fronda.ico")))
        app.setWindowIcon(application_icon)
        engine = QQmlApplicationEngine()
        controller = AppController()
        engine.rootContext().setContextProperty("appController", controller)
        qml = application_dir() / "qml" / "Main.qml"
        _write_launch_log(f"QML: {qml}")
        engine.load(QUrl.fromLocalFile(str(qml)))
        if not engine.rootObjects():
            _show_startup_error("QML engine did not create a root window. See Qt messages above.")
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
    except Exception:
        _show_startup_error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
