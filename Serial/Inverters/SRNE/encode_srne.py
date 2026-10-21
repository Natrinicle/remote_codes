#!/usr/bin/env python3
"""Encode/decode SRNE Modbus RTU on USB UART (no EyeBond wrap).

Slave 1, function 3 reads, function 6 single-register writes. CRC-16-Modbus
(init 0xFFFF, poly 0xA001, CRC little-endian on the wire). Default UART
9600 8N1. Typical USB-UART is QinHeng CH340 (1a86:7523) → /dev/ttyUSB0.

Same inner RTU as the EyeBond FC=4 tunnel under Network/Inverters/EyeBond.
This helper prints the unwrapped frames.

Example:
    ./encode_srne.py read cfg
    ./encode_srne.py read e204
    ./encode_srne.py write e205 0
    ./encode_srne.py parse 010302040027021e...
    ./encode_srne.py self-test
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

RTU_SLAVE = 1

SRNE_CFG_START = 256
SRNE_CFG_N = 18
SRNE_LIVE_START = 528
SRNE_LIVE_N = 18
SRNE_PHASE_START = 554
SRNE_PHASE_N = 14

READ_BLOCKS = {
    "cfg": (SRNE_CFG_START, SRNE_CFG_N),
    "live": (SRNE_LIVE_START, SRNE_LIVE_N),
    "phase": (SRNE_PHASE_START, SRNE_PHASE_N),
    "e204": (0xE204, 2),
    "e20a": (0xE20A, 2),
    "e20f": (0xE20F, 1),
}

WRITE_REGS = {
    "e205": 0xE205,  # AC-charge current limit, 0.1 A units
    "e204": 0xE204,  # output priority
    "e20a": 0xE20A,  # max charge A, 0.1 A units
    "e20b": 0xE20B,  # AC input range
    "e20f": 0xE20F,  # charge priority
}

# Proven TX on a split-phase SRNE UART, 2026-10-21.
PROVEN_CFG = bytes.fromhex("010301000012c43b")
PROVEN_LIVE = bytes.fromhex("010302100012c5ba")
PROVEN_PHASE = bytes.fromhex("0103022a000ee47e")
PROVEN_E204 = bytes.fromhex("0103e2040002b3b2")
PROVEN_E20A = bytes.fromhex("0103e20a0002d271")
PROVEN_E20F = bytes.fromhex("0103e20f00018271")
PROVEN_E205_ZERO = bytes.fromhex("0106e2050000afb3")


def _hex(data: bytes) -> str:
    return data.hex()


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


def rtu_read_holding(start: int, qty: int, *, slave: int = RTU_SLAVE) -> bytes:
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


def rtu_write_single(reg: int, value: int, *, slave: int = RTU_SLAVE) -> bytes:
    if value < 0 or value > 0xFFFF:
        raise ValueError("value must be 0..65535 (raw register)")
    body = bytes(
        (
            slave,
            6,
            (reg >> 8) & 0xFF,
            reg & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        )
    )
    crc = crc16_modbus(body)
    return body + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def srne_read(block: str, *, slave: int = RTU_SLAVE) -> bytes:
    start, qty = READ_BLOCKS[block]
    return rtu_read_holding(start, qty, slave=slave)


def srne_write(name: str, value: int, *, slave: int = RTU_SLAVE) -> bytes:
    return rtu_write_single(WRITE_REGS[name], value, slave=slave)


def _s16(value: int) -> int:
    return value - 65536 if value >= 32768 else value


def parse_rtu(raw: bytes) -> dict[str, object]:
    data = raw
    if len(data) < 5:
        raise ValueError("short RTU")
    slave, fn = data[0], data[1]
    if fn & 0x80:
        return {
            "exception": True,
            "slave": slave,
            "fn": fn,
            "code": data[2] if len(data) > 2 else None,
        }
    if fn in (3, 4):
        byte_count = data[2]
        need = 3 + byte_count + 2
        if need > len(data) or byte_count & 1:
            raise ValueError("bad RTU length")
        payload = data[: 3 + byte_count]
        regs = [
            (data[3 + i * 2] << 8) | data[4 + i * 2] for i in range(byte_count // 2)
        ]
    elif fn == 6:
        need = 8
        if len(data) < need:
            raise ValueError("short FC6 echo")
        payload = data[:6]
        regs = [(data[2] << 8) | data[3], (data[4] << 8) | data[5]]
    else:
        raise ValueError(f"unexpected RTU fn {fn}")
    expect = crc16_modbus(payload)
    got = data[len(payload)] | (data[len(payload) + 1] << 8)
    if expect != got:
        raise ValueError(f"rtu crc fail expect={expect:04x} got={got:04x}")
    return {
        "exception": False,
        "slave": slave,
        "fn": fn,
        "regs": regs,
    }


def decode_cfg(regs: Sequence[int]) -> dict[str, float | int]:
    if len(regs) < 18:
        raise ValueError("cfg needs 18 registers")
    batt_a = _s16(regs[2]) / 10.0
    return {
        "soc": float(regs[0]),
        "batt_v": _s16(regs[1]) / 10.0,
        "batt_a": batt_a,
        "chg_a": -batt_a if batt_a <= -0.05 else 0.0,
        "dsg_a": batt_a if batt_a >= 0.05 else 0.0,
        "pv1_v": _s16(regs[7]) / 10.0,
        "pv1_w": float(_s16(regs[9])),
        "pv2_v": _s16(regs[15]) / 10.0,
        "pv2_w": float(_s16(regs[17])),
    }


def decode_live(regs: Sequence[int]) -> dict[str, float | int]:
    if len(regs) < 18:
        raise ValueError("live needs 18 registers")
    return {
        "mode": int(regs[0]),
        "ac_out_w_l1": float(_s16(regs[11])),
        "load_pct_l1": float(regs[15]),
        "inv_c": _s16(regs[17]) / 10.0,
    }


def decode_phase(regs: Sequence[int]) -> dict[str, float]:
    if len(regs) < 9:
        raise ValueError("phase needs at least 9 registers")
    out: dict[str, float] = {"ac_out_w_l2": float(regs[8])}
    if len(regs) > 12:
        out["load_pct_l2"] = float(regs[12])
    return out


def decode_e204(regs: Sequence[int]) -> dict[str, float | int]:
    if len(regs) < 2:
        raise ValueError("e204 needs 2 registers")
    return {"output_pri": int(regs[0]), "mains_limit_a": regs[1] / 10.0}


def decode_e20a(regs: Sequence[int]) -> dict[str, float | int]:
    if len(regs) < 2:
        raise ValueError("e20a needs 2 registers")
    return {"max_chg_a": regs[0] / 10.0, "ac_range": int(regs[1])}


def decode_e20f(regs: Sequence[int]) -> dict[str, int]:
    if len(regs) < 1:
        raise ValueError("e20f needs 1 register")
    return {"chg_pri": int(regs[0])}


def self_test() -> None:
    assert rtu_read_holding(SRNE_CFG_START, SRNE_CFG_N) == PROVEN_CFG
    assert rtu_read_holding(SRNE_LIVE_START, SRNE_LIVE_N) == PROVEN_LIVE
    assert rtu_read_holding(SRNE_PHASE_START, SRNE_PHASE_N) == PROVEN_PHASE
    assert rtu_read_holding(0xE204, 2) == PROVEN_E204
    assert rtu_read_holding(0xE20A, 2) == PROVEN_E20A
    assert rtu_read_holding(0xE20F, 1) == PROVEN_E20F
    assert rtu_write_single(0xE205, 0) == PROVEN_E205_ZERO

    echo = parse_rtu(PROVEN_E205_ZERO)
    assert echo["fn"] == 6
    assert echo["regs"] == [0xE205, 0]

    cfg = decode_cfg(
        [
            47,
            542,
            0xFEE2,
            0,
            0,
            0,
            0,
            1200,
            0,
            611,
            0,
            0,
            0,
            0,
            0,
            800,
            0,
            1803,
        ]
    )
    assert cfg["soc"] == 47
    assert cfg["batt_v"] == 54.2
    assert abs(cfg["chg_a"] - 28.6) < 0.01
    assert cfg["pv1_w"] + cfg["pv2_w"] == 2414

    live = decode_live([3] + [0] * 10 + [1249] + [0, 0, 0, 40, 0, 350])
    assert live["mode"] == 3
    assert live["ac_out_w_l1"] == 1249
    assert live["inv_c"] == 35.0

    phase = decode_phase([0] * 8 + [826] + [0, 0, 0, 20])
    assert phase["ac_out_w_l2"] == 826
    assert decode_e204([1, 400])["mains_limit_a"] == 40.0
    assert decode_e20a([2000, 1])["ac_range"] == 1
    assert decode_e20f([2])["chg_pri"] == 2


def _print_map(info: dict[str, object]) -> None:
    for key, val in info.items():
        if isinstance(val, bytes):
            print(f"{key}: {_hex(val)}")
        else:
            print(f"{key}: {val}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_read = sub.add_parser("read", help="FC3 holding-register block")
    p_read.add_argument("block", choices=sorted(READ_BLOCKS))
    p_read.add_argument("--slave", type=int, default=RTU_SLAVE)
    p_write = sub.add_parser(
        "write",
        help="FC6 single register (print only; does not open the UART)",
    )
    p_write.add_argument("reg", choices=sorted(WRITE_REGS))
    p_write.add_argument("value", type=int, help="raw register (E205 0 = 0.0 A)")
    p_write.add_argument("--slave", type=int, default=RTU_SLAVE)
    p_parse = sub.add_parser("parse", help="decode one RTU frame (hex)")
    p_parse.add_argument("hex")
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "read":
        print(_hex(srne_read(args.block, slave=args.slave)))
    elif args.cmd == "write":
        print(_hex(srne_write(args.reg, args.value, slave=args.slave)))
    elif args.cmd == "parse":
        raw = bytes.fromhex(args.hex.replace(" ", ""))
        _print_map(parse_rtu(raw))
    elif args.cmd == "self-test":
        self_test()
        print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
