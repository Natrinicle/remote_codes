#!/usr/bin/env python3
"""Encode Magic Lantern / duoCo StripX 9-byte 7E…EF frames for BLE GATT FFF3.

Recovered on MELK-OA10 (Play wl.smartled.rgb 6.11.10). Service FFF0, write
FFF3 without response, notify FFF4. RGB solids use [7]=0x10.

Helpers print payloads. They do not scan or GATT-connect.

Example:
    ./encode_magic_lantern.py on
    ./encode_magic_lantern.py rgb 255,0,0
    ./encode_magic_lantern.py warn
    ./encode_magic_lantern.py self-test
"""

from __future__ import annotations

import argparse
import sys

HEAD = 0x7E
TAIL = 0xEF
RGB_TARGET = 0x10
CCT_TARGET = 0x08
ANALOG_TARGET = 0x00
FRAME_LEN = 9

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"

# Magic Lantern sniff (byte3 0xF0). StripX uses v=0/1 in that slot.
ML_ON = bytes((HEAD, 0x04, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, TAIL))
STRIPX_ON = bytes((HEAD, 0x04, 0x04, 0x01, 0x00, 0x01, 0xFF, 0x00, TAIL))
POWER_OFF = bytes((HEAD, 0x04, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, TAIL))

WARN_RGB = (255, 22, 0)
RED_RGB = (255, 0, 0)
GREEN_RGB = (0, 255, 0)
BLUE_RGB = (0, 0, 255)
BLACK_RGB = (0, 0, 0)

LIGHT_MODES = {
    0: "SingleRGB",
    1: "MultipleRGB",
    2: "CCT",
    3: "WhiteBlack",
}


def parse_hex(raw: str) -> bytes:
    text = raw.strip().lower().replace(" ", "").replace(":", "")
    text = text.removeprefix("0x")
    if len(text) % 2:
        raise ValueError(f"odd hex length {len(text)}")
    return bytes.fromhex(text)


def parse_rgb(raw: str) -> tuple[int, int, int]:
    text = raw.strip()
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 3:
            raise ValueError("rgb must be R,G,B or RRGGBB")
        vals = [int(p, 10) for p in parts]
        if any(v < 0 or v > 255 for v in vals):
            raise ValueError("rgb channel out of 0-255")
        return vals[0], vals[1], vals[2]
    data = parse_hex(text)
    if len(data) != 3:
        raise ValueError("rgb must be 3 bytes, e.g. ff0000")
    return data[0], data[1], data[2]


def parse_u8(raw: str, *, lo: int = 0, hi: int = 255, name: str = "byte") -> int:
    value = int(raw, 10)
    if value < lo or value > hi:
        raise ValueError(f"{name} must be {lo}..{hi}")
    return value


def wrap(body: bytes) -> bytes:
    """7E | 7 body bytes | EF."""
    if len(body) != 7:
        raise ValueError(f"body must be 7 bytes, got {len(body)}")
    return bytes((HEAD,)) + body + bytes((TAIL,))


def power_on(*, stripx: bool = False) -> bytes:
    return STRIPX_ON if stripx else ML_ON


def power_off() -> bytes:
    return POWER_OFF


def brightness(level: int, mode: int = 1) -> bytes:
    if level < 0 or level > 100:
        raise ValueError("brightness must be 0..100")
    if mode not in LIGHT_MODES:
        raise ValueError("mode must be 0..3")
    return wrap(bytes((0x04, 0x01, level, mode, 0xFF, 0xFF, 0x00)))


def rgb(red: int, green: int, blue: int) -> bytes:
    """Solid RGB. Always [7]=0x10. Never analog [7]=0x00."""
    for name, value in (("r", red), ("g", green), ("b", blue)):
        if value < 0 or value > 255:
            raise ValueError(f"{name} must be 0..255")
    frame = wrap(bytes((0x07, 0x05, 0x03, red, green, blue, RGB_TARGET)))
    if frame[7] != RGB_TARGET:
        raise RuntimeError("rgb() must emit [7]=0x10")
    return frame


def warn() -> bytes:
    return rgb(*WARN_RGB)


def cct(ww: int, cw: int) -> bytes:
    for name, value in (("ww", ww), ("cw", cw)):
        if value < 0 or value > 255:
            raise ValueError(f"{name} must be 0..255")
    return wrap(bytes((0x06, 0x05, 0x02, ww, cw, 0xFF, CCT_TARGET)))


def effect(mode: int) -> bytes:
    if mode < 0 or mode > 255:
        raise ValueError("effect mode must be 0..255")
    return wrap(bytes((0x05, 0x03, mode, 0x06, 0xFF, 0xFF, 0x00)))


def speed(level: int) -> bytes:
    if level < 0 or level > 255:
        raise ValueError("speed must be 0..255")
    return wrap(bytes((0x04, 0x02, level, 0xFF, 0xFF, 0xFF, 0x00)))


def decode(raw: bytes) -> str:
    hx = raw.hex()
    if len(raw) != FRAME_LEN or raw[0] != HEAD or raw[-1] != TAIL:
        return f"{hx}  (not a 9-byte 7E…EF frame)"
    target = raw[7]
    if raw[2:4] == b"\x05\x03":
        kind = "rgb" if target == RGB_TARGET else f"color target=0x{target:02x}"
        if target == ANALOG_TARGET:
            kind = "analog color [7]=0x00 (wrong RGBIC render target)"
        return (
            f"{hx}  {kind} rgb={raw[4]},{raw[5]},{raw[6]} "
            f"[{raw[4]:3d},{raw[5]:3d},{raw[6]:3d}]"
        )
    if raw[1:3] == b"\x04\x04":
        if raw[3] == 0x00 and raw[5] == 0x00:
            return f"{hx}  power off"
        tag = "stripx on" if raw[3] in (0x00, 0x01) else "magic lantern on"
        return f"{hx}  {tag} v=0x{raw[3]:02x}"
    if raw[1:3] == b"\x04\x01":
        mode = raw[4]
        label = LIGHT_MODES.get(mode, f"mode {mode}")
        return f"{hx}  brightness {raw[3]} {label}"
    if raw[1:4] == b"\x06\x05\x02":
        return f"{hx}  cct ww={raw[4]} cw={raw[5]} target=0x{target:02x}"
    if raw[1:3] == b"\x05\x03":
        return f"{hx}  effect mode={raw[3]}"
    if raw[1:3] == b"\x04\x02":
        return f"{hx}  speed {raw[3]}"
    if raw[1:2] == b"\x83" or raw[2:3] == b"\x83":
        return f"{hx}  system_time / truncated analog login (do not send truncated)"
    return f"{hx}  unknown"


def self_test() -> None:
    assert power_on() == bytes.fromhex("7e0404f00001ff00ef")
    assert power_on(stripx=True) == bytes.fromhex("7e0404010001ff00ef")
    assert power_off() == bytes.fromhex("7e0404000000ff00ef")
    assert rgb(255, 0, 0) == bytes.fromhex("7e070503ff000010ef")
    assert rgb(0, 255, 0) == bytes.fromhex("7e07050300ff0010ef")
    assert rgb(0, 0, 255) == bytes.fromhex("7e0705030000ff10ef")
    assert warn() == bytes.fromhex("7e070503ff160010ef")
    assert rgb(*WARN_RGB) == warn()
    assert rgb(*BLACK_RGB) == bytes.fromhex("7e07050300000010ef")
    assert brightness(100, 1) == bytes.fromhex("7e04016401ffff00ef")
    assert cct(0, 0) == bytes.fromhex("7e0605020000ff08ef")
    assert parse_rgb("255,22,0") == WARN_RGB
    assert parse_rgb("ff1600") == WARN_RGB
    for r, g, b in (RED_RGB, GREEN_RGB, BLUE_RGB, WARN_RGB, BLACK_RGB, (1, 2, 3)):
        frame = rgb(r, g, b)
        assert len(frame) == FRAME_LEN
        assert frame[0] == HEAD and frame[-1] == TAIL
        assert frame[7] == RGB_TARGET
        assert frame[7] != ANALOG_TARGET
    analog = bytes.fromhex("7e000503ff8c2800ef")
    assert "analog" in decode(analog)
    assert "warn" not in decode(analog)
    assert decode(warn()).startswith("7e070503ff160010ef")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    on_p = sub.add_parser("on", help="power on (Magic Lantern sniff)")
    on_p.add_argument(
        "--stripx",
        action="store_true",
        help="StripX v=1 power-on instead of Magic Lantern 0xF0",
    )
    sub.add_parser("off", help="power off")
    rgb_p = sub.add_parser("rgb", help="solid RGB [7]=0x10")
    rgb_p.add_argument("color", help="RRGGBB or R,G,B")
    sub.add_parser("warn", help="user-confirmed warn orange 255,22,0")
    sub.add_parser("red")
    sub.add_parser("green")
    sub.add_parser("blue")
    sub.add_parser("black", help="RGB 0,0,0 still on the RGB target")
    br_p = sub.add_parser("brightness", help="0-100")
    br_p.add_argument("level")
    br_p.add_argument(
        "--mode", default="1", help="LightMode 0-3 (default 1 MultipleRGB)"
    )
    cct_p = sub.add_parser("cct", help="WW CW pair [7]=0x08")
    cct_p.add_argument("ww")
    cct_p.add_argument("cw")
    eff_p = sub.add_parser("effect")
    eff_p.add_argument("mode")
    spd_p = sub.add_parser("speed")
    spd_p.add_argument("level")
    dec_p = sub.add_parser("decode")
    dec_p.add_argument("hex")
    sub.add_parser("self-test")

    args = parser.parse_args(argv)
    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "on":
        print(power_on(stripx=args.stripx).hex())
        return 0
    if args.cmd == "off":
        print(power_off().hex())
        return 0
    if args.cmd == "rgb":
        print(rgb(*parse_rgb(args.color)).hex())
        return 0
    if args.cmd == "warn":
        print(warn().hex())
        return 0
    if args.cmd == "red":
        print(rgb(*RED_RGB).hex())
        return 0
    if args.cmd == "green":
        print(rgb(*GREEN_RGB).hex())
        return 0
    if args.cmd == "blue":
        print(rgb(*BLUE_RGB).hex())
        return 0
    if args.cmd == "black":
        print(rgb(*BLACK_RGB).hex())
        return 0
    if args.cmd == "brightness":
        print(
            brightness(
                parse_u8(args.level, hi=100, name="brightness"),
                parse_u8(args.mode, hi=3, name="mode"),
            ).hex()
        )
        return 0
    if args.cmd == "cct":
        print(
            cct(
                parse_u8(args.ww, name="ww"),
                parse_u8(args.cw, name="cw"),
            ).hex()
        )
        return 0
    if args.cmd == "effect":
        print(effect(parse_u8(args.mode, name="effect")).hex())
        return 0
    if args.cmd == "speed":
        print(speed(parse_u8(args.level, name="speed")).hex())
        return 0
    if args.cmd == "decode":
        print(decode(parse_hex(args.hex)))
        return 0
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
