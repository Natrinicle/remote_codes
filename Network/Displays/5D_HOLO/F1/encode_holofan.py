#!/usr/bin/env python3
"""Print Holofan HTTP dest names, F1 geometry, and curl recipes.

Recovered on 5D HOLO model F1 firmware 1.1.0 (SoftAP prefix 5D_, HTTP :80,
WebSocket :9000). Windows 5D HoLo.exe and iOS 5D HoLo
(com.dmz.-D-HoLo99) speak this stack. Android MissYou UDP 50xxx does not.

Helpers print payloads and curl lines. They do not join Wi-Fi, POST, or
play. Do not pack SSIDs, PSKs, or personal MACs.

Example:
    ./encode_holofan.py dest-hex 30koi.bin
    ./encode_holofan.py dest-utf 33306b6f692e62696e
    ./encode_holofan.py geometry --model F1
    ./encode_holofan.py encode-cmd --model F1 --video swim.mp4 --out swim.bin
    ./encode_holofan.py curl-session
    ./encode_holofan.py curl-upload --name 30koi.bin --file 30koi.bin
    ./encode_holofan.py curl-play --name 30koi.bin
    ./encode_holofan.py devices --list
    ./encode_holofan.py presets --list
    ./encode_holofan.py upload-codes --list
    ./encode_holofan.py self-test
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

AP_IP = "192.168.4.1"
HTTP_PORT = 80
WS_PORT = 9000
SSID_PREFIX = "5D_"
APP_IOS_BUNDLE = "com.dmz.-D-HoLo99"
APP_IOS_STORE = "6563141154"
APP_WINDOWS = "5D HoLo.exe"
APP_ANDROID_MISSYOU = "MissYou UDP 50xxx — different stack, not this wire"

# Official on-disk: 812-byte LUT header + frames + pad file to 28800 (0x7080).
OFFICIAL_HEADER_BYTES = 812
PAD_MODULO = 28800
F1_FRAME_BLOCK = 138880

MODELS: dict[str, dict[str, int]] = {
    "F1": {
        "lights": 116,
        "lines": 520,
        "color_deep": 6,
        "frames": 20,
        "frame_block": F1_FRAME_BLOCK,
        "size": 2793600,
    },
    # F-MINI12 geometry from Windows 5D HoLo.exe modelCombo. Do not encode
    # F1 media at 48/300/5 — that scrambles the F1 disc.
    "F-MINI12": {
        "lights": 48,
        "lines": 300,
        "color_deep": 5,
        "frames": 20,
        "frame_block": 0,
        "size": 0,
    },
}

# Factory dest names recovered from an F1 DCIM list (UTF-8 of the hex names).
FACTORY_PRESETS: tuple[tuple[str, str], ...] = (
    ("01fish.bin", "stock 3D swim; play status total=9"),
    ("02count down.bin", "factory"),
    ("03wine .bin", "factory (trailing space in dest name)"),
    ("04cherries.bin", "factory"),
    ("05anglerfish.bin", "factory"),
    ("06Father Christmas.bin", "factory"),
    ("07Pikachu.bin", "factory; play status total=29"),
    ("08Coca Cola.bin", "factory"),
    ("08_NancyMorningSun.bin", "factory"),
    ("09christmas merry.bin", "factory"),
    ("09_NancyMorningSun.bin", "factory"),
    ("10_NancyMorningSun.bin", "factory"),
    ("10rose.bin", "factory"),
)

UPLOAD_CODES: tuple[tuple[int, str], ...] = (
    (0, "download file success"),
    (1, "No active session — GET /ctrl/session first"),
    (2, "no filename"),
    (3, "no boundary"),
    (5, "not found filename, or Failed to find Content-Type"),
    (6, "create file failed (ASCII dest name instead of hex)"),
    (7, "download file failed (truncated/partial .bin)"),
    (8, "file too large, or failed overwrite that deletes the dest"),
)

HANG_URIS: tuple[str, ...] = (
    "GET /DCIM/upload?filename=",
    "GET /DCIM/download?name=<hex>",
    "GET /DCIM/<hex>?action=download",
)

SHIPPED_ENCODE = (
    "--video-fit disc --fit-scale 0.95 --rotate 0 "
    "--lights 116 --lines 520 --color-deep 6 --frames 20 "
    "--header official --padding official"
)


def dest_hex(name: str) -> str:
    """UTF-8 filename as lowercase hex (multipart `name` field)."""
    return name.encode("utf-8").hex()


def dest_utf(hex_name: str) -> str:
    raw = bytes.fromhex(hex_name)
    return raw.decode("utf-8")


def diameter(lights: int) -> int:
    return (lights - 1) * 2


def official_size(frames: int, frame_block: int) -> int:
    raw = OFFICIAL_HEADER_BYTES + frames * frame_block
    if raw % PAD_MODULO == 0:
        return raw
    return raw + (PAD_MODULO - raw % PAD_MODULO)


def geometry_lines(model: str) -> list[str]:
    spec = MODELS[model]
    lights = spec["lights"]
    lines = [
        f"model={model}",
        f"lights={lights}",
        f"lines={spec['lines']}",
        f"color_deep={spec['color_deep']}",
        f"diameter={diameter(lights)}",
        f"header={OFFICIAL_HEADER_BYTES}",
        f"pad_modulo={PAD_MODULO}",
        f"frames_wifi_cap={spec['frames']}",
    ]
    if spec["frame_block"]:
        lines.append(f"frame_block={spec['frame_block']}")
        lines.append(
            f"official_size={official_size(spec['frames'], spec['frame_block'])}"
        )
    if spec["size"]:
        lines.append(f"proven_size={spec['size']}")
    return lines


def encode_cmd(
    *,
    model: str,
    video: str,
    out: str,
    fit_scale: str,
    rotate: str,
    frames: int | None,
) -> str:
    spec = MODELS[model]
    nframes = frames if frames is not None else spec["frames"]
    return (
        "holo-fan "
        f"--video {video} --out {out} "
        "--video-fit disc "
        f"--fit-scale {fit_scale} --rotate {rotate} "
        f"--lights {spec['lights']} --lines {spec['lines']} "
        f"--color-deep {spec['color_deep']} --frames {nframes} "
        "--header official --padding official"
    )


def curl_session(host: str) -> str:
    return f"curl -sS -m 5 http://{host}/ctrl/session"


def curl_loop_one(host: str) -> str:
    return f"curl -sS -m 5 'http://{host}/ctrl/set?loop=one'"


def curl_status(host: str) -> str:
    return f"curl -sS -m 5 'http://{host}/ctrl/play?action=status'"


def curl_upload(host: str, name: str, path: str) -> str:
    hx = dest_hex(name)
    return (
        f"curl -sS -m 120 -F name={hx} "
        f"-F 'file=@{path};filename={name};type=application/octet-stream' "
        f"http://{host}/DCIM/upload"
    )


def curl_play(host: str, name: str) -> str:
    hx = dest_hex(name)
    return f"curl -sS -m 8 'http://{host}/DCIM/{hx}?act=play'"


def devices_list() -> str:
    rows = [
        f"ssid_prefix={SSID_PREFIX}",
        f"ap_ip={AP_IP}",
        f"http={HTTP_PORT}",
        f"websocket={WS_PORT}",
        f"ios_bundle={APP_IOS_BUNDLE}",
        f"ios_store={APP_IOS_STORE}",
        f"windows={APP_WINDOWS}",
        f"not={APP_ANDROID_MISSYOU}",
        "models=" + ",".join(MODELS),
        "open_ports=80,9000",
    ]
    return "\n".join(rows)


def devices_match(token: str) -> str:
    t = token.strip()
    ok = t.startswith(SSID_PREFIX) or t in MODELS or t.upper() == "F1"
    return "match" if ok else "no-match"


def presets_list() -> str:
    lines = [f"{dest_hex(name)}  {name}  {note}" for name, note in FACTORY_PRESETS]
    return "\n".join(lines)


def upload_codes_list() -> str:
    lines = [f"{code}  {desc}" for code, desc in UPLOAD_CODES]
    lines.append("hang  " + " ; ".join(HANG_URIS))
    return "\n".join(lines)


def self_test() -> None:
    assert dest_hex("30koi.bin") == "33306b6f692e62696e"
    assert dest_utf("33306b6f692e62696e") == "30koi.bin"
    assert dest_hex("26cat.bin") == "32366361742e62696e"
    assert dest_hex("01fish.bin") == "3031666973682e62696e"
    spec = MODELS["F1"]
    assert diameter(spec["lights"]) == 230
    assert official_size(spec["frames"], spec["frame_block"]) == spec["size"]
    assert spec["size"] == 2793600
    assert spec["size"] % PAD_MODULO == 0
    cmd = encode_cmd(
        model="F1",
        video="swim.mp4",
        out="swim.bin",
        fit_scale="0.95",
        rotate="0",
        frames=20,
    )
    assert "--lights 116" in cmd
    assert "--header official" in cmd
    up = curl_upload(AP_IP, "30koi.bin", "30koi.bin")
    assert "name=33306b6f692e62696e" in up
    assert "DCIM/upload" in up
    play = curl_play(AP_IP, "30koi.bin")
    assert "act=play" in play
    assert devices_match("5D_TEST") == "match"
    assert devices_match("F1") == "match"
    assert devices_match("MissYou") == "no-match"
    print("ok")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    hx = sub.add_parser("dest-hex", help="UTF-8 dest filename → hex")
    hx.add_argument("name")

    ut = sub.add_parser("dest-utf", help="hex dest → UTF-8 filename")
    ut.add_argument("hex_name")

    geo = sub.add_parser("geometry", help="print model geometry")
    geo.add_argument("--model", default="F1", choices=sorted(MODELS))

    enc = sub.add_parser("encode-cmd", help="print holo-fan argv (does not run it)")
    enc.add_argument("--model", default="F1", choices=sorted(MODELS))
    enc.add_argument("--video", required=True)
    enc.add_argument("--out", required=True)
    enc.add_argument("--fit-scale", default="0.95")
    enc.add_argument("--rotate", default="0")
    enc.add_argument("--frames", type=int, default=None)

    host = argparse.ArgumentParser(add_help=False)
    host.add_argument("--host", default=AP_IP)

    sub.add_parser("curl-session", parents=[host], help="print GET /ctrl/session")
    sub.add_parser("curl-loop-one", parents=[host], help="print GET /ctrl/set?loop=one")
    sub.add_parser("curl-status", parents=[host], help="print play status")

    up = sub.add_parser("curl-upload", parents=[host], help="print POST /DCIM/upload")
    up.add_argument("--name", required=True, help="dest filename such as 30koi.bin")
    up.add_argument("--file", required=True, help="local .bin path")

    pl = sub.add_parser(
        "curl-play", parents=[host], help="print GET /DCIM/<hex>?act=play"
    )
    pl.add_argument("--name", required=True)

    rec = sub.add_parser(
        "curl-recover",
        parents=[host],
        help="print session + loop=one + play of a known-good dest",
    )
    rec.add_argument("--name", default="26cat.bin")

    dev = sub.add_parser("devices", help="SSID prefix / ports / apps")
    dev.add_argument("--list", action="store_true")
    dev.add_argument("match", nargs="*", help="match NAME")

    pre = sub.add_parser("presets", help="factory dest names from an F1 DCIM list")
    pre.add_argument("--list", action="store_true")

    codes = sub.add_parser("upload-codes", help="POST /DCIM/upload JSON codes")
    codes.add_argument("--list", action="store_true")

    sub.add_parser("self-test")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.cmd
    if cmd == "dest-hex":
        print(dest_hex(args.name))
        return 0
    if cmd == "dest-utf":
        print(dest_utf(args.hex_name))
        return 0
    if cmd == "geometry":
        print("\n".join(geometry_lines(args.model)))
        return 0
    if cmd == "encode-cmd":
        print(
            encode_cmd(
                model=args.model,
                video=args.video,
                out=args.out,
                fit_scale=args.fit_scale,
                rotate=args.rotate,
                frames=args.frames,
            )
        )
        return 0
    if cmd == "curl-session":
        print(curl_session(args.host))
        return 0
    if cmd == "curl-loop-one":
        print(curl_loop_one(args.host))
        return 0
    if cmd == "curl-status":
        print(curl_status(args.host))
        return 0
    if cmd == "curl-upload":
        print("# re-GET /ctrl/session immediately before this POST")
        print(curl_session(args.host))
        print(curl_upload(args.host, args.name, args.file))
        return 0
    if cmd == "curl-play":
        print("# first play after a new upload can fall to 01fish.bin total=9")
        print(curl_session(args.host))
        print(curl_loop_one(args.host))
        print(curl_play(args.host, args.name))
        print(curl_status(args.host))
        return 0
    if cmd == "curl-recover":
        print("# scramble recovery: play a proven dest (do not switcher=off)")
        print(curl_session(args.host))
        print(curl_loop_one(args.host))
        print(curl_play(args.host, args.name))
        print(curl_status(args.host))
        return 0
    if cmd == "devices":
        if args.list:
            print(devices_list())
            return 0
        if args.match:
            print(devices_match(" ".join(args.match)))
            return 0
        raise SystemExit("devices needs --list or match TOKEN")
    if cmd == "presets":
        if not args.list:
            raise SystemExit("presets needs --list")
        print(presets_list())
        return 0
    if cmd == "upload-codes":
        if not args.list:
            raise SystemExit("upload-codes needs --list")
        print(upload_codes_list())
        return 0
    if cmd == "self-test":
        self_test()
        return 0
    raise SystemExit(f"unknown cmd {cmd}")


if __name__ == "__main__":
    sys.exit(main())
