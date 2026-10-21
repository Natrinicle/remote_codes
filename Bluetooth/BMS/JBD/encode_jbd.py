#!/usr/bin/env python3
"""Encode JBD / Xiaoxiang BMS bodies for BLE GATT FF02 (and USB UART).

BLE: service FF00, notify FF01, write FF02. One GATT central at a time.
USB UART sibling is 9600 8N1 with the same DD…77 bytes (Serial/BMS/JBD).

Example:
    ./encode_jbd.py basic
    ./encode_jbd.py cells
    ./encode_jbd.py hw
    ./encode_jbd.py self-test
"""

from __future__ import annotations

import argparse

# Read:  DD A5 CMD 00 CHK_HI CHK_LO 77
# Write: DD 5A CMD LEN … CHK 77
READS = {
    "basic": bytes.fromhex("dda50300fffd77"),
    "cells": bytes.fromhex("dda50400fffc77"),
    "hw": bytes.fromhex("dda50500fffb77"),
    "resistance": bytes.fromhex("dda5f600ff0a77"),
}


def checksum(payload: bytes) -> bytes:
    """One's complement of the sum of CMD, LEN, and data, 16-bit."""
    total = sum(payload) & 0xFFFF
    chk = (0x10000 - total) & 0xFFFF
    return bytes(((chk >> 8) & 0xFF, chk & 0xFF))


def read_frame(cmd: int) -> bytes:
    body = bytes((cmd, 0))
    return b"\xdd\xa5" + body + checksum(body) + b"\x77"


def self_test() -> None:
    assert read_frame(0x03) == READS["basic"]
    assert read_frame(0x04) == READS["cells"]
    assert read_frame(0x05) == READS["hw"]
    assert read_frame(0xF6) == READS["resistance"]
    assert READS["basic"].startswith(b"\xdd\xa5")
    assert READS["basic"].endswith(b"\x77")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in READS:
        sub.add_parser(name)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    print(READS[args.cmd].hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
