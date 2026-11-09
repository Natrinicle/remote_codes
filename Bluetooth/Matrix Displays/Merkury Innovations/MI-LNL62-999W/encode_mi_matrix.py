#!/usr/bin/env python3
"""Encode MI Matrix Panel (MI-LNL62-999W) BLE frames.

Writes go to GATT FFD1 without response. Helpers print payloads. They
do not scan or GATT-connect.

Example:
    ./encode_mi_matrix.py self-test
    ./encode_mi_matrix.py on
    ./encode_mi_matrix.py pixel --index 0 --rgb ff0000
    ./encode_mi_matrix.py solid --rgb ff0000
    ./encode_mi_matrix.py decode bcff010155
"""

from __future__ import annotations

import argparse
import sys

HEAD = 0xBC
TAIL = 0x55
WIDTH = 16
HEIGHT = 16
PIXELS = WIDTH * HEIGHT
BLOCK_PIXELS = 32
BLOCK_COUNT = 8

SERVICE_UUID = "0000ffd0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ffd1-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ffd2-0000-1000-8000-00805f9b34fb"

# ASCII frames from MI Matrix Panel 1.0.2 libapp.so (com.fulllight.ledpixel).
APK_OFF = bytes.fromhex("bcff000055")
APK_ON = bytes.fromhex("bcff010155")
APK_STORE_1 = bytes.fromhex("bc0011f10355")
APK_STORE_2 = bytes.fromhex("bc0011f20455")
APK_MODE_12 = bytes.fromhex("bc00121255")
APK_MODE_13 = bytes.fromhex("bc00131355")
APK_MODE_15 = bytes.fromhex("bc00151555")
APK_LAMP = {
    "01": bytes.fromhex("bc0a01010c55"),
    "04": bytes.fromhex("bc0a01040055"),
    "05": bytes.fromhex("bc0a01050155"),
    "06": bytes.fromhex("bc0a01060255"),
    "dual": bytes.fromhex("bc0a0202ff0000ffffff0e55"),
}

# offe/mi-led-display protocol.txt (conflicts with APK power).
OFFE_OFF = bytes.fromhex("bcff00ff55")
OFFE_ON = bytes.fromhex("bcff010055")
GRAFFITI_A = bytes.fromhex("bc00010155")
GRAFFITI_B = bytes.fromhex("bc000d0d55")
PICTURE_START = bytes.fromhex("bc0ff1080855")
PICTURE_END = bytes.fromhex("bc0ff2080955")
VEC_PIXEL0_RED = bytes.fromhex("bc01010000ff0000ff55")
# offe HCI snoop (per-packet ATT Write Command): 4-frame clip.
ANIM_START_4 = bytes.fromhex("bc02f104f755")
ANIM_END_4 = bytes.fromhex("bc02f204f855")
ANIM_START_8 = bytes.fromhex("bc02f108fb55")
ANIM_END_8 = bytes.fromhex("bc02f208fc55")
# offe 4-frame clips started at 2. Live 8-slot fill uses first_frame_id=1.
ANIM_FIRST_FRAME_ID = 2


def _hex(data: bytes) -> str:
    return data.hex()


def parse_hex(raw: str) -> bytes:
    text = raw.strip().lower().replace(" ", "").replace(":", "")
    text = text.removeprefix("0x")
    if len(text) % 2:
        raise ValueError(f"odd hex length {len(text)}")
    return bytes.fromhex(text)


def parse_rgb(raw: str) -> tuple[int, int, int]:
    data = parse_hex(raw)
    if len(data) != 3:
        raise ValueError("rgb must be 3 bytes, e.g. ff0000")
    return data[0], data[1], data[2]


def wrap(body: bytes) -> bytes:
    """BC | body | 55. body already includes any checksum byte."""
    return bytes((HEAD,)) + body + bytes((TAIL,))


def checksum_wrap(interior: bytes) -> bytes:
    """BC | interior | sum8(interior) | 55. Matches picture start/end/blocks."""
    return wrap(interior + bytes((sum(interior) & 0xFF,)))


def power(on: bool) -> bytes:
    """APK PowerOff / on. Arg is duplicated (FF 00 00 / FF 01 01)."""
    return APK_ON if on else APK_OFF


def offe_power(on: bool) -> bytes:
    return OFFE_ON if on else OFFE_OFF


def short_mode(mode: int) -> bytes:
    """BC 00 MODE MODE 55. Second MODE equals 00+MODE (sum8)."""
    if not 0 <= mode <= 0xFF:
        raise ValueError(f"mode {mode} out of range")
    return checksum_wrap(bytes((0x00, mode)))


def reset_saved() -> bytes:
    """Wipe on-device playlist. APK BC00151555; offe first post-connect write."""
    return APK_MODE_15


def graffiti_start() -> list[bytes]:
    return [GRAFFITI_A, GRAFFITI_B]


def pixel_frame(index: int, red: int, green: int, blue: int) -> bytes:
    """Graffiti pixel. QQ is (index-1) mod 256 (offe protocol.txt example)."""
    if not 0 <= index <= 255:
        raise ValueError(f"pixel {index} out of range")
    for name, value in (("r", red), ("g", green), ("b", blue)):
        if not 0 <= value <= 255:
            raise ValueError(f"{name} {value} out of range")
    end = (index - 1) & 0xFF
    return wrap(bytes((0x01, 0x01, 0x00, index, red, green, blue, end)))


def picture_start() -> bytes:
    return PICTURE_START


def picture_end() -> bytes:
    return PICTURE_END


def picture_block(block: int, pixels: list[tuple[int, int, int]]) -> bytes:
    """One 32-pixel picture slice. block is 1..8. RGB then sum8 then 55."""
    if not 1 <= block <= BLOCK_COUNT:
        raise ValueError(f"block {block} out of range 1..{BLOCK_COUNT}")
    if len(pixels) != BLOCK_PIXELS:
        raise ValueError(f"need {BLOCK_PIXELS} pixels, got {len(pixels)}")
    interior = bytearray((0x0F, block))
    for red, green, blue in pixels:
        for value in (red, green, blue):
            if not 0 <= value <= 255:
                raise ValueError("rgb out of range")
        interior.extend((red, green, blue))
    return checksum_wrap(bytes(interior))


def picture_frames(pixels: list[tuple[int, int, int]]) -> list[bytes]:
    """start + 8 blocks + end for a 16x16 row-major RGB list."""
    if len(pixels) != PIXELS:
        raise ValueError(f"need {PIXELS} pixels, got {len(pixels)}")
    frames = [picture_start()]
    for block in range(BLOCK_COUNT):
        start = block * BLOCK_PIXELS
        frames.append(picture_block(block + 1, pixels[start : start + BLOCK_PIXELS]))
    frames.append(picture_end())
    return frames


def solid_frames(red: int, green: int, blue: int) -> list[bytes]:
    return picture_frames([(red, green, blue)] * PIXELS)


def animation_start(count: int) -> bytes:
    """BC 02 F1 NN sum8 55. NN is the clip frame count (offe used 4)."""
    if not 1 <= count <= 255:
        raise ValueError(f"count {count} out of range")
    return checksum_wrap(bytes((0x02, 0xF1, count)))


def animation_end(count: int) -> bytes:
    """BC 02 F2 NN sum8 55."""
    if not 1 <= count <= 255:
        raise ValueError(f"count {count} out of range")
    return checksum_wrap(bytes((0x02, 0xF2, count)))


def animation_block(
    frame_id: int, block: int, pixels: list[tuple[int, int, int]]
) -> bytes:
    """One 32-pixel animation slice. 102 bytes: BC 02 FF BB RGB96 sum8 55."""
    if not 0 <= frame_id <= 255:
        raise ValueError(f"frame {frame_id} out of range")
    if not 1 <= block <= BLOCK_COUNT:
        raise ValueError(f"block {block} out of range 1..{BLOCK_COUNT}")
    if len(pixels) != BLOCK_PIXELS:
        raise ValueError(f"need {BLOCK_PIXELS} pixels, got {len(pixels)}")
    interior = bytearray((0x02, frame_id, block))
    for red, green, blue in pixels:
        for value in (red, green, blue):
            if not 0 <= value <= 255:
                raise ValueError("rgb out of range")
        interior.extend((red, green, blue))
    return checksum_wrap(bytes(interior))


def animation_frames(
    frames: list[list[tuple[int, int, int]]],
    *,
    first_frame_id: int = ANIM_FIRST_FRAME_ID,
) -> list[bytes]:
    """Per-frame start + 8 blocks + end. offe 4-frame clips used ids 2..(1+N)."""
    if not frames:
        raise ValueError("need at least one frame")
    count = len(frames)
    out: list[bytes] = []
    for index, pixels in enumerate(frames):
        if len(pixels) != PIXELS:
            raise ValueError(f"need {PIXELS} pixels, got {len(pixels)}")
        frame_id = first_frame_id + index
        if frame_id > 255:
            raise ValueError(f"frame id {frame_id} out of range")
        out.append(animation_start(count))
        for block in range(BLOCK_COUNT):
            start = block * BLOCK_PIXELS
            out.append(
                animation_block(
                    frame_id, block + 1, pixels[start : start + BLOCK_PIXELS]
                )
            )
        out.append(animation_end(count))
    return out


def store(slot: int) -> bytes:
    if slot == 1:
        return APK_STORE_1
    if slot == 2:
        return APK_STORE_2
    raise ValueError("store slot is 1 or 2")


def lamp(name: str) -> bytes:
    key = name.strip().lower()
    if key not in APK_LAMP:
        raise ValueError(f"unknown lamp {name}")
    return APK_LAMP[key]


def iter_frames(data: bytes) -> list[bytes]:
    frames: list[bytes] = []
    i = 0
    while i < len(data):
        if data[i] != HEAD:
            i += 1
            continue
        try:
            end = data.index(TAIL, i + 1)
        except ValueError:
            break
        frames.append(data[i : end + 1])
        i = end + 1
    return frames


def describe(frame: bytes) -> str:
    if len(frame) < 3 or frame[0] != HEAD or frame[-1] != TAIL:
        return "not a BC…55 frame"
    hx = _hex(frame)
    if frame == APK_OFF:
        return "power-off apk"
    if frame == APK_ON:
        return "power-on apk"
    if frame == OFFE_OFF:
        return "power-off offe"
    if frame == OFFE_ON:
        return "power-on offe"
    if frame == GRAFFITI_A:
        return "graffiti-start a"
    if frame == GRAFFITI_B:
        return "graffiti-start b"
    if frame == PICTURE_START:
        return "picture-start"
    if frame == PICTURE_END:
        return "picture-end"
    if frame == APK_STORE_1:
        return "store 1"
    if frame == APK_STORE_2:
        return "store 2"
    if frame == APK_MODE_15:
        return "reset saved"
    if frame == APK_MODE_12:
        return "slideshow"
    if frame == APK_MODE_13:
        return "short-mode 0x13"
    if len(frame) == 5 and frame[1] == 0x00 and frame[2] == frame[3]:
        return f"short-mode 0x{frame[2]:02x}"
    if len(frame) == 10 and frame[1:4] == bytes((0x01, 0x01, 0x00)):
        return f"pixel i={frame[4]} rgb={frame[5]:02x}{frame[6]:02x}{frame[7]:02x}"
    if len(frame) == 101 and frame[1] == 0x0F and 1 <= frame[2] <= 8:
        interior = frame[1:-2]
        chk_ok = (sum(interior) & 0xFF) == frame[-2]
        return f"picture-block {frame[2]} checksum={'ok' if chk_ok else 'bad'}"
    if len(frame) == 6 and frame[1] == 0x02 and frame[2] in (0xF1, 0xF2):
        kind = "start" if frame[2] == 0xF1 else "end"
        interior = frame[1:-2]
        chk_ok = (sum(interior) & 0xFF) == frame[-2]
        return f"animation-{kind} count={frame[3]} checksum={'ok' if chk_ok else 'bad'}"
    if len(frame) == 102 and frame[1] == 0x02:
        interior = frame[1:-2]
        chk_ok = (sum(interior) & 0xFF) == frame[-2]
        return (
            f"animation-block frame={frame[2]} block={frame[3]} "
            f"checksum={'ok' if chk_ok else 'bad'}"
        )
    return f"unknown {hx}"


def self_test() -> None:
    assert power(False) == APK_OFF
    assert power(True) == APK_ON
    assert offe_power(False) == OFFE_OFF
    assert offe_power(True) == OFFE_ON
    assert short_mode(0x12) == APK_MODE_12
    assert short_mode(0x13) == APK_MODE_13
    assert short_mode(0x15) == APK_MODE_15
    assert reset_saved() == APK_MODE_15
    assert describe(APK_MODE_15) == "reset saved"
    assert short_mode(0x01) == GRAFFITI_A
    assert short_mode(0x0D) == GRAFFITI_B
    assert pixel_frame(0, 255, 0, 0) == VEC_PIXEL0_RED
    assert picture_start() == PICTURE_START
    assert picture_end() == PICTURE_END
    assert checksum_wrap(bytes((0x0F, 0xF1, 0x08))) == PICTURE_START
    assert checksum_wrap(bytes((0x0F, 0xF2, 0x08))) == PICTURE_END
    zeros = [(0, 0, 0)] * BLOCK_PIXELS
    block1 = picture_block(1, zeros)
    assert block1 == bytes.fromhex("bc0f01" + "00" * 96 + "10" + "55")
    assert (sum(block1[1:-2]) & 0xFF) == block1[-2]
    reds = solid_frames(255, 0, 0)
    assert len(reds) == 10
    assert reds[0] == PICTURE_START
    assert reds[-1] == PICTURE_END
    assert store(1) == APK_STORE_1
    assert store(2) == APK_STORE_2
    assert lamp("01") == APK_LAMP["01"]
    assert lamp("dual") == APK_LAMP["dual"]
    assert animation_start(4) == ANIM_START_4
    assert animation_end(4) == ANIM_END_4
    assert animation_start(8) == ANIM_START_8
    assert animation_end(8) == ANIM_END_8
    zeros = [(0, 0, 0)] * BLOCK_PIXELS
    ablock = animation_block(2, 1, zeros)
    assert len(ablock) == 102
    assert ablock[:4] == bytes((HEAD, 0x02, 2, 1))
    assert (sum(ablock[1:-2]) & 0xFF) == ablock[-2]
    clip = animation_frames([[(0, 0, 0)] * PIXELS] * 4)
    assert len(clip) == 4 * 10
    assert clip[0] == ANIM_START_4
    assert clip[9] == ANIM_END_4
    assert clip[1][2] == 2
    assert clip[11][2] == 3
    clip8 = animation_frames([[(0, 0, 0)] * PIXELS] * 8, first_frame_id=1)
    assert len(clip8) == 8 * 10
    assert clip8[0] == ANIM_START_8
    assert clip8[9] == ANIM_END_8
    assert clip8[1][2] == 1
    assert clip8[11][2] == 2


def _print_frames(frames: list[bytes]) -> None:
    for frame in frames:
        print(_hex(frame))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    sub.add_parser("on")
    sub.add_parser("off")
    sub.add_parser("offe-on")
    sub.add_parser("offe-off")
    sub.add_parser("graffiti-start")
    sub.add_parser("slideshow")
    sub.add_parser("reset")
    p_mode = sub.add_parser("mode")
    p_mode.add_argument("value", help="mode byte, decimal or 0xNN")
    p_pix = sub.add_parser("pixel")
    p_pix.add_argument("--index", type=int, required=True)
    p_pix.add_argument("--rgb", required=True, help="rrggbb hex")
    sub.add_parser("picture-start")
    sub.add_parser("picture-end")
    p_blk = sub.add_parser("picture-block")
    p_blk.add_argument("--index", type=int, required=True, help="block 1..8")
    p_blk.add_argument("--rgb", required=True, help="solid fill for this block")
    p_solid = sub.add_parser("solid")
    p_solid.add_argument("--rgb", required=True, help="rrggbb hex for all 256 pixels")
    p_store = sub.add_parser("store")
    p_store.add_argument("slot", type=int, choices=(1, 2))
    p_astart = sub.add_parser("animation-start")
    p_astart.add_argument("--count", type=int, default=4)
    p_aend = sub.add_parser("animation-end")
    p_aend.add_argument("--count", type=int, default=4)
    p_lamp = sub.add_parser("lamp")
    p_lamp.add_argument("name", choices=sorted(APK_LAMP))
    p_dec = sub.add_parser("decode")
    p_dec.add_argument("hex")
    args = parser.parse_args()

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "on":
        print(_hex(power(True)))
        return 0
    if args.cmd == "off":
        print(_hex(power(False)))
        return 0
    if args.cmd == "offe-on":
        print(_hex(offe_power(True)))
        return 0
    if args.cmd == "offe-off":
        print(_hex(offe_power(False)))
        return 0
    if args.cmd == "graffiti-start":
        _print_frames(graffiti_start())
        return 0
    if args.cmd == "slideshow":
        print(_hex(short_mode(0x12)))
        return 0
    if args.cmd == "reset":
        print(_hex(reset_saved()))
        return 0
    if args.cmd == "mode":
        raw = args.value.strip().lower()
        mode = int(raw, 16) if raw.startswith("0x") else int(raw, 0)
        print(_hex(short_mode(mode)))
        return 0
    if args.cmd == "pixel":
        red, green, blue = parse_rgb(args.rgb)
        print(_hex(pixel_frame(args.index, red, green, blue)))
        return 0
    if args.cmd == "picture-start":
        print(_hex(picture_start()))
        return 0
    if args.cmd == "picture-end":
        print(_hex(picture_end()))
        return 0
    if args.cmd == "picture-block":
        red, green, blue = parse_rgb(args.rgb)
        print(_hex(picture_block(args.index, [(red, green, blue)] * BLOCK_PIXELS)))
        return 0
    if args.cmd == "solid":
        red, green, blue = parse_rgb(args.rgb)
        _print_frames(solid_frames(red, green, blue))
        return 0
    if args.cmd == "store":
        print(_hex(store(args.slot)))
        return 0
    if args.cmd == "animation-start":
        print(_hex(animation_start(args.count)))
        return 0
    if args.cmd == "animation-end":
        print(_hex(animation_end(args.count)))
        return 0
    if args.cmd == "lamp":
        print(_hex(lamp(args.name)))
        return 0
    if args.cmd == "decode":
        recs = iter_frames(parse_hex(args.hex))
        if not recs:
            print("no BC…55 frame", file=sys.stderr)
            return 1
        for rec in recs:
            print(f"{describe(rec)} {_hex(rec)}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
