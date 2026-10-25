#!/usr/bin/env python3
"""BlueZ listing and aimotech:// URI helpers for the D30 CUPS driver.

Shared by the CUPS backend (root, mode 0700) and aimotech-setup-printer
(lpadmin group). Match Print Master / Aimotech / Quin / Phomemo D30
names. Never offer a Nelko P21 or a JBD/OGRPHY pack an ESC/POS URI.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DEVICE_LINE = re.compile(r"^Device\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(.*)$")
PLACEHOLDER_MAC = "AA:BB:CC:DD:EE:FF"
ALLOW_PREFIXES = (
    "d30",
    "aimotech",
    "quin",
    "phomemo",
    "printmaster",
    "labelife",
    "q30",
)
DENY_SUBSTR = (
    "ogrphy",
    "jbd",
    "xiaoxiang",
    "smartess",
    "heatgenie",
    "afterburner",
    "nelko",
    "labelnize",
    "polono",
    "ezink",
)
DENY_TOKENS = (
    "p21",
    "p31",
    "p22",
    "p24",
    "pl80",
    "pm220",
)


def is_aimotech_name(name: str) -> bool:
    n = name.strip().lower()
    if not n:
        return False
    if any(s in n for s in DENY_SUBSTR):
        return False
    tokens = n.replace("_", " ").replace("-", " ").split()
    if any(tok in DENY_TOKENS for tok in tokens):
        return False
    compact = n.replace("_", "").replace("-", "").replace(" ", "")
    if compact in DENY_TOKENS:
        return False
    for prefix in ALLOW_PREFIXES:
        p = prefix.replace(" ", "")
        if compact == p or compact.startswith(p) or p in tokens:
            return True
        if len(p) >= 3 and p in compact:
            return True
    return False


def normalize_mac(raw: str) -> str:
    compact = raw.strip().upper().replace(":", "").replace("-", "")
    if compact == PLACEHOLDER_MAC.replace(":", ""):
        raise ValueError("replace AA:BB:CC:DD:EE:FF with the printer Bluetooth MAC")
    if len(compact) != 12 or any(c not in "0123456789ABCDEF" for c in compact):
        raise ValueError(f"need six MAC octets, got {raw!r}")
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2))


def uri_host(addr: str) -> str:
    """Dash-separated MAC so CUPS does not parse colons as a port."""
    return normalize_mac(addr).replace(":", "-")


def parse_uri(uri: str) -> str:
    if not uri:
        raise ValueError("DEVICE_URI is empty")
    rest = uri
    for prefix in ("aimotech://", "aimotech:/", "aimotech:"):
        if rest.lower().startswith(prefix):
            rest = rest[len(prefix) :]
            break
    else:
        raise ValueError(f"DEVICE_URI must be aimotech://MAC, got {uri!r}")
    return normalize_mac(rest.strip().strip("/"))


def parse_bluetoothctl(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        match = DEVICE_LINE.match(line)
        if not match:
            continue
        addr, name = match.group(1).upper(), match.group(2).strip()
        if addr in seen or not is_aimotech_name(name):
            continue
        seen.add(addr)
        found.append((addr, name))
    return found


def parse_bluez_info(text: str, addr: str) -> tuple[str, str] | None:
    name = ""
    for line in text.splitlines():
        if line.startswith("Name="):
            name = line.split("=", 1)[1].strip()
            break
    if not is_aimotech_name(name):
        return None
    return (addr.upper(), name)


def list_bluez_cache() -> list[tuple[str, str]]:
    root = Path("/var/lib/bluetooth")
    if not root.is_dir():
        return []
    found: list[tuple[str, str]] = []
    try:
        infos = list(root.glob("*/*/info"))
    except OSError:
        return []
    for info in infos:
        addr = info.parent.name
        if addr.count(":") != 5:
            continue
        try:
            text = info.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hit = parse_bluez_info(text, addr)
        if hit:
            found.append(hit)
    return found


def list_bluez_devices() -> list[tuple[str, str]]:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    live: list[tuple[str, str]] = []
    try:
        proc = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env=env,
        )
        live = parse_bluetoothctl(proc.stdout or "")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        live = []
    seen = {addr for addr, _name in live}
    merged = list(live)
    for addr, name in list_bluez_cache():
        if addr not in seen:
            seen.add(addr)
            merged.append((addr, name))
    return merged


def cups_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'")


def cups_device_line(addr: str, name: str) -> str:
    model = name.strip() or "D30"
    make_model = cups_quote(f"Aimotech {model}")
    info = cups_quote(f"{model} Print Master SPP")
    devid = cups_quote(f"MFG:Aimotech;MDL:{model};CMD:ESCPOS;CLS:PRINTER;")
    return f'direct aimotech://{uri_host(addr)} "{make_model}" "{info}" "{devid}" ""'


def discover_lines(devices: list[tuple[str, str]] | None = None) -> list[str]:
    if devices is None:
        devices = list_bluez_devices()
    return [cups_device_line(addr, name) for addr, name in devices]


def self_test() -> None:
    assert parse_uri("aimotech://01:23:45:67:89:ab") == "01:23:45:67:89:AB"
    assert parse_uri("aimotech://01-23-45-67-89-AB") == "01:23:45:67:89:AB"
    assert parse_uri("aimotech://0123456789ab") == "01:23:45:67:89:AB"
    assert uri_host("01:23:45:67:89:AB") == "01-23-45-67-89-AB"
    try:
        parse_uri("aimotech://AA:BB:CC:DD:EE:FF")
    except ValueError:
        pass
    else:
        raise AssertionError("placeholder MAC must fail")
    try:
        parse_uri("aimotech://AABBCCDDEEFF")
    except ValueError:
        pass
    else:
        raise AssertionError("placeholder MAC must fail")
    try:
        parse_uri("nelko://01:23:45:67:89:AB")
    except ValueError:
        pass
    else:
        raise AssertionError("nelko URI must fail")
    assert is_aimotech_name("D30")
    assert is_aimotech_name("Phomemo D30")
    assert is_aimotech_name("Aimotech D30")
    assert is_aimotech_name("Print Master")
    assert is_aimotech_name("PrintMaster")
    assert is_aimotech_name("Quin-D30")
    assert is_aimotech_name("Labelife D30")
    assert not is_aimotech_name("P21")
    assert not is_aimotech_name("Nelko P21")
    assert not is_aimotech_name("ogrphy48100xxx")
    assert not is_aimotech_name("HeatGenie-S3")
    assert not is_aimotech_name("OnePlus 11 5G")
    assert not is_aimotech_name("")
    sample = (
        "Device 01:23:45:67:89:AB D30\n"
        "Device AA:BB:CC:DD:EE:FF ogrphy48100aaa\n"
        "Device 00:11:22:33:44:55 P21\n"
        "Device 0A:0B:0C:0D:0E:0F Phomemo D30\n"
        "Device 11:22:33:44:55:66 Print Master\n"
    )
    got = parse_bluetoothctl(sample)
    assert got == [
        ("01:23:45:67:89:AB", "D30"),
        ("0A:0B:0C:0D:0E:0F", "Phomemo D30"),
        ("11:22:33:44:55:66", "Print Master"),
    ]
    line = cups_device_line("01:23:45:67:89:AB", "D30")
    assert line.startswith("direct aimotech://01-23-45-67-89-AB ")
    assert "MFG:Aimotech;MDL:D30;CMD:ESCPOS;" in line
    assert parse_bluez_info("[General]\nName=D30\n", "01:23:45:67:89:ab") == (
        "01:23:45:67:89:AB",
        "D30",
    )
    assert parse_bluez_info("[General]\nName=P21\n", "aa:bb:cc:dd:ee:00") is None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) >= 2 and args[1] == "self-test":
        self_test()
        print("ok")
        return 0
    for line in discover_lines():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
