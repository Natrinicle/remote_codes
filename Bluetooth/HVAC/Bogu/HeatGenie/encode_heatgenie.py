#!/usr/bin/env python3
"""Encode/decode HeatGenie (Bogu) BLE frames.

Wire temps are tenths of °C. App °F is trunc((320 + 1.8 * raw) / 10).
CRC-16-CCITT nibble table, init 0, matching the uni-app Ee() helper.

Example:
    ./encode_heatgenie.py auto
    ./encode_heatgenie.py vent
    ./encode_heatgenie.py decode aa09ffef000000f255107b0020033101db01...
"""

from __future__ import annotations

import argparse
import secrets
import sys

# CRC-16-CCITT nibble table from HeatGenie app-service.js Ee()
_CRC_NIBBLE = [
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
]

CMD_ON = 1
CMD_OFF = 2
CMD_CLEAR = 5
CMD_BLOW_ON = 9
DB0_DN_CMD = 97
DB0_DN_GET_REG_ADDR = 99
DB0_DN_GET_REG_VAL = 100
DB0_DN_AUTO_UPDATA = 101
DB0_DN_SHORT_PARA = 102
ADDR_TYPE_REG = 2
ADDR_TYPE_PARA = 3
SHORT_RUN_MODE = 0
SHORT_TARGET_TEMP = 1
SHORT_TARGET_GEAR = 2
RUN_MODE_AUTO = 0
RUN_MODE_MAN = 1
RUN_MODE_START_STOP = 2

# Advanced para byte (offset 4). App labels stroke volume as ML; hardware is µL/stroke.
VOLT_TYPES = ("12V", "24V", "AU")
PUMP_TYPES = ("16uL", "22uL", "28uL")
WATT_TYPES = ("2KW", "3KW", "5KW", "8KW")

RUN_MODE = {
    0: "reset",
    1: "ignite",
    2: "auto",
    3: "manual",
    4: "cooldown",
    5: "standby",
    6: "error",
    7: "pump",
    8: "vent",
    9: "start-stop",
}

# errorCode at status offset 20. E-10 locks during cooldown; wait for fan 0, then retry.
ERROR_CODES = {
    512: "E-10",
}


def crc16(data: bytes, n: int | None = None) -> int:
    """CRC over the first n bytes (default: all). Init 0."""
    if n is None:
        n = len(data)
    acc = 0
    for b in data[:n]:
        nib = (acc >> 12) & 65535
        acc = (acc << 4) & 65535
        acc ^= _CRC_NIBBLE[15 & ((nib & 65535) ^ (b >> 4))]
        nib = (acc & 65535) >> 12
        acc = (acc << 4) & 65535
        acc ^= _CRC_NIBBLE[15 & ((nib & 65535) ^ (15 & b))]
    return acc & 65535


def append_crc(payload: bytes) -> bytes:
    c = crc16(payload)
    return payload + bytes((c >> 8, c & 255))


def cmd_frame(cmd: int, a0: int, a1: int, a2: int) -> bytes:
    """8-byte heaterSendCmd: AA 00 CMD A0 A1 A2 CRC_HI CRC_LO."""
    body = bytes((0xAA, 0, cmd, a0, a1, a2))
    return append_crc(body)


def auto_updata(*, interval: int = 20) -> bytes:
    return cmd_frame(DB0_DN_AUTO_UPDATA, ADDR_TYPE_REG, interval, 30)


def get_para_addr() -> bytes:
    return cmd_frame(DB0_DN_GET_REG_ADDR, ADDR_TYPE_PARA, 0, 0)


def get_para_val() -> bytes:
    """Ask for paraInfoArea (short 243 / 0xF3), length code 15 as in the app."""
    return cmd_frame(DB0_DN_GET_REG_VAL, 243, 0, 15)


def set_run_mode_auto() -> bytes:
    """恒温 / constant-temp mode."""
    return cmd_frame(DB0_DN_SHORT_PARA, SHORT_RUN_MODE, 0, RUN_MODE_AUTO)


def set_target_temp_f(deg_f: int) -> bytes:
    """SHORT_TARGET_TEMP with unit flag 1 = °F. App range 50–104."""
    if not 50 <= deg_f <= 104:
        raise ValueError(f"aimTemp °F {deg_f} outside 50-104")
    return cmd_frame(DB0_DN_SHORT_PARA, SHORT_TARGET_TEMP, 1, deg_f)


def set_target_temp_c(deg_c: int) -> bytes:
    if not 10 <= deg_c <= 40:
        raise ValueError(f"aimTemp °C {deg_c} outside 10-40")
    return cmd_frame(DB0_DN_SHORT_PARA, SHORT_TARGET_TEMP, 0, deg_c)


def set_target_gear(gear: int) -> bytes:
    if not 1 <= gear <= 10:
        raise ValueError("gear 1-10")
    return cmd_frame(DB0_DN_SHORT_PARA, SHORT_TARGET_GEAR, 0, gear)


def decode_advanced_byte(raw: int) -> dict[str, object]:
    """Parse paraInfoArea offset-4 bitfield (store/index.js)."""
    run_mode = raw & 3
    watt_raw = (raw >> 2) & 3
    pump = (raw >> 4) & 3
    volt = (raw >> 6) & 3
    volt = min(2, volt)
    watt = watt_raw if watt_raw == 0 else watt_raw + 1
    watt = min(watt, 3)
    pump = min(pump, 2)
    return {
        "raw": raw,
        "run_mode": run_mode,
        "volt_index": volt,
        "volt": VOLT_TYPES[volt],
        "pump_index": pump,
        "pump": PUMP_TYPES[pump],
        "watt_index": watt,
        "watt": WATT_TYPES[watt],
    }


def pack_advanced_byte(
    *,
    volt_index: int,
    pump_index: int,
    old_byte: int,
    watt_index: int | None = None,
) -> int:
    """Keep low nibble (runMode + watt bits) unless watt_index is given.

    Physical ZM25-12V22ml → volt_index=0 (12V), pump_index=1 (22uL).
    Lying with 16uL while the pump is 22uL makes the ECU pulse more (worse flood).
    """
    low = old_byte & 0x0F
    if watt_index is not None:
        i = (watt_index & 3) << 2
        if i:
            i -= 1
        low = (i | (old_byte & 3)) & 0x0F
    return ((volt_index & 3) << 6) | ((pump_index & 3) << 4) | low


def send_raw_data(
    addr4: bytes, payload: bytes, random_byte: int | None = None
) -> bytes:
    """heaterSendRawData: AA, len/4-1, 0xFF, rand, addr4, payload, inner CRC, outer CRC."""
    if random_byte is None:
        random_byte = secrets.randbelow(255) + 1
    hdr = bytes(
        (
            0xAA,
            len(payload) // 4 - 1,
            255,
            random_byte,
            addr4[0],
            addr4[1],
            addr4[2],
            addr4[3],
        )
    )
    body = hdr + payload
    inner = crc16(payload)
    mid = body + bytes((inner >> 8, inner & 255))
    outer = crc16(mid, len(payload) + 10)
    return mid + bytes((outer >> 8, outer & 255))


def _cmd_key(a0: int, random_byte: int | None = None) -> bytes:
    """DB0_DN_CMD with A1 unique vs the last key (else ACK d=1 and the ECU ignores it)."""
    if random_byte is None:
        random_byte = secrets.randbelow(255) + 1
    return cmd_frame(DB0_DN_CMD, a0, random_byte, 0)


def power(on: bool, random_byte: int | None = None) -> bytes:
    """ON=1 / OFF=2. After E-10, wait until cooldown fan is 0 before a new ON."""
    return _cmd_key(CMD_ON if on else CMD_OFF, random_byte)


def vent(random_byte: int | None = None) -> bytes:
    """CMD_BLOW_ON=9 (mode 8). After E-10, wait for fan 0; if ignored, wait ~60s and retry."""
    return _cmd_key(CMD_BLOW_ON, random_byte)


def clear_error(random_byte: int | None = None) -> bytes:
    """CMD_CLEAR=5. Live 2026-10-02: no ACK while still in E-10."""
    return _cmd_key(CMD_CLEAR, random_byte)


def u16le(buf: bytes, offset: int) -> int:
    return buf[offset] | (buf[offset + 1] << 8)


def tenths_c_to_display(raw: int) -> tuple[int, int]:
    """App truncations: °C integer and °F integer."""
    c = raw // 10
    f = int((320 + 1.8 * raw) / 10)
    return c, f


def decode_status(frame: bytes) -> dict[str, object]:
    """Parse a 52-byte AA 09 FF … F2 register dump."""
    if len(frame) < 52 or frame[0] != 0xAA:
        raise ValueError(f"not a HeatGenie long frame (len={len(frame)})")
    if crc16(frame) != 0:
        raise ValueError("full-frame CRC is not zero")
    if frame[7] != 0xF2:
        raise ValueError(f"byte7={frame[7]:#x}, expected 0xF2 register dump")
    p = frame[8:48]
    cabin = u16le(p, 6)
    shell = u16le(p, 8)
    cabin_c, cabin_f = tenths_c_to_display(cabin)
    shell_c, shell_f = tenths_c_to_display(shell)
    alt_raw = u16le(p, 4)
    mode = p[0] & 15
    err = u16le(p, 20)
    return {
        "mode": mode,
        "mode_name": RUN_MODE.get(mode, "unknown"),
        "run_flags": p[1],
        "volts": u16le(p, 2) / 10,
        "altitude_raw": alt_raw,
        "altitude_m": alt_raw,
        "pressure_kpa_guess": alt_raw / 10,
        "cabin_raw": cabin,
        "cabin_c": cabin_c,
        "cabin_f": cabin_f,
        "shell_raw": shell,
        "shell_c": shell_c,
        "shell_f": shell_f,
        "oil_pump_hz": u16le(p, 10) / 10,
        "glow": u16le(p, 12) / 10,
        "fan": u16le(p, 14) / 10,
        "error": err,
        "error_name": ERROR_CODES.get(err, ""),
    }


def decode_para_frame(frame: bytes) -> dict[str, object]:
    """Parse a long notify with byte7 == 0xF3 (paraInfoArea)."""
    if len(frame) < 20 or frame[0] != 0xAA:
        raise ValueError("not a HeatGenie para frame")
    if crc16(frame) != 0:
        raise ValueError("full-frame CRC is not zero")
    if frame[7] != 0xF3:
        raise ValueError(f"byte7={frame[7]:#x}, expected 0xF3 para dump")
    payload = frame[8:-4]
    adv = payload[4] if len(payload) > 4 else None
    out: dict[str, object] = {"payload_hex": payload.hex(), "payload_len": len(payload)}
    if adv is not None:
        out.update(decode_advanced_byte(adv))
    return out


def _hex(data: bytes) -> str:
    return data.hex()


def self_test() -> None:
    """Known vectors from the live HeatGenie session."""
    assert auto_updata().hex() == "aa006502141ed095"
    assert auto_updata(interval=0).hex() == "aa006502001e1f22"
    assert power(True, 0).hex() == "aa00610100007f7c"
    # Live 2026-10-02 vent that left E-10 after cooldown (fan 0).
    assert vent(0x9C).hex() == "aa0061099c008b5b"
    dump = bytes.fromhex(
        "aa09ffef000000f255107b0020033101db01000000000000"
        "f87ff87f0000044090b87e5b0000a505044b000000000000bb851ab5"
    )
    info = decode_status(dump)
    assert info["mode_name"] == "standby"
    assert info["volts"] == 12.3
    assert info["cabin_c"] == 30
    assert info["cabin_f"] == 86
    assert info["error"] == 0
    assert info["error_name"] == ""
    packed = pack_advanced_byte(volt_index=0, pump_index=1, old_byte=0x50)
    assert packed & 0xF0 == 0x10  # 12V + 22uL
    assert decode_advanced_byte(packed)["pump"] == "22uL"
    assert decode_advanced_byte(packed)["volt"] == "12V"
    assert set_target_temp_f(70).hex() == "aa00660101463562"
    assert set_run_mode_auto().hex() == "aa00660000001961"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auto", help="AUTO_UPDATA start (2 s reports)")
    sub.add_parser("auto-stop", help="AUTO_UPDATA stop")
    p_on = sub.add_parser("on", help="power ON frame (writeNoResponse to 3A01)")
    p_on.add_argument(
        "--rand", type=int, default=None, help="A1 random 1-255 (default: fresh)"
    )
    p_off = sub.add_parser("off", help="power OFF frame")
    p_off.add_argument(
        "--rand", type=int, default=None, help="A1 random 1-255 (default: fresh)"
    )
    p_vent = sub.add_parser(
        "vent",
        help="CMD_BLOW_ON / mode 8 (unique A1; after E-10 wait until fan 0)",
    )
    p_vent.add_argument(
        "--rand", type=int, default=None, help="A1 random 1-255 (default: fresh)"
    )
    p_clear = sub.add_parser("clear", help="CMD_CLEAR (often no ACK during E-10)")
    p_clear.add_argument(
        "--rand", type=int, default=None, help="A1 random 1-255 (default: fresh)"
    )
    p_dec = sub.add_parser("decode", help="decode a 52-byte status hex dump")
    p_dec.add_argument("hex")
    sub.add_parser("self-test", help="check CRC and decode vectors")
    sub.add_parser("para-addr", help="GET_REG_ADDR paraInfoArea")
    sub.add_parser("para-val", help="GET_REG_VAL paraInfoArea")
    sub.add_parser("mode-auto", help="constant-temp / 恒温 mode")
    p_tf = sub.add_parser("temp-f", help="set aim temp in °F (50-104)")
    p_tf.add_argument("deg", type=int)
    p_decp = sub.add_parser("decode-para", help="decode a 0xF3 para dump")
    p_decp.add_argument("hex")
    args = parser.parse_args()
    if args.cmd == "auto":
        print(_hex(auto_updata(interval=20)))
    elif args.cmd == "auto-stop":
        print(_hex(auto_updata(interval=0)))
    elif args.cmd == "on":
        print(_hex(power(True, args.rand)))
    elif args.cmd == "off":
        print(_hex(power(False, args.rand)))
    elif args.cmd == "vent":
        print(_hex(vent(args.rand)))
    elif args.cmd == "clear":
        print(_hex(clear_error(args.rand)))
    elif args.cmd == "decode":
        raw = bytes.fromhex(args.hex.replace(" ", ""))
        info = decode_status(raw)
        for key, val in info.items():
            print(f"{key}: {val}")
    elif args.cmd == "self-test":
        self_test()
        print("ok")
    elif args.cmd == "para-addr":
        print(_hex(get_para_addr()))
    elif args.cmd == "para-val":
        print(_hex(get_para_val()))
    elif args.cmd == "mode-auto":
        print(_hex(set_run_mode_auto()))
    elif args.cmd == "temp-f":
        print(_hex(set_target_temp_f(args.deg)))
    elif args.cmd == "decode-para":
        raw = bytes.fromhex(args.hex.replace(" ", ""))
        info = decode_para_frame(raw)
        for key, val in info.items():
            print(f"{key}: {val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
