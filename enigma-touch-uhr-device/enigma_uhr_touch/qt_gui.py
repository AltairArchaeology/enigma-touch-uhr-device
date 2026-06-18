from __future__ import annotations

import sys
import threading
import traceback
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .app_info import HELP_TEXT, MIT_LICENSE_TEXT, about_text
from .backends import (
    SerialBackend,
    SerialConfig,
    list_serial_ports,
    query_touch_command,
    query_touch_commands,
)
from .enigma_core import machine_from_touch_settings
from .touch_settings import (
    TouchSettings,
    build_touch_settings,
    format_setting_values,
    parse_model_response,
    parse_pair_response,
    parse_rotor_response,
    parse_touch_settings,
    value_after_label,
)
from .uhr import Plugboard, Uhr, UhrAdapter
from .ui_logic import (
    ConversionProgress,
    ConversionStopped,
    convert_direct_with_backend_stream,
    extract_port_device,
    format_groups,
    mapping_lines,
)


@dataclass(frozen=True)
class TaskResult:
    ok: bool
    value: object
    traceback_text: str = ""


class WorkerSignals(QObject):
    finished = Signal(object)
    progress = Signal(object)


class Worker(QRunnable):
    def __init__(self, task: Callable[..., object], *, with_progress: bool = False) -> None:
        super().__init__()
        self.task = task
        self.with_progress = with_progress
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.task(self.signals.progress.emit)
            else:
                result = self.task()
            self.signals.finished.emit(TaskResult(True, result))
        except Exception as exc:
            self.signals.finished.emit(TaskResult(False, exc, traceback.format_exc()))


class EnigmaUhrQtWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Enigma Touch - Uhr Device")
        self.resize(1100, 760)
        self.setMinimumSize(980, 680)

        self.thread_pool = QThreadPool.globalInstance()
        self.busy = False
        self.pending_success: Optional[Callable[[object], None]] = None
        self.stop_requested = threading.Event()
        self.active_backend: Optional[SerialBackend] = None
        self.conversion_active = False

        self._build_ui()
        self._apply_style()
        self.refresh_ports(show_errors=False)
        self.update_mapping_preview()

    def _build_ui(self) -> None:
        main = QWidget()
        root_layout = QVBoxLayout(main)
        root_layout.setContentsMargins(12, 10, 12, 8)
        root_layout.setSpacing(10)
        self.setCentralWidget(main)

        top = QHBoxLayout()
        top.setSpacing(8)
        root_layout.addLayout(top)

        top.addWidget(QLabel("Port"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(180)
        top.addWidget(self.port_combo, 1)
        top.addWidget(self._button("Refresh", self.refresh_ports))
        top.addWidget(self._button("Read Enigma Touch Settings", self.read_touch_settings))
        top.addSpacing(10)
        top.addWidget(QLabel("Baud"))
        self.baud_edit = QLineEdit("2400")
        self.baud_edit.setMaximumWidth(90)
        top.addWidget(self.baud_edit)
        top.addWidget(QLabel("Timeout"))
        self.timeout_edit = QLineEdit("2.0")
        self.timeout_edit.setMaximumWidth(70)
        top.addWidget(self.timeout_edit)
        top.addWidget(self._button("Help", self.show_help))
        top.addWidget(self._button("About", self.show_about))
        top.addWidget(self._button("License", self.show_license))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        settings_panel = QWidget()
        settings_panel.setMaximumWidth(470)
        settings_panel.setMinimumWidth(430)
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 8, 0)
        settings_layout.setSpacing(10)
        splitter.addWidget(settings_panel)

        self._build_settings(settings_layout)
        self._build_workspace(splitter)
        splitter.setSizes([445, 645])

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        root_layout.addWidget(self.status_label)

    def _build_settings(self, layout: QVBoxLayout) -> None:
        touch_box = QGroupBox("Enigma Touch Settings")
        touch_layout = QGridLayout(touch_box)
        self.model_edit = QLineEdit()
        self.reflector_edit = QLineEdit()
        self.rotors_edit = QLineEdit()
        self.rings_edit = QLineEdit()
        self.positions_edit = QLineEdit()
        self.pairs_edit = QLineEdit()
        self.reflector_d_edit = QLineEdit()
        self._settings_row(touch_layout, 0, "Model", self.model_edit, "?MO", self.read_model)
        self._settings_row(touch_layout, 1, "Reflector", self.reflector_edit)
        self._settings_row(touch_layout, 2, "Rotors", self.rotors_edit)
        rotor_button = self._button("?RO", self.read_rotor_set)
        rotor_button.setMaximumWidth(58)
        rotor_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        touch_layout.addWidget(rotor_button, 1, 2, 2, 1)
        self._settings_row(touch_layout, 3, "Rings", self.rings_edit, "?RI", self.read_rings)
        self._settings_row(touch_layout, 4, "Position", self.positions_edit, "?RP", self.read_positions)
        self._settings_row(touch_layout, 5, "Plugboard", self.pairs_edit, "?PB", self.read_plugboard)
        self._settings_row(touch_layout, 6, "Reflector D", self.reflector_d_edit, "?RD", self.read_reflector_d)
        layout.addWidget(touch_box)

        uhr_box = QGroupBox("Uhr Device")
        uhr_layout = QGridLayout(uhr_box)
        self.uhr_combo = QComboBox()
        self.uhr_combo.addItems([f"{position:02d}" for position in range(40)])
        self.uhr_combo.currentTextChanged.connect(self.update_mapping_preview)
        uhr_layout.addWidget(QLabel("Position"), 0, 0)
        uhr_layout.addWidget(self.uhr_combo, 0, 1)
        self.ahistoric_check = QCheckBox("Enable Ahistoric Uhr Device")
        self.ahistoric_check.setChecked(False)
        self.ahistoric_check.toggled.connect(self.update_mapping_preview)
        uhr_layout.addWidget(self.ahistoric_check, 1, 0, 1, 2)
        layout.addWidget(uhr_box)

        output_box = QGroupBox("Output")
        output_layout = QGridLayout(output_box)
        self.group_spin = QSpinBox()
        self.group_spin.setRange(0, 10)
        self.group_spin.setValue(5)
        self.preserve_check = QCheckBox("Keep Spaces and Punctuation")
        self.preserve_check.setChecked(False)
        self.preserve_check.toggled.connect(self.update_output_options)
        output_layout.addWidget(QLabel("Letters Per Group"), 0, 0)
        output_layout.addWidget(self.group_spin, 0, 1)
        output_layout.addWidget(self.preserve_check, 1, 0, 1, 2)
        self.update_output_options()
        layout.addWidget(output_box)

        map_box = QGroupBox("Map")
        map_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        map_layout = QVBoxLayout(map_box)
        self.map_text = self._text(readonly=True, height=110)
        self.map_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        map_layout.addWidget(self.map_text)
        map_layout.setStretch(0, 1)
        layout.addWidget(map_box, 1)

    def _settings_row(
        self,
        layout: QGridLayout,
        row: int,
        label: str,
        edit: QLineEdit,
        button_text: str | None = None,
        callback: Callable[[], None] | None = None,
    ) -> None:
        layout.addWidget(QLabel(label), row, 0)
        layout.addWidget(edit, row, 1)
        if button_text and callback:
            button = self._button(button_text, callback)
            button.setMaximumWidth(58)
            layout.addWidget(button, row, 2)

    def _build_workspace(self, splitter: QSplitter) -> None:
        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(8, 0, 0, 0)
        workspace_layout.setSpacing(10)
        splitter.addWidget(workspace)

        button_row = QHBoxLayout()
        self.convert_button = self._button("Convert", self.convert_text)
        button_row.addWidget(self.convert_button)
        self.stop_button = self._button("Stop", self.stop_conversion)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self._button("Clear", self.clear_text))
        self.refresh_position_check = QCheckBox("Update Position Before Convert")
        self.refresh_position_check.setChecked(True)
        button_row.addWidget(self.refresh_position_check)
        button_row.addStretch(1)
        workspace_layout.addLayout(button_row)

        message_box = QGroupBox("Message")
        message_layout = QVBoxLayout(message_box)
        self.input_text = self._text(height=170)
        message_layout.addWidget(self.input_text)
        workspace_layout.addWidget(message_box, 2)

        result_box = QGroupBox("Result")
        result_layout = QVBoxLayout(result_box)
        self.output_text = self._text(height=170)
        result_layout.addWidget(self.output_text)
        workspace_layout.addWidget(result_box, 2)

    def _apply_style(self) -> None:
        mono = QFont("Consolas", 10)
        for widget in (
            self.map_text,
            self.input_text,
            self.output_text,
        ):
            widget.setFont(mono)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f4ef;
                color: #211f1b;
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #b9b1a5;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QPushButton {
                background: #34444d;
                color: #fbfaf6;
                border: 0;
                border-radius: 4px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background: #40545f;
            }
            QPushButton:disabled {
                background: #9b9b96;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background: #fffdf8;
                border: 1px solid #b9b1a5;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #6b7e6f;
            }
            QLabel#status {
                background: #2d3337;
                color: #f8f5ed;
                padding: 7px 10px;
                border-radius: 4px;
            }
            """
        )

    def _button(self, text: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def _text(self, *, readonly: bool = False, height: int = 120) -> QTextEdit:
        text = QTextEdit()
        text.setAcceptRichText(False)
        text.setReadOnly(readonly)
        text.setMinimumHeight(height)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return text

    def refresh_ports(self, *, show_errors: bool = True) -> None:
        try:
            ports = list_serial_ports()
        except RuntimeError as exc:
            self.port_combo.clear()
            self.set_status(str(exc))
            if show_errors:
                self.show_error("Serial Ports", str(exc))
            return
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current:
            self.port_combo.setCurrentText(current)
        elif ports:
            self.port_combo.setCurrentIndex(0)
        self.set_status(f"{len(ports)} serial port(s) found" if ports else "No serial ports found")

    def read_touch_settings(self) -> None:
        try:
            config = self.serial_config()
        except ValueError as exc:
            self.show_error("Read Enigma Touch Settings", str(exc))
            return

        def task() -> TouchSettings:
            responses = query_touch_commands(
                config,
                ("?MO", "?RO", "?RI", "?RP", "?PB", "?RD"),
                query_delay=1.0,
            )
            return parse_touch_settings(responses)

        def success(value: object) -> None:
            settings = value if isinstance(value, TouchSettings) else None
            if settings is None:
                return
            self.apply_touch_settings(settings)
            if settings.has_uhr_plugboard:
                self.set_status(f"Read settings: {settings.model_name}")
            else:
                self.set_status(f"Read settings: {settings.model_name}; Uhr unavailable without plugboard")

        self.start_task("Reading Enigma Touch settings...", task, success)

    def read_model(self) -> None:
        self.read_single_setting("?MO")

    def read_rotor_set(self) -> None:
        self.read_single_setting("?RO")

    def read_rings(self) -> None:
        self.read_single_setting("?RI")

    def read_positions(self) -> None:
        self.read_single_setting("?RP")

    def read_plugboard(self) -> None:
        self.read_single_setting("?PB")

    def read_reflector_d(self) -> None:
        self.read_single_setting("?RD")

    def read_single_setting(self, command: str) -> None:
        try:
            config = self.serial_config()
        except ValueError as exc:
            self.show_error("Read Enigma Touch Settings", str(exc))
            return

        def task() -> str:
            return query_touch_command(config, command, query_delay=1.0)

        def success(value: object) -> None:
            try:
                self.apply_single_setting(command, str(value))
            except ValueError as exc:
                self.show_error("Read Enigma Touch Settings", str(exc))
                return
            self.set_status(f"Read {command}")

        self.start_task(f"Reading {command}...", task, success)

    def apply_single_setting(self, command: str, response: str) -> None:
        if command == "?MO":
            self.model_edit.setText(parse_model_response(response))
            return
        if command == "?RO":
            reflector, rotors = parse_rotor_response(response)
            self.reflector_edit.setText(reflector)
            self.rotors_edit.setText(" ".join(rotors))
            return
        if command == "?RI":
            self.rings_edit.setText(value_after_label(response, "Rings"))
            return
        if command == "?RP":
            self.positions_edit.setText(value_after_label(response, "Positions"))
            return
        if command == "?PB":
            self.pairs_edit.setText(parse_pair_response(response, "Plugboard"))
            self.update_mapping_preview()
            return
        if command == "?RD":
            self.reflector_d_edit.setText(parse_pair_response(response, "UKW D"))
            return
        raise ValueError(f"Unknown setting command {command!r}.")

    def apply_touch_settings(self, settings: TouchSettings) -> None:
        self.model_edit.setText(settings.model)
        self.reflector_edit.setText(settings.reflector)
        self.rotors_edit.setText(" ".join(settings.rotors))
        self.rings_edit.setText(settings.rings_display())
        self.positions_edit.setText(settings.positions_display())
        self.pairs_edit.setText(settings.plugboard_pairs)
        self.reflector_d_edit.setText(settings.reflector_d_pairs)
        self.update_mapping_preview()

    def convert_text(self) -> None:
        if self.refresh_position_check.isChecked():
            self.refresh_position_then_convert()
            return
        self.start_conversion()

    def refresh_position_then_convert(self) -> None:
        try:
            config = self.serial_config()
        except ValueError as exc:
            self.show_error("Serial", str(exc))
            return

        def task() -> str:
            return query_touch_command(config, "?RP", query_delay=1.0)

        def success(value: object) -> None:
            try:
                self.apply_single_setting("?RP", str(value))
            except ValueError as exc:
                self.show_error("Read Enigma Touch Settings", str(exc))
                return
            self.start_conversion()

        self.start_task("Updating rotor position...", task, success)

    def start_conversion(self) -> None:
        try:
            adapter = self.build_adapter()
            settings = self.build_touch_settings()
            ahistoric = self.ahistoric_check.isChecked()
            settings.require_uhr_supported(ahistoric=ahistoric)
            machine = machine_from_touch_settings(settings, adapter.plugboard, ahistoric=ahistoric)
        except ValueError as exc:
            self.show_error("Settings", str(exc))
            return

        text = self.input_text.toPlainText()
        preserve = self.preserve_check.isChecked()
        group = 0 if preserve else self.group_spin.value()

        try:
            config = self.serial_config()
        except ValueError as exc:
            self.show_error("Serial", str(exc))
            return
        backend_factory = lambda: SerialBackend(config)
        status = "Converting through Enigma Touch..."

        self.output_text.clear()
        self.stop_requested.clear()
        self.conversion_active = True

        def task(
            progress: Callable[[ConversionProgress], None],
        ) -> tuple[str, tuple[int, ...], bool, int, int]:
            backend = backend_factory()
            self.active_backend = backend
            try:
                try:
                    result = convert_direct_with_backend_stream(
                        adapter,
                        machine,
                        backend,
                        text,
                        preserve_nonletters=preserve,
                        progress=progress,
                        should_stop=self.stop_requested.is_set,
                    )
                except ConversionStopped as exc:
                    return (
                        exc.output_text,
                        machine.position_values(),
                        True,
                        exc.completed_letters,
                        exc.total_letters,
                    )
                return result, machine.position_values(), False, 0, 0
            finally:
                self.active_backend = None
                backend.close()

        def success(value: object) -> None:
            output, final_positions, stopped, completed_letters, total_letters = value
            self.output_text.setPlainText(format_groups(str(output), group))
            self.positions_edit.setText(format_setting_values(final_positions, numeric=settings.uses_numeric_labels))
            if stopped:
                self.set_status(f"Conversion stopped at {completed_letters}/{total_letters}")
            else:
                self.set_status("Conversion complete")

        def progress(value: object) -> None:
            if isinstance(value, ConversionProgress):
                self.output_text.setPlainText(format_groups(value.output_text, group))
                self.set_status(
                    f"Converting through Enigma Touch... {value.completed_letters}/{value.total_letters}"
                )

        self.start_task(status, task, success, progress=progress, with_progress=True)

    def stop_conversion(self) -> None:
        if not self.busy or not self.conversion_active:
            return
        self.stop_requested.set()
        backend = self.active_backend
        if backend is not None:
            backend.request_stop()
        self.stop_button.setEnabled(False)
        self.set_status("Stopping conversion...")

    def clear_text(self) -> None:
        for widget in (self.input_text, self.output_text):
            widget.clear()
        self.set_status("Cleared")

    def update_output_options(self) -> None:
        self.group_spin.setEnabled(not self.preserve_check.isChecked())

    def show_help(self) -> None:
        self.show_text_dialog("Help", HELP_TEXT, width=760, height=720)

    def show_about(self) -> None:
        self.show_text_dialog("About", about_text(), width=680, height=500)

    def show_license(self) -> None:
        self.show_text_dialog("License", MIT_LICENSE_TEXT, width=720, height=560)

    def show_text_dialog(self, title: str, text: str, *, width: int, height: int) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Enigma Touch - Uhr Device - {title}")
        dialog.resize(width, height)
        dialog.setMinimumSize(520, 360)

        layout = QVBoxLayout(dialog)
        content = QTextEdit()
        content.setAcceptRichText(False)
        content.setReadOnly(True)
        content.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        content.setPlainText(text.strip())
        layout.addWidget(content, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def build_adapter(self) -> UhrAdapter:
        ahistoric = self.ahistoric_check.isChecked()
        plugboard = Plugboard.parse(self.pairs_edit.text(), ahistoric=ahistoric)
        uhr = Uhr(plugboard, int(self.uhr_combo.currentText()), ahistoric=ahistoric)
        return UhrAdapter(plugboard, uhr)

    def build_touch_settings(self) -> TouchSettings:
        if not self.model_edit.text().strip():
            raise ValueError("Read Enigma Touch settings before converting.")
        return build_touch_settings(
            model=self.model_edit.text(),
            reflector=self.reflector_edit.text(),
            rotors=self.rotors_edit.text(),
            rings=self.rings_edit.text(),
            positions=self.positions_edit.text(),
            plugboard_pairs=self.pairs_edit.text(),
            reflector_d_pairs=self.reflector_d_edit.text(),
        )

    def update_mapping_preview(self) -> None:
        try:
            self.map_text.setPlainText(mapping_lines(self.build_adapter()))
            self.set_status("Map updated")
        except ValueError as exc:
            self.map_text.setPlainText(str(exc))

    def serial_config(self) -> SerialConfig:
        port = extract_port_device(self.port_combo.currentText())
        try:
            baud = int(self.baud_edit.text())
        except ValueError as exc:
            raise ValueError("Baud must be a whole number.") from exc
        try:
            timeout = float(self.timeout_edit.text())
        except ValueError as exc:
            raise ValueError("Timeout must be a number.") from exc
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")
        return SerialConfig(
            port=port,
            baud=baud,
            timeout=timeout,
            protocol="char",
        )

    def start_task(
        self,
        status: str,
        task: Callable[[], object],
        success: Callable[[object], None],
        *,
        progress: Callable[[object], None] | None = None,
        with_progress: bool = False,
    ) -> None:
        if self.busy:
            self.set_status("Busy")
            return
        self.busy = True
        self.pending_success = success
        self.set_busy_controls(False)
        self.set_status(status)
        worker = Worker(task, with_progress=with_progress)
        worker.signals.finished.connect(self.finish_task)
        if progress:
            worker.signals.progress.connect(progress)
        self.thread_pool.start(worker)

    @Slot(object)
    def finish_task(self, result: TaskResult) -> None:
        self.busy = False
        self.conversion_active = False
        self.set_busy_controls(True)
        success = self.pending_success
        self.pending_success = None
        if result.ok and success:
            success(result.value)
            return
        self.set_status("Error")
        self.show_error("Enigma Touch - Uhr Device", str(result.value))

    def set_busy_controls(self, enabled: bool) -> None:
        self.convert_button.setEnabled(enabled)
        self.stop_button.setEnabled(
            self.busy and self.conversion_active and not self.stop_requested.is_set()
        )

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Enigma Touch - Uhr Device")
    window = EnigmaUhrQtWindow()
    if "--smoke-test" in sys.argv:
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
