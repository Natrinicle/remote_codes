#!/usr/bin/env python3
"""Encode Voltronic LIB RS485 BMS as Modbus RTU FC3.

Slave 1, CRC-16-Modbus (init 0xFFFF, poly 0xA001). Typical RS485 9600 8N1.

Example:
    ./encode_voltroniclib.py soc
    ./encode_voltroniclib.py cells
    ./encode_voltroniclib.py limits
    ./encode_voltroniclib.py self-test
"""

from __future__ import annotations

import argparse

BLOCKS = {
    "soc": (37, 17),
    "cells": (16, 21),
    "limits": (112, 5),
}


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def rtu_read_holding(start: int, qty: int, *, slave: int = 1) -> bytes:
    body = bytes(
        (
            slave,
            3,
            (start >> 8) & 0xFF,
            start & 0xFF,
            (qty >> 8) & 0xFF,
            qty & 0xFF,
        )
    )
    crc = crc16_modbus(body)
    return body + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def self_test() -> None:
    frame = rtu_read_holding(37, 17)
    assert frame[0] == 1 and frame[1] == 3
    assert frame[2] == 0 and frame[3] == 37
    assert frame[4] == 0 and frame[5] == 17
    assert crc16_modbus(frame[:-2]) == frame[-2] | (frame[-1] << 8)
    assert len(rtu_read_holding(16, 21)) == 8
    assert len(rtu_read_holding(112, 5)) == 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in BLOCKS:
        sub.add_parser(name)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    start, qty = BLOCKS[args.cmd]
    print(rtu_read_holding(start, qty).hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
