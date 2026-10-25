"""Build on-wire frames from a 1bpp bitmap using the pack encoders."""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from types import ModuleType

from profiles import Profile
from raster import Bitmap1bpp

_PRINTERS = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=8)
def _load(name: str, rel: str) -> ModuleType:
    path = _PRINTERS / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def niimbot() -> ModuleType:
    return _load("encode_niimbot", "NIIMBOT/B1/encode_niimbot.py")


def nelko() -> ModuleType:
    return _load("encode_nelko", "Nelko/P21/encode_nelko.py")


def aimotech() -> ModuleType:
    return _load("encode_aimotech", "Aimotech/D30/encode_aimotech.py")


def _run_rows(rows: tuple[bytes, ...], empty, bitmap, max_run: int = 200):
    frames: list[bytes] = []
    y = 0
    n = len(rows)
    while y < n:
        run = 1
        while y + run < n and run < max_run and rows[y + run] == rows[y]:
            run += 1
        if all(b == 0 for b in rows[y]):
            frames.append(empty(y, run))
        else:
            frames.append(bitmap(y, rows[y], run))
        y += run
    return frames


def build_niimbot(
    bitmap: Bitmap1bpp, *, copies: int = 1, density: int = 3
) -> list[bytes]:
    enc = niimbot()
    width = bitmap.width
    height = bitmap.height
    frames = [enc.connect_frame(), *enc.handshake_frames()]
    frames.append(enc.density_frame(density))
    frames.append(enc.label_type_frame(1))
    frames.append(enc.print_start_frame(1, task="b1"))
    frames.append(enc.u8_payload(enc.CMD_PAGE_START, 1))
    frames.append(enc.page_size_frame(height, width, copies, task="b1"))
    frames.extend(
        _run_rows(
            bitmap.rows,
            enc.empty_row_frame,
            enc.bitmap_row_frame,
        )
    )
    frames.append(enc.u8_payload(enc.CMD_PAGE_END, 1))
    frames.append(enc.u8_payload(enc.CMD_PRINT_STATUS, 1))
    frames.append(enc.u8_payload(enc.CMD_PRINT_END, 1))
    return frames


def build_nelko(
    bitmap: Bitmap1bpp,
    *,
    copies: int = 1,
    density: int = 15,
    gap_mm: float = 5,
    width_mm: float = 14,
    height_mm: float = 40,
) -> list[bytes]:
    enc = nelko()
    # pack_msb set-bit=black; live P21 wants 0-bit=black. SIZE is the
    # paper tag (14×40), not the 12 mm printhead width.
    payload = enc.invert_bits(bitmap.payload())
    return enc.job_frames(
        width_mm=width_mm,
        height_mm=height_mm,
        gap_mm=gap_mm,
        density=density,
        copies=copies,
        payload=payload,
        width_bytes=bitmap.width_bytes,
        height=bitmap.height,
        mode=1,
    )


def _aimotech_pixels(bitmap: Bitmap1bpp) -> list[list[int]]:
    pixels: list[list[int]] = []
    for row in bitmap.rows:
        line: list[int] = []
        for x in range(bitmap.width):
            bit = (row[x // 8] >> (7 - (x % 8))) & 1
            line.append(0 if bit else 255)
        pixels.append(line)
    return pixels


def build_aimotech(bitmap: Bitmap1bpp, *, copies: int = 1) -> list[bytes]:
    enc = aimotech()
    packed = enc.invert_pack(_aimotech_pixels(bitmap))
    frames = [*enc.handshake_frames(), enc.init_cmd()]
    for _ in range(copies):
        frames.append(
            enc.raster_cmd(
                packed,
                width_bytes=bitmap.width_bytes,
                height=bitmap.height,
            )
        )
        frames.append(enc.feed_cmd(23))
    return frames


def build_job(profile: Profile, bitmap: Bitmap1bpp, *, copies: int = 1) -> list[bytes]:
    if profile.key == "niimbot-b1":
        return build_niimbot(bitmap, copies=copies)
    if profile.key == "nelko-p21":
        return build_nelko(bitmap, copies=copies)
    if profile.key == "aimotech-d30":
        return build_aimotech(bitmap, copies=copies)
    raise KeyError(profile.key)


def self_test() -> None:
    from PIL import Image
    from raster import raster_image

    im = Image.new("RGB", (96, 8), (255, 255, 255))
    px = im.load()
    for y in range(8):
        px[0, y] = (0, 0, 0)
    bmp96 = raster_image(im, width_dots=96, max_height=16, fit="stretch", dither=False)
    nelko_frames = build_nelko(bmp96)
    assert nelko_frames[0] == b"\r\n"
    assert nelko_frames[1].startswith(b"SIZE 14 mm,40 mm")
    assert nelko_frames[3] == b"DIRECTION 1,1\r\n"
    assert nelko_frames[4] == b"DENSITY 15\r\n"
    assert nelko_frames[6].startswith(b"BITMAP 0,0,12,8,1,")
    assert nelko_frames[6][len(b"BITMAP 0,0,12,8,1,")] == 0x7F
    assert nelko_frames[-1] == b"PRINT 1\r\n"
    aim = build_aimotech(bmp96)
    assert aim[0] == b"\x1f\x11\x38"
    assert aim[4] == b"\x1b\x40"
    assert aim[5].startswith(b"\x1d\x76\x30\x00")
    im384 = Image.new("RGB", (384, 2), (255, 255, 255))
    px384 = im384.load()
    px384[0, 0] = (0, 0, 0)
    bmp384 = raster_image(
        im384, width_dots=384, max_height=8, fit="stretch", dither=False
    )
    niim = build_niimbot(bmp384)
    assert niim[0].hex() == "035555c10101c1aaaa"
    assert niim[-1].hex() == "5555f30101f3aaaa"
