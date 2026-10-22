#!/usr/bin/env python3
"""Encode Nelko P21 TSPL (cloud command 0) print jobs.

Same ASCII TSPL bytes on BLE GATT 0000ff00 (write 0000ff02, notify
0000ff03, read 0000ff01, WRITE_NO_RESPONSE, MTU 512) and classic SPP
00001101. Helpers print payloads. They do not scan, GATT-connect, or
open an RFCOMM socket.

Commands are GB18030 (ASCII for this helper). BITMAP is
`BITMAP x,y,widthBytes,height,mode,` plus 1bpp MSB-first payload and
CRLF. isEncrypt=1 on P21 is RFID paper, not TSPL payload encryption.

Example:
    ./encode_nelko.py self-test
    ./encode_nelko.py size --width-mm 12 --height-mm 40
    ./encode_nelko.py job --width-mm 12 --height-mm 10 --payload 80
"""

from __future__ import annotations

import argparse
import sys

CRLF = b"\r\n"
ENC = "gb18030"
PRINTHEAD_DOTS = 96  # 12 mm at 8 dots/mm (203 dpi)
STATUS_ESC = bytes((0x1B, 0x21, 0x3F))  # ESC ! ?

VEC_SIZE_12_40 = "53495a45203132206d6d2c3430206d6d0d0a"
VEC_GAP_5 = "4741502035206d6d2c30206d6d0d0a"
VEC_DIRECTION = "444952454354494f4e20302c300d0a"
VEC_DENSITY_8 = "44454e5349545920380d0a"
VEC_CLS = "434c530d0a"
VEC_PRINT_1 = "5052494e5420310d0a"
VEC_BITMAP_80 = "4249544d415020302c302c312c312c302c800d0a"
VEC_STATUS = "1b213f"
VEC_TYPE = "7e21540d0a"


def _hex(data: bytes) -> str:
    return data.hex()


def parse_hex(raw: str) -> bytes:
    text = raw.strip().replace(" ", "").replace(":", "")
    if len(text) % 2:
        raise ValueError("hex length must be even")
    return bytes.fromhex(text)


def tspl(line: str) -> bytes:
    if not line.endswith("\r\n"):
        line = line + "\r\n"
    return line.encode(ENC)


def size_cmd(width_mm: float, height_mm: float) -> bytes:
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("size mm must be positive")
    w = int(width_mm) if width_mm == int(width_mm) else width_mm
    h = int(height_mm) if height_mm == int(height_mm) else height_mm
    return tspl(f"SIZE {w} mm,{h} mm")


def gap_cmd(gap_mm: float) -> bytes:
    if gap_mm < 0:
        raise ValueError("gap mm must be >= 0")
    g = int(gap_mm) if gap_mm == int(gap_mm) else gap_mm
    return tspl(f"GAP {g} mm,0 mm")


def direction_cmd(direction: int = 0, mirror: int = 0) -> bytes:
    if direction not in (0, 1) or mirror not in (0, 1):
        raise ValueError("direction and mirror are 0 or 1")
    return tspl(f"DIRECTION {direction},{mirror}")


def density_cmd(level: int) -> bytes:
    if not 0 <= level <= 15:
        raise ValueError("density 0-15")
    return tspl(f"DENSITY {level}")


def cls_cmd() -> bytes:
    return tspl("CLS")


def print_cmd(copies: int = 1) -> bytes:
    if not 1 <= copies <= 50:
        raise ValueError("copies 1-50")
    return tspl(f"PRINT {copies}")


def type_cmd() -> bytes:
    return tspl("~!T")


def status_cmd() -> bytes:
    return STATUS_ESC


def bitmap_cmd(
    payload: bytes,
    *,
    x: int = 0,
    y: int = 0,
    width_bytes: int | None = None,
    height: int | None = None,
    mode: int = 0,
) -> bytes:
    if mode not in (0, 1, 2):
        raise ValueError("bitmap mode 0 overwrite, 1 OR, 2 XOR")
    if not payload:
        raise ValueError("bitmap payload is empty")
    if width_bytes is None:
        width_bytes = len(payload)
    if height is None:
        if len(payload) % width_bytes:
            raise ValueError("payload length must divide width_bytes")
        height = len(payload) // width_bytes
    if width_bytes < 1 or height < 1:
        raise ValueError("bitmap geometry must be positive")
    if width_bytes * 8 > PRINTHEAD_DOTS:
        raise ValueError(f"width {width_bytes * 8} exceeds {PRINTHEAD_DOTS} dots")
    if len(payload) != width_bytes * height:
        raise ValueError("payload length must be width_bytes * height")
    header = f"BITMAP {x},{y},{width_bytes},{height},{mode},".encode(ENC)
    return header + payload + CRLF


def job_frames(
    *,
    width_mm: float = 12,
    height_mm: float = 40,
    gap_mm: float = 5,
    density: int | None = 8,
    copies: int = 1,
    payload: bytes | None = None,
) -> list[bytes]:
    frames = [
        size_cmd(width_mm, height_mm),
        gap_cmd(gap_mm),
        direction_cmd(0, 0),
    ]
    if density is not None:
        frames.append(density_cmd(density))
    frames.append(cls_cmd())
    frames.append(bitmap_cmd(payload or bytes((0x80,))))
    frames.append(print_cmd(copies))
    return frames


def self_test() -> None:
    assert _hex(size_cmd(12, 40)) == VEC_SIZE_12_40
    assert _hex(gap_cmd(5)) == VEC_GAP_5
    assert _hex(direction_cmd(0, 0)) == VEC_DIRECTION
    assert _hex(density_cmd(8)) == VEC_DENSITY_8
    assert _hex(cls_cmd()) == VEC_CLS
    assert _hex(print_cmd(1)) == VEC_PRINT_1
    assert _hex(bitmap_cmd(bytes((0x80,)))) == VEC_BITMAP_80
    assert _hex(status_cmd()) == VEC_STATUS
    assert _hex(type_cmd()) == VEC_TYPE
    job = job_frames()
    assert job[0] == size_cmd(12, 40)
    assert job[-1] == print_cmd(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    p_sz = sub.add_parser("size")
    p_sz.add_argument("--width-mm", type=float, default=12)
    p_sz.add_argument("--height-mm", type=float, default=40)
    p_gap = sub.add_parser("gap")
    p_gap.add_argument("--gap-mm", type=float, default=5)
    sub.add_parser("direction")
    p_den = sub.add_parser("density")
    p_den.add_argument("level", type=int, nargs="?", default=8)
    sub.add_parser("cls")
    p_pr = sub.add_parser("print")
    p_pr.add_argument("--copies", type=int, default=1)
    p_bm = sub.add_parser("bitmap")
    p_bm.add_argument("payload", help="1bpp row bytes as hex, e.g. 80")
    p_bm.add_argument("--width-bytes", type=int)
    p_bm.add_argument("--height", type=int)
    p_bm.add_argument("--mode", type=int, default=0)
    sub.add_parser("status")
    sub.add_parser("type")
    p_job = sub.add_parser("job")
    p_job.add_argument("--width-mm", type=float, default=12)
    p_job.add_argument("--height-mm", type=float, default=40)
    p_job.add_argument("--gap-mm", type=float, default=5)
    p_job.add_argument("--density", type=int, default=8)
    p_job.add_argument("--copies", type=int, default=1)
    p_job.add_argument("--payload", help="bitmap hex; default 80")
    p_dec = sub.add_parser("decode")
    p_dec.add_argument("hex")
    args = parser.parse_args(argv)

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "size":
        print(_hex(size_cmd(args.width_mm, args.height_mm)))
        return 0
    if args.cmd == "gap":
        print(_hex(gap_cmd(args.gap_mm)))
        return 0
    if args.cmd == "direction":
        print(_hex(direction_cmd(0, 0)))
        return 0
    if args.cmd == "density":
        print(_hex(density_cmd(args.level)))
        return 0
    if args.cmd == "cls":
        print(_hex(cls_cmd()))
        return 0
    if args.cmd == "print":
        print(_hex(print_cmd(args.copies)))
        return 0
    if args.cmd == "bitmap":
        print(
            _hex(
                bitmap_cmd(
                    parse_hex(args.payload),
                    width_bytes=args.width_bytes,
                    height=args.height,
                    mode=args.mode,
                )
            )
        )
        return 0
    if args.cmd == "status":
        print(_hex(status_cmd()))
        return 0
    if args.cmd == "type":
        print(_hex(type_cmd()))
        return 0
    if args.cmd == "job":
        payload = parse_hex(args.payload) if args.payload else None
        for pkt in job_frames(
            width_mm=args.width_mm,
            height_mm=args.height_mm,
            gap_mm=args.gap_mm,
            density=args.density,
            copies=args.copies,
            payload=payload,
        ):
            print(_hex(pkt))
        return 0
    if args.cmd == "decode":
        data = parse_hex(args.hex)
        try:
            print(data.decode(ENC))
        except UnicodeDecodeError:
            print(_hex(data))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    sys.exit(main())
