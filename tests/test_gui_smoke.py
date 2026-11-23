from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtTest import QTest
    from PyQt6.QtGui import QKeySequence
    from PyQt6.QtWidgets import QApplication

    from aw2724dm_control.config import ConfigStore
    from aw2724dm_control.ddc import InputSource, Monitor
    from aw2724dm_control.gui import MainWindow, ShortcutDialog, gnome_binding

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

    def test_window_loads_detected_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigStore(Path(directory) / "config.json")
            window = MainWindow(config, FakeDDC())
            QTest.qWait(300)
            self.assertEqual(window.monitor_combo.count(), 1)
            self.assertEqual(window.toggle_first.count(), 2)
            self.assertTrue(window.brightness.isEnabled())
            self.assertEqual(window.brightness.value(), 70)
            window.really_quit = True
            window.tray.hide()
            window.close()

    def test_shortcut_dialog_allows_selecting_two_inputs(self) -> None:
        inputs = [InputSource(0x0F, "DisplayPort-1"), InputSource(0x11, "HDMI-1")]
        dialog = ShortcutDialog(inputs, {}, None)
        self.assertEqual(dialog.first_input.currentData(), 0x0F)
        self.assertEqual(dialog.second_input.currentData(), 0x11)
        self.assertEqual(gnome_binding(QKeySequence("Ctrl+Alt+M")), "<Ctrl><Alt>m")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
