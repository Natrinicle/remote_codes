#!/usr/bin/env python3
"""Build Flipper Zero raw IR for the Carrier Air V 36-bit protocol.

The captured remote is state-based: every button press sends the full
climate state (mode + fan + setpoint + power), not a one-shot command.
Flipper files in this folder are real captures. This helper is for making
additional combinations once you understand the bit map in README.md.

Example:
    ./encode_air_v.py --name Cool_70_Auto --payload B335A26FC
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable

# Nominal timings from the Flipper captures. They also match
# IRremoteESP8266 CARRIER_AC40 constants (header 8402/4166, bit 547,
# one 1540, zero 497) within capture jitter. Inter-frame gap is ~20 ms
# like CARRIER_AC, not the 150 ms AC40 gap.
HDR_MARK = 8243
HDR_SPACE = 4156
BIT_MARK = 532
ONE_SPACE = 1529
ZERO_SPACE = 501
GAP = 20018
STOP_MARK = 532
FREQUENCY = 38000
DUTY_CYCLE = "0.330000"
NBITS = 36


def parse_payload(text: str) -> int:
    """Parse a 36-bit payload from hex, with or without spaces.

    Accepts ``B3 35 A2 AF C`` (last nibble) or ``B335A2AFC``.
    """
    hexstr = "".join(ch for ch in text.strip() if ch not in " \t:_-")
    if len(hexstr) == 9:
        value = int(hexstr, 16)
    elif len(hexstr) == 8:
        value = int(hexstr, 16) << 4
    else:
        raise ValueError(f"expected 9 hex digits (36 bits), got {hexstr!r}")
    if value.bit_length() > NBITS:
        raise ValueError(f"payload does not fit in {NBITS} bits: {hexstr}")
    return value


def bits_of(value: int) -> list[int]:
    return [(value >> (NBITS - 1 - i)) & 1 for i in range(NBITS)]


def invert36(value: int) -> int:
    return (~value) & ((1 << NBITS) - 1)


def frame_samples(value: int) -> list[int]:
    samples = [HDR_MARK, HDR_SPACE]
    for bit in bits_of(value):
        samples.append(BIT_MARK)
        samples.append(ONE_SPACE if bit else ZERO_SPACE)
    samples.append(STOP_MARK)
    return samples


def triple_frame(value: int) -> list[int]:
    """data + ~data + data, with GAP between frames (not after the last)."""
    frames = [
        frame_samples(value),
        frame_samples(invert36(value)),
        frame_samples(value),
    ]
    out: list[int] = []
    for i, frame in enumerate(frames):
        if i:
            out.append(GAP)
        out.extend(frame)
    return out


def flipper_block(name: str, value: int) -> str:
    data = " ".join(str(n) for n in triple_frame(value))
    hex_payload = f"{value:09X}"
    hex_pretty = f"{hex_payload[0:2]} {hex_payload[2:4]} {hex_payload[4:6]} {hex_payload[6:8]} {hex_payload[8]}"
    return "\n".join(
        [
            "#",
            f"# payload {hex_pretty}",
            f"name: {name}",
            "type: raw",
            f"frequency: {FREQUENCY}",
            f"duty_cycle: {DUTY_CYCLE}",
            f"data: {data}",
        ]
    )


def format_hex(value: int) -> str:
    h = f"{value:09X}"
    return f"{h[0:2]} {h[2:4]} {h[4:6]} {h[6:8]} {h[8]}"


KNOWN: dict[str, str] = {
    "Off": "B3 35 D2 AF C",
    "Cool_63_Auto": "B3 35 A0 6F C",
    "Cool_75_Auto": "B3 35 AE 6F C",
    "Cool_90_Auto": "B3 35 AF 6F C",
    "Cool_75_Low": "B3 35 AE EF C",
    "Cool_75_High": "B3 35 AE 9F C",
    "Dry_63_Auto": "B3 35 A0 AF C",
    "Dry_70_Auto": "B3 35 A2 AF C",
    "Dry_81_Auto": "B3 35 A5 AF C",
    "Dry_90_Auto": "B3 35 AF AF C",
    "Fan_Low": "B3 35 AF 5F E",
    "Fan_High": "B3 35 AF 3F E",
    "Furn_45_Auto": "B3 35 A6 8F E",
    "Furn_90_Auto": "B3 35 AF 8F C",
}

# Off-timer packet 1: Furnace 45 Auto with bit 17 set. Packet 2 is
# B3 35 7X F1 0 where X is the bit-reversed 4-bit hour (1-12).
OFF_TIMER_P1 = "B3 35 E6 8F E"


def reverse_nibble(n: int) -> int:
    return int(f"{n & 0xF:04b}"[::-1], 2)


def off_timer_payloads(hours: int) -> tuple[int, int]:
    if not 1 <= hours <= 12:
        raise ValueError(f"off timer hours must be 1-12, got {hours}")
    p1 = parse_payload(OFF_TIMER_P1)
    p2 = parse_payload(f"B3 35 7{reverse_nibble(hours):X} F1 0")
    return p1, p2


def flipper_block_two(name: str, first: int, second: int) -> str:
    data = " ".join(str(n) for n in triple_frame(first) + [GAP] + triple_frame(second))
    return "\n".join(
        [
            "#",
            f"# packet1 {format_hex(first)}  packet2 {format_hex(second)}",
            f"name: {name}",
            "type: raw",
            f"frequency: {FREQUENCY}",
            f"duty_cycle: {DUTY_CYCLE}",
            f"data: {data}",
        ]
    )


def iter_known() -> Iterable[tuple[str, int]]:
    for name, payload in KNOWN.items():
        yield name, parse_payload(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="Custom", help="Flipper button name")
    parser.add_argument(
        "--payload",
        help="36-bit hex payload, e.g. B335A26FC or 'B3 35 A2 6F C'",
    )
    parser.add_argument(
        "--list-known",
        action="store_true",
        help="Print captured single-packet payloads",
    )
    parser.add_argument(
        "--off-timer",
        type=int,
        metavar="HOURS",
        help="Emit a two-packet Off_Timer_NH block for 1-12 hours (Furnace 45 Auto)",
    )
    args = parser.parse_args()

    if args.list_known:
        for name, value in iter_known():
            print(f"{name:16}  {format_hex(value)}")
        print("Off_Timer_NH     two packets; use --off-timer N")
        return

    if args.off_timer is not None:
        p1, p2 = off_timer_payloads(args.off_timer)
        print(flipper_block_two(f"Off_Timer_{args.off_timer}H", p1, p2))
        return

    if not args.payload:
        parser.error("--payload is required unless --list-known or --off-timer is set")

    value = parse_payload(args.payload)
    print(flipper_block(args.name, value))


if __name__ == "__main__":
    main()
