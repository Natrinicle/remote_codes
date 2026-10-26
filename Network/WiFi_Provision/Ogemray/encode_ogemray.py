#!/usr/bin/env python3
"""Encode Ogemray SmartConfig WiFi-provision dest maps.

Protocol: Ogemray SmartConfig (ogemray.android.smartconnection.SmartConfig).
Prints multicast dests `239.{i}.{b0}.{b1}` and the constant UDP payload.
Does not bind sockets or send UDP. Do not pass a live SSID or PSK;
self-test uses TestSSID / TestPass.

Example products recovered from: Greater Goods Weight Gurus SKU 0396 and
0385 (`setupType` wifi), app `com.dmdbrands.gurus.weight`. AP prefix
`gg_SmartScale_`.

Example:
    ./encode_ogemray.py self-test
    ./encode_ogemray.py ogemray --ssid TestSSID --password TestPass
    ./encode_ogemray.py ap --ssid TestSSID --password TestPass
"""

from __future__ import annotations

import argparse

OGEMRAY_XOR = 0x5C
OGEMRAY_ADD = 158
OGEMRAY_CRC_INIT = 4129
OGEMRAY_UDP_PORT = 7070
OGEMRAY_BIND_PORT = 7777
OGEMRAY_PAYLOAD = b"multicastmsg"
OGEMRAY_INTERVAL_MS = 20
OGEMRAY_TTL = 4
AP_HOST = "192.168.1.1"
AP_PORT = 10001

# CRC-16 table from SmartConfig.crc_tab (poly 0x1021, init 4129).
OGEMRAY_CRC_TAB: tuple[int, ...] = (
    0,
    4129,
    8258,
    12387,
    16516,
    20645,
    24774,
    28903,
    33032,
    37161,
    41290,
    45419,
    49548,
    53677,
    57806,
    61935,
    4657,
    528,
    12915,
    8786,
    21173,
    17044,
    29431,
    25302,
    37689,
    33560,
    45947,
    41818,
    54205,
    50076,
    62463,
    58334,
    9314,
    13379,
    1056,
    5121,
    25830,
    29895,
    17572,
    21637,
    42346,
    46411,
    34088,
    38153,
    58862,
    62927,
    50604,
    54669,
    13907,
    9842,
    5649,
    1584,
    30423,
    26358,
    22165,
    18100,
    46939,
    42874,
    38681,
    34616,
    63455,
    59390,
    55197,
    51132,
    18628,
    22757,
    26758,
    30887,
    2112,
    6241,
    10242,
    14371,
    51660,
    55789,
    59790,
    63919,
    35144,
    39273,
    43274,
    47403,
    23285,
    19156,
    31415,
    27286,
    6769,
    2640,
    14899,
    10770,
    56317,
    52188,
    64447,
    60318,
    39801,
    35672,
    47931,
    43802,
    27814,
    31879,
    19684,
    23749,
    11298,
    15363,
    3168,
    7233,
    60846,
    64911,
    52716,
    56781,
    44330,
    48395,
    36200,
    40265,
    32407,
    28342,
    24277,
    20212,
    15891,
    11826,
    7761,
    3696,
    65439,
    61374,
    57309,
    53244,
    48923,
    44858,
    40793,
    36728,
    37256,
    33193,
    45514,
    41451,
    53516,
    49453,
    61774,
    57711,
    4224,
    161,
    12482,
    8419,
    20484,
    16421,
    28742,
    24679,
    33721,
    37784,
    41979,
    46042,
    49981,
    54044,
    58239,
    62302,
    689,
    4752,
    8947,
    13010,
    16949,
    21012,
    25207,
    29270,
    46570,
    42443,
    38312,
    34185,
    62830,
    58703,
    54572,
    50445,
    13538,
    9411,
    5280,
    1153,
    29798,
    25671,
    21540,
    17413,
    42971,
    47098,
    34713,
    38840,
    59231,
    63358,
    50973,
    55100,
    9939,
    14066,
    1681,
    5808,
    26199,
    30326,
    17941,
    22068,
    55628,
    51565,
    63758,
    59695,
    39368,
    35305,
    47498,
    43435,
    22596,
    18533,
    30726,
    26663,
    6336,
    2273,
    14466,
    10403,
    52093,
    56156,
    60223,
    64286,
    35833,
    39896,
    43963,
    48026,
    19061,
    23124,
    27191,
    31254,
    2801,
    6864,
    10931,
    14994,
    64814,
    60687,
    56684,
    52557,
    48554,
    44427,
    40424,
    36297,
    31782,
    27655,
    23652,
    19525,
    15522,
    11395,
    7392,
    3265,
    61215,
    65342,
    53085,
    57212,
    44955,
    49082,
    36825,
    40952,
    28183,
    32310,
    20053,
    24180,
    11923,
    16050,
    3793,
    7920,
)

TEST_SSID = "TestSSID"
TEST_PASS = "TestPass"

# Locked 2026-10-26 from ogemray_encrypt(TestSSID, TestPass, user=0).
VEC_OGEMRAY_PLAIN = "18080800000054657374535349445465737450617373096e"
VEC_OGEMRAY_ENC = "e2f2f2fafafaa6d7cdc6adadb3b6a6d7cdc6aadbcdcdf3d0"


def _hex(data: bytes) -> str:
    return data.hex()


def _java_short(value: int) -> int:
    """Java `(short) value` then widen back to int (sign-extend 16)."""
    value &= 0xFFFF
    if value >= 0x8000:
        return value - 0x10000
    return value


def ogemray_crc16(data: bytes, init: int = OGEMRAY_CRC_INIT) -> int:
    """SmartConfig.CalCrc16. Length arg in the APK is unused; CRC is the array."""
    crc = init
    for byte in data:
        signed = byte - 256 if byte >= 128 else byte
        idx = ((crc >> 8) ^ signed) & 255
        crc = _java_short(OGEMRAY_CRC_TAB[idx] ^ (crc << 8))
    return crc & 0xFFFF


def ogemray_encrypt(data: bytes, xor_key: int = OGEMRAY_XOR) -> bytes:
    """`(b XOR 0x5C) + 158`, Java byte wrap."""
    return bytes(((byte ^ xor_key) + OGEMRAY_ADD) & 0xFF for byte in data)


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def ogemray_plain(
    ssid: str,
    password: str,
    *,
    user_number: int = 0,
    token: bytes | None = None,
) -> bytes:
    """Header + SSID + PSK + optional extra + CRC16-BE, padded even.

    extra is 0 when user_number is 0. Otherwise 1 + 32-byte token (33).
    """
    if user_number < 0 or user_number > 255:
        raise ValueError("user_number must be 0..255")
    ssid_b = _utf8(ssid) if ssid else b""
    pwd_b = _utf8(password) if password else b""
    if not ssid_b and pwd_b:
        raise ValueError("Ogemray rejects empty SSID with a password set")
    extra = b""
    if user_number == 0:
        if token is not None:
            raise ValueError("token requires user_number != 0")
    else:
        if token is None:
            raise ValueError("user_number != 0 needs a 32-byte token")
        if len(token) != 32:
            raise ValueError("token must be 32 bytes")
        extra = bytes((user_number,)) + token
    if not ssid_b and not pwd_b and not extra:
        raise ValueError("Ogemray rejects empty SSID, password, and extra")

    ssid_len = len(ssid_b)
    pwd_len = len(pwd_b)
    extra_len = len(extra)
    total = ssid_len + pwd_len + 8 + extra_len
    padded = total if total % 2 == 0 else total + 1
    blob = bytearray(padded)
    blob[0] = total if total % 2 == 0 else padded - 1
    blob[1] = ssid_len
    blob[2] = pwd_len
    blob[3] = extra_len
    blob[5] = 0
    blob[6 : 6 + ssid_len] = ssid_b
    blob[6 + ssid_len : 6 + ssid_len + pwd_len] = pwd_b
    blob[6 + ssid_len + pwd_len : 6 + ssid_len + pwd_len + extra_len] = extra
    crc_len = 6 + ssid_len + pwd_len + extra_len
    crc = ogemray_crc16(bytes(blob[:crc_len]))
    blob[crc_len] = (crc >> 8) & 0xFF
    blob[crc_len + 1] = crc & 0xFF
    return bytes(blob)


def ogemray_dests(encrypted: bytes) -> list[str]:
    """Multicast dest `239.{pair_index}.{b0}.{b1}` for each encrypted pair."""
    if len(encrypted) % 2:
        raise ValueError("encrypted blob length must be even")
    dests: list[str] = []
    for index in range(len(encrypted) // 2):
        b0 = encrypted[index * 2]
        b1 = encrypted[index * 2 + 1]
        dests.append(f"239.{index}.{b0}.{b1}")
    return dests


def _print_ogemray(encrypted: bytes, plain: bytes) -> None:
    dests = ogemray_dests(encrypted)
    print(f"plain: {_hex(plain)}")
    print(f"encrypted: {_hex(encrypted)}")
    print(f"pairs: {len(dests)}")
    print(f"payload: {_hex(OGEMRAY_PAYLOAD)}  {OGEMRAY_PAYLOAD.decode('ascii')}")
    print(f"udp: {OGEMRAY_UDP_PORT}")
    print(f"bind: {OGEMRAY_BIND_PORT} (app; this helper does not bind)")
    print(f"interval_ms: {OGEMRAY_INTERVAL_MS}")
    print(f"ttl: {OGEMRAY_TTL}")
    for dest in dests:
        print(dest)


def self_test() -> None:
    if ogemray_encrypt(bytes((0,))) != bytes((0xFA,)):
        raise ValueError("ogemray_encrypt 0x00")

    plain = ogemray_plain(TEST_SSID, TEST_PASS)
    enc = ogemray_encrypt(plain)
    if _hex(plain) != VEC_OGEMRAY_PLAIN:
        raise ValueError(f"ogemray plain {_hex(plain)}")
    if _hex(enc) != VEC_OGEMRAY_ENC:
        raise ValueError(f"ogemray enc {_hex(enc)}")
    dests = ogemray_dests(enc)
    if len(dests) != len(enc) // 2:
        raise ValueError("ogemray dest count")
    if not dests[0].startswith("239.0."):
        raise ValueError(f"first dest {dests[0]}")
    if OGEMRAY_PAYLOAD != b"multicastmsg" or len(OGEMRAY_PAYLOAD) != 12:
        raise ValueError("payload")

    token = bytes((0x11,)) * 32
    extra_plain = ogemray_plain(TEST_SSID, TEST_PASS, user_number=1, token=token)
    if extra_plain[3] != 33:
        raise ValueError("extra_len")
    if len(extra_plain) % 2:
        raise ValueError("extra pad")
    extra_enc = ogemray_encrypt(extra_plain)
    if len(ogemray_dests(extra_enc)) != len(extra_enc) // 2:
        raise ValueError("extra dests")


def _add_ogemray_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ssid", required=True, help="UTF-8 SSID (use a test name)")
    parser.add_argument(
        "--password",
        required=True,
        help="UTF-8 PSK (use a test value; this helper does not send)",
    )
    parser.add_argument("--user-number", type=int, default=0)
    parser.add_argument(
        "--token-hex",
        default="",
        help="32-byte token as hex when user-number is not 0",
    )


def _token_from_args(user_number: int, token_hex: str) -> bytes | None:
    if user_number == 0:
        if token_hex:
            raise ValueError("token-hex requires --user-number != 0")
        return None
    raw = token_hex.strip().replace(" ", "")
    if not raw:
        raise ValueError("user-number != 0 needs --token-hex (32 bytes)")
    token = bytes.fromhex(raw)
    if len(token) != 32:
        raise ValueError("token-hex must decode to 32 bytes")
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_og = sub.add_parser("ogemray", help="multicast-IP shout (print only)")
    _add_ogemray_args(p_og)
    p_ap = sub.add_parser(
        "ap", help="Plan B TCP blob for 192.168.1.1:10001 (print only)"
    )
    _add_ogemray_args(p_ap)
    sub.add_parser("self-test", help="check vectors; prints ok")
    args = parser.parse_args()

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0

    token = _token_from_args(args.user_number, args.token_hex)
    plain = ogemray_plain(
        args.ssid,
        args.password,
        user_number=args.user_number,
        token=token,
    )
    enc = ogemray_encrypt(plain)
    if args.cmd == "ap":
        print(f"tcp: {AP_HOST}:{AP_PORT}")
        print("join AP SSID prefix gg_SmartScale_ first (Plan B)")
    _print_ogemray(enc, plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
