#!/usr/bin/env python3
"""Victron VE.Direct checksum helper.

Text protocol is 19200 8N1 ASCII `key\\tvalue` lines, block ending in
`Checksum\\t` plus a binary checksum byte so the whole block sums to 0.
HEX protocol is `:` + hex payload + two hex checksum digits + CR.
HEX checksum is the two's complement of the sum of the payload bytes.

Example:
    ./encode_vedirect.py checksum 7f00
    ./encode_vedirect.py self-test
"""

from __future__ import annotations

import argparse


def hex_checksum(payload: bytes) -> str:
    return f"{(-sum(payload)) & 0xFF:02X}"


def text_sum(block: bytes) -> int:
    return sum(block) & 0xFF


def self_test() -> None:
    assert hex_checksum(b"\x01\x02") == "FD"
    filler = bytes(range(256))
    assert text_sum(filler + bytes(((256 - text_sum(filler)) & 0xFF,))) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_sum = sub.add_parser("checksum", help="HEX-protocol checksum of payload")
    p_sum.add_argument("hex")
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "checksum":
        print(hex_checksum(bytes.fromhex(args.hex.replace(" ", ""))))
    elif args.cmd == "self-test":
        self_test()
        print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
