#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

import pyvisa

from hmp4040 import HMP4040


DEFAULT_HOST = os.getenv("HMP4040_HOST", "10.42.0.232")
DEFAULT_PORT = int(os.getenv("HMP4040_PORT", "5025"))
DEFAULT_TIMEOUT = int(os.getenv("HMP4040_TIMEOUT", "3000"))


def eprint(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


def fmt_bool(value: int | bool) -> str:
    return "ON" if int(value) else "OFF"


def validate_channel(value: str) -> int:
    try:
        channel = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("channel must be an integer") from exc

    if channel not in (1, 2, 3, 4):
        raise argparse.ArgumentTypeError("channel must be one of: 1, 2, 3, 4")

    return channel

def validate_nonnegative_float(value: str) -> float:
    v = float(value)
    if v < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return v


def validate_delay(value: str) -> int:
    try:
        v = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("delay must be an integer") from exc

    if not (0 <= v <= 250):
        raise argparse.ArgumentTypeError("delay must be between 0 and 250 ms")
    return v

def open_device(host: str, port: int, timeout_ms: int):
    rm = pyvisa.ResourceManager()
    resource = f"TCPIP::{host}::{port}::SOCKET"
    ps = rm.open_resource(resource)
    ps.timeout = timeout_ms
    ps.read_termination = "\n"
    ps.write_termination = "\n"
    return rm, ps


def qstr(ps, cmd: str) -> str:
    return ps.query(cmd).strip()


def qint(ps, cmd: str) -> int:
    return int(qstr(ps, cmd))


def qfloat(ps, cmd: str) -> float:
    return float(qstr(ps, cmd))


def select_channel(ps, channel: int) -> None:
    ps.write(f"INSTrument:NSELect {channel}")


def print_header(title: str) -> None:
    print(title)
    print("-" * len(title))


def print_kv(key: str, value) -> None:
    print(f"{key:<18} {value}")


def cmd_info(ps, _args) -> int:
    print(qstr(ps, "*IDN?"))
    return 0


def cmd_status(ps, _args) -> int:
    dev = HMP4040(ps)
    print(qstr(ps, "*IDN?"))
    print()
    for line in dev.get_inst_state():
        print(line)
    return 0


def cmd_ch_status(ps, args) -> int:
    select_channel(ps, args.channel)

    set_voltage = qfloat(ps, "SOURce:VOLTage?")
    current_limit = qfloat(ps, "SOURce:CURRent?")
    measured_voltage = qfloat(ps, "MEASure:VOLTage?")
    measured_current = qfloat(ps, "MEASure:CURRent?")
    ovp_limit = qfloat(ps, "VOLTage:PROTection?")
    ovp_mode = qstr(ps, "VOLTage:PROTection:MODE?")
    output_state = qint(ps, "OUTPut:STATe?")

    print_header(f"Channel {args.channel}")
    print_kv("Set voltage:", f"{set_voltage:.3f} V")
    print_kv("Measured voltage:", f"{measured_voltage:.3f} V")
    print_kv("Current limit:", f"{current_limit:.3f} A")
    print_kv("Measured current:", f"{measured_current:.3f} A")
    print_kv("OVP limit:", f"{ovp_limit:.3f} V")
    print_kv("OVP mode:", ovp_mode)
    print_kv("Output:", fmt_bool(output_state))
    return 0


def cmd_ch_set(ps, args) -> int:
    select_channel(ps, args.channel)

    changed = False
    if args.voltage is not None:
        ps.write(f"SOURce:VOLTage {args.voltage}")
        changed = True
    if args.current is not None:
        ps.write(f"SOURce:CURRent {args.current}")
        changed = True

    if not changed:
        raise ValueError("nothing to set; use --voltage and/or --current")

    set_voltage = qfloat(ps, "SOURce:VOLTage?")
    current_limit = qfloat(ps, "SOURce:CURRent?")

    print_header(f"Channel {args.channel} updated")
    print_kv("Voltage:", f"{set_voltage:.3f} V")
    print_kv("Current limit:", f"{current_limit:.3f} A")
    return 0


def cmd_ch_on(ps, args) -> int:
    select_channel(ps, args.channel)
    ps.write("OUTPut:STATe 1")
    print(f"Channel {args.channel} output: {fmt_bool(qint(ps, 'OUTPut:STATe?'))}")
    return 0


def cmd_ch_off(ps, args) -> int:
    select_channel(ps, args.channel)
    ps.write("OUTPut:STATe 0")
    print(f"Channel {args.channel} output: {fmt_bool(qint(ps, 'OUTPut:STATe?'))}")
    return 0


def cmd_out_on(ps, _args) -> int:
    ps.write("OUTPut:GENeral 1")
    print("Global output: ON")
    return 0


def cmd_out_off(ps, _args) -> int:
    ps.write("OUTPut:GENeral 0")
    print("Global output: OFF")
    return 0


def cmd_reset(ps, _args) -> int:
    ps.write("*RST")
    print("Device reset command sent.")
    return 0


def cmd_raw_query(ps, args) -> int:
    print(qstr(ps, args.command))
    return 0


def cmd_raw_write(ps, args) -> int:
    ps.write(args.command)
    print("Command sent.")
    return 0


def cmd_fuse_status(ps, args) -> int:
    select_channel(ps, args.channel)
    state = qint(ps, "FUSE?")
    delay = qstr(ps, "FUSE:DELay?")
    tripped = qint(ps, "FUSE:TRIPped?")

    print_header(f"Fuse status - Channel {args.channel}")
    print_kv("Fuse:", fmt_bool(state))
    print_kv("Delay:", f"{delay} ms")
    print_kv("Tripped:", "YES" if tripped else "NO")
    return 0


def cmd_fuse_on(ps, args) -> int:
    select_channel(ps, args.channel)
    ps.write("FUSE ON")
    print(f"Channel {args.channel} fuse: {fmt_bool(qint(ps, 'FUSE?'))}")
    return 0


def cmd_fuse_off(ps, args) -> int:
    select_channel(ps, args.channel)
    ps.write("FUSE OFF")
    print(f"Channel {args.channel} fuse: {fmt_bool(qint(ps, 'FUSE?'))}")
    return 0


def cmd_fuse_delay(ps, args) -> int:
    select_channel(ps, args.channel)
    if args.value is not None:
        ps.write(f"FUSE:DELay {args.value}")
    print(f"Channel {args.channel} fuse delay: {qstr(ps, 'FUSE:DELay?')} ms")
    return 0


def cmd_fuse_trip(ps, args) -> int:
    select_channel(ps, args.channel)
    tripped = qint(ps, "FUSE:TRIPped?")
    print(f"Channel {args.channel} fuse tripped: {'YES' if tripped else 'NO'}")
    return 0


def cmd_fuse_link(ps, args) -> int:
    if args.channel == args.target:
        raise ValueError("channel and target cannot be the same")
    select_channel(ps, args.channel)
    ps.write(f"FUSE:LINK {args.target}")
    linked = qint(ps, f"FUSE:LINK? {args.target}")
    print(f"Fuse link CH{args.channel} -> CH{args.target}: {'YES' if linked else 'NO'}")
    return 0


def cmd_fuse_unlink(ps, args) -> int:
    if args.channel == args.target:
        raise ValueError("channel and target cannot be the same")
    select_channel(ps, args.channel)
    ps.write(f"FUSE:UNLink {args.target}")
    linked = qint(ps, f"FUSE:LINK? {args.target}")
    print(f"Fuse link CH{args.channel} -> CH{args.target}: {'YES' if linked else 'NO'}")
    return 0


def cmd_fuse_links(ps, args) -> int:
    select_channel(ps, args.channel)
    print_header(f"Fuse links - Channel {args.channel}")
    for target in (1, 2, 3, 4):
        if target == args.channel:
            continue
        linked = qint(ps, f"FUSE:LINK? {target}")
        print_kv(f"Linked to CH{target}:", "YES" if linked else "NO")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hmp4040",
        description="Friendly CLI for Rohde & Schwarz HMP4040 over TCP SCPI socket",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"device IP address (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SCPI TCP port (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"timeout in ms (default: {DEFAULT_TIMEOUT})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="show device identification")
    sub.add_parser("status", help="show all channel states")
    sub.add_parser("reset", help="send *RST")

    p_ch = sub.add_parser("ch", help="channel operations")
    ch_sub = p_ch.add_subparsers(dest="ch_command", required=True)

    p_ch_status = ch_sub.add_parser("status", help="show one channel state")
    p_ch_status.add_argument("channel", type=validate_channel)

    p_ch_set = ch_sub.add_parser("set", help="set channel voltage/current")
    p_ch_set.add_argument("channel", type=validate_channel)
    p_ch_set.add_argument("--voltage", type=validate_nonnegative_float)
    p_ch_set.add_argument("--current", type=validate_nonnegative_float)

    p_ch_on = ch_sub.add_parser("on", help="turn channel output on")
    p_ch_on.add_argument("channel", type=validate_channel)

    p_ch_off = ch_sub.add_parser("off", help="turn channel output off")
    p_ch_off.add_argument("channel", type=validate_channel)

    p_out = sub.add_parser("out", help="global output operations")
    out_sub = p_out.add_subparsers(dest="out_command", required=True)
    out_sub.add_parser("on", help="turn global output on")
    out_sub.add_parser("off", help="turn global output off")

    p_fuse = sub.add_parser("fuse", help="electronic fuse operations")
    fuse_sub = p_fuse.add_subparsers(dest="fuse_command", required=True)

    p_fuse_status = fuse_sub.add_parser("status", help="show fuse state")
    p_fuse_status.add_argument("channel", type=validate_channel)

    p_fuse_on = fuse_sub.add_parser("on", help="turn fuse on")
    p_fuse_on.add_argument("channel", type=validate_channel)

    p_fuse_off = fuse_sub.add_parser("off", help="turn fuse off")
    p_fuse_off.add_argument("channel", type=validate_channel)

    p_fuse_delay = fuse_sub.add_parser("delay", help="get or set fuse delay")
    p_fuse_delay.add_argument("channel", type=validate_channel)
    p_fuse_delay.add_argument("--value", type=validate_delay)

    p_fuse_trip = fuse_sub.add_parser("trip", help="query fuse trip state")
    p_fuse_trip.add_argument("channel", type=validate_channel)

    p_fuse_link = fuse_sub.add_parser("link", help="link fuse to another channel")
    p_fuse_link.add_argument("channel", type=validate_channel)
    p_fuse_link.add_argument("target", type=validate_channel)

    p_fuse_unlink = fuse_sub.add_parser("unlink", help="unlink fuse from another channel")
    p_fuse_unlink.add_argument("channel", type=validate_channel)
    p_fuse_unlink.add_argument("target", type=validate_channel)

    p_fuse_links = fuse_sub.add_parser("links", help="show fuse links")
    p_fuse_links.add_argument("channel", type=validate_channel)

    p_raw = sub.add_parser("raw", help="send raw SCPI commands")
    raw_sub = p_raw.add_subparsers(dest="raw_command", required=True)

    p_raw_query = raw_sub.add_parser("query", help="send SCPI query")
    p_raw_query.add_argument("command", help='example: "*IDN?"')

    p_raw_write = raw_sub.add_parser("write", help="send SCPI write command")
    p_raw_write.add_argument("command", help='example: "INSTrument:NSELect 1"')

    return parser


def dispatch(ps, args) -> int:
    if args.command == "info":
        return cmd_info(ps, args)
    if args.command == "status":
        return cmd_status(ps, args)
    if args.command == "reset":
        return cmd_reset(ps, args)

    if args.command == "ch":
        if args.ch_command == "status":
            return cmd_ch_status(ps, args)
        if args.ch_command == "set":
            return cmd_ch_set(ps, args)
        if args.ch_command == "on":
            return cmd_ch_on(ps, args)
        if args.ch_command == "off":
            return cmd_ch_off(ps, args)

    if args.command == "out":
        if args.out_command == "on":
            return cmd_out_on(ps, args)
        if args.out_command == "off":
            return cmd_out_off(ps, args)

    if args.command == "fuse":
        if args.fuse_command == "status":
            return cmd_fuse_status(ps, args)
        if args.fuse_command == "on":
            return cmd_fuse_on(ps, args)
        if args.fuse_command == "off":
            return cmd_fuse_off(ps, args)
        if args.fuse_command == "delay":
            return cmd_fuse_delay(ps, args)
        if args.fuse_command == "trip":
            return cmd_fuse_trip(ps, args)
        if args.fuse_command == "link":
            return cmd_fuse_link(ps, args)
        if args.fuse_command == "unlink":
            return cmd_fuse_unlink(ps, args)
        if args.fuse_command == "links":
            return cmd_fuse_links(ps, args)

    if args.command == "raw":
        if args.raw_command == "query":
            return cmd_raw_query(ps, args)
        if args.raw_command == "write":
            return cmd_raw_write(ps, args)

    raise ValueError("unknown command")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        rm, ps = open_device(args.host, args.port, args.timeout)
    except Exception as exc:
        eprint(f"Connection failed: {exc}")
        return 1

    try:
        return dispatch(ps, args)
    except KeyboardInterrupt:
        eprint("Interrupted.")
        return 130
    except Exception as exc:
        eprint(f"Command failed: {exc}")
        return 2
    finally:
        try:
            ps.close()
        except Exception:
            pass
        try:
            rm.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
