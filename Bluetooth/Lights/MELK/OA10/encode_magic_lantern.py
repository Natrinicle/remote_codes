#!/usr/bin/env python3
"""Encode Magic Lantern / duoCo StripX 9-byte 7E…EF frames for BLE GATT FFF3.

Recovered on MELK-OA10 (Play wl.smartled.rgb 6.11.10). Service FFF0, write
FFF3 without response, notify FFF4. RGB solids use [7]=0x10.

Named effects and scenes come from Magic Lantern ModeFragment plus
R.array.modes_group0..8 (not RGBWControl, which is only RGB/W/CCT flags).
Sound-sensitive frames come from BluetoothLEService + StreamingFragment.

Helpers print payloads. They do not scan or GATT-connect.

Example:
    ./encode_magic_lantern.py on
    ./encode_magic_lantern.py rgb 255,0,0
    ./encode_magic_lantern.py warn
    ./encode_magic_lantern.py effect auto-play
    ./encode_magic_lantern.py scene rainbow
    ./encode_magic_lantern.py mic-eq rhythm
    ./encode_magic_lantern.py devices --list
    ./encode_magic_lantern.py devices match MELK-OA10 00:BE:00:00:00:00
    ./encode_magic_lantern.py self-test
"""

from __future__ import annotations

import argparse
import re
import sys

HEAD = 0x7E
TAIL = 0xEF
RGB_TARGET = 0x10
CCT_TARGET = 0x08
ANALOG_TARGET = 0x00
MUSIC_AMP_TARGET = 0x20
FRAME_LEN = 9

# Magic Lantern 6.11.10 device detection (jadx com.easylink.colorful).
# Print-only. Helpers do not scan or GATT-connect. GATT UUIDs below are
# after connect, not a scan filter.
APP_PLAY = "wl.smartled.rgb"
APP_PACKAGE = "com.easylink.colorful"
APP_VERSION = "6.11.10"
NAME_FILTER = "MELK-"
# Global.NAME_BROADCAST_FILTER — defined in Global.java; unused in this APK.
NAME_BROADCAST_FILTER = "MELK_"
# IllegalDeviceUtil: hide unless the address string contains this.
# Kotlin contains$default(address, "BE", false, 2, null) → ignoreCase default false.
MAC_CONTAINS = "BE"
# Global.DUO_CO_STRIP_CHANNEL. "smartled" would skip the BE check; this APK is not that.
DUO_CO_STRIP_CHANNEL = "duoCoStrip"
SMARTLED_CHANNEL = "smartled"
DEVICE_NAME_PREFIXES: tuple[str, ...] = (
    "MELK-OB",
    "MELK-OC",
    "MELK-OE",
    "MELK-OT",
    "MELK-TX",
)
# Underscore forms of DeviceName constants in the APK strings dump; not the scan filter.
DEVICE_NAME_UNDERSCORE: tuple[str, ...] = (
    "MELK_OB",
    "MELK_OC",
    "MELK_OE",
    "MELK_OT",
    "MELK_TX",
)
# Unique hyphen prefixes from the APK strings dump. No MELK-OA.
APK_NAME_STRINGS: tuple[str, ...] = ("MELK-DYDS", *DEVICE_NAME_PREFIXES)
SCENE_PREFIXES: tuple[str, ...] = ("MELK-OC", "MELK-OT")
HIDE_MIC_PREFIXES: tuple[str, ...] = ("MELK-OE", "MELK-OB", "MELK-TX")
RGBIC_W_RE = re.compile(r"^MELK-.+W.*", re.IGNORECASE)
CCT_RE = re.compile(r"^MELK-.+CT.*", re.IGNORECASE)
DYDS_INFIX = "MELK-DYDS"
DYDS_EFFECT_MODE = 156
DYDS_EFFECT_NAME = "Exploding star"


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

# slug -> (mode_byte, display name, group). From R.array.modes_group0..7_command.
EFFECTS: dict[str, tuple[int, str, str]] = {
    "auto-play": (0, "Auto Play", "Basic"),
    "magic-forward": (1, "Magic Forward", "Basic"),
    "magic-back": (2, "Magic Back", "Basic"),
    "7-color-energy": (212, "7-Color Energy", "Basic"),
    "7-color-jump": (193, "7-Color Jump", "Basic"),
    "r-g-b-jump": (194, "R-G-B Jump", "Basic"),
    "y-c-p-jump": (195, "Y-C-P Jump", "Basic"),
    "7-color-strobe": (196, "7-Color Strobe", "Basic"),
    "r-g-b-strobe": (197, "R-G-B Strobe", "Basic"),
    "y-c-p-strobe": (198, "Y-C-P Strobe", "Basic"),
    "7-color-gradual": (199, "7-Color Gradual", "Basic"),
    "r-y-gradual": (200, "R-Y Gradual", "Basic"),
    "r-p-gradual": (201, "R-P Gradual", "Basic"),
    "g-c-gradual": (202, "G-C Gradual", "Basic"),
    "g-y-gradual": (203, "G-Y Gradual", "Basic"),
    "b-p-gradual": (204, "B-P Gradual", "Basic"),
    "red-marquee": (205, "Red Marquee", "Basic"),
    "green-marquee": (206, "Green Marquee", "Basic"),
    "blue-marquee": (207, "Blue Marquee", "Basic"),
    "yellow-marquee": (208, "Yellow Marquee", "Basic"),
    "cyan-marquee": (209, "Cyan Marquee", "Basic"),
    "purple-marquee": (210, "Purple Marquee", "Basic"),
    "white-marquee": (211, "White Marquee", "Basic"),
    # OA10 RGBIC rainbow: 7-color-race is user-confirmed. 7-color-wave
    # (83) blends and reads pastel. Scene rainbow is hidden on OA10.
    "7-color-race": (77, "7-Color Race", "Basic"),
    "7-color-race-back": (78, "7-Color Race Back", "Basic"),
    "r-g-b-race": (79, "R-G-B Race", "Basic"),
    "r-g-b-race-back": (80, "R-G-B Race Back", "Basic"),
    "y-c-p-race": (81, "Y-C-P Race", "Basic"),
    "y-c-p-race-back": (82, "Y-C-P Race Back", "Basic"),
    "7-color-wave": (83, "7-Color Wave", "Basic"),
    "7-color-wave-back": (84, "7-Color Wave Back", "Basic"),
    "r-g-b-wave": (85, "R-G-B Wave", "Basic"),
    "r-g-b-wave-back": (86, "R-G-B Wave Back", "Basic"),
    "y-c-p-wave": (87, "Y-C-P Wave", "Basic"),
    "y-c-p-wave-back": (88, "Y-C-P Wave Back", "Basic"),
    "7-color-flush": (181, "7-Color Flush", "Basic"),
    "7-color-flush-back": (182, "7-Color Flush Back", "Basic"),
    "r-g-b-flush": (183, "R-G-B Flush", "Basic"),
    "r-g-b-flush-back": (184, "R-G-B Flush Back", "Basic"),
    "y-c-p-flush": (185, "Y-C-P Flush", "Basic"),
    "y-c-p-flush-back": (186, "Y-C-P Flush Back", "Basic"),
    "7-color-flush-close": (187, "7-Color Flush Close", "Basic"),
    "7-color-flush-open": (188, "7-Color Flush Open", "Basic"),
    "r-g-b-flush-close": (189, "R-G-B Flush Close", "Basic"),
    "r-g-b-flush-open": (190, "R-G-B Flush Open", "Basic"),
    "y-c-p-flush-close": (191, "Y-C-P Flush Close", "Basic"),
    "y-c-p-flush-open": (192, "Y-C-P Flush Open", "Basic"),
    "7-color-close": (57, "7-Color Close", "Curtain"),
    "7-color-open": (58, "7-Color Open", "Curtain"),
    "r-g-b-close": (59, "R-G-B Close", "Curtain"),
    "r-g-b-open": (60, "R-G-B Open", "Curtain"),
    "y-c-p-close": (61, "Y-C-P Close", "Curtain"),
    "y-c-p-open": (62, "Y-C-P Open", "Curtain"),
    "red-close": (63, "Red Close", "Curtain"),
    "red-open": (64, "Red Open", "Curtain"),
    "green-close": (65, "Green Close", "Curtain"),
    "green-open": (66, "Green Open", "Curtain"),
    "blue-close": (67, "Blue Close", "Curtain"),
    "blue-open": (68, "Blue Open", "Curtain"),
    "yellow-close": (69, "Yellow Close", "Curtain"),
    "yellow-open": (70, "Yellow Open", "Curtain"),
    "cyan-close": (71, "Cyan Close", "Curtain"),
    "cyan-open": (72, "Cyan Open", "Curtain"),
    "purple-close": (73, "Purple Close", "Curtain"),
    "purple-open": (74, "Purple Open", "Curtain"),
    "white-close": (75, "White Close", "Curtain"),
    "white-open": (76, "White Open", "Curtain"),
    "7-color-trans": (3, "7-Color Trans", "Trans"),
    "7-color-trans-back": (4, "7-Color Trans Back", "Trans"),
    "r-g-b-trans": (5, "R-G-B Trans", "Trans"),
    "r-g-b-trans-back": (6, "R-G-B Trans Back", "Trans"),
    "y-c-p-trans": (7, "Y-C-P Trans", "Trans"),
    "y-c-p-trans-back": (8, "Y-C-P Trans Back", "Trans"),
    "6-color-to-red": (9, "6-Color to Red", "Trans"),
    "6-color-to-red-back": (10, "6-Color to Red Back", "Trans"),
    "6-color-to-green": (11, "6-Color to Green", "Trans"),
    "6-color-to-green-back": (12, "6-Color to Green Back", "Trans"),
    "6-color-to-blue": (13, "6-Color to Blue", "Trans"),
    "6-color-to-blue-back": (14, "6-Color to Blue Back", "Trans"),
    "6-color-to-cyan": (15, "6-Color to Cyan", "Trans"),
    "6-color-to-cyan-back": (16, "6-Color to Cyan Back", "Trans"),
    "6-color-to-yellow": (17, "6-Color to Yellow", "Trans"),
    "6-color-to-yellow-back": (18, "6-Color to Yellow Back", "Trans"),
    "6-color-to-purple": (19, "6-Color to Purple", "Trans"),
    "6-color-to-purple-back": (20, "6-Color to Purple Back", "Trans"),
    "6-color-to-white": (21, "6-Color to White", "Trans"),
    "6-color-to-white-back": (22, "6-Color to White Back", "Trans"),
    "7-color-water": (39, "7-Color Water", "Water"),
    "7-color-water-back": (40, "7-Color Water Back", "Water"),
    "r-g-b-water": (41, "R-G-B Water", "Water"),
    "r-g-b-water-back": (42, "R-G-B Water Back", "Water"),
    "y-c-p-water": (43, "Y-C-P Water", "Water"),
    "y-c-p-water-back": (44, "Y-C-P Water Back", "Water"),
    "r-g-water": (45, "R-G Water", "Water"),
    "r-g-water-back": (46, "R-G Water Back", "Water"),
    "g-b-water": (47, "G-B Water", "Water"),
    "g-b-water-back": (48, "G-B Water Back", "Water"),
    "y-b-water": (49, "Y-B Water", "Water"),
    "y-b-water-back": (50, "Y-B Water Back", "Water"),
    "y-c-water": (51, "Y-C Water", "Water"),
    "y-c-water-back": (52, "Y-C Water Back", "Water"),
    "c-p-water": (53, "C-P Water", "Water"),
    "c-p-water-back": (54, "C-P Water Back", "Water"),
    "white-water": (55, "White Water", "Water"),
    "white-water-back": (56, "White Water Back", "Water"),
    "w-r-w-flow": (143, "W-R-W Flow", "Flow"),
    "w-r-w-flow-back": (144, "W-R-W Flow Back", "Flow"),
    "w-g-w-flow": (145, "W-G-W Flow", "Flow"),
    "w-g-w-flow-back": (146, "W-G-W Flow Back", "Flow"),
    "w-b-w-flow": (147, "W-B-W Flow", "Flow"),
    "w-b-w-flow-back": (148, "W-B-W Flow Back", "Flow"),
    "w-y-w-flow": (149, "W-Y-W Flow", "Flow"),
    "w-y-w-flow-back": (150, "W-Y-W Flow Back", "Flow"),
    "w-c-w-flow": (151, "W-C-W Flow", "Flow"),
    "w-c-w-flow-back": (152, "W-C-W Flow Back", "Flow"),
    "w-p-w-flow": (153, "W-P-W Flow", "Flow"),
    "w-p-w-flow-back": (154, "W-P-W Flow Back", "Flow"),
    "r-w-r-flow": (155, "R-W-R Flow", "Flow"),
    "r-w-r-flow-back": (156, "R-W-R Flow Back", "Flow"),
    "g-w-g-flow": (157, "G-W-G Flow", "Flow"),
    "g-w-g-flow-back": (158, "G-W-G Flow Back", "Flow"),
    "b-w-b-flow": (159, "B-W-B Flow", "Flow"),
    "b-w-b-flow-back": (160, "B-W-B Flow Back", "Flow"),
    "y-w-y-flow": (161, "Y-W-Y Flow", "Flow"),
    "y-w-y-flow-back": (162, "Y-W-Y Flow Back", "Flow"),
    "c-w-c-flow": (163, "C-W-C Flow", "Flow"),
    "c-w-c-flow-back": (164, "C-W-C Flow Back", "Flow"),
    "p-w-p-flow": (165, "P-W-P Flow", "Flow"),
    "p-w-p-flow-back": (166, "P-W-P Flow Back", "Flow"),
    "7-color-tail": (23, "7-Color Tail", "Tail"),
    "7-color-tail-back": (24, "7-Color Tail Back", "Tail"),
    "red-tail": (25, "Red Tail", "Tail"),
    "red-tail-back": (26, "Red Tail Back", "Tail"),
    "green-tail": (27, "Green Tail", "Tail"),
    "green-tail-back": (28, "Green Tail Back", "Tail"),
    "blue-tail": (29, "Blue Tail", "Tail"),
    "blue-tail-back": (30, "Blue Tail Back", "Tail"),
    "yellow-tail": (31, "Yellow Tail", "Tail"),
    "yellow-tail-back": (32, "Yellow Tail Back", "Tail"),
    "cyan-tail": (33, "Cyan Tail", "Tail"),
    "cyan-tail-back": (34, "Cyan Tail Back", "Tail"),
    "purple-tail": (35, "Purple Tail", "Tail"),
    "purple-tail-back": (36, "Purple Tail Back", "Tail"),
    "white-tail": (37, "White Tail", "Tail"),
    "white-tail-back": (38, "White Tail Back", "Tail"),
    "red-running": (89, "Red Running", "Run"),
    "green-running": (91, "Green Running", "Run"),
    "blue-running": (93, "Blue Running", "Run"),
    "yellow-running": (95, "Yellow Running", "Run"),
    "cyan-running": (97, "Cyan Running", "Run"),
    "purple-running": (99, "Purple Running", "Run"),
    "white-running": (101, "White Running", "Run"),
    "7-color-running": (103, "7-Color Running", "Run"),
    "r-g-b-running": (105, "R-G-B Running", "Run"),
    "y-c-p-running": (107, "Y-C-P Running", "Run"),
    "b-p-c-y-running": (109, "B-P-C-Y Running", "Run"),
    "b-g-c-y-running": (111, "B-G-C-Y Running", "Run"),
    "red-dot-in-white-running": (113, "Red-Dot in White Running", "Run"),
    "green-dot-in-red-running-115": (115, "Green-Dot in Red Running", "Run"),
    "blue-dot-in-green-running": (117, "Blue-Dot in Green Running", "Run"),
    "yellow-dot-in-blue-running": (119, "Yellow-Dot in Blue Running", "Run"),
    "cyan-dot-in-yellow-running-121": (121, "Cyan-Dot in Yellow Running", "Run"),
    "purple-dot-in-cyan-running": (123, "Purple-Dot in Cyan Running", "Run"),
    "white-dot-in-purple-running": (125, "White-Dot in Purple Running", "Run"),
    "white-dot-in-red-running": (127, "White-Dot in Red Running", "Run"),
    "7-color-in-red-running": (129, "7-Color in Red Running", "Run"),
    "7-color-in-green-running": (131, "7-Color in Green Running", "Run"),
    "7-color-in-blue-running": (133, "7-Color in Blue Running", "Run"),
    "7-color-in-yellow-running": (135, "7-Color in Yellow Running", "Run"),
    "7-color-in-cyan-running": (137, "7-Color in Cyan Running", "Run"),
    "7-color-in-purple-running": (139, "7-Color in Purple Running", "Run"),
    "7-color-in-white-running": (141, "7-Color in White Running", "Run"),
    "green-dot-in-blue-running": (167, "Green-Dot in Blue Running", "Run"),
    "green-dot-in-red-running-169": (169, "Green-Dot in Red Running", "Run"),
    "red-dot-in-blue-running": (171, "Red-Dot in Blue Running", "Run"),
    "cyan-dot-in-yellow-running-173": (173, "Cyan-Dot in Yellow Running", "Run"),
    "yellow-dot-in-purple-running": (175, "Yellow-Dot in Purple Running", "Run"),
    "white-dot-in-yelllow-running": (177, "White-Dot in Yelllow Running", "Run"),
    "yellow-dot-in-white-running": (179, "Yellow-Dot in White Running", "Run"),
    "red-run-back": (90, "Red Run Back", "RunBack"),
    "green-run-back": (92, "Green Run Back", "RunBack"),
    "blue-run-back": (94, "Blue Run Back", "RunBack"),
    "yellow-run-back": (96, "Yellow Run Back", "RunBack"),
    "cyan-run-back": (98, "Cyan Run Back", "RunBack"),
    "purple-run-back": (100, "Purple Run Back", "RunBack"),
    "white-run-back": (102, "White Run Back", "RunBack"),
    "7-color-run-back": (104, "7-Color Run Back", "RunBack"),
    "r-g-b-run-back": (106, "R-G-B Run Back", "RunBack"),
    "y-c-p-run-back": (108, "Y-C-P Run Back", "RunBack"),
    "b-p-c-y-run-back": (110, "B-P-C-Y Run Back", "RunBack"),
    "b-g-c-y-run-back": (112, "B-G-C-Y Run Back", "RunBack"),
    "red-dot-in-white-run-back": (114, "Red-Dot in White Run Back", "RunBack"),
    "green-dot-in-red-run-back-116": (116, "Green-Dot in Red Run Back", "RunBack"),
    "blue-dot-in-green-run-back": (118, "Blue-Dot in Green Run Back", "RunBack"),
    "yellow-dot-in-blue-run-back": (120, "Yellow-Dot in Blue Run Back", "RunBack"),
    "cyan-dot-in-yellow-run-back-122": (122, "Cyan-Dot in Yellow Run Back", "RunBack"),
    "purple-dot-in-cyan-run-back": (124, "Purple-Dot in Cyan Run Back", "RunBack"),
    "white-dot-in-purple-run-back": (126, "White-Dot in Purple Run Back", "RunBack"),
    "white-dot-in-red-run-back": (128, "White-Dot in Red Run Back", "RunBack"),
    "7-color-in-red-run-back": (130, "7-Color in Red Run Back", "RunBack"),
    "7-color-in-green-run-back": (132, "7-Color in Green Run Back", "RunBack"),
    "7-color-in-blue-run-back": (134, "7-Color in Blue Run Back", "RunBack"),
    "7-color-in-yellow-run-back": (136, "7-Color in Yellow Run Back", "RunBack"),
    "7-color-in-cyan-run-back": (138, "7-Color in Cyan Run Back", "RunBack"),
    "7-color-in-purple-run-back": (140, "7-Color in Purple Run Back", "RunBack"),
    "7-color-in-white-run-back": (142, "7-Color in White Run Back", "RunBack"),
    "green-dot-in-blue-run-back": (168, "Green-Dot in Blue Run Back", "RunBack"),
    "green-dot-in-red-run-back-170": (170, "Green-Dot in Red Run Back", "RunBack"),
    "red-dot-in-blue-run-back": (172, "Red-Dot in Blue Run Back", "RunBack"),
    "cyan-dot-in-yellow-run-back-174": (174, "Cyan-Dot in Yellow Run Back", "RunBack"),
    "yellow-dot-in-purple-run-back": (176, "Yellow-Dot in Purple Run Back", "RunBack"),
    "white-dot-in-yelllow-run-back": (178, "White-Dot in Yelllow Run Back", "RunBack"),
    "yellow-dot-in-white-run-back": (180, "Yellow-Dot in White Run Back", "RunBack"),
}

# slug -> (scene_byte, display name, group). From R.array.modes_group8_command.
# Wire is scene opcode 0x31, not the effect envelope.
SCENES: dict[str, tuple[int, str, str]] = {
    "sunrise": (1, "Sunrise", "Scenes"),
    "sunset": (2, "Sunset", "Scenes"),
    "birthday": (3, "Birthday", "Scenes"),
    "candlelight": (4, "Candlelight", "Scenes"),
    "fireworks": (5, "Fireworks", "Scenes"),
    "party": (6, "Party", "Scenes"),
    "datiny": (7, "Datiny", "Scenes"),
    "starry-sky": (8, "Starry sky", "Scenes"),
    "romantic": (9, "Romantic", "Scenes"),
    "disco": (10, "Disco", "Scenes"),
    "rainbow": (11, "Rainbow", "Scenes"),
    "movie": (12, "Movie", "Scenes"),
    "christmas": (13, "Christmas", "Scenes"),
    "flowing": (14, "Flowing", "Scenes"),
    "sleeping": (15, "Sleeping", "Scenes"),
    "ocean": (16, "Ocean", "Scenes"),
    "forest": (17, "Forest", "Scenes"),
    "reading": (18, "Reading", "Scenes"),
    "working": (19, "Working", "Scenes"),
    "dazzle": (20, "Dazzle", "Scenes"),
    "gentle": (21, "Gentle", "Scenes"),
    "wedding": (22, "Wedding", "Scenes"),
    "snow": (23, "Snow", "Scenes"),
    "fire": (24, "Fire", "Scenes"),
    "lightning": (25, "Lightning", "Scenes"),
    "valentines-day": (26, "Valentine's Day", "Scenes"),
    "hallowmas": (27, "Hallowmas", "Scenes"),
    "warnning": (28, "Warnning", "Scenes"),
}

# StreamingFragment radio -> BluetoothUtil.ExternalMicEqMode.
# Wire byte is mode + 128 (BluetoothLEService.changeExternalMicEqMode).
MIC_EQ: dict[str, tuple[int, str]] = {
    "energic": (0, "Energic"),
    "rhythm": (1, "Rhythm"),
    "spectrum": (2, "Spectrum"),
    "rolling": (3, "Rolling"),
    "energic-two": (4, "Energic two"),
    "rhythm-two": (5, "Rhythm two"),
    "spectrum-two": (6, "Spectrum two"),
    "rolling-two": (7, "Rolling two"),
}


def _slug(text: str) -> str:
    out: list[str] = []
    for ch in text.strip().lower().replace("'", ""):
        out.append(ch if ch.isalnum() else "-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _index_by_mode(table: dict[str, tuple]) -> dict[int, tuple[str, str, str]]:
    by_mode: dict[int, tuple[str, str, str]] = {}
    for slug, spec in table.items():
        mode = spec[0]
        name = spec[1]
        group = spec[2] if len(spec) > 2 else ""
        by_mode.setdefault(mode, (slug, name, group))
    return by_mode


EFFECTS_BY_MODE = _index_by_mode(EFFECTS)
SCENES_BY_MODE = _index_by_mode(SCENES)
MIC_EQ_BY_MODE = {spec[0]: (slug, spec[1]) for slug, spec in MIC_EQ.items()}


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


def resolve_named(
    token: str,
    table: dict[str, tuple],
    *,
    kind: str,
    hi: int = 255,
) -> int:
    text = token.strip()
    if text.isdigit() or text.startswith(("0x", "0X")):
        mode = int(text, 0)
        if mode < 0 or mode > hi:
            raise ValueError(f"{kind} must be 0..{hi}")
        return mode
    slug = _slug(text)
    if slug in table:
        return table[slug][0]
    lowered = {spec[1].lower(): spec[0] for spec in table.values()}
    if text.lower() in lowered:
        return lowered[text.lower()]
    raise ValueError(f"unknown {kind} {token!r}; try '{kind} --list'")


def effect(mode: int) -> bytes:
    if mode < 0 or mode > 255:
        raise ValueError("effect mode must be 0..255")
    return wrap(bytes((0x05, 0x03, mode, 0x06, 0xFF, 0xFF, 0x00)))


def scene(mode: int) -> bytes:
    if mode < 0 or mode > 255:
        raise ValueError("scene must be 0..255")
    return wrap(bytes((0x05, 0x31, mode, 0x07, 0xFF, 0xFF, 0x01)))


def speed(level: int) -> bytes:
    if level < 0 or level > 255:
        raise ValueError("speed must be 0..255")
    return wrap(bytes((0x04, 0x02, level, 0xFF, 0xFF, 0xFF, 0x00)))


def mic_on() -> bytes:
    return wrap(bytes((0x04, 0x07, 0x01, 0xFF, 0xFF, 0xFF, 0x00)))


def mic_off() -> bytes:
    return wrap(bytes((0x04, 0x07, 0x00, 0xFF, 0xFF, 0xFF, 0x00)))


def mic_eq(mode: int) -> bytes:
    if mode < 0 or mode > 7:
        raise ValueError("mic-eq must be 0..7")
    return wrap(bytes((0x07, 0x03, mode + 128, 0x04, 0xFF, 0xFF, 0x00)))


def mic_sensitivity(level: int) -> bytes:
    if level < 0 or level > 100:
        raise ValueError("mic-sensitivity must be 0..100")
    return wrap(bytes((0x04, 0x06, level, 0xFF, 0xFF, 0xFF, 0x00)))


def music_amp(red: int, green: int, blue: int) -> bytes:
    for name, value in (("r", red), ("g", green), ("b", blue)):
        if value < 0 or value > 255:
            raise ValueError(f"{name} must be 0..255")
    return wrap(bytes((0x07, 0x05, 0x03, red, green, blue, MUSIC_AMP_TARGET)))


def decode(raw: bytes) -> str:
    hx = raw.hex()
    if len(raw) != FRAME_LEN or raw[0] != HEAD or raw[-1] != TAIL:
        return f"{hx}  (not a 9-byte 7E…EF frame)"
    target = raw[7]
    if raw[1:4] == b"\x07\x05\x03":
        kind = "rgb" if target == RGB_TARGET else f"color target=0x{target:02x}"
        if target == ANALOG_TARGET:
            kind = "analog color [7]=0x00 (wrong RGBIC render target)"
        elif target == MUSIC_AMP_TARGET:
            kind = "music amp [7]=0x20"
        return (
            f"{hx}  {kind} rgb={raw[4]},{raw[5]},{raw[6]} "
            f"[{raw[4]:3d},{raw[5]:3d},{raw[6]:3d}]"
        )
    if raw[2:4] == b"\x05\x03":
        kind = "rgb" if target == RGB_TARGET else f"color target=0x{target:02x}"
        if target == ANALOG_TARGET:
            kind = "analog color [7]=0x00 (wrong RGBIC render target)"
        elif target == MUSIC_AMP_TARGET:
            kind = "music amp [7]=0x20"
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
        info = EFFECTS_BY_MODE.get(raw[3])
        extra = f" {info[1]}" if info else ""
        return f"{hx}  effect mode={raw[3]}{extra}"
    if raw[1:3] == b"\x05\x31":
        info = SCENES_BY_MODE.get(raw[3])
        extra = f" {info[1]}" if info else ""
        return f"{hx}  scene {raw[3]}{extra}"
    if raw[1:3] == b"\x04\x02":
        return f"{hx}  speed {raw[3]}"
    if raw[1:3] == b"\x04\x07":
        state = "on" if raw[3] else "off"
        return f"{hx}  external mic {state}"
    if raw[1:3] == b"\x04\x06":
        return f"{hx}  mic sensitivity {raw[3]}"
    if raw[1:3] == b"\x07\x03":
        eq = raw[3] - 128
        info = MIC_EQ_BY_MODE.get(eq)
        extra = f" {info[1]}" if info else ""
        return f"{hx}  mic-eq {eq}{extra} wire=0x{raw[3]:02x}"
    if raw[1:2] == b"\x83" or raw[2:3] == b"\x83":
        return f"{hx}  system_time / truncated analog login (do not send truncated)"
    return f"{hx}  unknown"


def _list_table(table: dict[str, tuple], *, kind: str) -> str:
    lines = [f"{kind:8} {'slug':24} {'mode':>4} group"]
    for slug, spec in table.items():
        lines.append(
            f"{kind:8} {slug:24} {spec[0]:4d} {spec[2] if len(spec) > 2 else ''}  {spec[1]}"
        )
    return "\n".join(lines)


def _starts_with_any(name: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if name.startswith(prefix):
            return prefix
    return None


def is_illegal_device(name: str | None, address: str | None) -> bool:
    """IllegalDeviceUtil.getIllegalDevice for this duoCoStrip APK."""
    if DUO_CO_STRIP_CHANNEL == SMARTLED_CHANNEL:
        return False
    if name is None or address is None:
        return False
    return MAC_CONTAINS not in address


def match_device(name: str, mac: str | None = None) -> dict[str, object]:
    """Apply Magic Lantern 6.11.10 scan + feature-gate rules. Print-only."""
    name_ok = name.startswith(NAME_FILTER)
    if mac is None:
        mac_checked = False
        mac_ok: bool | None = None
        accepted = name_ok
    else:
        mac_checked = True
        mac_ok = MAC_CONTAINS in mac
        accepted = name_ok and not is_illegal_device(name, mac)
    return {
        "name": name,
        "mac": mac,
        "name_ok": name_ok,
        "mac_checked": mac_checked,
        "mac_ok": mac_ok,
        "accepted": accepted,
        "device_name": _starts_with_any(name, DEVICE_NAME_PREFIXES),
        "scenes": _starts_with_any(name, SCENE_PREFIXES) is not None,
        "hide_mic": _starts_with_any(name, HIDE_MIC_PREFIXES) is not None,
        "rgbic_w": RGBIC_W_RE.match(name) is not None,
        "cct": CCT_RE.match(name) is not None,
        "dyds_extra": DYDS_INFIX in name,
    }


def format_device_catalog() -> str:
    lines = [
        f"{'field':16} value",
        f"{'app':16} {APP_PLAY} {APP_VERSION}",
        f"{'package':16} {APP_PACKAGE}",
        f"{'name_filter':16} {NAME_FILTER}",
        f"{'name_broadcast':16} {NAME_BROADCAST_FILTER}  unused in this APK",
        f"{'mac_contains':16} {MAC_CONTAINS}  case-sensitive; required when MAC given",
        (
            f"{'duo_co_channel':16} {DUO_CO_STRIP_CHANNEL}  "
            f"{SMARTLED_CHANNEL} would skip BE check"
        ),
        f"{'gatt_service':16} {SERVICE_UUID}  after connect, not a scan filter",
        f"{'gatt_write':16} {WRITE_UUID}  write-without-response",
        f"{'gatt_notify':16} {NOTIFY_UUID}",
        f"{'scan_company_id':16} not filtered",
        f"{'analog_elk':16} not supported (ELK-BLEDOM ads rejected)",
        f"{'oa10':16} generic {NAME_FILTER} (no DeviceName MELK-OA)",
    ]
    for prefix in DEVICE_NAME_PREFIXES:
        lines.append(f"{'device_name':16} {prefix}")
    for text_s in APK_NAME_STRINGS:
        lines.append(f"{'apk_string':16} {text_s}")
    for text_s in DEVICE_NAME_UNDERSCORE:
        lines.append(f"{'apk_string':16} {text_s}")
    lines.extend(
        [
            (
                f"{'gate_scenes':16} show if name starts with "
                f"{' or '.join(SCENE_PREFIXES)}"
            ),
            (
                f"{'gate_hide_mic':16} hide if name starts with "
                f"{', '.join(HIDE_MIC_PREFIXES)}"
            ),
            f"{'gate_rgbic_w':16} {RGBIC_W_RE.pattern}  CASE_INSENSITIVE",
            f"{'gate_cct':16} {CCT_RE.pattern}  CASE_INSENSITIVE",
            (
                f"{'gate_dyds':16} name contains {DYDS_INFIX} → effect "
                f"{DYDS_EFFECT_MODE} {DYDS_EFFECT_NAME} (not OA10 default)"
            ),
            (
                f"{'encoder':16} encode_magic_lantern.py  "
                "print-only for every accepted MELK-*"
            ),
        ]
    )
    return "\n".join(lines)


def format_device_match(hit: dict[str, object]) -> str:
    name = str(hit["name"])
    mac = hit["mac"]
    mac_s = str(mac) if mac is not None else "(omitted)"
    verdict = "ACCEPT" if hit["accepted"] else "REJECT"
    reasons: list[str] = []
    if not hit["name_ok"]:
        reasons.append(f"name does not start with {NAME_FILTER}")
    if hit["mac_checked"] and not hit["mac_ok"]:
        reasons.append(f"mac does not contain {MAC_CONTAINS}")
    if hit["accepted"]:
        if hit["mac_checked"]:
            reasons.append(f"name filter pass; mac contains {MAC_CONTAINS}")
        else:
            reasons.append("name filter pass; mac check skipped")
    device_name = hit["device_name"]
    if device_name:
        dn = str(device_name)
    elif hit["name_ok"]:
        dn = f"generic {NAME_FILTER}"
    else:
        dn = "(none)"
    if hit["mac_checked"]:
        mac_check = "pass" if hit["mac_ok"] else "fail"
    else:
        mac_check = "skipped"
    dyds = "yes" if hit["dyds_extra"] else "no"
    if hit["dyds_extra"]:
        dyds += f"  effect {DYDS_EFFECT_MODE} {DYDS_EFFECT_NAME}"
    lines = [
        f"{'verdict':16} {verdict}",
        f"{'name':16} {name}",
        f"{'mac':16} {mac_s}",
        f"{'name_filter':16} {'pass' if hit['name_ok'] else 'fail'}",
        f"{'mac_check':16} {mac_check}",
        f"{'reason':16} {'; '.join(reasons)}",
        f"{'device_name':16} {dn}",
        f"{'scenes':16} {'show' if hit['scenes'] else 'hide'}",
        f"{'mic':16} {'hide' if hit['hide_mic'] else 'show'}",
        f"{'rgbic_w':16} {'yes' if hit['rgbic_w'] else 'no'}",
        f"{'cct':16} {'yes' if hit['cct'] else 'no'}",
        f"{'dyds_extra':16} {dyds}",
    ]
    return "\n".join(lines)


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
    assert effect(0) == bytes.fromhex("7e05030006ffff00ef")
    assert effect(resolve_named("auto-play", EFFECTS, kind="effect")) == effect(0)
    assert effect(resolve_named("Auto Play", EFFECTS, kind="effect")) == effect(0)
    assert effect(resolve_named("7-color-jump", EFFECTS, kind="effect")) == effect(193)
    assert effect(
        resolve_named("7-color-race", EFFECTS, kind="effect")
    ) == bytes.fromhex("7e05034d06ffff00ef")
    assert scene(11) == bytes.fromhex("7e05310b07ffff01ef")
    assert scene(resolve_named("rainbow", SCENES, kind="scene")) == scene(11)
    assert resolve_named("Valentine's Day", SCENES, kind="scene") == 26
    assert mic_on() == bytes.fromhex("7e040701ffffff00ef")
    assert mic_off() == bytes.fromhex("7e040700ffffff00ef")
    assert mic_eq(1) == bytes.fromhex("7e07038104ffff00ef")
    assert mic_eq(resolve_named("rhythm", MIC_EQ, kind="mic-eq", hi=7)) == mic_eq(1)
    assert mic_sensitivity(50) == bytes.fromhex("7e040632ffffff00ef")
    assert music_amp(255, 0, 0) == bytes.fromhex("7e070503ff000020ef")
    assert "music amp" in decode(music_amp(255, 0, 0))
    assert "Auto Play" in decode(effect(0))
    assert "Rainbow" in decode(scene(11))
    assert len(EFFECTS) == 213
    assert len(SCENES) == 28
    assert resolve_named("green-dot-in-red-running-115", EFFECTS, kind="effect") == 115
    assert resolve_named("green-dot-in-red-running-169", EFFECTS, kind="effect") == 169
    be_mac = "00:BE:00:00:00:00"
    no_be_mac = "00:11:22:33:44:55"
    oa10 = match_device("MELK-OA10", be_mac)
    assert oa10["accepted"] is True
    assert oa10["name_ok"] is True
    assert oa10["mac_ok"] is True
    assert oa10["device_name"] is None
    assert oa10["scenes"] is False
    assert oa10["hide_mic"] is False
    assert oa10["rgbic_w"] is False
    assert oa10["cct"] is False
    assert oa10["dyds_extra"] is False
    blocked = match_device("MELK-OA10", no_be_mac)
    assert blocked["accepted"] is False
    assert blocked["mac_ok"] is False
    analog = match_device("ELK-BLEDOM", be_mac)
    assert analog["accepted"] is False
    assert analog["name_ok"] is False
    oc = match_device("MELK-OC", be_mac)
    assert oc["accepted"] is True
    assert oc["scenes"] is True
    assert oc["device_name"] == "MELK-OC"
    oe = match_device("MELK-OE", be_mac)
    assert oe["hide_mic"] is True
    assert oe["scenes"] is False
    wname = match_device("MELK-OA10W", be_mac)
    assert wname["accepted"] is True
    assert wname["rgbic_w"] is True
    assert wname["device_name"] is None
    cct_hit = match_device("MELK-xxCT", be_mac)
    assert cct_hit["cct"] is True
    dyds = match_device("MELK-DYDS", be_mac)
    assert dyds["dyds_extra"] is True
    assert dyds["accepted"] is True
    skipped = match_device("MELK-OA10")
    assert skipped["mac_checked"] is False
    assert skipped["accepted"] is True
    catalog = format_device_catalog()
    assert catalog == format_device_catalog()
    assert NAME_FILTER in catalog
    assert NAME_BROADCAST_FILTER in catalog
    assert "unused in this APK" in catalog
    for prefix in DEVICE_NAME_PREFIXES:
        assert prefix in catalog
    assert SERVICE_UUID in catalog
    assert "not a scan filter" in catalog
    assert DYDS_INFIX in catalog
    assert str(DYDS_EFFECT_MODE) in catalog
    ob = match_device("MELK-OB", be_mac)
    assert ob["hide_mic"] is True
    ot = match_device("MELK-OT", be_mac)
    assert ot["scenes"] is True
    tx = match_device("MELK-TX", be_mac)
    assert tx["hide_mic"] is True
    # APK contains() is case-sensitive (ignoreCase default false).
    assert match_device("MELK-OA10", "00:be:00:00:00:00")["accepted"] is False
    assert DUO_CO_STRIP_CHANNEL != SMARTLED_CHANNEL
    assert "ACCEPT" in format_device_match(oa10)
    assert "mac check skipped" in format_device_match(skipped)
    analog_txt = format_device_match(analog)
    assert "REJECT" in analog_txt
    assert "(none)" in analog_txt
    assert not is_illegal_device(None, be_mac)
    assert is_illegal_device("MELK-OA10", no_be_mac)
    assert not is_illegal_device("MELK-OA10", be_mac)


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
    eff_p = sub.add_parser("effect", help="named or numeric 7E 05 03 MODE 06…")
    eff_p.add_argument("mode", nargs="?", help="slug, display name, or 0-255")
    eff_p.add_argument("--list", action="store_true", help="print named effects")
    scn_p = sub.add_parser("scene", help="named or numeric 7E 05 31 SCENE 07…")
    scn_p.add_argument("mode", nargs="?", help="slug, display name, or 0-255")
    scn_p.add_argument("--list", action="store_true", help="print named scenes")
    spd_p = sub.add_parser("speed")
    spd_p.add_argument("level")
    mic_p = sub.add_parser("mic", help="external mic on/off")
    mic_p.add_argument("state", choices=("on", "off"))
    eq_p = sub.add_parser("mic-eq", help="sound-sensitive EQ mode")
    eq_p.add_argument(
        "mode", nargs="?", help="energic|rhythm|spectrum|rolling or *-two"
    )
    eq_p.add_argument("--list", action="store_true")
    sens_p = sub.add_parser("mic-sensitivity", help="0-100")
    sens_p.add_argument("level")
    amp_p = sub.add_parser("music-amp", help="music amplitude RGB [7]=0x20")
    amp_p.add_argument("color", help="RRGGBB or R,G,B")
    dec_p = sub.add_parser("decode")
    dec_p.add_argument("hex")
    sub.add_parser("self-test")
    dev_p = sub.add_parser(
        "devices",
        help="print-only Magic Lantern 6.11.10 device catalog (no scan)",
    )
    dev_p.add_argument(
        "--list",
        action="store_true",
        help="print filter, GATT, prefixes, and feature gates",
    )
    dev_sub = dev_p.add_subparsers(dest="devices_cmd")
    match_p = dev_sub.add_parser(
        "match", help="accept/reject + gates for advertised NAME [MAC]"
    )
    match_p.add_argument("name", help="advertised GAP name")
    match_p.add_argument(
        "mac",
        nargs="?",
        default=None,
        help="BLE address; omit to skip the BE-in-MAC check",
    )

    args = parser.parse_args(argv)
    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    if args.cmd == "devices":
        if args.list:
            print(format_device_catalog())
            return 0
        if args.devices_cmd == "match":
            print(format_device_match(match_device(args.name, args.mac)))
            return 0
        raise ValueError("devices needs --list or match NAME [MAC]")
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
        if args.list:
            print(_list_table(EFFECTS, kind="effect"))
            return 0
        if not args.mode:
            raise ValueError("effect needs a name, slug, or 0-255 (or --list)")
        print(effect(resolve_named(args.mode, EFFECTS, kind="effect")).hex())
        return 0
    if args.cmd == "scene":
        if args.list:
            print(_list_table(SCENES, kind="scene"))
            return 0
        if not args.mode:
            raise ValueError("scene needs a name, slug, or 0-255 (or --list)")
        print(scene(resolve_named(args.mode, SCENES, kind="scene")).hex())
        return 0
    if args.cmd == "speed":
        print(speed(parse_u8(args.level, name="speed")).hex())
        return 0
    if args.cmd == "mic":
        print((mic_on() if args.state == "on" else mic_off()).hex())
        return 0
    if args.cmd == "mic-eq":
        if args.list:
            for slug, spec in MIC_EQ.items():
                print(
                    f"mic-eq   {slug:16} {spec[0]}  {spec[1]}  wire=0x{spec[0] + 128:02x}"
                )
            return 0
        if not args.mode:
            raise ValueError("mic-eq needs a name or 0-7 (or --list)")
        print(mic_eq(resolve_named(args.mode, MIC_EQ, kind="mic-eq", hi=7)).hex())
        return 0
    if args.cmd == "mic-sensitivity":
        print(
            mic_sensitivity(parse_u8(args.level, hi=100, name="mic-sensitivity")).hex()
        )
        return 0
    if args.cmd == "music-amp":
        print(music_amp(*parse_rgb(args.color)).hex())
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
