#!/usr/bin/env python3
"""BlueZ listing and nelko:// URI helpers for the P21 CUPS driver.

Shared by the CUPS backend (root, mode 0700) and nelko-setup-printer
(lpadmin group). Keep name allow/deny here so discovery never offers
JBD/OGRPHY 0000ff00 packs a TSPL URI.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DEVICE_LINE = re.compile(r"^Device\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(.*)$")
CACHE_LINE = re.compile(r"^([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\t(.*)$")
PLACEHOLDER_MAC = "AA:BB:CC:DD:EE:FF"
DEVICE_CACHE = Path("/var/cache/cups/nelko.devices")
ALLOW_PREFIXES = (
    "p21",
    "p31",
    "p22",
    "p24",
    "pl80",
    "pm220",
    "nelko",
    "labelnize",
    "polono",
    "ezink",
)
DENY_SUBSTR = (
    "ogrphy",
    "jbd",
    "xiaoxiang",
    "smartess",
    "heatgenie",
    "afterburner",
)


def is_nelko_name(name: str) -> bool:
    n = name.strip().lower()
    if not n:
        return False
    if any(s in n for s in DENY_SUBSTR):
        return False
    tokens = n.replace("_", " ").replace("-", " ").split()
    for prefix in ALLOW_PREFIXES:
        if n == prefix or n.startswith(prefix) or prefix in tokens:
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
    for prefix in ("nelko://", "nelko:/", "nelko:"):
        if rest.lower().startswith(prefix):
            rest = rest[len(prefix) :]
            break
    else:
        raise ValueError(f"DEVICE_URI must be nelko://MAC, got {uri!r}")
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
        if addr in seen or not is_nelko_name(name):
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
    if not is_nelko_name(name):
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


def parse_device_cache(text: str) -> list[tuple[str, str]]:
    """Last-seen P21-class devices so Get-Devices still lists them when off."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = CACHE_LINE.match(line)
        if not match:
            continue
        try:
            addr = normalize_mac(match.group(1))
        except ValueError:
            continue
        name = match.group(2).strip()
        if addr in seen or not is_nelko_name(name):
            continue
        seen.add(addr)
        found.append((addr, name))
    return found


def format_device_cache(devices: list[tuple[str, str]]) -> str:
    lines = [
        "# printer-driver-nelko last-seen BlueZ devices",
        "# MAC<TAB>name. Get-Devices still lists these when the printer is off.",
    ]
    seen: set[str] = set()
    for addr, name in devices:
        try:
            mac = normalize_mac(addr)
        except ValueError:
            continue
        label = name.strip()
        if mac in seen or not is_nelko_name(label):
            continue
        seen.add(mac)
        lines.append(f"{mac}\t{label}")
        if len(seen) >= 16:
            break
    return "\n".join(lines) + "\n"


def read_device_cache(path: Path | None = None) -> list[tuple[str, str]]:
    cache = path or DEVICE_CACHE
    try:
        text = cache.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return parse_device_cache(text)


def write_device_cache(
    devices: list[tuple[str, str]], path: Path | None = None
) -> None:
    cache = path or DEVICE_CACHE
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(format_device_cache(devices), encoding="utf-8")
    except OSError:
        return


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
    live_seen = set(seen)
    for addr, name in read_device_cache():
        if addr not in seen:
            seen.add(addr)
            merged.append((addr, name))
    if live_seen:
        write_device_cache(merged)
    return merged


def cups_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'")


def cups_device_line(addr: str, name: str) -> str:
    model = name.strip() or "P21"
    make_model = cups_quote(f"Nelko {model}")
    info = cups_quote(f"{model} RFCOMM TSPL")
    devid = cups_quote(f"MFG:Nelko;MDL:{model};CMD:TSPL;CLS:PRINTER;")
    return f'direct nelko://{uri_host(addr)} "{make_model}" "{info}" "{devid}" ""'


def discover_lines(devices: list[tuple[str, str]] | None = None) -> list[str]:
    if devices is None:
        devices = list_bluez_devices()
    return [cups_device_line(addr, name) for addr, name in devices]


def self_test() -> None:
    assert parse_uri("nelko://01:23:45:67:89:ab") == "01:23:45:67:89:AB"
    assert parse_uri("nelko://01-23-45-67-89-AB") == "01:23:45:67:89:AB"
    assert parse_uri("nelko://0123456789ab") == "01:23:45:67:89:AB"
    assert uri_host("01:23:45:67:89:AB") == "01-23-45-67-89-AB"
    try:
        parse_uri("nelko://AA:BB:CC:DD:EE:FF")
    except ValueError:
        pass
    else:
        raise AssertionError("placeholder MAC must fail")
    try:
        parse_uri("nelko://AABBCCDDEEFF")
    except ValueError:
        pass
    else:
        raise AssertionError("placeholder MAC must fail")
    assert is_nelko_name("P21")
    assert is_nelko_name("P31S")
    assert is_nelko_name("Nelko P21")
    assert is_nelko_name("PL80E")
    assert not is_nelko_name("ogrphy48100xxx")
    assert not is_nelko_name("HeatGenie-S3")
    assert not is_nelko_name("OnePlus 11 5G")
    assert not is_nelko_name("")
    sample = (
        "Device 01:23:45:67:89:AB P21\n"
        "Device AA:BB:CC:DD:EE:FF ogrphy48100aaa\n"
        "Device 00:11:22:33:44:55 HeatGenie-S3\n"
        "Device 0A:0B:0C:0D:0E:0F Nelko P21\n"
    )
    got = parse_bluetoothctl(sample)
    assert got == [("01:23:45:67:89:AB", "P21"), ("0A:0B:0C:0D:0E:0F", "Nelko P21")]
    line = cups_device_line("01:23:45:67:89:AB", "P21")
    assert line.startswith("direct nelko://01-23-45-67-89-AB ")
    assert "MFG:Nelko;MDL:P21;CMD:TSPL;" in line
    assert parse_bluez_info("[General]\nName=P21\n", "01:23:45:67:89:ab") == (
        "01:23:45:67:89:AB",
        "P21",
    )
    assert (
        parse_bluez_info("[General]\nName=ogrphy48100aaa\n", "aa:bb:cc:dd:ee:00")
        is None
    )
    cache_text = (
        "# comment\n"
        "01:23:45:67:89:AB\tP21\n"
        "00:11:22:33:44:55\tD30\n"
        "AA:BB:CC:DD:EE:FF\tNelko P21\n"
        "0A:0B:0C:0D:0E:0F\tNelko P21\n"
    )
    assert parse_device_cache(cache_text) == [
        ("01:23:45:67:89:AB", "P21"),
        ("0A:0B:0C:0D:0E:0F", "Nelko P21"),
    ]
    formatted = format_device_cache(
        [
            ("01:23:45:67:89:AB", "P21"),
            ("00:11:22:33:44:55", "D30"),
            ("AA:BB:CC:DD:EE:FF", "Nelko P21"),
        ]
    )
    assert "01:23:45:67:89:AB\tP21" in formatted
    assert "D30" not in formatted
    assert PLACEHOLDER_MAC not in formatted


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
