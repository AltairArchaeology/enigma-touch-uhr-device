from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional

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
    parse_setting_values,
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


class EnigmaUhrApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Enigma Touch - Uhr Device")
        self.root.minsize(980, 700)

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="2400")
        self.timeout_var = tk.StringVar(value="2.0")
        self.model_var = tk.StringVar()
        self.reflector_var = tk.StringVar()
        self.rotors_var = tk.StringVar()
        self.rings_var = tk.StringVar()
        self.positions_var = tk.StringVar()
        self.pairs_var = tk.StringVar()
        self.reflector_d_var = tk.StringVar()
        self.uhr_var = tk.StringVar(value="00")
        self.group_var = tk.StringVar(value="5")
        self.preserve_nonletters_var = tk.BooleanVar(value=False)
        self.ahistoric_var = tk.BooleanVar(value=False)
        self.refresh_position_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")

        self.task_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self.pending_success: Optional[Callable[[object], None]] = None
        self.pending_progress: Optional[Callable[[object], None]] = None
        self.stop_requested = threading.Event()
        self.active_backend: Optional[SerialBackend] = None
        self.conversion_active = False

        self._build_styles()
        self._build_ui()
        self.refresh_ports(show_errors=False)
        self.update_mapping_preview()
        self.root.after(100, self.poll_tasks)

    def _build_styles(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f6f4ef")
        style.configure("TLabel", background="#f6f4ef", foreground="#211f1b")
        style.configure("TLabelframe", background="#f6f4ef", bordercolor="#b9b1a5", relief="solid")
        style.configure("TLabelframe.Label", background="#f6f4ef", foreground="#211f1b")
        style.configure("TButton", padding=(10, 5))
        style.configure("Primary.TButton", padding=(12, 6))
        style.configure("Status.TLabel", background="#2d3337", foreground="#f8f5ed", padding=(10, 6))

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=24)
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=(6, 10))
        ttk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(top, text="Read Enigma Touch Settings", command=self.read_touch_settings).grid(
            row=0, column=3, padx=(0, 12)
        )

        ttk.Label(top, text="Baud").grid(row=0, column=4, sticky="w")
        ttk.Entry(top, textvariable=self.baud_var, width=9).grid(row=0, column=5, padx=(6, 10))
        ttk.Label(top, text="Timeout").grid(row=0, column=6, sticky="w")
        ttk.Entry(top, textvariable=self.timeout_var, width=6).grid(row=0, column=7, padx=(6, 10))
        ttk.Button(top, text="Help", command=self.show_help).grid(row=0, column=8)
        ttk.Button(top, text="About", command=self.show_about).grid(row=0, column=9, padx=(8, 0))
        ttk.Button(top, text="License", command=self.show_license).grid(row=0, column=10, padx=(8, 0))

        body = ttk.Frame(self.root, padding=(12, 6, 12, 8))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        settings = ttk.Frame(body)
        settings.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        settings.columnconfigure(0, weight=1)

        self._build_settings(settings)
        self._build_message_area(body)

        status = ttk.Label(self.root, textvariable=self.status_var, style="Status.TLabel", anchor="w")
        status.grid(row=2, column=0, sticky="ew")

    def _build_settings(self, parent: ttk.Frame) -> None:
        touch_frame = ttk.LabelFrame(parent, text="Enigma Touch Settings", padding=10)
        touch_frame.grid(row=0, column=0, sticky="ew")
        touch_frame.columnconfigure(1, weight=1)
        self._settings_row(touch_frame, 0, "Model", self.model_var, "?MO", self.read_model)
        self._settings_row(touch_frame, 1, "Reflector", self.reflector_var)
        self._settings_row(touch_frame, 2, "Rotors", self.rotors_var)
        ttk.Button(touch_frame, text="?RO", width=5, command=self.read_rotor_set).grid(
            row=1, column=2, rowspan=2, sticky="nsew", pady=(6, 0)
        )
        self._settings_row(touch_frame, 3, "Rings", self.rings_var, "?RI", self.read_rings)
        self._settings_row(touch_frame, 4, "Position", self.positions_var, "?RP", self.read_positions)
        self._settings_row(touch_frame, 5, "Plugboard", self.pairs_var, "?PB", self.read_plugboard)
        self._settings_row(touch_frame, 6, "Reflector D", self.reflector_d_var, "?RD", self.read_reflector_d)

        uhr_frame = ttk.LabelFrame(parent, text="Uhr Device", padding=10)
        uhr_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        uhr_frame.columnconfigure(1, weight=1)
        ttk.Label(uhr_frame, text="Position").grid(row=0, column=0, sticky="w")
        self.uhr_combo = ttk.Combobox(
            uhr_frame,
            textvariable=self.uhr_var,
            values=tuple(f"{position:02d}" for position in range(40)),
            state="readonly",
            width=8,
        )
        self.uhr_combo.grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        self.uhr_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_mapping_preview())
        ttk.Checkbutton(
            uhr_frame,
            text="Enable Ahistoric Uhr Device",
            variable=self.ahistoric_var,
            command=self.update_mapping_preview,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        output_frame = ttk.LabelFrame(parent, text="Output", padding=10)
        output_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Letters Per Group").grid(row=0, column=0, sticky="w")
        self.group_spin = ttk.Spinbox(output_frame, from_=0, to=10, textvariable=self.group_var, width=8)
        self.group_spin.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Checkbutton(
            output_frame,
            text="Keep Spaces and Punctuation",
            variable=self.preserve_nonletters_var,
            command=self.update_output_options,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.update_output_options()

        map_frame = ttk.LabelFrame(parent, text="Map", padding=10)
        map_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        self.map_text = tk.Text(map_frame, width=48, height=9, wrap="word", font=("Consolas", 9), relief="flat")
        self.map_text.grid(row=0, column=0, sticky="nsew")
        self.map_text.configure(state="disabled")

    def _settings_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        button_text: str | None = None,
        command: Callable[[], None] | None = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 6, 0))
        ttk.Entry(parent, textvariable=variable, width=28).grid(
            row=row, column=1, sticky="ew", padx=(8, 6), pady=(0 if row == 0 else 6, 0)
        )
        if button_text and command:
            ttk.Button(parent, text=button_text, width=5, command=command).grid(
                row=row, column=2, sticky="e", pady=(0 if row == 0 else 6, 0)
            )

    def _build_message_area(self, parent: ttk.Frame) -> None:
        messages = ttk.Frame(parent)
        messages.grid(row=0, column=1, sticky="nsew")
        messages.columnconfigure(0, weight=1)
        messages.rowconfigure(1, weight=1)
        messages.rowconfigure(2, weight=1)

        controls = ttk.Frame(messages)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.convert_button = ttk.Button(
            controls, text="Convert", style="Primary.TButton", command=self.convert_text
        )
        self.convert_button.grid(
            row=0, column=0, padx=(0, 8)
        )
        self.stop_button = ttk.Button(controls, text="Stop", command=self.stop_conversion, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(controls, text="Clear", command=self.clear_text).grid(row=0, column=2)
        ttk.Checkbutton(
            controls,
            text="Update Position Before Convert",
            variable=self.refresh_position_var,
        ).grid(row=0, column=3, padx=(12, 0))

        input_frame = ttk.LabelFrame(messages, text="Message", padding=8)
        input_frame.grid(row=1, column=0, sticky="nsew")
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)
        self.input_text = scrolledtext.ScrolledText(input_frame, height=8, wrap="word", font=("Consolas", 11))
        self.input_text.grid(row=0, column=0, sticky="nsew")

        output_frame = ttk.LabelFrame(messages, text="Result", padding=8)
        output_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output_text = scrolledtext.ScrolledText(output_frame, height=8, wrap="word", font=("Consolas", 11))
        self.output_text.grid(row=0, column=0, sticky="nsew")

    def refresh_ports(self, *, show_errors: bool = True) -> None:
        try:
            ports = list_serial_ports()
        except RuntimeError as exc:
            self.port_combo.configure(values=())
            self.set_status(str(exc))
            if show_errors:
                messagebox.showerror("Serial Ports", str(exc))
            return

        self.port_combo.configure(values=ports)
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        self.set_status(f"{len(ports)} serial port(s) found" if ports else "No serial ports found")

    def read_touch_settings(self) -> None:
        try:
            config = self.serial_config()
        except ValueError as exc:
            messagebox.showerror("Read Enigma Touch Settings", str(exc))
            return

        def task() -> TouchSettings:
            responses = query_touch_commands(
                config,
                ("?MO", "?RO", "?RI", "?RP", "?PB", "?RD"),
                query_delay=1.0,
            )
            return parse_touch_settings(responses)

        def success(result: object) -> None:
            settings = result if isinstance(result, TouchSettings) else None
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
            messagebox.showerror("Read Enigma Touch Settings", str(exc))
            return

        def task() -> str:
            return query_touch_command(config, command, query_delay=1.0)

        def success(result: object) -> None:
            response = str(result)
            try:
                self.apply_single_setting(command, response)
            except ValueError as exc:
                messagebox.showerror("Read Enigma Touch Settings", str(exc))
                return
            self.set_status(f"Read {command}")

        self.start_task(f"Reading {command}...", task, success)

    def apply_single_setting(self, command: str, response: str) -> None:
        if command == "?MO":
            self.model_var.set(parse_model_response(response))
            return
        if command == "?RO":
            reflector, rotors = parse_rotor_response(response)
            self.reflector_var.set(reflector)
            self.rotors_var.set(" ".join(rotors))
            return
        if command == "?RI":
            self.rings_var.set(value_after_label(response, "Rings"))
            return
        if command == "?RP":
            self.positions_var.set(value_after_label(response, "Positions"))
            return
        if command == "?PB":
            self.pairs_var.set(parse_pair_response(response, "Plugboard"))
            self.update_mapping_preview()
            return
        if command == "?RD":
            self.reflector_d_var.set(parse_pair_response(response, "UKW D"))
            return
        raise ValueError(f"Unknown setting command {command!r}.")

    def apply_touch_settings(self, settings: TouchSettings) -> None:
        self.model_var.set(settings.model)
        self.reflector_var.set(settings.reflector)
        self.rotors_var.set(" ".join(settings.rotors))
        self.rings_var.set(settings.rings_display())
        self.positions_var.set(settings.positions_display())
        self.pairs_var.set(settings.plugboard_pairs)
        self.reflector_d_var.set(settings.reflector_d_pairs)
        self.update_mapping_preview()

    def convert_text(self) -> None:
        if self.refresh_position_var.get():
            self.refresh_position_then_convert()
            return
        self.start_conversion()

    def refresh_position_then_convert(self) -> None:
        try:
            config = self.serial_config()
        except ValueError as exc:
            messagebox.showerror("Serial", str(exc))
            return

        def task() -> str:
            return query_touch_command(config, "?RP", query_delay=1.0)

        def success(result: object) -> None:
            try:
                self.apply_single_setting("?RP", str(result))
            except ValueError as exc:
                messagebox.showerror("Read Enigma Touch Settings", str(exc))
                return
            self.start_conversion()

        self.start_task("Updating rotor position...", task, success)

    def start_conversion(self) -> None:
        try:
            adapter = self.build_adapter()
            settings = self.build_touch_settings()
            ahistoric = self.ahistoric_var.get()
            settings.require_uhr_supported(ahistoric=ahistoric)
            machine = machine_from_touch_settings(settings, adapter.plugboard, ahistoric=ahistoric)
            preserve_nonletters = self.preserve_nonletters_var.get()
            group = 0 if preserve_nonletters else self.group_size()
        except ValueError as exc:
            messagebox.showerror("Settings", str(exc))
            return

        text = self.input_text.get("1.0", "end-1c")

        try:
            config = self.serial_config()
        except ValueError as exc:
            messagebox.showerror("Serial", str(exc))
            return
        backend_factory = lambda: SerialBackend(config)
        status = "Converting through Enigma Touch..."
        self.set_text(self.output_text, "")
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
                        preserve_nonletters=preserve_nonletters,
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

        def success(result: object) -> None:
            output, final_positions, stopped, completed_letters, total_letters = result
            self.set_text(self.output_text, format_groups(str(output), group))
            self.positions_var.set(format_setting_values(final_positions, numeric=settings.uses_numeric_labels))
            if stopped:
                self.set_status(f"Conversion stopped at {completed_letters}/{total_letters}")
            else:
                self.set_status("Conversion complete")

        def progress(value: object) -> None:
            if isinstance(value, ConversionProgress):
                self.set_text(self.output_text, format_groups(value.output_text, group))
                self.set_status(
                    f"Converting through Enigma Touch... {value.completed_letters}/{value.total_letters}"
                )

        self.start_task(status, task, success, progress=progress)

    def stop_conversion(self) -> None:
        if not self.busy or not self.conversion_active:
            return
        self.stop_requested.set()
        backend = self.active_backend
        if backend is not None:
            backend.request_stop()
        self.stop_button.configure(state="disabled")
        self.set_status("Stopping conversion...")

    def clear_text(self) -> None:
        for widget in (self.input_text, self.output_text):
            self.set_text(widget, "")
        self.set_status("Cleared")

    def update_output_options(self) -> None:
        state = "disabled" if self.preserve_nonletters_var.get() else "normal"
        self.group_spin.configure(state=state)

    def show_help(self) -> None:
        self.show_text_dialog("Help", HELP_TEXT, geometry="760x720")

    def show_about(self) -> None:
        self.show_text_dialog("About", about_text(), geometry="680x500")

    def show_license(self) -> None:
        self.show_text_dialog("License", MIT_LICENSE_TEXT, geometry="720x560")

    def show_text_dialog(self, title: str, text: str, *, geometry: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Enigma Touch - Uhr Device - {title}")
        dialog.geometry(geometry)
        dialog.minsize(520, 360)
        dialog.transient(self.root)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        content = scrolledtext.ScrolledText(dialog, wrap="word", font=("Segoe UI", 10), padx=12, pady=12)
        content.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
        content.insert("1.0", text.strip())
        content.configure(state="disabled")
        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(row=1, column=0, pady=(0, 10))

    def build_adapter(self) -> UhrAdapter:
        ahistoric = self.ahistoric_var.get()
        plugboard = Plugboard.parse(self.pairs_var.get(), ahistoric=ahistoric)
        try:
            position = int(self.uhr_var.get())
        except ValueError as exc:
            raise ValueError("Uhr position must be a number from 0 to 39.") from exc
        uhr = Uhr(plugboard, position, ahistoric=ahistoric)
        return UhrAdapter(plugboard, uhr)

    def build_touch_settings(self) -> TouchSettings:
        if not self.model_var.get().strip():
            raise ValueError("Read Enigma Touch settings before converting.")
        return build_touch_settings(
            model=self.model_var.get(),
            reflector=self.reflector_var.get(),
            rotors=self.rotors_var.get(),
            rings=self.rings_var.get(),
            positions=self.positions_var.get(),
            plugboard_pairs=self.pairs_var.get(),
            reflector_d_pairs=self.reflector_d_var.get(),
        )

    def update_mapping_preview(self) -> None:
        try:
            adapter = self.build_adapter()
            text = mapping_lines(adapter)
            self.set_status("Map updated")
        except ValueError as exc:
            text = str(exc)
        self.set_text(self.map_text, text, readonly=True)

    def serial_config(self) -> SerialConfig:
        port = extract_port_device(self.port_var.get())
        try:
            baud = int(self.baud_var.get())
        except ValueError as exc:
            raise ValueError("Baud must be a whole number.") from exc
        try:
            timeout = float(self.timeout_var.get())
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

    def group_size(self) -> int:
        try:
            group = int(self.group_var.get())
        except ValueError as exc:
            raise ValueError("Group size must be a whole number.") from exc
        if group < 0:
            raise ValueError("Group size cannot be negative.")
        return group

    def start_task(
        self,
        status: str,
        task: Callable[..., object],
        success: Callable[[object], None],
        *,
        progress: Callable[[object], None] | None = None,
    ) -> None:
        if self.busy:
            self.set_status("Busy")
            return
        self.busy = True
        self.pending_success = success
        self.pending_progress = progress
        self.set_busy_controls(False)
        self.set_status(status)

        def runner() -> None:
            try:
                if progress:
                    result = task(lambda value: self.task_queue.put(("progress", value)))
                else:
                    result = task()
                self.task_queue.put(("ok", result))
            except Exception as exc:
                self.task_queue.put(("error", exc))

        threading.Thread(target=runner, daemon=True).start()

    def poll_tasks(self) -> None:
        while True:
            try:
                kind, payload = self.task_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "progress":
                progress = self.pending_progress
                if progress:
                    progress(payload)
                continue

            self.busy = False
            self.conversion_active = False
            self.set_busy_controls(True)
            success = self.pending_success
            self.pending_success = None
            self.pending_progress = None

            if kind == "ok" and success:
                success(payload)
            elif kind == "error":
                messagebox.showerror("Enigma Touch - Uhr Device", str(payload))
                self.set_status("Error")

        self.root.after(50, self.poll_tasks)

    def set_busy_controls(self, enabled: bool) -> None:
        self.convert_button.configure(state="normal" if enabled else "disabled")
        stop_enabled = self.busy and self.conversion_active and not self.stop_requested.is_set()
        self.stop_button.configure(state="normal" if stop_enabled else "disabled")

    def set_text(self, widget: tk.Text, text: str, *, readonly: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        if readonly:
            widget.configure(state="disabled")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = tk.Tk()
    if "--smoke-test" in args:
        root.withdraw()
        EnigmaUhrApp(root)
        root.update_idletasks()
        root.destroy()
        return 0
    EnigmaUhrApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
