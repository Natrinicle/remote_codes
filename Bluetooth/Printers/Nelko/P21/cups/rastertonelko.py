#!/usr/bin/env python3
"""CUPS filter: PNG/JPEG/PDF/CUPS-raster → Nelko P21 TSPL2.

argv: job-id user title copies options [file]
Stdout is the TSPL job the backend writes over RFCOMM. Proven framing:
leading CRLF, SIZE 14×40 mm, GAP 5, DIRECTION 1,1, DENSITY 15, CLS,
BITMAP mode 1, 0-bit black, PRINT.

PIL mode-1 `.tobytes()` is already 0=black. Do not use pack_msb here.
"""

from __future__ import annotations

import struct
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

WIDTH_DOTS = 96
HEIGHT_DOTS = 320
DPI = 203
WIDTH_MM = 14
HEIGHT_MM = 40
GAP_MM = 5
DEFAULT_DENSITY = 15
HEADER2 = 1796


def log(msg: str) -> None:
    print(f"rastertonelko: {msg}", file=sys.stderr, flush=True)


def build_tspl(
    payload: bytes,
    *,
    width_dots: int = WIDTH_DOTS,
    height_dots: int = HEIGHT_DOTS,
    width_mm: int = WIDTH_MM,
    height_mm: int = HEIGHT_MM,
    gap_mm: int = GAP_MM,
    density: int = DEFAULT_DENSITY,
    copies: int = 1,
) -> bytes:
    if width_dots % 8:
        raise ValueError("width_dots must be a multiple of 8")
    need = (width_dots // 8) * height_dots
    if len(payload) != need:
        raise ValueError(f"payload {len(payload)} != {need}")
    if not 1 <= copies <= 50:
        raise ValueError("copies 1-50")
    if not 0 <= density <= 15:
        raise ValueError("density 0-15")
    header = (
        f"\r\nSIZE {width_mm} mm,{height_mm} mm\r\n"
        f"GAP {gap_mm} mm,0 mm\r\n"
        "DIRECTION 1,1\r\n"
        f"DENSITY {density}\r\n"
        "CLS\r\n"
        f"BITMAP 0,0,{width_dots // 8},{height_dots},1,"
    ).encode("ascii")
    return header + payload + f"\r\nPRINT {copies}\r\n".encode("ascii")


def fit_label(im: Image.Image) -> Image.Image:
    rgb = ImageOps.exif_transpose(im.convert("RGB"))
    rgb.thumbnail((WIDTH_DOTS, HEIGHT_DOTS), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (WIDTH_DOTS, HEIGHT_DOTS), (255, 255, 255))
    x = (WIDTH_DOTS - rgb.size[0]) // 2
    y = (HEIGHT_DOTS - rgb.size[1]) // 2
    canvas.paste(rgb, (x, y))
    return canvas.convert("1")


def payload_from_image(im: Image.Image) -> bytes:
    mask = fit_label(im)
    data = mask.tobytes()
    return data.ljust((WIDTH_DOTS // 8) * HEIGHT_DOTS, b"\xff")


def _pdf_to_image(data: bytes) -> Image.Image:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        pdfium = None
    if pdfium is not None:
        doc = pdfium.PdfDocument(data)
        try:
            page = doc[0]
            bitmap = page.render(scale=DPI / 72.0)
            return bitmap.to_pil()
        finally:
            doc.close()
    pdftoppm = None
    for name in ("pdftoppm", "/usr/bin/pdftoppm"):
        if Path(name).name == name:
            from shutil import which

            pdftoppm = which(name)
        elif Path(name).is_file():
            pdftoppm = name
        if pdftoppm:
            break
    if not pdftoppm:
        raise RuntimeError("PDF needs pypdfium2 or pdftoppm")
    proc = subprocess.run(
        [pdftoppm, "-png", "-r", str(DPI), "-singlefile"],
        input=data,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError("pdftoppm failed")
    return Image.open(BytesIO(proc.stdout))


def raster_to_image(
    width: int,
    height: int,
    bpp: int,
    bpl: int,
    cspace: int,
    raw: bytes,
) -> Image.Image:
    if len(raw) < height * bpl:
        raise ValueError("truncated CUPS raster page")
    rows = [raw[i * bpl : (i + 1) * bpl] for i in range(height)]
    if bpp == 1:
        im = Image.frombytes(
            "1", (width, height), b"".join(r[: (width + 7) // 8] for r in rows)
        )
        if cspace == 3:
            im = ImageOps.invert(im.convert("L")).convert("1")
        return im
    if bpp == 8:
        im = Image.frombytes("L", (width, height), b"".join(r[:width] for r in rows))
        if cspace == 3:
            im = ImageOps.invert(im)
        return im.convert("RGB")
    if bpp in (24, 32):
        px_size = 3 if bpp == 24 else 4
        rgb = bytearray()
        for row in rows:
            for x in range(width):
                off = x * px_size
                rgb.extend(row[off : off + 3])
        return Image.frombytes("RGB", (width, height), bytes(rgb))
    raise ValueError(f"unsupported cups raster bpp={bpp} cspace={cspace}")


def cups_raster_pages(buf: bytes) -> list[Image.Image]:
    magic = buf[:4]
    little = magic in (b"RaS2", b"RaS3")
    big = magic in (b"2SaR", b"3SaR")
    if not little and not big:
        raise ValueError("need CUPS raster v2/v3 (RaS2/RaS3)")
    endian = "<" if little else ">"
    pos = 4
    pages: list[Image.Image] = []
    while pos + HEADER2 <= len(buf):
        header = buf[pos : pos + HEADER2]
        pos += HEADER2
        # cups_page_header2_t: 256 B of char[] then 29 uint32 then cupsWidth.
        width, height, _mt, _bpc, bpp, bpl, _order, cspace = struct.unpack_from(
            endian + "8I", header, 372
        )
        nbytes = int(height) * int(bpl)
        raw = buf[pos : pos + nbytes]
        pos += nbytes
        pages.append(
            raster_to_image(
                int(width), int(height), int(bpp), int(bpl), int(cspace), raw
            )
        )
    if not pages:
        raise ValueError("CUPS raster had no pages")
    return pages


def open_source(data: bytes) -> Image.Image:
    if data[:4] in (b"RaS2", b"RaS3", b"RaSt", b"2SaR", b"3SaR", b"tSaR"):
        return cups_raster_pages(data)[0]
    if data[:4] == b"%PDF":
        return _pdf_to_image(data)
    return Image.open(BytesIO(data))


def parse_density(options: str) -> int:
    tokens = options.replace(",", " ").split()
    for token in tokens:
        if token.startswith("NelkoDensity="):
            return int(token.split("=", 1)[1].split("/")[0])
    for token in tokens:
        if token.startswith("cupsInteger0="):
            return int(token.split("=", 1)[1])
    return DEFAULT_DENSITY


def self_test() -> None:
    im = Image.new("RGB", (96, 320), (255, 255, 255))
    px = im.load()
    for y in range(8):
        px[0, y] = (0, 0, 0)
    payload = payload_from_image(im)
    assert len(payload) == 12 * 320
    assert payload[0] == 0x7F
    job = build_tspl(payload)
    assert job.startswith(b"\r\nSIZE 14 mm,40 mm\r\n")
    assert b"DIRECTION 1,1\r\n" in job
    assert b"DENSITY 15\r\n" in job
    assert b"BITMAP 0,0,12,320,1," in job
    assert job.endswith(b"\r\nPRINT 1\r\n")
    two = build_tspl(payload, copies=2)
    assert two.endswith(b"\r\nPRINT 2\r\n")
    assert parse_density("media=Label14x40 NelkoDensity=10") == 10
    assert parse_density("cupsInteger0=8") == 8
    assert parse_density("") == DEFAULT_DENSITY


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) >= 2 and args[1] == "self-test":
        self_test()
        print("ok")
        return 0
    copies = 1
    options = ""
    src: bytes
    if len(args) >= 6:
        try:
            copies = max(1, int(args[4]))
        except ValueError:
            copies = 1
        options = args[5]
        if len(args) >= 7 and args[6]:
            src = Path(args[6]).read_bytes()
        else:
            src = sys.stdin.buffer.read()
    else:
        src = sys.stdin.buffer.read()
    if not src:
        log("empty input")
        return 1
    try:
        density = parse_density(options)
        im = open_source(src)
        payload = payload_from_image(im)
        job = build_tspl(payload, density=density, copies=copies)
    except (OSError, RuntimeError, ValueError) as exc:
        log(str(exc))
        return 1
    log(f"job {len(job)} B copies={copies} density={parse_density(options)}")
    sys.stdout.buffer.write(job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
