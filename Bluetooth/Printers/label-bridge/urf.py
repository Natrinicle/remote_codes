"""Decode Apple AirPrint URF (UNIRAST) into RGB pages.

Format from public UNIRAST notes: 12-byte file header, 32-byte page
header, then per-line unsigned repeat plus a PackBits-like stream.
0x80 fills the rest of the line with white. This decoder is original.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"UNIRAST\x00"


@dataclass(frozen=True)
class UrfPage:
    width: int
    height: int
    dpi: int
    bpp: int
    rgb: bytes


def _pixel_size(bpp: int) -> int:
    if bpp in (8, 24, 32):
        return bpp // 8
    if bpp == 1:
        return 1
    raise ValueError(f"unsupported URF bpp {bpp}")


def _to_rgb(pixel: bytes, bpp: int) -> bytes:
    if bpp == 24:
        return pixel[:3]
    if bpp == 32:
        return pixel[:3]
    if bpp == 8:
        return bytes((pixel[0], pixel[0], pixel[0]))
    if bpp == 1:
        v = 0 if pixel[0] == 0 else 255
        return bytes((v, v, v))
    raise ValueError(f"unsupported URF bpp {bpp}")


def _white(bpp: int) -> bytes:
    return b"\xff" * _pixel_size(bpp)


def decode_urf(data: bytes) -> list[UrfPage]:
    if len(data) < 12 or data[:8] != MAGIC:
        raise ValueError("not UNIRAST")
    (pages,) = struct.unpack(">I", data[8:12])
    if pages < 1 or pages > 64:
        raise ValueError(f"URF page count {pages} out of range")
    off = 12
    out: list[UrfPage] = []
    for _ in range(pages):
        page, off = _decode_page(data, off)
        out.append(page)
    return out


def _decode_page(data: bytes, off: int) -> tuple[UrfPage, int]:
    if off + 32 > len(data):
        raise ValueError("truncated URF page header")
    bpp = data[off]
    width, height, dpi = struct.unpack(">III", data[off + 12 : off + 24])
    off += 32
    if width < 1 or height < 1 or width > 12000 or height > 18000:
        raise ValueError(f"URF geometry {width}x{height} rejected")
    px = _pixel_size(bpp)
    white = _white(bpp)
    rgb = bytearray(width * height * 3)
    y = 0
    while y < height:
        if off >= len(data):
            raise ValueError("truncated URF line repeat")
        extra = data[off]
        off += 1
        line, off = _decode_line(data, off, width, px, white)
        copies = extra + 1
        if y + copies > height:
            copies = height - y
        row_rgb = bytearray()
        for i in range(width):
            row_rgb += _to_rgb(line[i * px : (i + 1) * px], bpp)
        for _ in range(copies):
            start = y * width * 3
            rgb[start : start + width * 3] = row_rgb
            y += 1
    return UrfPage(width, height, dpi or 203, bpp, bytes(rgb)), off


def _decode_line(
    data: bytes, off: int, width: int, px: int, white: bytes
) -> tuple[bytes, int]:
    line = bytearray(width * px)
    filled = 0
    while filled < width:
        if off >= len(data):
            raise ValueError("truncated URF packbits")
        code = data[off]
        off += 1
        signed = code - 256 if code >= 128 else code
        if signed == -128:
            remain = width - filled
            line[filled * px :] = white * remain
            filled = width
            break
        if signed >= 0:
            n = signed + 1
            if off + px > len(data):
                raise ValueError("truncated URF repeat pixel")
            pix = data[off : off + px]
            off += px
            for _ in range(n):
                if filled >= width:
                    break
                line[filled * px : (filled + 1) * px] = pix
                filled += 1
        else:
            n = (-signed) + 1
            nbytes = n * px
            if off + nbytes > len(data):
                raise ValueError("truncated URF literal")
            take = min(n, width - filled)
            line[filled * px : (filled + take) * px] = data[off : off + take * px]
            off += nbytes
            filled += take
    return bytes(line), off


def encode_gray_page(width: int, height: int, dpi: int, gray: bytes) -> bytes:
    """Encode 8-bpp gray (0=black) as a one-page URF. Used by self-test."""
    if len(gray) != width * height:
        raise ValueError("gray length")
    out = bytearray(MAGIC)
    out += struct.pack(">I", 1)
    out += bytes((8, 0, 0, 4)) + struct.pack(">IIIIIII", 1, 0, width, height, dpi, 0, 0)
    for y in range(height):
        out.append(0)  # this line once
        row = gray[y * width : (y + 1) * width]
        i = 0
        while i < width:
            run = 1
            while i + run < width and run < 128 and row[i + run] == row[i]:
                run += 1
            out.append(run - 1)  # repeat pixel run times
            out.append(row[i])
            i += run
    return bytes(out)


def self_test() -> None:
    width, height, dpi = 8, 2, 203
    gray = bytes([0, 255, 255, 255, 255, 255, 255, 255] * 2)
    blob = encode_gray_page(width, height, dpi, gray)
    pages = decode_urf(blob)
    assert len(pages) == 1
    page = pages[0]
    assert page.width == 8 and page.height == 2
    assert page.rgb[:3] == b"\x00\x00\x00"
    assert page.rgb[3:6] == b"\xff\xff\xff"
