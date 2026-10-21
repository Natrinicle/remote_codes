#!/usr/bin/env python3
"""Print Pylontech RS485 console commands (read-only).

Typical UART 115200 8N1. Send ASCII plus CR. Do not send togpro / setprt /
config from this helper.

Example:
    ./encode_pylontech.py help
    ./encode_pylontech.py pwr
    ./encode_pylontech.py bat
    ./encode_pylontech.py self-test
"""

from __future__ import annotations

import argparse

COMMANDS = {
    "help": "help",
    "pwr": "pwr",
    "bat": "bat",
}


def frame(command: str) -> bytes:
    return f"{command}\r".encode("ascii")


def self_test() -> None:
    assert frame("pwr") == b"pwr\r"
    assert frame("help").endswith(b"\r")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in COMMANDS:
        sub.add_parser(name)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0
    print(frame(COMMANDS[args.cmd]).hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
