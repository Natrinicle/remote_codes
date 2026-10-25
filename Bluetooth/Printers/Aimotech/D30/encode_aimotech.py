#!/usr/bin/env python3
"""Encode Aimotech / Print Master D30 ESC/POS raster jobs.

Print Master 5.23.1 (`com.project.aimotech.printmaster`) connects over
classic RFCOMM SPP `00001101-0000-1000-8000-00805f9b34fb` (BluetoothSPP).
This APK has no GATT UUID table. Helpers print payloads. They do not
scan, GATT-connect, or open an RFCOMM socket.

D30Printer (QuinPrinter): ESC @ init, GS v 0 raster (`InsSet.Y` +
`XNvUtil.img2Nv(..., 128, true)`), ESC d 23 feed. Handshake after
connect is `1F 11 38`, `12`, `13`, `07`. Printhead 96 dots (12 mm at
8 dots/mm). img2Nv invert=true walks bottom-right to top-left.

Example:
    ./encode_aimotech.py self-test
    ./encode_aimotech.py init
    ./encode_aimotech.py handshake
    ./encode_aimotech.py print-seq --width-bytes 12 --height 1
"""

from __future__ import annotations

import argparse
import sys

ESC = 0x1B
GS = 0x1D
US = 0x1F

CMD_INIT = bytes((ESC, 0x40))  # ESC @
CMD_FEED = bytes((ESC, 0x64, 23))  # ESC d 23
CMD_GS_V0 = bytes((GS, 0x76, 0x30, 0x00))  # GS v 0 m=0
PRINTHEAD_BYTES = 12  # D30Printer.N = 12; O = 96 dots

# InsGet after connect (PrinterKit.AnonymousClass3).
GET_38 = bytes((US, 0x11, 0x38))
GET_12 = bytes((US, 0x11, 0x12))
GET_13 = bytes((US, 0x11, 0x13))
GET_07 = bytes((US, 0x11, 0x07))

GET_NAMES = {
    0x07: "get-07",
    0x12: "get-12",
    0x13: "get-13",
    0x38: "get-38",
}

VEC_INIT = "1b40"
VEC_GET_38 = "1f1138"
VEC_GET_12 = "1f1112"
VEC_GET_13 = "1f1113"
VEC_GET_07 = "1f1107"
VEC_FEED = "1b6417"
VEC_RASTER_EMPTY = "1d7630000c000100000000000000000000000000"
VEC_RASTER_BLACK_LSB = "1d7630000100010001"


def _hex(data: bytes) -> str:
    return data.hex()


def parse_hex(raw: str) -> bytes:
    text = raw.strip().replace(" ", "").replace(":", "")
    if len(text) % 2:
        raise ValueError("hex length must be even")
    return bytes.fromhex(text)


def init_cmd() -> bytes:
    return CMD_INIT


def feed_cmd(lines: int = 23) -> bytes:
    if not 0 <= lines <= 255:
        raise ValueError("feed lines 0-255")
    return bytes((ESC, 0x64, lines))


def get_cmd(code: int) -> bytes:
    if not 0 <= code <= 255:
        raise ValueError("get code 0-255")
    return bytes((US, 0x11, code))


def handshake_frames() -> list[bytes]:
    return [GET_38, GET_12, GET_13, GET_07]


def raster_cmd(payload: bytes, *, width_bytes: int, height: int) -> bytes:
    if width_bytes < 1 or height < 1:
        raise ValueError("raster geometry must be positive")
    if width_bytes > PRINTHEAD_BYTES:
        raise ValueError(f"width_bytes {width_bytes} exceeds D30 {PRINTHEAD_BYTES}")
    if len(payload) != width_bytes * height:
        raise ValueError("payload length must be width_bytes * height")
    header = CMD_GS_V0 + bytes(
        (width_bytes & 0xFF, width_bytes >> 8, height & 0xFF, height >> 8)
    )
    return header + payload


def invert_pack(rows: list[list[int]], threshold: int = 128) -> bytes:
    """Pack 1bpp like XNvUtil.img2Nv invert=true (bottom-right to top-left)."""
    if not rows:
        raise ValueError("no rows")
    height = len(rows)
    width = len(rows[0])
    if width % 8:
        raise ValueError("width must be a multiple of 8")
    width_bytes = width // 8
    out = bytearray(width_bytes * height)
    idx = 0
    bit_count = 0
    acc = 0
    for y in range(height - 1, -1, -1):
        row = rows[y]
        if len(row) != width:
            raise ValueError("ragged rows")
        for x in range(width - 1, -1, -1):
            if row[x] < threshold:
                acc += 1
            bit_count += 1
            if bit_count == 8:
                out[idx] = acc
                idx += 1
                bit_count = 0
                acc = 0
            else:
                acc <<= 1
    return bytes(out)


def empty_payload(width_bytes: int, height: int) -> bytes:
    return bytes(width_bytes * height)


def print_seq_frames(
    *,
    width_bytes: int = PRINTHEAD_BYTES,
    height: int = 1,
    payload: bytes | None = None,
    copies: int = 1,
) -> list[bytes]:
    if not 1 <= copies <= 255:
        raise ValueError("copies 1-255")
    body = payload if payload is not None else empty_payload(width_bytes, height)
    frames = [init_cmd()]
    for _ in range(copies):
        frames.append(raster_cmd(body, width_bytes=width_bytes, height=height))
        frames.append(feed_cmd(23))
    return frames


def job_bytes(
    *,
    width_bytes: int = PRINTHEAD_BYTES,
    height: int = 1,
    payload: bytes | None = None,
    copies: int = 1,
) -> bytes:
    """Concatenated ESC @ + GS v 0 + ESC d 23 job for an RFCOMM write."""
    return b"".join(
        print_seq_frames(
            width_bytes=width_bytes,
            height=height,
            payload=payload,
            copies=copies,
        )
    )


def self_test() -> None:
    assert _hex(init_cmd()) == VEC_INIT
    assert _hex(get_cmd(0x38)) == VEC_GET_38
    assert _hex(get_cmd(0x12)) == VEC_GET_12
    assert _hex(get_cmd(0x13)) == VEC_GET_13
    assert _hex(get_cmd(0x07)) == VEC_GET_07
    assert handshake_frames() == [GET_38, GET_12, GET_13, GET_07]
    assert _hex(feed_cmd(23)) == VEC_FEED
    empty = raster_cmd(bytes(12), width_bytes=12, height=1)
    assert _hex(empty) == VEC_RASTER_EMPTY
    packed = invert_pack([[0, 255, 255, 255, 255, 255, 255, 255]])
    assert packed == bytes((0x01,))
    assert _hex(raster_cmd(packed, width_bytes=1, height=1)) == VEC_RASTER_BLACK_LSB
    seq = print_seq_frames(width_bytes=12, height=1)
    assert seq[0] == init_cmd()
    assert seq[1] == empty
    assert seq[2] == feed_cmd(23)
    joined = job_bytes(width_bytes=12, height=1)
    assert joined == init_cmd() + empty + feed_cmd(23)
    two = job_bytes(width_bytes=12, height=1, copies=2)
    assert two == init_cmd() + empty + feed_cmd(23) + empty + feed_cmd(23)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    sub.add_parser("init")
    sub.add_parser("handshake")
    p_get = sub.add_parser("get")
    p_get.add_argument("code", help="hex byte after 1F 11, e.g. 38")
    p_feed = sub.add_parser("feed")
    p_feed.add_argument("lines", type=int, nargs="?", default=23)
    p_rs = sub.add_parser("raster")
    p_rs.add_argument("--width-bytes", type=int, default=PRINTHEAD_BYTES)
    p_rs.add_argument("--height", type=int, default=1)
    p_rs.add_argument("--payload", help="row bytes as hex; default zeros")
    p_seq = sub.add_parser("print-seq")
    p_seq.add_argument("--width-bytes", type=int, default=PRINTHEAD_BYTES)
    p_seq.add_argument("--height", type=int, default=1)
    p_seq.add_argument("--copies", type=int, default=1)
    p_seq.add_argument("--payload", help="row bytes as hex; default zeros")
    p_dec = sub.add_parser("decode")
    p_dec.add_argument("hex")
    args = parser.parse_args(argv)

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "init":
        print(_hex(init_cmd()))
        return 0
    if args.cmd == "handshake":
        for pkt in handshake_frames():
            print(_hex(pkt))
        return 0
    if args.cmd == "get":
        print(_hex(get_cmd(int(args.code, 16))))
        return 0
    if args.cmd == "feed":
        print(_hex(feed_cmd(args.lines)))
        return 0
    if args.cmd == "raster":
        payload = (
            parse_hex(args.payload)
            if args.payload
            else empty_payload(args.width_bytes, args.height)
        )
        print(
            _hex(raster_cmd(payload, width_bytes=args.width_bytes, height=args.height))
        )
        return 0
    if args.cmd == "print-seq":
        payload = parse_hex(args.payload) if args.payload else None
        for pkt in print_seq_frames(
            width_bytes=args.width_bytes,
            height=args.height,
            payload=payload,
            copies=args.copies,
        ):
            print(_hex(pkt))
        return 0
    if args.cmd == "decode":
        data = parse_hex(args.hex)
        if data.startswith(CMD_INIT) and len(data) == 2:
            print("init ESC @")
            return 0
        if data[:2] == bytes((US, 0x11)) and len(data) == 3:
            code = data[2]
            print(f"get 1F 11 {code:02x} {GET_NAMES.get(code, '')}".rstrip())
            return 0
        if data[:4] == CMD_GS_V0 and len(data) >= 8:
            width = data[4] | (data[5] << 8)
            height = data[6] | (data[7] << 8)
            print(f"GS v 0 raster {width}x{height} payload {len(data) - 8} B")
            return 0
        if data[:2] == bytes((ESC, 0x64)) and len(data) == 3:
            print(f"feed ESC d {data[2]}")
            return 0
        print(_hex(data))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    sys.exit(main())
