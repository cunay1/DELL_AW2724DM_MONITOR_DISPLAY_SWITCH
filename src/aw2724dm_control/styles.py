from __future__ import annotations

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication


def apply_application_style(application: QApplication) -> None:
    dark = application.palette().color(QPalette.ColorRole.Window).lightness() < 128
    border = "#475569" if dark else "#cbd5e1"
    surface = "#1e293b" if dark else "#f8fafc"
    text = "#f8fafc" if dark else "#0f172a"
    muted = "#334155" if dark else "#e2e8f0"
    application.setStyleSheet(
        f"""
        QMainWindow {{
            background: {surface};
        }}
        QGroupBox {{
            border: 1px solid {border};
            border-radius: 10px;
            margin-top: 14px;
            padding-top: 12px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            color: #3b82f6;
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }}
        QPushButton {{
            background-color: #2563eb;
            color: white;
            border: none;
            border-radius: 7px;
            padding: 8px 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{ background-color: #1d4ed8; }}
        QPushButton:pressed {{ background-color: #1e40af; }}
        QPushButton:disabled {{ background-color: {muted}; color: #94a3b8; }}
        QPushButton#secondaryButton {{ background-color: #0891b2; }}
        QPushButton#secondaryButton:hover {{ background-color: #0e7490; }}
        QPushButton#toggleButton {{ background-color: #7c3aed; }}
        QPushButton#toggleButton:hover {{ background-color: #6d28d9; }}
        QPushButton#shortcutButton {{ background-color: #9333ea; }}
        QPushButton#shortcutButton:hover {{ background-color: #7e22ce; }}
        QPushButton#updateButton {{ background-color: #059669; }}
        QPushButton#updateButton:hover {{ background-color: #047857; }}
        QPushButton#trayButton {{ background-color: #475569; }}
        QPushButton#trayButton:hover {{ background-color: #334155; }}
        QPushButton[inputSource="true"] {{
            background-color: #0f766e;
            min-height: 42px;
        }}
        QPushButton[inputSource="true"]:hover {{ background-color: #115e59; }}
        QComboBox, QLineEdit, QKeySequenceEdit, QTableWidget {{
            border: 1px solid {border};
            border-radius: 6px;
            padding: 5px;
            background-color: {surface};
            color: {text};
            selection-background-color: #2563eb;
            selection-color: white;
        }}
        QComboBox:focus, QLineEdit:focus, QKeySequenceEdit:focus {{
            border: 2px solid #3b82f6;
        }}
        QMenuBar {{
            background-color: {surface};
            color: {text};
            padding: 3px;
        }}
        QMenuBar::item {{ padding: 6px 10px; border-radius: 5px; }}
        QMenuBar::item:selected {{ background-color: #2563eb; color: white; }}
        QMenu {{ background-color: {surface}; color: {text}; border: 1px solid {border}; }}
        QMenu::item {{ padding: 7px 28px 7px 12px; }}
        QMenu::item:selected {{ background-color: #2563eb; color: white; }}
        QMenu::indicator:checked {{ background-color: #22c55e; border-radius: 4px; }}
        QSlider::groove:horizontal {{ height: 6px; background: {muted}; border-radius: 3px; }}
        QSlider::sub-page:horizontal {{ background: #3b82f6; border-radius: 3px; }}
        QSlider::handle:horizontal {{
            background: #2563eb;
            width: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }}
        QProgressBar {{
            border: 1px solid {border};
            border-radius: 7px;
            text-align: center;
            min-height: 18px;
            background: {muted};
            color: {text};
        }}
        QProgressBar::chunk {{ background-color: #22c55e; border-radius: 6px; }}
        QStatusBar {{ border-top: 1px solid {border}; color: {text}; }}
        """
    )
