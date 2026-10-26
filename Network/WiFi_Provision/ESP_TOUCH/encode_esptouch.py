#!/usr/bin/env python3
"""Encode ESP-TOUCH (Espressif length coding) WiFi-provision length maps.

GuideCode UDP payloads of length 515, 514, 513, 512 filled with 0x31.
DatumCode records become u16 + EXTRA_LEN 40. Prints dest / length maps.
Does not bind sockets or send UDP. Do not pass a live SSID or PSK;
self-test uses TestSSID / TestPass.

Example products recovered from: Greater Goods SKU 0384 and 0397
(`setupType` espTouchWifi).

Example:
    ./encode_esptouch.py self-test
    ./encode_esptouch.py esptouch --ssid TestSSID --password TestPass
"""

from __future__ import annotations

import argparse
import ipaddress
from collections.abc import Sequence

GUIDE_U8S: tuple[int, ...] = (515, 514, 513, 512)
ESPT_EXTRA_LEN = 40
ESPT_INDEX_MAX = 127
ESPT_SPEC_BYTE = 0x31
ESPT_TARGET_PORT = 7001
ESPT_LISTEN_PORT = 18266
ESPT_GUIDE_INTERVAL_MS = 8
ESPT_DATA_INTERVAL_MS = 8
ESPT_GUIDE_TIMEOUT_MS = 2000
ESPT_DATA_TIMEOUT_MS = 4000
ESPT_SEND_WINDOW_MS = 90000
CRC8_POLY = 140

TEST_SSID = "TestSSID"
TEST_PASS = "TestPass"
TEST_BSSID = "AA:BB:CC:DD:EE:FF"
TEST_IP = "192.0.2.10"
PLACEHOLDER_MAC = "AA:BB:CC:DD:EE:FF"

VEC_ESPT_DATA: tuple[int, ...] = (
    121,
    296,
    273,
    72,
    297,
    176,
    129,
    298,
    243,
    185,
    299,
    282,
    158,
    300,
    148,
    242,
    313,
    210,
    180,
    301,
    216,
    248,
    302,
    248,
    56,
    303,
    74,
    51,
    314,
    51,
    72,
    304,
    130,
    253,
    305,
    44,
    254,
    306,
    221,
    180,
    315,
    148,
    239,
    307,
    91,
    79,
    308,
    268,
    173,
    309,
    200,
    85,
    316,
    261,
    174,
    310,
    57,
    207,
    311,
    75,
    159,
    312,
    267,
    54,
    317,
    230,
    247,
    318,
    71,
)

# splitUint8To2bytes(20) → 0x14 hex digits 1,4 (ByteUtil self-test).
VEC_SPLIT_20 = (1, 4)


def _java_short(value: int) -> int:
    """Java `(short) value` then widen back to int (sign-extend 16)."""
    value &= 0xFFFF
    if value >= 0x8000:
        return value - 0x10000
    return value


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def parse_bssid(text: str) -> bytes:
    """Colon, dash, or 12-hex BSSID. Placeholder AA:BB:CC:DD:EE:FF is allowed here."""
    raw = text.strip().replace("-", ":")
    if ":" not in raw:
        if len(raw) != 12:
            raise ValueError("BSSID must be 12 hex digits or six octets")
        raw = ":".join(raw[i : i + 2] for i in range(0, 12, 2))
    parts = raw.split(":")
    if len(parts) != 6:
        raise ValueError("BSSID needs six octets")
    return bytes(int(part, 16) for part in parts)


def parse_ipv4(text: str) -> str:
    addr = ipaddress.IPv4Address(text)
    return str(addr)


def _crc8_table() -> tuple[int, ...]:
    table: list[int] = []
    for index in range(256):
        value = index
        for _ in range(8):
            if value & 1:
                value = (value >> 1) ^ CRC8_POLY
            else:
                value >>= 1
        table.append(value & 0xFFFF)
    return tuple(table)


CRC8_TABLE = _crc8_table()


def crc8(data: bytes | Sequence[int]) -> int:
    """ggesptouchlib CRC8. getValue is the low 8 bits."""
    value = 0
    for item in data:
        byte = item & 0xFF
        mixed = CRC8_TABLE[(byte ^ value) & 255] ^ (value << 8)
        value = _java_short(mixed)
    return value & 255


def split_uint8_to_2bytes(value: int) -> tuple[int, int]:
    """Nibble-split of Integer.toHexString(value), 0..255."""
    if value < 0 or value > 255:
        raise ValueError("splitUint8To2bytes out of boundary")
    hex_s = format(value, "x")
    if len(hex_s) > 1:
        return int(hex_s[0], 16), int(hex_s[1], 16)
    return 0, int(hex_s[0], 16)


def combine_2bytes_to_one(high: int, low: int) -> int:
    if high < 0 or high > 15 or low < 0 or low > 15:
        raise ValueError("combine2bytesToOne out of boundary")
    return ((high << 4) | low) & 0xFF


def combine_2bytes_to_u16(high: int, low: int) -> int:
    return ((high & 0xFF) << 8) | (low & 0xFF)


def data_code_bytes(datum: int, index: int) -> bytes:
    """Six-byte DataCode.getBytes() for one datum and sequence index."""
    if index > ESPT_INDEX_MAX:
        raise ValueError("ESP-TOUCH index > 127")
    datum &= 0xFF
    data_high, data_low = split_uint8_to_2bytes(datum)
    crc_val = crc8(bytes((datum, index & 0xFF)))
    crc_high, crc_low = split_uint8_to_2bytes(crc_val)
    return bytes(
        (
            0,
            combine_2bytes_to_one(crc_high, data_high),
            1,
            index & 0xFF,
            0,
            combine_2bytes_to_one(crc_low, data_low),
        )
    )


def datum_code_bytes(
    ssid: bytes,
    bssid: bytes,
    password: bytes,
    local_ip: str,
    hidden: bool,
) -> bytes:
    """Concatenated DataCode records (DatumCode.getBytes())."""
    pwd_len = len(password)
    crc_ssid = crc8(ssid)
    crc_bssid = crc8(bssid)
    ssid_len = len(ssid)
    ip_octets = [int(part) for part in parse_ipv4(local_ip).split(".")]
    ip_len = len(ip_octets)
    extra_head = ip_len + 5 + pwd_len
    total = ssid_len + extra_head
    bssid_seq_base = total if hidden else extra_head

    records: list[bytes] = [
        data_code_bytes(total, 0),
        data_code_bytes(pwd_len, 1),
        data_code_bytes(crc_ssid, 2),
        data_code_bytes(crc_bssid, 3),
    ]
    xor_v = crc_bssid ^ (crc_ssid ^ (total ^ pwd_len))
    xor_v &= 0xFF
    for offset, octet in enumerate(ip_octets):
        records.append(data_code_bytes(octet, offset + 5))
        xor_v = (xor_v ^ octet) & 0xFF
    for offset, byte in enumerate(password):
        records.append(data_code_bytes(byte, offset + 5 + ip_len))
        xor_v = (xor_v ^ byte) & 0xFF
    for byte in ssid:
        xor_v = (xor_v ^ byte) & 0xFF
    if hidden:
        for offset, byte in enumerate(ssid):
            records.append(data_code_bytes(byte, offset + 5 + ip_len + pwd_len))
    records.insert(4, data_code_bytes(xor_v, 4))
    insert_at = 5
    for offset, byte in enumerate(bssid):
        rec = data_code_bytes(byte, bssid_seq_base + offset)
        if insert_at >= len(records):
            records.append(rec)
        else:
            records.insert(insert_at, rec)
        insert_at += 4
    return b"".join(records)


def datum_u8s(data_bytes: bytes) -> list[int]:
    """U16 of each pair plus EXTRA_LEN 40 (DatumCode.getU8s)."""
    if len(data_bytes) % 2:
        raise ValueError("DataCode stream length must be even")
    out: list[int] = []
    for index in range(len(data_bytes) // 2):
        pair = combine_2bytes_to_u16(data_bytes[index * 2], data_bytes[index * 2 + 1])
        out.append(pair + ESPT_EXTRA_LEN)
    return out


def spec_bytes(length: int) -> bytes:
    if length < 0:
        raise ValueError("UDP length must be >= 0")
    return bytes((ESPT_SPEC_BYTE,)) * length


def esptouch_guide() -> list[int]:
    return list(GUIDE_U8S)


def esptouch_data_u8s(
    ssid: str,
    password: str,
    bssid: str,
    local_ip: str,
    *,
    hidden: bool = False,
) -> list[int]:
    data = datum_code_bytes(
        _utf8(ssid),
        parse_bssid(bssid),
        _utf8(password) if password else b"",
        local_ip,
        hidden,
    )
    return datum_u8s(data)


def _print_esptouch(guide: Sequence[int], data: Sequence[int], dest: str) -> None:
    print(f"guide_u8s: {' '.join(str(v) for v in guide)}")
    print(f"data_u8s: {' '.join(str(v) for v in data)}")
    print(f"data_count: {len(data)}")
    print(f"dest: {dest}")
    print(f"udp: {ESPT_TARGET_PORT}")
    print(f"listen: {ESPT_LISTEN_PORT} (app; this helper does not bind)")
    print(f"guide_interval_ms: {ESPT_GUIDE_INTERVAL_MS}")
    print(f"data_interval_ms: {ESPT_DATA_INTERVAL_MS}")
    print(f"guide_timeout_ms: {ESPT_GUIDE_TIMEOUT_MS}")
    print(f"data_timeout_ms: {ESPT_DATA_TIMEOUT_MS}")
    print(f"send_window_ms: {ESPT_SEND_WINDOW_MS}")
    print(f"spec_byte: {ESPT_SPEC_BYTE:02x}")


def self_test() -> None:
    high, low = split_uint8_to_2bytes(20)
    if (high, low) != VEC_SPLIT_20:
        raise ValueError(f"splitUint8 20 got {(high, low)}")
    if combine_2bytes_to_one(1, 4) != 20:
        raise ValueError("combine2bytesToOne 1,4")
    if crc8(b"") != 0:
        raise ValueError("crc8 empty")

    if esptouch_guide() != list(GUIDE_U8S):
        raise ValueError("guide")
    data = esptouch_data_u8s(TEST_SSID, TEST_PASS, TEST_BSSID, TEST_IP, hidden=False)
    if data != list(VEC_ESPT_DATA):
        raise ValueError(f"esptouch data {data}")
    if any(value < ESPT_EXTRA_LEN for value in data):
        raise ValueError("esptouch u8 below EXTRA_LEN")
    rec = data_code_bytes(20, 0)
    if len(rec) != 6 or rec[0] != 0 or rec[2] != 1 or rec[4] != 0:
        raise ValueError("DataCode shape")
    hidden = esptouch_data_u8s(TEST_SSID, TEST_PASS, TEST_BSSID, TEST_IP, hidden=True)
    if len(hidden) <= len(data):
        raise ValueError("hidden SSID should add data codes")
    parse_bssid(PLACEHOLDER_MAC)
    parse_ipv4(TEST_IP)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_esp = sub.add_parser("esptouch", help="UDP-length shout (print only)")
    p_esp.add_argument("--ssid", required=True)
    p_esp.add_argument("--password", required=True)
    p_esp.add_argument("--bssid", default=PLACEHOLDER_MAC)
    p_esp.add_argument(
        "--local-ip", default=TEST_IP, help="phone IPv4 (TEST-NET default)"
    )
    p_esp.add_argument(
        "--hidden", action="store_true", help="include SSID bytes in DatumCode"
    )
    p_esp.add_argument(
        "--multicast",
        action="store_true",
        help="print dest 234.1.1.1 instead of 255.255.255.255",
    )
    sub.add_parser("self-test", help="check vectors; prints ok")
    args = parser.parse_args()

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0

    dest = "234.1.1.1" if args.multicast else "255.255.255.255"
    guide = esptouch_guide()
    data = esptouch_data_u8s(
        args.ssid,
        args.password,
        args.bssid,
        args.local_ip,
        hidden=args.hidden,
    )
    _print_esptouch(guide, data, dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
