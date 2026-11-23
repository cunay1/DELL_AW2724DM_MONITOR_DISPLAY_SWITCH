from __future__ import annotations

from datetime import datetime
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QProcess, QThreadPool, QTimer, Qt
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QSlider,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QKeySequenceEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import ConfigStore
from .ddc import DDCUtil, InputSource, Monitor
from .gnome import install_shortcut
from .i18n import get_language, set_language, tr
from .logging_config import export_logs, get_logger
from .updater import UpdateInfo, apply_update, check_for_update
from .worker import Worker


logger = get_logger("gui")


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
        self.setWindowTitle(tr("shortcut_title"))
        layout = QFormLayout(self)
        self.name = QLineEdit(tr("shortcut_default_name"))
        self.action = QComboBox()
        self.action.addItem(tr("toggle_action"), ("toggle", None))
        for source in inputs:
            key = f"0x{source.code:02x}"
            label = aliases.get(key, source.name)
            self.action.addItem(tr("direct_action", label=label, key=key), ("input", source.code))
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
        layout.addRow(tr("name"), self.name)
        layout.addRow(tr("action"), self.action)
        layout.addRow(tr("first_input"), self.first_input)
        layout.addRow(tr("second_input"), self.second_input)
        layout.addRow(tr("shortcut_key"), self.key)
        hint = QLabel(tr("shortcut_hint"))
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
        self.update_progress_dialog: QProgressDialog | None = None
        self.update_worker: Worker | None = None

        self.setWindowTitle(tr("window_title"))
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(760, 680)
        self.setMinimumSize(650, 560)
        self._build_ui()
        self._build_menu()
        self._build_tray()
        logger.info("Main window created; language=%s", get_language())
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
        self.refresh_button = QPushButton(tr("refresh"))
        self.refresh_button.clicked.connect(self.refresh_monitors)
        top.addWidget(QLabel(tr("monitor")))
        top.addWidget(self.monitor_combo, 1)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.inputs_group = QGroupBox(tr("input_sources"))
        self.inputs_layout = QGridLayout(self.inputs_group)
        layout.addWidget(self.inputs_group)

        toggle_group = QGroupBox(tr("quick_toggle"))
        toggle_layout = QHBoxLayout(toggle_group)
        self.toggle_first = QComboBox()
        self.toggle_second = QComboBox()
        self.toggle_button = QPushButton(tr("toggle_inputs"))
        self.toggle_first.currentIndexChanged.connect(self._save_toggle)
        self.toggle_second.currentIndexChanged.connect(self._save_toggle)
        self.toggle_button.clicked.connect(self.toggle_input)
        toggle_layout.addWidget(self.toggle_first, 1)
        toggle_layout.addWidget(QLabel("↔"))
        toggle_layout.addWidget(self.toggle_second, 1)
        toggle_layout.addWidget(self.toggle_button)
        layout.addWidget(toggle_group)

        controls = QGroupBox(tr("display_settings"))
        controls_layout = QGridLayout(controls)
        self.brightness = self._make_slider()
        self.contrast = self._make_slider()
        self.brightness_value = QLabel("—")
        self.contrast_value = QLabel("—")
        self.brightness.valueChanged.connect(lambda value: self.brightness_value.setText(str(value)))
        self.contrast.valueChanged.connect(lambda value: self.contrast_value.setText(str(value)))
        self.brightness.sliderReleased.connect(
            lambda: self.set_control(0x10, self.brightness.value(), tr("brightness"))
        )
        self.contrast.sliderReleased.connect(
            lambda: self.set_control(0x12, self.contrast.value(), tr("contrast"))
        )
        controls_layout.addWidget(QLabel(tr("brightness")), 0, 0)
        controls_layout.addWidget(self.brightness, 0, 1)
        controls_layout.addWidget(self.brightness_value, 0, 2)
        controls_layout.addWidget(QLabel(tr("contrast")), 1, 0)
        controls_layout.addWidget(self.contrast, 1, 1)
        controls_layout.addWidget(self.contrast_value, 1, 2)
        layout.addWidget(controls)

        aliases_group = QGroupBox(tr("port_aliases"))
        aliases_layout = QVBoxLayout(aliases_group)
        self.alias_table = QTableWidget(0, 3)
        self.alias_table.setHorizontalHeaderLabels([tr("code"), tr("hardware_name"), tr("alias")])
        self.alias_table.horizontalHeader().setStretchLastSection(True)
        self.alias_table.itemChanged.connect(self._alias_changed)
        aliases_layout.addWidget(self.alias_table)
        layout.addWidget(aliases_group, 1)

        bottom = QHBoxLayout()
        self.shortcut_button = QPushButton(tr("assign_shortcut"))
        self.shortcut_button.clicked.connect(self.add_shortcut)
        self.update_button = QPushButton(tr("check_updates"))
        self.update_button.clicked.connect(lambda: self.check_updates(manual=True))
        self.hide_button = QPushButton(tr("hide_to_tray"))
        self.hide_button.clicked.connect(self.hide)
        bottom.addWidget(self.shortcut_button)
        bottom.addWidget(self.update_button)
        bottom.addStretch()
        bottom.addWidget(self.hide_button)
        layout.addLayout(bottom)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.version_label = QLabel(tr("version", version=__version__))
        self.version_label.setToolTip(tr("version_tooltip"))
        self.statusBar().addPermanentWidget(self.version_label)
        self.statusBar().showMessage(tr("scanning_monitors"))

    def _build_menu(self) -> None:
        language_menu = self.menuBar().addMenu(tr("language_menu"))
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        for label, code in (("English", "en"), ("Türkçe", "tr")):
            action = QAction(label, self, checkable=True)
            action.setChecked(get_language() == code)
            action.triggered.connect(lambda checked, selected=code: self.change_language(selected))
            language_group.addAction(action)
            language_menu.addAction(action)

        help_menu = self.menuBar().addMenu(tr("help"))
        export_action = QAction(tr("export_logs"), self)
        export_action.triggered.connect(self.export_support_logs)
        help_menu.addAction(export_action)
        help_menu.addSeparator()
        about_action = QAction(tr("about"), self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def change_language(self, language: str) -> None:
        if language == get_language():
            return
        self.config.data["language"] = language
        self.config.save()
        logger.info("Language changed to %s", language)
        set_language(language)
        QMessageBox.information(self, tr("language_changed_title"), tr("language_changed"))
        program = "/usr/local/bin/aw2724dm-control"
        arguments: list[str] = []
        if not Path(program).exists():
            import sys

            program = sys.executable
            arguments = ["-m", "aw2724dm_control"]
        if QProcess.startDetached(program, arguments)[0]:
            self.quit_application()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_html", version=__version__),
        )

    def export_support_logs(self) -> None:
        suggested = Path.home() / (
            "aw2724dm-control-logs-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"
        )
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("export_logs_title"),
            str(suggested),
            tr("log_archive_filter"),
        )
        if not filename:
            return
        try:
            archive = export_logs(Path(filename))
        except Exception as exc:
            logger.exception("Log export failed")
            self._show_error(str(exc))
            return
        logger.info("Support logs exported to %s", archive)
        QMessageBox.information(
            self,
            tr("logs_exported_title"),
            tr("logs_exported", path=archive),
        )

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
        show_action = QAction(tr("show_window"), self)
        show_action.triggered.connect(self.show_from_tray)
        self.tray_menu.addAction(show_action)
        self.tray_inputs_menu = self.tray_menu.addMenu(tr("input_source"))
        self.tray_menu.addSeparator()
        about_action = QAction(tr("about"), self)
        about_action.triggered.connect(self.show_about)
        self.tray_menu.addAction(about_action)
        self.tray_menu.addSeparator()
        quit_action = QAction(tr("quit"), self)
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
            tr("tray_continues"),
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )

    def _run_async(self, function, *args, success=None, message: str | None = None) -> None:
        self.busy_count += 1
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage(message or tr("working"))
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
            self.statusBar().showMessage(tr("ready"), 3000)

    def _show_error(self, message: str) -> None:
        logger.error("User-visible operation error: %s", message)
        self.statusBar().showMessage(tr("error"), 4000)
        QMessageBox.critical(self, tr("operation_error"), message)

    def current_monitor(self) -> Monitor | None:
        index = self.monitor_combo.currentIndex()
        return self.monitors[index] if 0 <= index < len(self.monitors) else None

    def refresh_monitors(self) -> None:
        logger.debug("Refreshing monitor list")
        self._run_async(
            self.ddc.detect,
            success=self._monitors_loaded,
            message=tr("scanning_vcp"),
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
                tr("monitor_not_found"),
                tr("monitor_not_found_detail"),
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
            label = QLabel(tr("inputs_not_detected"))
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
            toggle_action = self.tray_inputs_menu.addAction(tr("toggle_inputs"))
            toggle_action.triggered.connect(self.toggle_input)
        else:
            action = self.tray_inputs_menu.addAction(tr("no_input"))
            action.setEnabled(False)

    def _load_controls(self, display: int) -> None:
        self.brightness.setEnabled(False)
        self.contrast.setEnabled(False)
        self._run_async(
            self.ddc.get_vcp,
            display,
            0x10,
            success=lambda value: self._control_loaded(self.brightness, int(value)),
            message=tr("reading_brightness"),
        )
        self._run_async(
            self.ddc.get_vcp,
            display,
            0x12,
            success=lambda value: self._control_loaded(self.contrast, int(value)),
            message=tr("reading_contrast"),
        )

    @staticmethod
    def _control_loaded(slider: QSlider, value: int) -> None:
        slider.setValue(max(0, min(100, value)))
        slider.setEnabled(True)

    def set_input(self, code: int) -> None:
        monitor = self.current_monitor()
        if monitor:
            logger.info("Setting display %s input to 0x%02x", monitor.display, code)
            self._run_async(
                self.ddc.set_input,
                monitor.display,
                code,
                success=lambda _: self.tray.showMessage(
                    tr("input_changed"), tr("new_input", code=code)
                ),
                message=tr("setting_input", code=code),
            )

    def toggle_input(self) -> None:
        monitor = self.current_monitor()
        first = self.toggle_first.currentData()
        second = self.toggle_second.currentData()
        if not monitor or first is None or second is None:
            return
        if first == second:
            QMessageBox.warning(self, tr("invalid_selection"), tr("choose_two_inputs"))
            return
        self._run_async(
            self.ddc.toggle,
            monitor.display,
            int(first),
            int(second),
            success=lambda code: self.tray.showMessage(
                tr("input_changed"), tr("new_input", code=int(code))
            ),
            message=tr("switching_input"),
        )

    def set_control(self, feature: int, value: int, name: str) -> None:
        monitor = self.current_monitor()
        if monitor:
            logger.info(
                "Setting display %s VCP 0x%02x to %s", monitor.display, feature, value
            )
            self._run_async(
                self.ddc.set_vcp,
                monitor.display,
                feature,
                value,
                message=tr("setting_control", name=name, value=value),
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
            QMessageBox.warning(self, tr("invalid_shortcut"), tr("invalid_shortcut_detail"))
            return
        action, code = dialog.action.currentData()
        first = dialog.first_input.currentData()
        second = dialog.second_input.currentData()
        if action == "toggle" and (first is None or second is None or first == second):
            QMessageBox.warning(self, tr("invalid_selection"), tr("shortcut_choose_two"))
            return
        command = (
            f"aw2724dm-control --display {monitor.display} "
            f"--toggle 0x{int(first):02x} 0x{int(second):02x}"
        )
        if action == "input":
            command = f"aw2724dm-control --display {monitor.display} --set-input 0x{int(code):02x}"
        try:
            path = install_shortcut(dialog.name.text().strip() or tr("monitor_control"), command, binding)
        except Exception as exc:
            self._show_error(str(exc))
            return
        QMessageBox.information(
            self, tr("shortcut_added"), tr("shortcut_created", path=path)
        )

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
            self.statusBar().showMessage(tr("checking_updates"))
        worker = Worker(check_for_update)
        worker.signals.succeeded.connect(lambda info: self._update_check_finished(info, manual))
        if manual:
            worker.signals.failed.connect(self._show_error)
        worker.signals.finished.connect(lambda: self.update_button.setEnabled(True))
        self.pool.start(worker)

    def _update_check_finished(self, result: object, manual: bool) -> None:
        import time

        self.statusBar().showMessage(tr("update_check_complete"), 3000)
        self.config.data["last_update_check"] = int(time.time())
        self.config.save()
        info = result if isinstance(result, UpdateInfo) else None
        if info is None:
            if manual:
                QMessageBox.information(
                    self,
                    tr("no_update"),
                    tr("latest_version"),
                )
            return
        answer = QMessageBox.question(
            self,
            tr("update_found"),
            tr(
                "update_question",
                available=info.available_version,
                current=info.current_version,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_update(info.available_version)

    def _start_update(self, version: str) -> None:
        logger.info("User approved update to %s", version)
        self.update_button.setEnabled(False)
        dialog = QProgressDialog(tr("update_stage_authorize"), "", 0, 100, self)
        dialog.setWindowTitle(tr("update_progress_title"))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setValue(2)
        dialog.show()
        self.update_progress_dialog = dialog
        worker = Worker(apply_update, version, provide_progress=True)
        worker.signals.progress.connect(self._update_progress_changed)
        worker.signals.succeeded.connect(self._update_applied)
        worker.signals.failed.connect(self._update_failed)
        worker.signals.finished.connect(self._update_worker_finished)
        self.update_worker = worker
        self.pool.start(worker)

    def _update_progress_changed(self, value: int, message: str) -> None:
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.setLabelText(message)
            self.update_progress_dialog.setValue(value)
        self.statusBar().showMessage(f"{message} ({value}%)")

    def _close_update_progress(self) -> None:
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.close()
            self.update_progress_dialog.deleteLater()
            self.update_progress_dialog = None

    def _update_failed(self, message: str) -> None:
        self._close_update_progress()
        self._show_error(message)

    def _update_worker_finished(self) -> None:
        self.update_button.setEnabled(True)
        self.update_worker = None

    def _update_applied(self, _result: object) -> None:
        self._close_update_progress()
        QMessageBox.information(self, tr("update_complete"), tr("update_applied"))
        self.quit_application()


def create_window(config: ConfigStore, ddc: DDCUtil) -> MainWindow:
    return MainWindow(config, ddc)
