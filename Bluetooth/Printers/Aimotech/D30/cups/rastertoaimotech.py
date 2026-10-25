#!/usr/bin/env python3
"""CUPS filter: PNG/JPEG/PDF/CUPS-raster → Aimotech D30 ESC/POS.

argv: job-id user title copies options [file]
Stdout is the ESC @ + GS v 0 + ESC d 23 job the backend writes over
RFCOMM. Packing matches XNvUtil.img2Nv invert=true (bottom-right to
top-left, red channel < 128 is dark). Printhead 96 dots / 12 mm.

Unproven on a live D30 this session. Do not emit TSPL.
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
HEADER2 = 1796


def _ensure_share_path() -> None:
    here = Path(__file__).resolve().parent
    for path in (here, here.parent, Path("/usr/share/printer-driver-aimotech")):
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _load_encode():
    _ensure_share_path()
    import encode_aimotech

    return encode_aimotech


encode_aimotech = _load_encode()


def log(msg: str) -> None:
    print(f"rastertoaimotech: {msg}", file=sys.stderr, flush=True)


def fit_label(im: Image.Image) -> Image.Image:
    rgb = ImageOps.exif_transpose(im.convert("RGB"))
    rgb.thumbnail((WIDTH_DOTS, HEIGHT_DOTS), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (WIDTH_DOTS, HEIGHT_DOTS), (255, 255, 255))
    x = (WIDTH_DOTS - rgb.size[0]) // 2
    y = (HEIGHT_DOTS - rgb.size[1]) // 2
    canvas.paste(rgb, (x, y))
    return canvas


def payload_from_image(im: Image.Image) -> bytes:
    canvas = fit_label(im)
    px = canvas.load()
    rows = [[px[x, y][0] for x in range(WIDTH_DOTS)] for y in range(HEIGHT_DOTS)]
    return encode_aimotech.invert_pack(rows)


def build_job(payload: bytes, *, copies: int = 1) -> bytes:
    need = (WIDTH_DOTS // 8) * HEIGHT_DOTS
    if len(payload) != need:
        raise ValueError(f"payload {len(payload)} != {need}")
    return encode_aimotech.job_bytes(
        width_bytes=WIDTH_DOTS // 8,
        height=HEIGHT_DOTS,
        payload=payload,
        copies=copies,
    )


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


def self_test() -> None:
    encode_aimotech.self_test()
    im = Image.new("RGB", (96, 320), (255, 255, 255))
    payload = payload_from_image(im)
    assert payload == bytes(12 * 320)
    job = build_job(payload)
    assert job.startswith(encode_aimotech.CMD_INIT)
    assert encode_aimotech.CMD_GS_V0 in job
    assert job.endswith(encode_aimotech.CMD_FEED)
    two = build_job(payload, copies=2)
    assert two.count(encode_aimotech.CMD_GS_V0) == 2
    black = Image.new("RGB", (96, 320), (255, 255, 255))
    px = black.load()
    px[0, 0] = (0, 0, 0)
    packed = payload_from_image(black)
    assert packed[-1] == 0x01
    assert packed[0] == 0x00


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) >= 2 and args[1] == "self-test":
        self_test()
        print("ok")
        return 0
    copies = 1
    src: bytes
    if len(args) >= 6:
        try:
            copies = max(1, int(args[4]))
        except ValueError:
            copies = 1
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
        im = open_source(src)
        payload = payload_from_image(im)
        job = build_job(payload, copies=copies)
    except (OSError, RuntimeError, ValueError) as exc:
        log(str(exc))
        return 1
    log(f"job {len(job)} B copies={copies}")
    sys.stdout.buffer.write(job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
