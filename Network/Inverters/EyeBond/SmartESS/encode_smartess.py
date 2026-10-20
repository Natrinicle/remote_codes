#!/usr/bin/env python3
"""Encode/decode SmartESS / EyeBond local LAN frames.

UDP 58899 hijack ASCII, then TCP 8899 EyeBond wrapper. This dongle family
was proven as SRNE Modbus RTU (FC3) inside EyeBond FC=4. PI17 GS / PI30
QPIGS returned empty FC=4 on the same collector.

Prints payloads only. Does not bind 8899 or send UDP.

Example:
    ./encode_smartess.py hijack 192.0.2.10
    ./encode_smartess.py heartbeat --dummy-date
    ./encode_smartess.py read cfg
    ./encode_smartess.py decode 00010001000a0101...
    ./encode_smartess.py self-test
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

UDP_PORT = 58899
TCP_PORT = 8899
HDR = 8
WIRE_OFF = 6

FC_HEARTBEAT = 1
FC_QUERY = 2
FC_FORWARD = 4

# Proven on-wire 2026-10-13. Inner RTU slave is not the EyeBond header addr.
DEVCODE_SRNE = 0x0001
COLLECTOR_ADDR = 0xFF
MGMT_ADDR = 1
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
}

# FC2 identity probe used after the collector's first heartbeat.
QUERY_FIELDS = bytes((2, 5, 6, 14))


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


def hijack_payload(listen_ip: str, tcp_port: int = TCP_PORT) -> bytes:
    """ASCII the collector understands on UDP 58899. Trailing semicolon required."""
    return f"set>server={listen_ip}:{tcp_port};".encode("ascii")


def wrap_eyebond(
    fc: int,
    payload: bytes,
    *,
    tid: int = 1,
    devcode: int = 0,
    addr: int = MGMT_ADDR,
) -> bytes:
    total = HDR + len(payload)
    wire = total - WIRE_OFF
    if tid <= 0 or tid > 0xFFFF:
        raise ValueError("tid must be 1..65535")
    header = bytes(
        (
            (tid >> 8) & 0xFF,
            tid & 0xFF,
            (devcode >> 8) & 0xFF,
            devcode & 0xFF,
            (wire >> 8) & 0xFF,
            wire & 0xFF,
            addr & 0xFF,
            fc & 0xFF,
        )
    )
    return header + payload


def heartbeat(
    *,
    dummy_date: bool = False,
    year: int = 2026,
    month: int = 1,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    tid: int = 1,
) -> bytes:
    """FC=1. Dummy 2026-01-01 kept the session; a live UTC date once closed it."""
    if dummy_date or year < 2020:
        y, month, day, hour, minute, second = 26, 1, 1, 0, 0, 0
    else:
        y = year - 2000
    payload = bytes((y, month, day, hour, minute, second, 0, 60))
    return wrap_eyebond(FC_HEARTBEAT, payload, tid=tid, devcode=0, addr=MGMT_ADDR)


def collector_query(*, tid: int = 1) -> bytes:
    return wrap_eyebond(FC_QUERY, QUERY_FIELDS, tid=tid, devcode=1, addr=MGMT_ADDR)


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


def srne_read(block: str, *, tid: int = 1) -> bytes:
    start, qty = READ_BLOCKS[block]
    rtu = rtu_read_holding(start, qty)
    return wrap_eyebond(
        FC_FORWARD, rtu, tid=tid, devcode=DEVCODE_SRNE, addr=COLLECTOR_ADDR
    )


def parse_eyebond(frame: bytes) -> dict[str, object]:
    if len(frame) < HDR:
        raise ValueError("short EyeBond header")
    tid = (frame[0] << 8) | frame[1]
    devcode = (frame[2] << 8) | frame[3]
    wire = (frame[4] << 8) | frame[5]
    total = wire + WIRE_OFF
    if total < HDR or len(frame) < total:
        raise ValueError(f"truncated frame wire={wire} have={len(frame)}")
    addr = frame[6]
    fc = frame[7]
    payload = frame[HDR:total]
    return {
        "tid": tid,
        "devcode": f"0x{devcode:04X}",
        "addr": addr,
        "fc": fc,
        "payload": payload,
        "total": total,
    }


def _s16(value: int) -> int:
    return value - 65536 if value >= 32768 else value


def parse_rtu(raw: bytes) -> dict[str, object]:
    data = raw
    stripped_prefix = False
    if len(data) >= 10 and data[0] == 0xFF and data[1] == 0x04:
        data = data[2:]
        stripped_prefix = True
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
    if fn not in (3, 4):
        raise ValueError(f"unexpected RTU fn {fn}")
    byte_count = data[2]
    need = 3 + byte_count + 2
    if need > len(data) or byte_count & 1:
        raise ValueError("bad RTU length")
    expect = crc16_modbus(data[: 3 + byte_count])
    got = data[3 + byte_count] | (data[3 + byte_count + 1] << 8)
    if expect != got:
        raise ValueError(f"rtu crc fail expect={expect:04x} got={got:04x}")
    regs = [(data[3 + i * 2] << 8) | data[4 + i * 2] for i in range(byte_count // 2)]
    return {
        "exception": False,
        "slave": slave,
        "fn": fn,
        "regs": regs,
        "stripped_ff04": stripped_prefix,
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


def self_test() -> None:
    hijack = hijack_payload("192.0.2.10")
    assert hijack == b"set>server=192.0.2.10:8899;"

    hb = heartbeat(dummy_date=True, tid=1)
    parsed = parse_eyebond(hb)
    assert parsed["fc"] == FC_HEARTBEAT
    assert parsed["addr"] == MGMT_ADDR
    assert parsed["payload"] == bytes((26, 1, 1, 0, 0, 0, 0, 60))
    assert parsed["total"] == 16
    assert (hb[4] << 8 | hb[5]) == 10  # wire = total - 6

    q = collector_query(tid=2)
    assert parse_eyebond(q)["payload"] == QUERY_FIELDS

    rtu = rtu_read_holding(SRNE_CFG_START, SRNE_CFG_N)
    assert rtu[0] == RTU_SLAVE and rtu[1] == 3
    assert crc16_modbus(rtu[:-2]) == rtu[-2] | (rtu[-1] << 8)

    frame = srne_read("cfg", tid=3)
    inner = parse_eyebond(frame)
    assert inner["fc"] == FC_FORWARD
    assert inner["addr"] == COLLECTOR_ADDR
    assert inner["devcode"] == "0x0001"
    assert inner["payload"] == rtu

    # Reply shape: optional 0xFF 0x04 prefix, then RTU FC3 with 2 regs.
    regs_body = bytes((RTU_SLAVE, 3, 4, 0x00, 47, 0x02, 0x1E))
    crc = crc16_modbus(regs_body)
    reply = bytes((0xFF, 0x04)) + regs_body + bytes((crc & 0xFF, crc >> 8))
    parsed_rtu = parse_rtu(reply)
    assert parsed_rtu["stripped_ff04"] is True
    assert parsed_rtu["regs"] == [47, 0x021E]

    cfg = decode_cfg(
        [
            47,
            542,
            0xFEE2,  # -28.6 A → charge
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
    assert cfg["dsg_a"] == 0.0
    assert cfg["pv1_w"] + cfg["pv2_w"] == 2414

    live = decode_live([3] + [0] * 10 + [1249] + [0, 0, 0, 40, 0, 350])
    assert live["mode"] == 3
    assert live["ac_out_w_l1"] == 1249
    assert live["inv_c"] == 35.0

    phase = decode_phase([0] * 8 + [826] + [0, 0, 0, 20])
    assert phase["ac_out_w_l2"] == 826
    assert phase["load_pct_l2"] == 20


def _print_map(info: dict[str, object]) -> None:
    for key, val in info.items():
        if isinstance(val, bytes):
            print(f"{key}: {_hex(val)}")
        else:
            print(f"{key}: {val}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_hijack = sub.add_parser("hijack", help="UDP 58899 ASCII (print only)")
    p_hijack.add_argument("listen_ip", help="RFC1918 address of the TCP 8899 listener")
    p_hijack.add_argument("--tcp-port", type=int, default=TCP_PORT)
    p_hb = sub.add_parser("heartbeat", help="EyeBond FC=1")
    p_hb.add_argument(
        "--dummy-date",
        action="store_true",
        help="2026-01-01 00:00:00 (collector accepted this; live UTC once FINed)",
    )
    p_hb.add_argument("--tid", type=int, default=1)
    p_q = sub.add_parser("query", help="EyeBond FC=2 identity 2,5,6,14")
    p_q.add_argument("--tid", type=int, default=1)
    p_read = sub.add_parser("read", help="SRNE FC3 inside EyeBond FC=4")
    p_read.add_argument("block", choices=sorted(READ_BLOCKS))
    p_read.add_argument("--tid", type=int, default=1)
    p_dec = sub.add_parser("decode", help="decode one EyeBond TCP frame (hex)")
    p_dec.add_argument("hex")
    p_rtu = sub.add_parser("parse-rtu", help="decode inner Modbus RTU (hex)")
    p_rtu.add_argument("hex")
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "hijack":
        print(hijack_payload(args.listen_ip, args.tcp_port).decode("ascii"))
    elif args.cmd == "heartbeat":
        print(_hex(heartbeat(dummy_date=args.dummy_date, tid=args.tid)))
    elif args.cmd == "query":
        print(_hex(collector_query(tid=args.tid)))
    elif args.cmd == "read":
        print(_hex(srne_read(args.block, tid=args.tid)))
    elif args.cmd == "decode":
        raw = bytes.fromhex(args.hex.replace(" ", ""))
        info = parse_eyebond(raw)
        _print_map(info)
    elif args.cmd == "parse-rtu":
        raw = bytes.fromhex(args.hex.replace(" ", ""))
        _print_map(parse_rtu(raw))
    elif args.cmd == "self-test":
        self_test()
        print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
