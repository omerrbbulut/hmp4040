#!/usr/bin/env python3
from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass
from typing import Optional

import pyvisa
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)


# ============================================================
# Models
# ============================================================

@dataclass
class ChannelSummary:
    channel: int
    set_voltage: float
    measured_voltage: float
    current_limit: float
    measured_current: float
    output_state: int
    fuse_state: int
    fuse_tripped: int


@dataclass
class ChannelDetails:
    channel: int
    set_voltage: float
    measured_voltage: float
    current_limit: float
    measured_current: float
    ovp_limit: float
    ovp_mode: str
    output_state: int
    fuse_state: int
    fuse_delay: str
    fuse_tripped: int
    fuse_links: dict[int, bool]


@dataclass
class DeviceSnapshot:
    idn: str
    global_output: Optional[int]
    channels: list[ChannelSummary]
    selected: ChannelDetails


# ============================================================
# Device / service layer
# ============================================================

class HMP4040Service:
    def __init__(self, host: str, port: int = 5025, timeout_ms: int = 3000):
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.rm = None
        self.ps = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        with self._lock:
            self.rm = pyvisa.ResourceManager()
            resource = f"TCPIP::{self.host}::{self.port}::SOCKET"
            self.ps = self.rm.open_resource(resource)
            self.ps.timeout = self.timeout_ms
            self.ps.read_termination = "\n"
            self.ps.write_termination = "\n"

    def close(self) -> None:
        with self._lock:
            if self.ps is not None:
                try:
                    self.ps.close()
                except Exception:
                    pass
                self.ps = None
            if self.rm is not None:
                try:
                    self.rm.close()
                except Exception:
                    pass
                self.rm = None

    def _ensure(self) -> None:
        if self.ps is None:
            raise RuntimeError("Device not connected")

    def _query_str_unlocked(self, cmd: str) -> str:
        self._ensure()
        return self.ps.query(cmd).strip()

    def _query_int_unlocked(self, cmd: str) -> int:
        return int(self._query_str_unlocked(cmd))

    def _query_float_unlocked(self, cmd: str) -> float:
        return float(self._query_str_unlocked(cmd))

    def _write_unlocked(self, cmd: str) -> None:
        self._ensure()
        self.ps.write(cmd)

    def _select_channel_unlocked(self, channel: int) -> None:
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1..4")
        self._write_unlocked(f"INSTrument:NSELect {channel}")

    # -------- basic --------

    def idn(self) -> str:
        with self._lock:
            return self._query_str_unlocked("*IDN?")

    def reset(self) -> None:
        with self._lock:
            self._write_unlocked("*RST")

    def raw_query(self, cmd: str) -> str:
        with self._lock:
            return self._query_str_unlocked(cmd)

    def raw_write(self, cmd: str) -> None:
        with self._lock:
            self._write_unlocked(cmd)

    # -------- outputs --------

    def set_channel_output(self, channel: int, on: bool) -> None:
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"OUTPut:STATe {1 if on else 0}")

    def get_channel_output(self, channel: int) -> int:
        with self._lock:
            self._select_channel_unlocked(channel)
            return self._query_int_unlocked("OUTPut:STATe?")

    def set_global_output(self, on: bool) -> None:
        with self._lock:
            self._write_unlocked(f"OUTPut:GENeral {1 if on else 0}")

    def get_global_output(self) -> Optional[int]:
        # Some instruments may not support a direct query here reliably.
        # Try common form; if unavailable, return None.
        with self._lock:
            try:
                return self._query_int_unlocked("OUTPut:GENeral?")
            except Exception:
                return None

    def enable_selected_plus_global(self, channel: int) -> tuple[int, Optional[int]]:
        self.set_channel_output(channel, True)
        self.set_global_output(True)
        ch_state = self.get_channel_output(channel)
        global_state = self.get_global_output()
        return ch_state, global_state

    def disable_selected_channel(self, channel: int) -> int:
        self.set_channel_output(channel, False)
        return self.get_channel_output(channel)

    def enable_selected_channel(self, channel: int) -> int:
        self.set_channel_output(channel, True)
        return self.get_channel_output(channel)

    def enable_global_only(self) -> Optional[int]:
        self.set_global_output(True)
        return self.get_global_output()

    def disable_global_only(self) -> Optional[int]:
        self.set_global_output(False)
        return self.get_global_output()

    # -------- channel --------

    def set_voltage(self, channel: int, value: float) -> None:
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"SOURce:VOLTage {value}")

    def set_current(self, channel: int, value: float) -> None:
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"SOURce:CURRent {value}")

    def get_channel_summary(self, channel: int) -> ChannelSummary:
        with self._lock:
            self._select_channel_unlocked(channel)
            return ChannelSummary(
                channel=channel,
                set_voltage=self._query_float_unlocked("SOURce:VOLTage?"),
                measured_voltage=self._query_float_unlocked("MEASure:VOLTage?"),
                current_limit=self._query_float_unlocked("SOURce:CURRent?"),
                measured_current=self._query_float_unlocked("MEASure:CURRent?"),
                output_state=self._query_int_unlocked("OUTPut:STATe?"),
                fuse_state=self._query_int_unlocked("FUSE?"),
                fuse_tripped=self._query_int_unlocked("FUSE:TRIPped?"),
            )

    def get_channel_details(self, channel: int) -> ChannelDetails:
        with self._lock:
            self._select_channel_unlocked(channel)

            details = ChannelDetails(
                channel=channel,
                set_voltage=self._query_float_unlocked("SOURce:VOLTage?"),
                measured_voltage=self._query_float_unlocked("MEASure:VOLTage?"),
                current_limit=self._query_float_unlocked("SOURce:CURRent?"),
                measured_current=self._query_float_unlocked("MEASure:CURRent?"),
                ovp_limit=self._query_float_unlocked("VOLTage:PROTection?"),
                ovp_mode=self._query_str_unlocked("VOLTage:PROTection:MODE?"),
                output_state=self._query_int_unlocked("OUTPut:STATe?"),
                fuse_state=self._query_int_unlocked("FUSE?"),
                fuse_delay=self._query_str_unlocked("FUSE:DELay?"),
                fuse_tripped=self._query_int_unlocked("FUSE:TRIPped?"),
                fuse_links={},
            )

            links: dict[int, bool] = {}
            for target in (1, 2, 3, 4):
                if target == channel:
                    continue
                links[target] = bool(self._query_int_unlocked(f"FUSE:LINK? {target}"))
            details.fuse_links = links
            return details

    def get_all_channel_summaries(self) -> list[ChannelSummary]:
        return [self.get_channel_summary(ch) for ch in (1, 2, 3, 4)]

    # -------- fuse --------

    def set_fuse(self, channel: int, on: bool) -> None:
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"FUSE {'ON' if on else 'OFF'}")

    def get_fuse_status(self, channel: int) -> int:
        with self._lock:
            self._select_channel_unlocked(channel)
            return self._query_int_unlocked("FUSE?")

    def set_fuse_delay(self, channel: int, delay_ms: int) -> None:
        if not (0 <= delay_ms <= 250):
            raise ValueError("Fuse delay must be between 0 and 250 ms")
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"FUSE:DELay {delay_ms}")

    def get_fuse_delay(self, channel: int) -> str:
        with self._lock:
            self._select_channel_unlocked(channel)
            return self._query_str_unlocked("FUSE:DELay?")

    def get_fuse_trip(self, channel: int) -> int:
        with self._lock:
            self._select_channel_unlocked(channel)
            return self._query_int_unlocked("FUSE:TRIPped?")

    def fuse_link(self, channel: int, target: int) -> None:
        if channel == target:
            raise ValueError("Source and target cannot be the same")
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"FUSE:LINK {target}")

    def fuse_unlink(self, channel: int, target: int) -> None:
        if channel == target:
            raise ValueError("Source and target cannot be the same")
        with self._lock:
            self._select_channel_unlocked(channel)
            self._write_unlocked(f"FUSE:UNLink {target}")

    def get_fuse_links(self, channel: int) -> dict[int, bool]:
        with self._lock:
            self._select_channel_unlocked(channel)
            result = {}
            for target in (1, 2, 3, 4):
                if target == channel:
                    continue
                result[target] = bool(self._query_int_unlocked(f"FUSE:LINK? {target}"))
            return result

    # -------- snapshot --------

    def get_snapshot(self, selected_channel: int) -> DeviceSnapshot:
        return DeviceSnapshot(
            idn=self.idn(),
            global_output=self.get_global_output(),
            channels=self.get_all_channel_summaries(),
            selected=self.get_channel_details(selected_channel),
        )


# ============================================================
# TUI
# ============================================================

class HMP4040TUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #topbar {
        height: auto;
        border: round $panel;
        margin: 1;
        padding: 1;
    }

    #button_row {
        height: auto;
        margin-top: 1;
    }

    #button_row Button {
        margin-right: 1;
        margin-bottom: 1;
        min-width: 16;
    }

    #main_tabs {
        height: 1fr;
        margin: 0 1 1 1;
    }

    .section {
        border: round $panel;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    .row {
        layout: horizontal;
        height: auto;
    }

    .col {
        width: 1fr;
        min-width: 28;
        margin-right: 1;
    }

    .stack Button {
        margin-bottom: 1;
        width: 100%;
    }

    .field_label {
        margin-bottom: 1;
    }

    .field_input {
        margin-bottom: 1;
    }

    #monitor_box, #raw_result_box, #system_box {
        border: round $panel;
        padding: 1;
        height: 1fr;
    }

    #monitor_view, #raw_result_view, #system_view, #log_view {
        height: 1fr;
        overflow: auto;
    }

    #log_box {
        border: round $panel;
        padding: 1;
        margin: 0 1 1 1;
        height: 8;
    }

    TabPane {
        overflow-y: auto;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_now", "Refresh"),
    ]

    def __init__(self, host: str, port: int = 5025, timeout_ms: int = 3000):
        super().__init__()
        self.service = HMP4040Service(host=host, port=port, timeout_ms=timeout_ms)
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.connected = False
        self.idn_value = "Not connected"
        self.selected_channel = 1
        self.log_lines: list[str] = []
        self.last_snapshot: Optional[DeviceSnapshot] = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="topbar"):
            yield Static(f"Target: {self.host}:{self.port}", id="target_text")
            yield Static("Connection: disconnected", id="status_text")
            yield Static("IDN: -", id="idn_text")

            with Horizontal(id="button_row"):
                yield Button("Connect", id="connect_btn", variant="success")
                yield Button("Refresh", id="refresh_btn")
                yield Button("Reset Device", id="reset_btn", variant="warning")
                yield Button("Global Output ON", id="global_on_btn", variant="primary")
                yield Button("Global Output OFF", id="global_off_btn", variant="error")

        with TabbedContent(id="main_tabs"):
            with TabPane("Overview"):
                with Container(id="monitor_box"):
                    yield Static("No data yet.", id="monitor_view")

            with TabPane("Channel"):
                with Container(classes="section"):
                    yield Static("Selected channel")
                    yield Select(
                        [(f"CH{i}", i) for i in range(1, 5)],
                        value=1,
                        id="channel_select",
                    )

                with Container(classes="section"):
                    yield Static("Voltage / Current")
                    yield Static("Voltage (V)", classes="field_label")
                    yield Input(placeholder="e.g. 5.0", id="voltage_input", classes="field_input")
                    yield Button("Apply Voltage", id="apply_voltage_btn", variant="primary")

                    yield Static("Current limit (A)", classes="field_label")
                    yield Input(placeholder="e.g. 1.5", id="current_input", classes="field_input")
                    yield Button("Apply Current", id="apply_current_btn", variant="primary")

                with Container(classes="section"):
                    yield Static("Channel Output Controls")
                    with Vertical(classes="stack"):
                        yield Button("Selected Channel ON", id="output_on_btn", variant="success")
                        yield Button("Selected Channel OFF", id="output_off_btn", variant="error")
                        yield Button("Selected + Global ON", id="selected_plus_global_on_btn", variant="primary")
                        yield Button("Global ON", id="global_on_local_btn")
                        yield Button("Global OFF", id="global_off_local_btn")

                with Container(classes="section"):
                    yield Static("Channel Status")
                    yield Static("No data yet.", id="channel_status_view")

            with TabPane("Fuse"):
                with Container(classes="section"):
                    with Horizontal(classes="row"):
                        with Vertical(classes="col stack"):
                            yield Button("Fuse ON", id="fuse_on_btn", variant="success")
                            yield Button("Fuse OFF", id="fuse_off_btn", variant="error")
                            yield Button("Read Fuse Status", id="fuse_status_btn")

                        with Vertical(classes="col"):
                            yield Static("Fuse delay (ms)", classes="field_label")
                            yield Input(placeholder="0..250", id="fuse_delay_input", classes="field_input")
                            yield Button("Apply Fuse Delay", id="apply_fuse_delay_btn", variant="primary")
                            yield Button("Read Fuse Delay", id="read_fuse_delay_btn")
                            yield Button("Read Fuse Trip", id="read_fuse_trip_btn")

                with Container(classes="section"):
                    with Horizontal(classes="row"):
                        with Vertical(classes="col"):
                            yield Static("Source channel", classes="field_label")
                            yield Select(
                                [(f"CH{i}", i) for i in range(1, 5)],
                                value=1,
                                id="fuse_source_select",
                            )

                        with Vertical(classes="col"):
                            yield Static("Target channel", classes="field_label")
                            yield Select(
                                [(f"CH{i}", i) for i in range(1, 5)],
                                value=2,
                                id="fuse_target_select",
                            )

                        with Vertical(classes="col stack"):
                            yield Button("Link", id="fuse_link_btn", variant="primary")
                            yield Button("Unlink", id="fuse_unlink_btn")
                            yield Button("Read Links", id="fuse_links_btn")

                with Container(classes="section"):
                    yield Static("Fuse View")
                    yield Static("No data yet.", id="fuse_view")

            with TabPane("Raw SCPI"):
                with Container(classes="section"):
                    yield Static("SCPI command")
                    yield Input(placeholder='e.g. *IDN? or INSTrument:NSELect 1', id="raw_input")
                    with Horizontal(classes="row"):
                        yield Button("Send Query", id="raw_query_btn", variant="primary")
                        yield Button("Send Write", id="raw_write_btn")

                with Container(id="raw_result_box"):
                    yield Static("Raw response will appear here.", id="raw_result_view")

            with TabPane("System"):
                with Container(id="system_box"):
                    yield Static("No data yet.", id="system_view")

        with Container(id="log_box"):
            yield Static("Log")
            yield Static("", id="log_view")

        yield Footer()

    def on_mount(self) -> None:
        self._set_connection_status("connecting...")
        self.connect_worker()
        self.set_interval(4.0, self.periodic_refresh)

    # ---------------- UI helpers ----------------

    def _set_connection_status(self, text: str) -> None:
        self.query_one("#status_text", Static).update(f"Connection: {text}")

    def _set_idn(self, text: str) -> None:
        self.query_one("#idn_text", Static).update(f"IDN: {text}")

    def append_log(self, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {message}")
        self.log_lines = self.log_lines[-200:]
        try:
            self.query_one("#log_view", Static).update("\n".join(self.log_lines[-15:]))
        except Exception:
            pass

    def _render_channel_status(self, d: ChannelDetails, global_output: Optional[int]) -> None:
        global_text = "UNKNOWN" if global_output is None else ("ON" if global_output else "OFF")
        text = "\n".join(
            [
                f"Channel: CH{d.channel}",
                f"Set voltage      : {d.set_voltage:.3f} V",
                f"Measured voltage : {d.measured_voltage:.3f} V",
                f"Current limit    : {d.current_limit:.3f} A",
                f"Measured current : {d.measured_current:.3f} A",
                f"Channel output   : {'ON' if d.output_state else 'OFF'}",
                f"Global output    : {global_text}",
                f"OVP limit        : {d.ovp_limit:.3f} V",
                f"OVP mode         : {d.ovp_mode}",
            ]
        )
        self.query_one("#channel_status_view", Static).update(text)

    def _render_fuse_view(self, d: ChannelDetails) -> None:
        lines = [
            f"Channel: CH{d.channel}",
            f"Fuse state : {'ON' if d.fuse_state else 'OFF'}",
            f"Fuse delay : {d.fuse_delay} ms",
            f"Fuse trip  : {'YES' if d.fuse_tripped else 'NO'}",
            "Links:",
        ]
        for target in (1, 2, 3, 4):
            if target == d.channel:
                continue
            lines.append(f"  CH{target}: {'YES' if d.fuse_links.get(target, False) else 'NO'}")
        self.query_one("#fuse_view", Static).update("\n".join(lines))

    def _render_monitor(self, snap: DeviceSnapshot) -> None:
        global_text = "UNKNOWN" if snap.global_output is None else ("ON" if snap.global_output else "OFF")
        lines = [
            f"Device: {snap.idn}",
            f"Global output: {global_text}",
            "",
            "All channels:",
        ]
        for s in snap.channels:
            lines.append(
                f"CH{s.channel} | "
                f"Set {s.set_voltage:.3f} V | "
                f"Meas {s.measured_voltage:.3f} V | "
                f"ILim {s.current_limit:.3f} A | "
                f"IMeas {s.measured_current:.3f} A | "
                f"ChOut {'ON' if s.output_state else 'OFF'} | "
                f"Fuse {'ON' if s.fuse_state else 'OFF'} | "
                f"Trip {'YES' if s.fuse_tripped else 'NO'}"
            )
        self.query_one("#monitor_view", Static).update("\n".join(lines))

    def _render_system(self, snap: DeviceSnapshot) -> None:
        global_text = "UNKNOWN" if snap.global_output is None else ("ON" if snap.global_output else "OFF")
        text = "\n".join(
            [
                f"Host          : {self.host}",
                f"Port          : {self.port}",
                f"Timeout (ms)  : {self.timeout_ms}",
                f"Connected     : {'YES' if self.connected else 'NO'}",
                f"IDN           : {snap.idn}",
                f"Global output : {global_text}",
                f"Selected ch   : CH{self.selected_channel}",
            ]
        )
        self.query_one("#system_view", Static).update(text)

    # ---------------- refresh / connect ----------------

    def periodic_refresh(self) -> None:
        if self.connected:
            self.refresh_worker(self.selected_channel)

    @work(exclusive=True, thread=True)
    def connect_worker(self) -> None:
        try:
            self.service.connect()
            idn = self.service.idn()
            self.call_from_thread(self._on_connected, idn)
        except Exception as exc:
            self.call_from_thread(self._on_connect_error, str(exc))

    def _on_connected(self, idn: str) -> None:
        self.connected = True
        self.idn_value = idn
        self._set_connection_status("connected")
        self._set_idn(idn)
        self.append_log(f"Connected: {idn}")
        self.refresh_worker(self.selected_channel)

    def _on_connect_error(self, error: str) -> None:
        self.connected = False
        self._set_connection_status(f"failed: {error}")
        self.append_log(f"Connection failed: {error}")

    @work(exclusive=True, thread=True)
    def refresh_worker(self, channel: int) -> None:
        try:
            snap = self.service.get_snapshot(channel)
            self.call_from_thread(self._apply_refresh, snap)
        except Exception as exc:
            self.call_from_thread(self._on_refresh_error, str(exc))

    def _apply_refresh(self, snap: DeviceSnapshot) -> None:
        self.last_snapshot = snap
        self._render_monitor(snap)
        self._render_channel_status(snap.selected, snap.global_output)
        self._render_fuse_view(snap.selected)
        self._render_system(snap)
        self._set_connection_status("connected")
        self._set_idn(snap.idn)

    def _on_refresh_error(self, error: str) -> None:
        self._set_connection_status(f"refresh failed: {error}")
        self.append_log(f"Refresh failed: {error}")

    # ---------------- actions ----------------

    @work(exclusive=True, thread=True)
    def action_worker(self, action: str, value1=None, value2=None) -> None:
        try:
            ch = self.selected_channel

            if action == "set_voltage":
                self.service.set_voltage(ch, float(value1))
            elif action == "set_current":
                self.service.set_current(ch, float(value1))
            elif action == "output_on":
                ch_state = self.service.enable_selected_channel(ch)
                self.call_from_thread(self._handle_info_message, f"CH{ch} output readback: {'ON' if ch_state else 'OFF'}")
                return
            elif action == "output_off":
                ch_state = self.service.disable_selected_channel(ch)
                self.call_from_thread(self._handle_info_message, f"CH{ch} output readback: {'ON' if ch_state else 'OFF'}")
                return
            elif action == "selected_plus_global_on":
                ch_state, global_state = self.service.enable_selected_plus_global(ch)
                gtxt = "UNKNOWN" if global_state is None else ("ON" if global_state else "OFF")
                self.call_from_thread(self._handle_info_message, f"CH{ch}+GLOBAL readback: channel={'ON' if ch_state else 'OFF'}, global={gtxt}")
                return
            elif action == "global_on":
                global_state = self.service.enable_global_only()
                gtxt = "UNKNOWN" if global_state is None else ("ON" if global_state else "OFF")
                self.call_from_thread(self._handle_info_message, f"Global output readback: {gtxt}")
                return
            elif action == "global_off":
                global_state = self.service.disable_global_only()
                gtxt = "UNKNOWN" if global_state is None else ("ON" if global_state else "OFF")
                self.call_from_thread(self._handle_info_message, f"Global output readback: {gtxt}")
                return
            elif action == "fuse_on":
                self.service.set_fuse(ch, True)
            elif action == "fuse_off":
                self.service.set_fuse(ch, False)
            elif action == "fuse_delay":
                self.service.set_fuse_delay(ch, int(value1))
            elif action == "fuse_link":
                self.service.fuse_link(int(value1), int(value2))
            elif action == "fuse_unlink":
                self.service.fuse_unlink(int(value1), int(value2))
            elif action == "reset":
                self.service.reset()
            elif action == "raw_query":
                result = self.service.raw_query(str(value1))
                self.call_from_thread(self._on_raw_query_result, str(value1), result)
                return
            elif action == "raw_write":
                self.service.raw_write(str(value1))
                self.call_from_thread(self._on_raw_write_result, str(value1))
                return
            elif action == "fuse_status_read":
                state = self.service.get_fuse_status(ch)
                self.call_from_thread(self._handle_info_message, f"CH{ch} fuse state: {'ON' if state else 'OFF'}")
                return
            elif action == "fuse_delay_read":
                delay = self.service.get_fuse_delay(ch)
                self.call_from_thread(self._handle_info_message, f"CH{ch} fuse delay: {delay} ms")
                return
            elif action == "fuse_trip_read":
                trip = self.service.get_fuse_trip(ch)
                self.call_from_thread(self._handle_info_message, f"CH{ch} fuse trip: {'YES' if trip else 'NO'}")
                return
            elif action == "fuse_links_read":
                links = self.service.get_fuse_links(ch)
                text = ", ".join([f"CH{k}={'YES' if v else 'NO'}" for k, v in links.items()])
                self.call_from_thread(self._handle_info_message, f"CH{ch} fuse links: {text}")
                return
            else:
                raise ValueError(f"Unknown action: {action}")

            self.call_from_thread(self._on_action_success, action, value1, value2)
        except Exception as exc:
            self.call_from_thread(self._on_action_error, str(exc))

    def _on_action_success(self, action: str, value1=None, value2=None) -> None:
        messages = {
            "set_voltage": f"CH{self.selected_channel}: voltage set to {value1} V",
            "set_current": f"CH{self.selected_channel}: current limit set to {value1} A",
            "fuse_on": f"CH{self.selected_channel}: fuse ON",
            "fuse_off": f"CH{self.selected_channel}: fuse OFF",
            "fuse_delay": f"CH{self.selected_channel}: fuse delay set to {value1} ms",
            "fuse_link": f"Fuse link CH{value1} -> CH{value2}",
            "fuse_unlink": f"Fuse unlink CH{value1} -> CH{value2}",
            "reset": "Device reset sent",
        }
        self.append_log(messages.get(action, action))
        self.refresh_worker(self.selected_channel)

    def _on_action_error(self, error: str) -> None:
        self.append_log(f"Error: {error}")
        self._set_connection_status(f"action failed: {error}")

    def _handle_info_message(self, text: str) -> None:
        self.append_log(text)
        self.refresh_worker(self.selected_channel)

    def _on_raw_query_result(self, cmd: str, result: str) -> None:
        self.append_log(f"Raw query: {cmd}")
        self.query_one("#raw_result_view", Static).update(result)

    def _on_raw_write_result(self, cmd: str) -> None:
        self.append_log(f"Raw write: {cmd}")
        self.query_one("#raw_result_view", Static).update("Command sent.")
        self.refresh_worker(self.selected_channel)

    # ---------------- events ----------------

    def action_refresh_now(self) -> None:
        if self.connected:
            self.refresh_worker(self.selected_channel)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is None or event.value == Select.BLANK:
            return

        if event.select.id == "channel_select":
            self.selected_channel = int(event.value)
            self.query_one("#fuse_source_select", Select).value = int(event.value)
            if self.connected:
                self.refresh_worker(self.selected_channel)

        elif event.select.id == "fuse_source_select":
            self.selected_channel = int(event.value)
            self.query_one("#channel_select", Select).value = int(event.value)
            if self.connected:
                self.refresh_worker(self.selected_channel)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "connect_btn":
            self._set_connection_status("connecting...")
            self.connect_worker()
            return

        if not self.connected:
            self.append_log("Not connected.")
            return

        if bid == "refresh_btn":
            self.refresh_worker(self.selected_channel)
        elif bid == "reset_btn":
            self.action_worker("reset")
        elif bid == "global_on_btn":
            self.action_worker("global_on")
        elif bid == "global_off_btn":
            self.action_worker("global_off")

        elif bid == "apply_voltage_btn":
            self.action_worker("set_voltage", self.query_one("#voltage_input", Input).value.strip())
        elif bid == "apply_current_btn":
            self.action_worker("set_current", self.query_one("#current_input", Input).value.strip())
        elif bid == "output_on_btn":
            self.action_worker("output_on")
        elif bid == "output_off_btn":
            self.action_worker("output_off")
        elif bid == "selected_plus_global_on_btn":
            self.action_worker("selected_plus_global_on")
        elif bid == "global_on_local_btn":
            self.action_worker("global_on")
        elif bid == "global_off_local_btn":
            self.action_worker("global_off")

        elif bid == "fuse_on_btn":
            self.action_worker("fuse_on")
        elif bid == "fuse_off_btn":
            self.action_worker("fuse_off")
        elif bid == "apply_fuse_delay_btn":
            self.action_worker("fuse_delay", self.query_one("#fuse_delay_input", Input).value.strip())
        elif bid == "fuse_status_btn":
            self.action_worker("fuse_status_read")
        elif bid == "read_fuse_delay_btn":
            self.action_worker("fuse_delay_read")
        elif bid == "read_fuse_trip_btn":
            self.action_worker("fuse_trip_read")
        elif bid == "fuse_links_btn":
            self.action_worker("fuse_links_read")
        elif bid == "fuse_link_btn":
            source = int(self.query_one("#fuse_source_select", Select).value)
            target = int(self.query_one("#fuse_target_select", Select).value)
            self.action_worker("fuse_link", source, target)
        elif bid == "fuse_unlink_btn":
            source = int(self.query_one("#fuse_source_select", Select).value)
            target = int(self.query_one("#fuse_target_select", Select).value)
            self.action_worker("fuse_unlink", source, target)

        elif bid == "raw_query_btn":
            self.action_worker("raw_query", self.query_one("#raw_input", Input).value.strip())
        elif bid == "raw_write_btn":
            self.action_worker("raw_write", self.query_one("#raw_input", Input).value.strip())

    def on_unmount(self) -> None:
        self.service.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Friendly TUI for Rohde & Schwarz HMP4040")
    parser.add_argument("--host", default="10.42.0.232")
    parser.add_argument("--port", type=int, default=5025)
    parser.add_argument("--timeout", type=int, default=3000)
    args = parser.parse_args()

    app = HMP4040TUI(host=args.host, port=args.port, timeout_ms=args.timeout)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
