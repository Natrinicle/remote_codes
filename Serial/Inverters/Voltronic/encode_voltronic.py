#!/usr/bin/env python3
"""Encode Voltronic / Axpert / InfiniSolar ASCII PI30 queries.

USB HID hidraw (no baud) or USB UART (often 2400 or 9600 8N1). Frame is
COMMAND + checksum + CR. Suffix `$` is CRC-16 (nibble table, poly 0x1021);
`@` is an 8-bit sum; no suffix means no checksum.

This is not Modbus. A CH340 USB-UART on an SRNE inverter will not answer
QPIGS.

Example:
    ./encode_voltronic.py qpigs
    ./encode_voltronic.py qpiri
    ./encode_voltronic.py qmod
    ./encode_voltronic.py raw QPIWS
    ./encode_voltronic.py self-test
"""

from __future__ import annotations

import argparse

CRC_TA = (
    0x0000,
    0x1021,
    0x2042,
    0x3063,
    0x4084,
    0x50A5,
    0x60C6,
    0x70E7,
    0x8108,
    0x9129,
    0xA14A,
    0xB16B,
    0xC18C,
    0xD1AD,
    0xE1CE,
    0xF1EF,
)

COMMANDS = {
    "qpigs": "QPIGS",
    "qpiri": "QPIRI",
    "qmod": "QMOD",
    "qpiws": "QPIWS",
    "qpi": "QPI",
    "qvfw": "QVFW",
}


def crc16_voltronic(data: bytes) -> bytes:
    """PI30 CRC. High and low bytes that would be CR/LF/`(` are incremented."""
    crc = 0
    for byte in data:
        da = (crc >> 12) & 0x0F
        crc = ((crc << 4) & 0xFFFF) ^ CRC_TA[da ^ (byte >> 4)]
        da = (crc >> 12) & 0x0F
        crc = ((crc << 4) & 0xFFFF) ^ CRC_TA[da ^ (byte & 0x0F)]
    hi = (crc >> 8) & 0xFF
    lo = crc & 0xFF
    if lo in (0x28, 0x0D, 0x0A):
        lo = (lo + 1) & 0xFF
    if hi in (0x28, 0x0D, 0x0A):
        hi = (hi + 1) & 0xFF
    return bytes((hi, lo))


def checksum_at(data: bytes) -> bytes:
    return bytes((sum(data) & 0xFF,))


def frame(command: str, *, check: str = "$") -> bytes:
    body = command.encode("ascii")
    if check == "$":
        return body + crc16_voltronic(body) + b"\r"
    if check == "@":
        return body + checksum_at(body) + b"\r"
    if check in {"", "none"}:
        return body + b"\r"
    raise ValueError("check must be $, @, or none")


def self_test() -> None:
    qpigs = frame("QPIGS", check="$")
    assert qpigs.startswith(b"QPIGS")
    assert qpigs.endswith(b"\r")
    assert len(qpigs) == 8
    body, crc = qpigs[:5], qpigs[5:7]
    assert crc16_voltronic(body) == crc
    assert frame("QPIGS", check="@")[5] == (sum(b"QPIGS") & 0xFF)
    assert frame("QPIGS", check="none") == b"QPIGS\r"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, command in COMMANDS.items():
        p = sub.add_parser(name, help=f"{command}$CRC\\r")
        p.add_argument("--check", choices=("$", "@", "none"), default="$")
    p_raw = sub.add_parser("raw", help="arbitrary ASCII command")
    p_raw.add_argument("command")
    p_raw.add_argument("--check", choices=("$", "@", "none"), default="$")
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "raw":
        command = args.command
    else:
        command = COMMANDS[args.cmd]
    print(frame(command, check=args.check).hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
