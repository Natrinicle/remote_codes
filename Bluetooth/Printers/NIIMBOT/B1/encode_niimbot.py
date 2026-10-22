#!/usr/bin/env python3
"""Encode/decode NIIMBOT B1 (task b1) and B1 Pro (task v4) 55 55 frames.

Same bytes on BLE GATT and USB Type-C CDC. Helpers print payloads. They
do not scan, GATT-connect, or open a TTY.

Example:
    ./encode_niimbot.py self-test
    ./encode_niimbot.py connect
    ./encode_niimbot.py handshake
    ./encode_niimbot.py print-seq --height 320 --width 384
    ./encode_niimbot.py decode 555521010323aaaa
"""

from __future__ import annotations

import argparse
import sys

HEAD = b"\x55\x55"
TAIL = b"\xaa\xaa"
CONNECT_PREFIX = b"\x03"

CMD_PRINT_START = 0x01
CMD_PAGE_START = 0x03
CMD_SET_PAGE_SIZE = 0x13
CMD_RFID = 0x1A
CMD_SET_DENSITY = 0x21
CMD_SET_LABEL_TYPE = 0x23
CMD_PRINTER_INFO = 0x40
CMD_EMPTY_ROW = 0x84
CMD_BITMAP_ROW = 0x85
CMD_PRINT_STATUS = 0xA3
CMD_STATUS_DATA = 0xA5
CMD_CONNECT = 0xC1
CMD_CANCEL = 0xDA
CMD_HEARTBEAT = 0xDC
CMD_PAGE_END = 0xE3
CMD_PRINT_END = 0xF3

PRINTHEAD = {"b1": 384, "v4": 567}

INFO_KEYS = {
    "density": 0x01,
    "speed": 0x02,
    "label": 0x03,
    "shutdown": 0x07,
    "model": 0x08,
    "sw": 0x09,
    "battery": 0x0A,
    "serial": 0x0B,
    "hw": 0x0C,
    "mac": 0x0D,
    "area": 0x0F,
}

# B1 (protocol 3) must query these after connect or setup acks and never prints.
HANDSHAKE_INFO_ORDER = (0x08, 0x0B, 0x0D, 0x0A, 0x07, 0x03, 0x0C, 0x09)

CMD_NAMES = {
    CMD_PRINT_START: "PrintStart",
    0x02: "PrintStartAck",
    CMD_PAGE_START: "PageStart",
    0x04: "PageStartAck",
    CMD_SET_PAGE_SIZE: "SetPageSize",
    0x14: "SetPageSizeAck",
    CMD_RFID: "RfidInfo",
    0x1B: "RfidInfoAck",
    CMD_SET_DENSITY: "SetDensity",
    0x31: "SetDensityAck",
    CMD_SET_LABEL_TYPE: "SetLabelType",
    0x33: "SetLabelTypeAck",
    CMD_PRINTER_INFO: "PrinterInfo",
    CMD_EMPTY_ROW: "PrintEmptyRow",
    CMD_BITMAP_ROW: "PrintBitmapRow",
    0x86: "PrinterCheckLine",
    CMD_PRINT_STATUS: "PrintStatus",
    0xB3: "PrintStatusAck",
    CMD_STATUS_DATA: "PrinterStatusData",
    0xB5: "PrinterStatusDataAck",
    CMD_CONNECT: "Connect",
    0xC2: "ConnectAck",
    CMD_CANCEL: "CancelPrint",
    0xD0: "CancelAck",
    0xD3: "CheckLineOrUnsolicited",
    0xDB: "PrintError",
    CMD_HEARTBEAT: "Heartbeat",
    0xD9: "HeartbeatAck",
    0xDD: "HeartbeatAck",
    0xDE: "HeartbeatAck",
    0xDF: "HeartbeatAck",
    0xE0: "PageIndex",
    CMD_PAGE_END: "PageEnd",
    0xE4: "PageEndAck",
    CMD_PRINT_END: "PrintEnd",
    0xF4: "PrintEndAck",
}

# Independent vectors (XOR bcc computed here; not copied from another client).
VEC_CONNECT = "035555c10101c1aaaa"
VEC_DENSITY3 = "555521010323aaaa"
VEC_LABEL1 = "555523010123aaaa"
VEC_PRINT_START_B1 = "555501070001000000000007aaaa"
VEC_PAGE_START = "555503010103aaaa"
VEC_PAGE_SIZE_B1 = "55551306014001800001d4aaaa"
VEC_STATUS_DATA = "5555a50101a5aaaa"
VEC_INFO08 = "555540010849aaaa"
VEC_HEARTBEAT04 = "5555dc0104d9aaaa"
VEC_EMPTY_ROW = "5555840300000186aaaa"
VEC_PAGE_END = "5555e30101e3aaaa"
VEC_PRINT_END = "5555f30101f3aaaa"
VEC_PRINT_STATUS = "5555a30101a3aaaa"
VEC_BITMAP_ROW = "555585070000000100018002aaaa"
VEC_RFID = "55551a01011aaaaa"
VEC_CANCEL = "5555da0101daaaaa"
VEC_PRINT_START_V4 = "555501090001000000000003000aaaaa"
VEC_PAGE_SIZE_V4 = "5555130d01400180000100000000000000dfaaaa"


def _hex(data: bytes) -> str:
    return data.hex()


def frame(cmd: int, data: bytes = b"") -> bytes:
    """55 55 | cmd | len | data | bcc | AA AA. bcc = cmd XOR len XOR data."""
    if not 0 <= cmd <= 0xFF:
        raise ValueError(f"cmd {cmd} out of range")
    length = len(data)
    if length > 255:
        raise ValueError(f"payload {length} exceeds 255")
    bcc = cmd ^ length
    for byte in data:
        bcc ^= byte
    return HEAD + bytes((cmd, length)) + data + bytes((bcc,)) + TAIL


def connect_frame() -> bytes:
    """Connect 0xC1 with the extra 0x03 prefix in front of 55 55."""
    return CONNECT_PREFIX + frame(CMD_CONNECT, b"\x01")


def u8_payload(cmd: int, value: int = 1) -> bytes:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"u8 {value} out of range")
    return frame(cmd, bytes((value,)))


def parse_info_key(raw: str) -> int:
    key = raw.strip().lower()
    if key in INFO_KEYS:
        return INFO_KEYS[key]
    key = key.removeprefix("0x")
    val = int(key, 16)
    if not 0 <= val <= 0xFF:
        raise ValueError(f"info key {raw!r} out of range")
    return val


def info_frame(key: int) -> bytes:
    if not 0 <= key <= 0xFF:
        raise ValueError(f"info key {key} out of range")
    return frame(CMD_PRINTER_INFO, bytes((key,)))


def density_frame(level: int) -> bytes:
    if not 1 <= level <= 5:
        raise ValueError("density 1-5")
    return u8_payload(CMD_SET_DENSITY, level)


def label_type_frame(kind: int) -> bytes:
    if not 1 <= kind <= 255:
        raise ValueError("label-type 1-255")
    return u8_payload(CMD_SET_LABEL_TYPE, kind)


def print_start_frame(pages: int, *, task: str = "b1", speed: int = 3) -> bytes:
    if not 1 <= pages <= 0xFFFF:
        raise ValueError("pages 1-65535")
    body = bytes((pages >> 8, pages & 0xFF, 0, 0, 0, 0, 0))
    if task == "v4":
        if not 1 <= speed <= 5:
            raise ValueError("speed 1-5")
        body = bytes((pages >> 8, pages & 0xFF, 0, 0, 0, 0, 0, speed, 0))
    elif task != "b1":
        raise ValueError(f"task {task!r} is not b1 or v4")
    return frame(CMD_PRINT_START, body)


def page_size_frame(
    height: int, width: int, copies: int = 1, *, task: str = "b1"
) -> bytes:
    if not 1 <= height <= 0xFFFF:
        raise ValueError("height 1-65535")
    if not 1 <= width <= 0xFFFF:
        raise ValueError("width 1-65535")
    if not 1 <= copies <= 0xFFFF:
        raise ValueError("copies 1-65535")
    limit = PRINTHEAD[task]
    if width > limit:
        raise ValueError(f"width {width} exceeds {task} printhead {limit}")
    geom = bytes(
        (
            height >> 8,
            height & 0xFF,
            width >> 8,
            width & 0xFF,
            copies >> 8,
            copies & 0xFF,
        )
    )
    if task == "v4":
        geom = geom + bytes(7)
    elif task != "b1":
        raise ValueError(f"task {task!r} is not b1 or v4")
    return frame(CMD_SET_PAGE_SIZE, geom)


def empty_row_frame(row: int, count: int = 1) -> bytes:
    if not 0 <= row <= 0xFFFF:
        raise ValueError("row 0-65535")
    if not 1 <= count <= 255:
        raise ValueError("empty-row count 1-255")
    return frame(CMD_EMPTY_ROW, bytes((row >> 8, row & 0xFF, count)))


def _black_bits(payload: bytes) -> int:
    return sum(byte.bit_count() for byte in payload)


def bitmap_row_frame(row: int, payload: bytes, run: int = 1) -> bytes:
    """Total-mode 0x85: row:u16 | 00 | black_lo black_hi | run | row bytes.

    1bpp MSB-first, set bit = black. black_* is the popcount of payload
    (little-endian), not the byte length.
    """
    if not 0 <= row <= 0xFFFF:
        raise ValueError("row 0-65535")
    if not 1 <= run <= 255:
        raise ValueError("run 1-255")
    if not payload:
        raise ValueError("bitmap payload is empty")
    black = _black_bits(payload)
    header = bytes((row >> 8, row & 0xFF, 0, black & 0xFF, (black >> 8) & 0xFF, run))
    return frame(CMD_BITMAP_ROW, header + payload)


def handshake_frames() -> list[bytes]:
    frames = [u8_payload(CMD_STATUS_DATA, 1)]
    frames.extend(info_frame(key) for key in HANDSHAKE_INFO_ORDER)
    frames.append(u8_payload(CMD_HEARTBEAT, 4))
    return frames


def print_seq_frames(
    *,
    task: str = "b1",
    density: int = 3,
    label_type: int = 1,
    pages: int = 1,
    height: int = 320,
    width: int = 384,
    copies: int = 1,
    speed: int = 3,
    payload: bytes | None = None,
    row: int = 0,
    run: int = 1,
) -> list[bytes]:
    out = [connect_frame()]
    if task == "b1":
        out.extend(handshake_frames())
    out.append(density_frame(density))
    out.append(label_type_frame(label_type))
    out.append(print_start_frame(pages, task=task, speed=speed))
    if task == "b1":
        out.append(u8_payload(CMD_PAGE_START, 1))
    else:
        out.append(u8_payload(CMD_PRINT_STATUS, 1))
    out.append(page_size_frame(height, width, copies, task=task))
    if payload is not None:
        out.append(bitmap_row_frame(row, payload, run))
    else:
        out.append(empty_row_frame(row, run))
    out.append(u8_payload(CMD_PAGE_END, 1))
    out.append(u8_payload(CMD_PRINT_STATUS, 1))
    out.append(u8_payload(CMD_PRINT_END, 1))
    return out


def _bcc_ok(cmd: int, data: bytes, bcc: int) -> bool:
    acc = cmd ^ len(data)
    for byte in data:
        acc ^= byte
    return acc == bcc


def iter_frames(blob: bytes) -> list[dict[str, object]]:
    """Cut 55 55 frames from a blob. Optional leading 0x03 on Connect."""
    found: list[dict[str, object]] = []
    i = 0
    prefix = False
    if blob[:1] == CONNECT_PREFIX and blob[1:3] == HEAD:
        prefix = True
        i = 1
    while i + 7 <= len(blob):
        if blob[i : i + 2] != HEAD:
            i += 1
            continue
        cmd = blob[i + 2]
        length = blob[i + 3]
        total = length + 7
        if i + total > len(blob):
            break
        pkt = blob[i : i + total]
        data = pkt[4 : 4 + length]
        bcc = pkt[4 + length]
        tail = pkt[5 + length :]
        name = CMD_NAMES.get(cmd)
        if name is None and 0x41 <= cmd <= 0x4F:
            name = f"PrinterInfoAck_0x{cmd:02x}"
        rec: dict[str, object] = {
            "cmd": cmd,
            "name": name or f"cmd_0x{cmd:02x}",
            "len": length,
            "data": data,
            "bcc": bcc,
            "bcc_ok": _bcc_ok(cmd, data, bcc),
            "tail_ok": tail == TAIL,
            "connect_prefix": prefix,
        }
        if cmd == 0xB3 and len(data) >= 4:
            rec["page"] = (data[0] << 8) | data[1]
            rec["print_pct"] = data[2]
            rec["feed_pct"] = data[3]
        found.append(rec)
        prefix = False
        i += total
    return found


def parse_hex(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", "").replace(":", ""))


def self_test() -> None:
    assert connect_frame().hex() == VEC_CONNECT
    assert density_frame(3).hex() == VEC_DENSITY3
    assert label_type_frame(1).hex() == VEC_LABEL1
    assert print_start_frame(1, task="b1").hex() == VEC_PRINT_START_B1
    assert u8_payload(CMD_PAGE_START, 1).hex() == VEC_PAGE_START
    assert page_size_frame(320, 384, 1, task="b1").hex() == VEC_PAGE_SIZE_B1
    assert u8_payload(CMD_STATUS_DATA, 1).hex() == VEC_STATUS_DATA
    assert info_frame(0x08).hex() == VEC_INFO08
    assert u8_payload(CMD_HEARTBEAT, 4).hex() == VEC_HEARTBEAT04
    assert empty_row_frame(0, 1).hex() == VEC_EMPTY_ROW
    assert u8_payload(CMD_PAGE_END, 1).hex() == VEC_PAGE_END
    assert u8_payload(CMD_PRINT_END, 1).hex() == VEC_PRINT_END
    assert u8_payload(CMD_PRINT_STATUS, 1).hex() == VEC_PRINT_STATUS
    assert bitmap_row_frame(0, bytes((0x80,)), 1).hex() == VEC_BITMAP_ROW
    assert u8_payload(CMD_RFID, 1).hex() == VEC_RFID
    assert u8_payload(CMD_CANCEL, 1).hex() == VEC_CANCEL
    assert print_start_frame(1, task="v4", speed=3).hex() == VEC_PRINT_START_V4
    assert page_size_frame(320, 384, 1, task="v4").hex() == VEC_PAGE_SIZE_V4
    pkt = density_frame(3)
    recs = iter_frames(pkt)
    assert len(recs) == 1
    assert recs[0]["name"] == "SetDensity"
    assert recs[0]["bcc_ok"] is True
    recs = iter_frames(connect_frame())
    assert recs[0]["connect_prefix"] is True
    assert recs[0]["name"] == "Connect"
    hs = handshake_frames()
    assert len(hs) == 10
    assert hs[0].hex() == VEC_STATUS_DATA
    assert hs[1].hex() == VEC_INFO08
    assert hs[-1].hex() == VEC_HEARTBEAT04
    seq = print_seq_frames(task="b1")
    assert seq[0].hex() == VEC_CONNECT
    assert seq[-1].hex() == VEC_PRINT_END


def _add_job_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--density", type=int, default=3)
    parser.add_argument("--label-type", type=int, default=1)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument("--width", type=int, default=384)
    parser.add_argument("--copies", type=int, default=1)
    parser.add_argument("--speed", type=int, default=3)
    parser.add_argument("--row", type=int, default=0)
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument(
        "--payload",
        default=None,
        help="bitmap row hex (MSB-first 1bpp); default is one empty row",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        choices=("b1", "v4"),
        default="b1",
        help="b1 = B1 203 dpi 7-byte PrintStart; v4 = B1 Pro 9/13-byte",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    sub.add_parser("connect")
    sub.add_parser("status-data")
    p_info = sub.add_parser("info")
    p_info.add_argument("key", help="name (model, serial, …) or hex (08)")
    sub.add_parser("heartbeat")
    sub.add_parser("handshake")
    p_den = sub.add_parser("density")
    p_den.add_argument("level", type=int, nargs="?", default=3)
    p_lab = sub.add_parser("label-type")
    p_lab.add_argument("kind", type=int, nargs="?", default=1)
    p_ps = sub.add_parser("print-start")
    p_ps.add_argument("--pages", type=int, default=1)
    p_ps.add_argument("--speed", type=int, default=3)
    sub.add_parser("page-start")
    p_sz = sub.add_parser("page-size")
    p_sz.add_argument("--height", type=int, default=320)
    p_sz.add_argument("--width", type=int, default=384)
    p_sz.add_argument("--copies", type=int, default=1)
    p_er = sub.add_parser("empty-row")
    p_er.add_argument("--row", type=int, default=0)
    p_er.add_argument("--count", type=int, default=1)
    p_br = sub.add_parser("bitmap-row")
    p_br.add_argument("--row", type=int, default=0)
    p_br.add_argument("--run", type=int, default=1)
    p_br.add_argument("payload", help="row bytes as hex, e.g. 80")
    sub.add_parser("page-end")
    sub.add_parser("print-status")
    sub.add_parser("print-end")
    sub.add_parser("rfid")
    sub.add_parser("cancel")
    p_seq = sub.add_parser("print-seq")
    _add_job_args(p_seq)
    p_dec = sub.add_parser("decode")
    p_dec.add_argument("hex")
    args = parser.parse_args()
    task: str = args.task

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "connect":
        print(_hex(connect_frame()))
        return 0
    if args.cmd == "status-data":
        print(_hex(u8_payload(CMD_STATUS_DATA, 1)))
        return 0
    if args.cmd == "info":
        print(_hex(info_frame(parse_info_key(args.key))))
        return 0
    if args.cmd == "heartbeat":
        print(_hex(u8_payload(CMD_HEARTBEAT, 4)))
        return 0
    if args.cmd == "handshake":
        for pkt in handshake_frames():
            print(_hex(pkt))
        return 0
    if args.cmd == "density":
        print(_hex(density_frame(args.level)))
        return 0
    if args.cmd == "label-type":
        print(_hex(label_type_frame(args.kind)))
        return 0
    if args.cmd == "print-start":
        print(_hex(print_start_frame(args.pages, task=task, speed=args.speed)))
        return 0
    if args.cmd == "page-start":
        print(_hex(u8_payload(CMD_PAGE_START, 1)))
        return 0
    if args.cmd == "page-size":
        print(_hex(page_size_frame(args.height, args.width, args.copies, task=task)))
        return 0
    if args.cmd == "empty-row":
        print(_hex(empty_row_frame(args.row, args.count)))
        return 0
    if args.cmd == "bitmap-row":
        print(_hex(bitmap_row_frame(args.row, parse_hex(args.payload), args.run)))
        return 0
    if args.cmd == "page-end":
        print(_hex(u8_payload(CMD_PAGE_END, 1)))
        return 0
    if args.cmd == "print-status":
        print(_hex(u8_payload(CMD_PRINT_STATUS, 1)))
        return 0
    if args.cmd == "print-end":
        print(_hex(u8_payload(CMD_PRINT_END, 1)))
        return 0
    if args.cmd == "rfid":
        print(_hex(u8_payload(CMD_RFID, 1)))
        return 0
    if args.cmd == "cancel":
        print(_hex(u8_payload(CMD_CANCEL, 1)))
        return 0
    if args.cmd == "print-seq":
        payload = parse_hex(args.payload) if args.payload else None
        for pkt in print_seq_frames(
            task=task,
            density=args.density,
            label_type=args.label_type,
            pages=args.pages,
            height=args.height,
            width=args.width,
            copies=args.copies,
            speed=args.speed,
            payload=payload,
            row=args.row,
            run=args.run,
        ):
            print(_hex(pkt))
        return 0
    if args.cmd == "decode":
        recs = iter_frames(parse_hex(args.hex))
        if not recs:
            print("no 55 55 frame", file=sys.stderr)
            return 1
        for rec in recs:
            bits = [
                rec["name"],
                f"cmd=0x{rec['cmd']:02x}",
                f"len={rec['len']}",
                f"data={_hex(rec['data'])}",
                "bcc_ok" if rec["bcc_ok"] else "bcc_bad",
            ]
            if rec["connect_prefix"]:
                bits.append("prefix03")
            if not rec["tail_ok"]:
                bits.append("tail_bad")
            if "page" in rec:
                bits.append(f"page={rec['page']}")
                bits.append(f"print%={rec['print_pct']}")
            print(" ".join(str(b) for b in bits))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
