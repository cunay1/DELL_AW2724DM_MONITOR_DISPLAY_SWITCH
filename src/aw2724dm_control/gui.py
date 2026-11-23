from __future__ import annotations

from functools import partial
from pathlib import Path

from PyQt6.QtCore import QThreadPool, QTimer, Qt
from PyQt6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QKeySequenceEdit,
    QVBoxLayout,
    QWidget,
)

from .config import ConfigStore
from .ddc import DDCUtil, InputSource, Monitor
from .gnome import install_shortcut
from .updater import UpdateInfo, apply_update, check_for_update
from .worker import Worker


def icon_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "aw2724dm-control.svg"


def gnome_binding(sequence: QKeySequence) -> str:
    portable = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    if not portable or "," in portable:
        return ""
    parts = [part for part in portable.split("+") if part]
    if not parts:
        return ""
    modifiers = {"Ctrl": "<Ctrl>", "Alt": "<Alt>", "Shift": "<Shift>", "Meta": "<Super>"}
    key = parts[-1]
    if len(key) == 1:
        key = key.lower()
    return "".join(modifiers.get(part, "") for part in parts[:-1]) + key


class ShortcutDialog(QDialog):
    def __init__(self, inputs: list[InputSource], aliases: dict[str, str], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("GNOME Kısayolu Ata")
        layout = QFormLayout(self)
        self.name = QLineEdit("Monitör girişini değiştir")
        self.action = QComboBox()
        self.action.addItem("İki giriş arasında geçiş", ("toggle", None))
        for source in inputs:
            key = f"0x{source.code:02x}"
            label = aliases.get(key, source.name)
            self.action.addItem(f"Doğrudan: {label} ({key})", ("input", source.code))
        self.first_input = QComboBox()
        self.second_input = QComboBox()
        for source in inputs:
            key = f"0x{source.code:02x}"
            label = aliases.get(key, source.name)
            self.first_input.addItem(f"{label} ({key})", source.code)
            self.second_input.addItem(f"{label} ({key})", source.code)
        if len(inputs) > 1:
            self.second_input.setCurrentIndex(1)
        self.key = QKeySequenceEdit(QKeySequence("Ctrl+Alt+M"))
        self.key.setClearButtonEnabled(True)
        layout.addRow("Ad", self.name)
        layout.addRow("Eylem", self.action)
        layout.addRow("Birinci giriş", self.first_input)
        layout.addRow("İkinci giriş", self.second_input)
        layout.addRow("Kısayol tuşu", self.key)
        hint = QLabel("Kutuyu seçip istediğiniz tuş birleşimine basın; örneğin Ctrl+Alt+M veya Super+F8.")
        hint.setWordWrap(True)
        layout.addRow("", hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.action.currentIndexChanged.connect(self._action_changed)
        self._action_changed()

    def _action_changed(self) -> None:
        is_toggle = self.action.currentData()[0] == "toggle"
        self.first_input.setEnabled(is_toggle)
        self.second_input.setEnabled(is_toggle)


class MainWindow(QMainWindow):
    def __init__(self, config: ConfigStore, ddc: DDCUtil) -> None:
        super().__init__()
        self.config = config
        self.ddc = ddc
        self.pool = QThreadPool.globalInstance()
        self.monitors: list[Monitor] = []
        self.busy_count = 0
        self.really_quit = False
        self._updating_aliases = False

        self.setWindowTitle("Monitör Giriş Kaynağı ve Ayar Yöneticisi")
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(760, 680)
        self.setMinimumSize(650, 560)
        self._build_ui()
        self._build_tray()
        self.refresh_monitors()
        QTimer.singleShot(2500, self._automatic_update_check)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        top = QHBoxLayout()
        self.monitor_combo = QComboBox()
        self.monitor_combo.setMinimumWidth(400)
        self.monitor_combo.currentIndexChanged.connect(self._monitor_changed)
        self.refresh_button = QPushButton("Yenile")
        self.refresh_button.clicked.connect(self.refresh_monitors)
        top.addWidget(QLabel("Monitör:"))
        top.addWidget(self.monitor_combo, 1)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.inputs_group = QGroupBox("Giriş kaynakları")
        self.inputs_layout = QGridLayout(self.inputs_group)
        layout.addWidget(self.inputs_group)

        toggle_group = QGroupBox("Hızlı geçiş")
        toggle_layout = QHBoxLayout(toggle_group)
        self.toggle_first = QComboBox()
        self.toggle_second = QComboBox()
        self.toggle_button = QPushButton("İki Giriş Arasında Geç")
        self.toggle_first.currentIndexChanged.connect(self._save_toggle)
        self.toggle_second.currentIndexChanged.connect(self._save_toggle)
        self.toggle_button.clicked.connect(self.toggle_input)
        toggle_layout.addWidget(self.toggle_first, 1)
        toggle_layout.addWidget(QLabel("↔"))
        toggle_layout.addWidget(self.toggle_second, 1)
        toggle_layout.addWidget(self.toggle_button)
        layout.addWidget(toggle_group)

        controls = QGroupBox("Görüntü ayarları")
        controls_layout = QGridLayout(controls)
        self.brightness = self._make_slider()
        self.contrast = self._make_slider()
        self.brightness_value = QLabel("—")
        self.contrast_value = QLabel("—")
        self.brightness.valueChanged.connect(lambda value: self.brightness_value.setText(str(value)))
        self.contrast.valueChanged.connect(lambda value: self.contrast_value.setText(str(value)))
        self.brightness.sliderReleased.connect(
            lambda: self.set_control(0x10, self.brightness.value(), "Parlaklık")
        )
        self.contrast.sliderReleased.connect(
            lambda: self.set_control(0x12, self.contrast.value(), "Kontrast")
        )
        controls_layout.addWidget(QLabel("Parlaklık"), 0, 0)
        controls_layout.addWidget(self.brightness, 0, 1)
        controls_layout.addWidget(self.brightness_value, 0, 2)
        controls_layout.addWidget(QLabel("Kontrast"), 1, 0)
        controls_layout.addWidget(self.contrast, 1, 1)
        controls_layout.addWidget(self.contrast_value, 1, 2)
        layout.addWidget(controls)

        aliases_group = QGroupBox("Port takma adları")
        aliases_layout = QVBoxLayout(aliases_group)
        self.alias_table = QTableWidget(0, 3)
        self.alias_table.setHorizontalHeaderLabels(["Kod", "Donanım adı", "Takma ad"])
        self.alias_table.horizontalHeader().setStretchLastSection(True)
        self.alias_table.itemChanged.connect(self._alias_changed)
        aliases_layout.addWidget(self.alias_table)
        layout.addWidget(aliases_group, 1)

        bottom = QHBoxLayout()
        self.shortcut_button = QPushButton("GNOME Kısayolu Ata…")
        self.shortcut_button.clicked.connect(self.add_shortcut)
        self.update_button = QPushButton("Güncellemeleri Denetle")
        self.update_button.clicked.connect(lambda: self.check_updates(manual=True))
        self.hide_button = QPushButton("Sistem Tepsisine Gizle")
        self.hide_button.clicked.connect(self.hide)
        bottom.addWidget(self.shortcut_button)
        bottom.addWidget(self.update_button)
        bottom.addStretch()
        bottom.addWidget(self.hide_button)
        layout.addLayout(bottom)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Monitörler aranıyor…")

    @staticmethod
    def _make_slider() -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setEnabled(False)
        return slider

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(str(icon_path())), self)
        self.tray.setToolTip("AW2724DM Monitor Control")
        self.tray_menu = QMenu()
        show_action = QAction("Pencereyi Göster", self)
        show_action.triggered.connect(self.show_from_tray)
        self.tray_menu.addAction(show_action)
        self.tray_inputs_menu = self.tray_menu.addMenu("Giriş Kaynağı")
        self.tray_menu.addSeparator()
        quit_action = QAction("Çıkış", self)
        quit_action.triggered.connect(self.quit_application)
        self.tray_menu.addAction(quit_action)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        self.really_quit = True
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.really_quit or not self.config.data.get("close_to_tray", True):
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "AW2724DM Monitor Control",
            "Uygulama sistem tepsisinde çalışmaya devam ediyor.",
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )

    def _run_async(self, function, *args, success=None, message: str = "İşlem yapılıyor…") -> None:
        self.busy_count += 1
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage(message)
        worker = Worker(function, *args)
        if success is not None:
            worker.signals.succeeded.connect(success)
        worker.signals.failed.connect(self._show_error)
        worker.signals.finished.connect(self._job_finished)
        self.pool.start(worker)

    def _job_finished(self) -> None:
        self.busy_count = max(0, self.busy_count - 1)
        if self.busy_count == 0:
            self.refresh_button.setEnabled(True)
            self.statusBar().showMessage("Hazır", 3000)

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage("Hata", 4000)
        QMessageBox.critical(self, "İşlem Hatası", message)

    def current_monitor(self) -> Monitor | None:
        index = self.monitor_combo.currentIndex()
        return self.monitors[index] if 0 <= index < len(self.monitors) else None

    def refresh_monitors(self) -> None:
        self._run_async(
            self.ddc.detect,
            success=self._monitors_loaded,
            message="Monitörler ve VCP özellikleri taranıyor…",
        )

    def _monitors_loaded(self, monitors: object) -> None:
        self.monitors = list(monitors) if isinstance(monitors, list) else []
        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        for monitor in self.monitors:
            self.monitor_combo.addItem(monitor.title)
        wanted = int(self.config.data.get("selected_display", 1))
        index = next((i for i, item in enumerate(self.monitors) if item.display == wanted), 0)
        if self.monitors:
            self.monitor_combo.setCurrentIndex(index)
        self.monitor_combo.blockSignals(False)
        if not self.monitors:
            self._populate_monitor(None)
            QMessageBox.warning(
                self,
                "Monitör Bulunamadı",
                "ddcutil kullanılabilir bir DDC/CI monitörü algılamadı. Monitör menüsünden DDC/CI özelliğini açın ve i2c grup üyeliğini denetleyin.",
            )
            return
        self._monitor_changed(index)

    def _monitor_changed(self, index: int) -> None:
        monitor = self.current_monitor()
        if monitor is None:
            return
        self.config.data["selected_display"] = monitor.display
        self.config.save()
        self._populate_monitor(monitor)
        self._load_controls(monitor.display)

    def _clear_layout(self, layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _populate_monitor(self, monitor: Monitor | None) -> None:
        self._clear_layout(self.inputs_layout)
        inputs = monitor.inputs if monitor else []
        aliases = self.config.aliases(monitor.display) if monitor else {}
        if not inputs:
            label = QLabel("VCP 0x60 giriş değerleri algılanamadı.")
            self.inputs_layout.addWidget(label, 0, 0)
        for position, source in enumerate(inputs):
            key = f"0x{source.code:02x}"
            text = aliases.get(key, source.name)
            button = QPushButton(f"{text}\n{key}")
            button.setMinimumHeight(55)
            button.clicked.connect(partial(self.set_input, source.code))
            self.inputs_layout.addWidget(button, position // 3, position % 3)
        self._populate_toggle(inputs, aliases, monitor.display if monitor else 0)
        self._populate_aliases(inputs, aliases)
        self._populate_tray(inputs, aliases)

    def _populate_toggle(self, inputs: list[InputSource], aliases: dict[str, str], display: int) -> None:
        self.toggle_first.blockSignals(True)
        self.toggle_second.blockSignals(True)
        self.toggle_first.clear()
        self.toggle_second.clear()
        for source in inputs:
            key = f"0x{source.code:02x}"
            label = aliases.get(key, source.name)
            self.toggle_first.addItem(label, source.code)
            self.toggle_second.addItem(label, source.code)
        saved = self.config.toggle_inputs(display)
        if saved:
            for combo, code in ((self.toggle_first, saved[0]), (self.toggle_second, saved[1])):
                found = combo.findData(code)
                if found >= 0:
                    combo.setCurrentIndex(found)
        elif len(inputs) > 1:
            self.toggle_second.setCurrentIndex(1)
        self.toggle_first.blockSignals(False)
        self.toggle_second.blockSignals(False)
        enabled = len(inputs) >= 2
        self.toggle_first.setEnabled(enabled)
        self.toggle_second.setEnabled(enabled)
        self.toggle_button.setEnabled(enabled)
        if enabled:
            self._save_toggle()

    def _save_toggle(self) -> None:
        monitor = self.current_monitor()
        first = self.toggle_first.currentData()
        second = self.toggle_second.currentData()
        if monitor and first is not None and second is not None and first != second:
            self.config.set_toggle_inputs(monitor.display, int(first), int(second))

    def _populate_aliases(self, inputs: list[InputSource], aliases: dict[str, str]) -> None:
        self._updating_aliases = True
        self.alias_table.setRowCount(len(inputs))
        for row, source in enumerate(inputs):
            key = f"0x{source.code:02x}"
            code_item = QTableWidgetItem(key)
            name_item = QTableWidgetItem(source.name)
            alias_item = QTableWidgetItem(aliases.get(key, ""))
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.alias_table.setItem(row, 0, code_item)
            self.alias_table.setItem(row, 1, name_item)
            self.alias_table.setItem(row, 2, alias_item)
        self.alias_table.resizeColumnsToContents()
        self._updating_aliases = False

    def _alias_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_aliases or item.column() != 2:
            return
        monitor = self.current_monitor()
        code_item = self.alias_table.item(item.row(), 0)
        if monitor and code_item:
            self.config.set_alias(monitor.display, int(code_item.text(), 0), item.text())
            self._populate_monitor(monitor)

    def _populate_tray(self, inputs: list[InputSource], aliases: dict[str, str]) -> None:
        self.tray_inputs_menu.clear()
        for source in inputs:
            key = f"0x{source.code:02x}"
            action = self.tray_inputs_menu.addAction(aliases.get(key, source.name))
            action.triggered.connect(partial(self.set_input, source.code))
        if inputs:
            self.tray_inputs_menu.addSeparator()
            toggle_action = self.tray_inputs_menu.addAction("İki giriş arasında geç")
            toggle_action.triggered.connect(self.toggle_input)
        else:
            action = self.tray_inputs_menu.addAction("Giriş bulunamadı")
            action.setEnabled(False)

    def _load_controls(self, display: int) -> None:
        self.brightness.setEnabled(False)
        self.contrast.setEnabled(False)
        self._run_async(
            self.ddc.get_vcp,
            display,
            0x10,
            success=lambda value: self._control_loaded(self.brightness, int(value)),
            message="Parlaklık okunuyor…",
        )
        self._run_async(
            self.ddc.get_vcp,
            display,
            0x12,
            success=lambda value: self._control_loaded(self.contrast, int(value)),
            message="Kontrast okunuyor…",
        )

    @staticmethod
    def _control_loaded(slider: QSlider, value: int) -> None:
        slider.setValue(max(0, min(100, value)))
        slider.setEnabled(True)

    def set_input(self, code: int) -> None:
        monitor = self.current_monitor()
        if monitor:
            self._run_async(
                self.ddc.set_input,
                monitor.display,
                code,
                success=lambda _: self.tray.showMessage("Monitör girişi değiştirildi", f"Yeni giriş: 0x{code:02x}"),
                message=f"Giriş 0x{code:02x} olarak ayarlanıyor…",
            )

    def toggle_input(self) -> None:
        monitor = self.current_monitor()
        first = self.toggle_first.currentData()
        second = self.toggle_second.currentData()
        if not monitor or first is None or second is None:
            return
        if first == second:
            QMessageBox.warning(self, "Geçersiz Seçim", "Geçiş için iki farklı giriş seçin.")
            return
        self._run_async(
            self.ddc.toggle,
            monitor.display,
            int(first),
            int(second),
            success=lambda code: self.tray.showMessage(
                "Monitör girişi değiştirildi", f"Yeni giriş: 0x{int(code):02x}"
            ),
            message="Giriş kaynağı değiştiriliyor…",
        )

    def set_control(self, feature: int, value: int, name: str) -> None:
        monitor = self.current_monitor()
        if monitor:
            self._run_async(
                self.ddc.set_vcp,
                monitor.display,
                feature,
                value,
                message=f"{name} %{value} olarak ayarlanıyor…",
            )

    def add_shortcut(self) -> None:
        monitor = self.current_monitor()
        if monitor is None:
            return
        dialog = ShortcutDialog(monitor.inputs, self.config.aliases(monitor.display), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        binding = gnome_binding(dialog.key.keySequence())
        if not binding:
            QMessageBox.warning(self, "Geçersiz Kısayol", "Tek bir geçerli klavye kısayolu girin.")
            return
        action, code = dialog.action.currentData()
        first = dialog.first_input.currentData()
        second = dialog.second_input.currentData()
        if action == "toggle" and (first is None or second is None or first == second):
            QMessageBox.warning(self, "Geçersiz Seçim", "Kısayol için iki farklı monitör girişi seçin.")
            return
        command = (
            f"aw2724dm-control --display {monitor.display} "
            f"--toggle 0x{int(first):02x} 0x{int(second):02x}"
        )
        if action == "input":
            command = f"aw2724dm-control --display {monitor.display} --set-input 0x{int(code):02x}"
        try:
            path = install_shortcut(dialog.name.text().strip() or "Monitör kontrolü", command, binding)
        except Exception as exc:
            self._show_error(str(exc))
            return
        QMessageBox.information(self, "Kısayol Eklendi", f"GNOME kısayolu oluşturuldu:\n{path}")

    def _automatic_update_check(self) -> None:
        import time

        if not self.config.data.get("check_updates", True):
            return
        last_check = int(self.config.data.get("last_update_check", 0))
        if int(time.time()) - last_check >= 6 * 60 * 60:
            self.check_updates(manual=False)

    def check_updates(self, manual: bool = False) -> None:
        self.update_button.setEnabled(False)
        if manual:
            self.statusBar().showMessage("GitHub üzerinde güncelleme denetleniyor…")
        worker = Worker(check_for_update)
        worker.signals.succeeded.connect(lambda info: self._update_check_finished(info, manual))
        if manual:
            worker.signals.failed.connect(self._show_error)
        worker.signals.finished.connect(lambda: self.update_button.setEnabled(True))
        self.pool.start(worker)

    def _update_check_finished(self, result: object, manual: bool) -> None:
        import time

        self.statusBar().showMessage("Güncelleme denetimi tamamlandı", 3000)
        self.config.data["last_update_check"] = int(time.time())
        self.config.save()
        info = result if isinstance(result, UpdateInfo) else None
        if info is None:
            if manual:
                QMessageBox.information(
                    self,
                    "Güncelleme Yok",
                    "AW2724DM Monitor Control'ın en güncel sürümünü kullanıyorsunuz.",
                )
            return
        answer = QMessageBox.question(
            self,
            "Güncelleme Bulundu",
            f"Yeni sürüm kullanılabilir: {info.available_version}\n"
            f"Mevcut sürüm: {info.current_version}\n\n"
            "Güncelleme şimdi indirilsin ve kurulsun mu? Yönetici onayı istenecektir.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run_async(
                apply_update,
                success=self._update_applied,
                message="Güncelleme indiriliyor ve uygulanıyor…",
            )

    def _update_applied(self, result: object) -> None:
        details = str(result).strip()
        message = "Güncelleme başarıyla uygulandı. Uygulama şimdi kapanacak; yeniden başlatın."
        if details:
            message += f"\n\n{details}"
        QMessageBox.information(self, "Güncelleme Tamamlandı", message)
        self.quit_application()


def create_window(config: ConfigStore, ddc: DDCUtil) -> MainWindow:
    return MainWindow(config, ddc)
