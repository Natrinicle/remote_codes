#!/usr/bin/env python3
"""Encode/decode HeatGenie (Bogu) BLE frames.

Wire temps are tenths of °C. App °F is trunc((320 + 1.8 * raw) / 10).
CRC-16-CCITT nibble table, init 0, matching the uni-app Ee() helper.

Example:
    ./encode_heatgenie.py auto
    ./encode_heatgenie.py decode aa09ffef000000f255107b0020033101db01...
"""

from __future__ import annotations

import argparse
import sys

# CRC-16-CCITT nibble table from HeatGenie app-service.js Ee()
_CRC_NIBBLE = [
    0,
    4129,
    8258,
    12387,
    16516,
    20645,
    24774,
    28903,
    33032,
    37161,
    41290,
    45419,
    49548,
    53677,
    57806,
    61935,
]

CMD_ON = 1
CMD_OFF = 2
DB0_DN_CMD = 97
DB0_DN_AUTO_UPDATA = 101
ADDR_TYPE_REG = 2

RUN_MODE = {
    0: "reset",
    1: "ignite",
    2: "auto",
    3: "manual",
    4: "cooldown",
    5: "standby",
    6: "error",
    7: "pump",
    8: "vent",
    9: "start-stop",
}


def crc16(data: bytes, n: int | None = None) -> int:
    """CRC over the first n bytes (default: all). Init 0."""
    if n is None:
        n = len(data)
    acc = 0
    for b in data[:n]:
        nib = (acc >> 12) & 65535
        acc = (acc << 4) & 65535
        acc ^= _CRC_NIBBLE[15 & ((nib & 65535) ^ (b >> 4))]
        nib = (acc & 65535) >> 12
        acc = (acc << 4) & 65535
        acc ^= _CRC_NIBBLE[15 & ((nib & 65535) ^ (15 & b))]
    return acc & 65535


def append_crc(payload: bytes) -> bytes:
    c = crc16(payload)
    return payload + bytes((c >> 8, c & 255))


def cmd_frame(cmd: int, a0: int, a1: int, a2: int) -> bytes:
    """8-byte heaterSendCmd: AA 00 CMD A0 A1 A2 CRC_HI CRC_LO."""
    body = bytes((0xAA, 0, cmd, a0, a1, a2))
    return append_crc(body)


def auto_updata(*, interval: int = 20) -> bytes:
    return cmd_frame(DB0_DN_AUTO_UPDATA, ADDR_TYPE_REG, interval, 30)


def power(on: bool, random_byte: int = 1) -> bytes:
    return cmd_frame(DB0_DN_CMD, CMD_ON if on else CMD_OFF, random_byte, 0)


def u16le(buf: bytes, offset: int) -> int:
    return buf[offset] | (buf[offset + 1] << 8)


def tenths_c_to_display(raw: int) -> tuple[int, int]:
    """App truncations: °C integer and °F integer."""
    c = raw // 10
    f = int((320 + 1.8 * raw) / 10)
    return c, f


def decode_status(frame: bytes) -> dict[str, object]:
    """Parse a 52-byte AA 09 FF … F2 register dump."""
    if len(frame) < 52 or frame[0] != 0xAA:
        raise ValueError(f"not a HeatGenie long frame (len={len(frame)})")
    if crc16(frame) != 0:
        raise ValueError("full-frame CRC is not zero")
    if frame[7] != 0xF2:
        raise ValueError(f"byte7={frame[7]:#x}, expected 0xF2 register dump")
    p = frame[8:48]
    cabin = u16le(p, 6)
    shell = u16le(p, 8)
    cabin_c, cabin_f = tenths_c_to_display(cabin)
    shell_c, shell_f = tenths_c_to_display(shell)
    mode = p[0] & 15
    return {
        "mode": mode,
        "mode_name": RUN_MODE.get(mode, "unknown"),
        "run_flags": p[1],
        "volts": u16le(p, 2) / 10,
        "altitude_m": u16le(p, 4),
        "cabin_raw": cabin,
        "cabin_c": cabin_c,
        "cabin_f": cabin_f,
        "shell_raw": shell,
        "shell_c": shell_c,
        "shell_f": shell_f,
        "error": u16le(p, 20),
    }


def _hex(data: bytes) -> str:
    return data.hex()


def self_test() -> None:
    """Known vectors from the live HeatGenie session."""
    assert auto_updata().hex() == "aa006502141ed095"
    assert auto_updata(interval=0).hex() == "aa006502001e1f22"
    assert power(True, 0).hex() == "aa00610100007f7c"
    dump = bytes.fromhex(
        "aa09ffef000000f255107b0020033101db01000000000000"
        "f87ff87f0000044090b87e5b0000a505044b000000000000bb851ab5"
    )
    info = decode_status(dump)
    assert info["mode_name"] == "standby"
    assert info["volts"] == 12.3
    assert info["cabin_c"] == 30
    assert info["cabin_f"] == 86


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auto", help="AUTO_UPDATA start (2 s reports)")
    sub.add_parser("auto-stop", help="AUTO_UPDATA stop")
    p_on = sub.add_parser("on", help="power ON frame (writeNoResponse to 3A01)")
    p_on.add_argument("--rand", type=int, default=1)
    p_off = sub.add_parser("off", help="power OFF frame")
    p_off.add_argument("--rand", type=int, default=1)
    p_dec = sub.add_parser("decode", help="decode a 52-byte status hex dump")
    p_dec.add_argument("hex")
    sub.add_parser("self-test", help="check CRC and decode vectors")
    args = parser.parse_args()
    if args.cmd == "auto":
        print(_hex(auto_updata(interval=20)))
    elif args.cmd == "auto-stop":
        print(_hex(auto_updata(interval=0)))
    elif args.cmd == "on":
        print(_hex(power(True, args.rand)))
    elif args.cmd == "off":
        print(_hex(power(False, args.rand)))
    elif args.cmd == "decode":
        raw = bytes.fromhex(args.hex.replace(" ", ""))
        info = decode_status(raw)
        for key, val in info.items():
            print(f"{key}: {val}")
    elif args.cmd == "self-test":
        self_test()
        print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
