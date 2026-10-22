"""Raster PNG/JPEG/PDF (and raw RGB) to 1bpp printhead rows.

MSB-first, set bit = black. Width is padded to a multiple of 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


@dataclass(frozen=True)
class Bitmap1bpp:
    width: int
    height: int
    rows: tuple[bytes, ...]
    dpi: int

    @property
    def width_bytes(self) -> int:
        return (self.width + 7) // 8

    def payload(self) -> bytes:
        return b"".join(self.rows)

    def height_mm(self) -> float:
        return self.height * 25.4 / self.dpi

    def width_mm(self) -> float:
        return self.width * 25.4 / self.dpi


def _open_pdf(data: bytes, dpi: int) -> Image.Image:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("PDF needs pypdfium2 (pip install pypdfium2)") from exc
    doc = pdfium.PdfDocument(data)
    try:
        page = doc[0]
        scale = dpi / 72.0
        bitmap = page.render(scale=scale)
        return bitmap.to_pil()
    finally:
        doc.close()


def open_image(source: bytes | Path | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, Path):
        data = source.read_bytes()
    else:
        data = source
    if data[:4] == b"%PDF":
        return _open_pdf(data, 203).convert("RGB")
    return Image.open(BytesIO(data)).convert("RGB")


def pack_msb(mask: Image.Image) -> tuple[bytes, ...]:
    """Pack a mode-1 image (0=black) into MSB-first rows."""
    if mask.mode != "1":
        raise ValueError("pack_msb expects mode 1")
    width, height = mask.size
    width_bytes = (width + 7) // 8
    px = mask.load()
    rows: list[bytes] = []
    for y in range(height):
        row = bytearray(width_bytes)
        for x in range(width):
            if px[x, y] == 0:
                row[x // 8] |= 0x80 >> (x % 8)
        rows.append(bytes(row))
    return tuple(rows)


def raster_image(
    source: bytes | Path | Image.Image,
    *,
    width_dots: int,
    max_height: int,
    dpi: int = 203,
    fit: str = "contain",
    dither: bool = True,
    threshold: int = 128,
) -> Bitmap1bpp:
    if width_dots < 8 or width_dots % 8:
        raise ValueError("width_dots must be a positive multiple of 8")
    if max_height < 1:
        raise ValueError("max_height must be positive")
    if fit not in ("contain", "width", "stretch"):
        raise ValueError("fit must be contain, width, or stretch")
    im = ImageOps.exif_transpose(open_image(source))
    src_w, src_h = im.size
    if src_w < 1 or src_h < 1:
        raise ValueError("empty image")
    if fit == "width":
        new_h = max(1, round(src_h * width_dots / src_w))
        new_h = min(new_h, max_height)
        im = im.resize((width_dots, new_h), Image.Resampling.LANCZOS)
    elif fit == "stretch":
        im = im.resize(
            (width_dots, min(max_height, max(1, src_h))),
            Image.Resampling.LANCZOS,
        )
    else:
        im = im.copy()
        im.thumbnail((width_dots, max_height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width_dots, max(1, im.size[1])), (255, 255, 255))
        canvas.paste(im, ((width_dots - im.size[0]) // 2, 0))
        im = canvas
    gray = im.convert("L")
    if dither:
        mask = gray.convert("1")
    else:
        mask = gray.point(lambda p: 0 if p < threshold else 255, mode="1")
    rows = pack_msb(mask)
    return Bitmap1bpp(mask.size[0], mask.size[1], rows, dpi)


def from_rgb(
    rgb: bytes,
    width: int,
    height: int,
    *,
    dpi: int = 203,
    width_dots: int,
    max_height: int,
    fit: str = "contain",
    dither: bool = True,
) -> Bitmap1bpp:
    if len(rgb) != width * height * 3:
        raise ValueError("rgb length must be width*height*3")
    im = Image.frombytes("RGB", (width, height), rgb)
    return raster_image(
        im,
        width_dots=width_dots,
        max_height=max_height,
        dpi=dpi,
        fit=fit,
        dither=dither,
    )


def self_test() -> None:
    im = Image.new("RGB", (16, 8), (255, 255, 255))
    px = im.load()
    for y in range(8):
        px[0, y] = (0, 0, 0)
    bmp = raster_image(im, width_dots=16, max_height=16, fit="stretch", dither=False)
    assert bmp.width == 16
    assert bmp.height == 8
    assert bmp.rows[0] == bytes((0x80, 0x00))
    wide = raster_image(im, width_dots=96, max_height=40, fit="contain", dither=False)
    assert wide.width == 96
    assert wide.height <= 40
