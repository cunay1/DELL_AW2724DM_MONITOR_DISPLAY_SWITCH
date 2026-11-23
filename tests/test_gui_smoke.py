from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtTest import QTest
    from PyQt6.QtGui import QKeySequence
    from PyQt6.QtWidgets import QApplication

    from aw2724dm_control.config import ConfigStore
    from aw2724dm_control.ddc import InputSource, Monitor
    from aw2724dm_control.gui import MainWindow, ShortcutDialog, gnome_binding
    from aw2724dm_control.i18n import get_language, set_language, tr
    from aw2724dm_control.main import run_gui
    from aw2724dm_control.styles import apply_application_style
    from aw2724dm_control import __version__

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class FakeDDC:
    def detect(self) -> list[Monitor]:
        return [
            Monitor(
                display=1,
                model="AW2724DM",
                connector="card1-DP-1",
                inputs=[InputSource(0x0F, "DisplayPort-1"), InputSource(0x11, "HDMI-1")],
            )
        ]

    def get_vcp(self, display: int, feature: int) -> int:
        return 70 if feature == 0x10 else 60

    def set_vcp(self, display: int, feature: int, value: int) -> None:
        return None

    def set_input(self, display: int, value: int) -> None:
        return None

    def toggle(self, display: int, first: int, second: int) -> int:
        return second


@unittest.skipUnless(PYQT_AVAILABLE, "PyQt6 kurulu değil")
class GUISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        set_language("en")

    def test_window_loads_detected_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigStore(Path(directory) / "config.json")
            self.assertEqual(config.data["language"], "en")
            window = MainWindow(config, FakeDDC())
            QTest.qWait(300)
            self.assertEqual(window.monitor_combo.count(), 1)
            self.assertEqual(window.toggle_first.count(), 2)
            self.assertTrue(window.brightness.isEnabled())
            self.assertEqual(window.brightness.value(), 70)
            self.assertEqual(window.update_button.objectName(), "updateButton")
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_colored_theme_is_applied(self) -> None:
        apply_application_style(self.application)
        stylesheet = self.application.styleSheet()
        self.assertIn("QPushButton#updateButton", stylesheet)
        self.assertIn("QMenuBar::item:selected", stylesheet)
        self.assertIn("QProgressBar::chunk", stylesheet)

    def test_shortcut_dialog_allows_selecting_two_inputs(self) -> None:
        inputs = [InputSource(0x0F, "DisplayPort-1"), InputSource(0x11, "HDMI-1")]
        dialog = ShortcutDialog(inputs, {}, None)
        self.assertEqual(dialog.first_input.currentData(), 0x0F)
        self.assertEqual(dialog.second_input.currentData(), 0x11)
        self.assertEqual(gnome_binding(QKeySequence("Ctrl+Alt+M")), "<Ctrl><Alt>m")
        dialog.close()

    def test_gui_startup_accepts_wayland_without_x11_display(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigStore(Path(directory) / "config.json")
            environment = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}
            with (
                patch.dict(os.environ, environment, clear=True),
                patch("PyQt6.QtWidgets.QApplication") as application_class,
                patch("aw2724dm_control.styles.apply_application_style"),
                patch("aw2724dm_control.gui.create_window") as create_window,
            ):
                application_class.return_value.exec.return_value = 0
                self.assertEqual(run_gui(config, FakeDDC()), 0)
                create_window.return_value.show.assert_called_once_with()

    def test_about_dialog_contains_application_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(ConfigStore(Path(directory) / "config.json"), FakeDDC())
            with patch("aw2724dm_control.gui.QMessageBox.about") as about:
                window.show_about()
                self.assertIn(f"Version {__version__}", about.call_args.args[2])
            self.assertEqual(window.version_label.text(), f"Version {__version__}")
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_language_choice_is_saved_and_restarts_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigStore(Path(directory) / "config.json")
            window = MainWindow(config, FakeDDC())
            with (
                patch("aw2724dm_control.gui.QMessageBox.information"),
                patch("aw2724dm_control.gui.QProcess.startDetached", return_value=(True, 1234)),
                patch.object(window, "quit_application") as quit_application,
            ):
                window.change_language("tr")
            self.assertEqual(get_language(), "tr")
            self.assertEqual(ConfigStore(config.path).data["language"], "tr")
            self.assertEqual(tr("refresh"), "Yenile")
            quit_application.assert_called_once_with()
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_update_success_dialog_does_not_include_installer_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(ConfigStore(Path(directory) / "config.json"), FakeDDC())
            oversized_output = "installer output\n" * 1000
            with (
                patch("aw2724dm_control.gui.QMessageBox.information") as information,
                patch.object(window, "restart_application") as restart_application,
            ):
                window._update_applied(oversized_output)
                QTest.qWait(10)
            message = information.call_args.args[2]
            self.assertNotIn("installer output", message)
            self.assertLess(len(message), 300)
            restart_application.assert_called_once_with()
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_settings_contains_flagged_language_choices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(ConfigStore(Path(directory) / "config.json"), FakeDDC())
            settings_action = next(
                action for action in window.menuBar().actions() if action.text() == "Settings"
            )
            language_action = next(
                action for action in settings_action.menu().actions() if action.menu() is not None
            )
            labels = [action.text() for action in language_action.menu().actions()]
            self.assertIn("🇬🇧 English", labels)
            self.assertIn("🇹🇷 Türkçe", labels)
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_close_without_tray_setting_requests_real_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigStore(Path(directory) / "config.json")
            config.data["close_to_tray"] = False
            window = MainWindow(config, FakeDDC())
            with patch.object(window, "quit_application") as quit_application:
                window.close()
                QTest.qWait(10)
            quit_application.assert_called_once_with()
            window.really_quit = True
            window.tray.hide()

    def test_restart_is_queued_before_quitting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(ConfigStore(Path(directory) / "config.json"), FakeDDC())
            with patch.object(window, "quit_application") as quit_application:
                window.restart_application()
            self.assertIs(QApplication.instance().property("restart_requested"), True)
            quit_application.assert_called_once_with()
            QApplication.instance().setProperty("restart_requested", False)
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_update_uses_stage_progress_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(ConfigStore(Path(directory) / "config.json"), FakeDDC())
            with patch.object(window.pool, "start") as start:
                window._start_update("9.8.7")
            self.assertIsNotNone(window.update_progress_dialog)
            self.assertEqual(window.update_progress_dialog.value(), 2)
            self.assertFalse(window.update_button.isEnabled())
            worker = start.call_args.args[0]
            worker.signals.progress.emit(65, "Installing…")
            self.assertEqual(window.update_progress_dialog.value(), 65)
            self.assertEqual(window.update_progress_dialog.labelText(), "Installing…")
            window._close_update_progress()
            window.really_quit = True
            window.tray.hide()
            window.close()


if __name__ == "__main__":
    unittest.main()
