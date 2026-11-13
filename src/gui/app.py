from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow

APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #18181B;
    color: #F4F4F5;
    font-size: 13px;
}
QToolBar {
    background-color: #27272A;
    border-bottom: 1px solid #3F3F46;
    spacing: 6px;
    padding: 4px 8px;
}
QToolButton, QPushButton {
    background-color: #27272A;
    border: 1px solid #3F3F46;
    border-radius: 5px;
    padding: 5px 10px;
}
QToolButton:hover, QPushButton:hover {
    background-color: #3F3F46;
}
QToolButton:checked, QPushButton:checked {
    background-color: #0284C7;
    border-color: #38BDF8;
    color: #FFFFFF;
}
QToolButton:disabled, QPushButton:disabled {
    color: #71717A;
    background-color: #1F1F23;
}
QGroupBox {
    border: 1px solid #3F3F46;
    border-radius: 6px;
    margin-top: 10px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #38BDF8;
}
QComboBox {
    background-color: #27272A;
    border: 1px solid #3F3F46;
    border-radius: 4px;
    padding: 4px 8px;
}
QScrollArea {
    border: none;
}
QStatusBar {
    background-color: #27272A;
    border-top: 1px solid #3F3F46;
    color: #D4D4D8;
}
"""


def run_gui(argv: Sequence[str] | None = None) -> int:
    """Create the Qt application, show MainWindow, and enter the event loop."""
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(list(sys.argv if argv is None else argv))
        app.setApplicationName("py-ico")
        app.setStyle("Fusion")
        app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    if owns_app:
        return app.exec()
    return 0

