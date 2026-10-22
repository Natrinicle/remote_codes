#!/usr/bin/env python3
"""LAN print bridge for NIIMBOT B1, Nelko P21, and Aimotech D30.

Helpers under Bluetooth/Printers/*/encode_*.py print payloads. This
client rasters a page, encodes those payloads, and (unless --dry-run)
writes them over BLE GATT or classic SPP.

    ./labelbridge.py self-test
    ./labelbridge.py scan
    ./labelbridge.py print label.png --model nelko-p21 --address AA:BB:...
    ./labelbridge.py serve --model nelko-p21 --address AA:BB:...
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ipp import self_test as ipp_self_test
from jobs import self_test as jobs_self_test
from profiles import PROFILES, get_profile, match_ble_name
from raster import raster_image
from raster import self_test as raster_self_test
from server import DEFAULT_PORT, Bridge, serve
from server import self_test as server_self_test
from transport import (
    list_serial_ports,
    scan_ble,
)
from transport import (
    self_test as transport_self_test,
)
from urf import self_test as urf_self_test

log = logging.getLogger("labelbridge")


def _setup_log(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def cmd_self_test() -> int:
    raster_self_test()
    urf_self_test()
    ipp_self_test()
    jobs_self_test()
    transport_self_test()
    server_self_test()
    print("ok")
    return 0


async def cmd_scan() -> int:
    devices = await scan_ble()
    if not devices:
        print("no BLE devices (printer powered and advertising?)")
        return 1
    for address, name in devices:
        keys = match_ble_name(name)
        tag = ",".join(keys) if keys else "-"
        print(f"{address}\t{name or '?'}\t{tag}")
    ports = list_serial_ports()
    for port in ports:
        print(f"{port}\t(serial)\tspp")
    return 0


async def cmd_print(args: argparse.Namespace) -> int:
    profile = get_profile(args.model)
    path = Path(args.file)
    blob = path.read_bytes()
    bitmap = raster_image(
        blob,
        width_dots=profile.width_dots,
        max_height=profile.max_height_dots
        if args.fit == "width"
        else profile.default_height_dots,
        dpi=profile.dpi,
        fit=args.fit,
        dither=not args.no_dither,
    )
    bridge = Bridge(
        profile,
        address=args.address,
        spp_port=args.spp_port,
        fit=args.fit,
        dither=not args.no_dither,
        dry_run=args.dry_run,
    )
    msg = await bridge.print_bytes(blob, copies=args.copies)
    print(msg)
    print(f"raster {bitmap.width}x{bitmap.height} @ {bitmap.dpi} dpi")
    return 0


async def cmd_serve(args: argparse.Namespace) -> int:
    profile = get_profile(args.model)
    bridge = Bridge(
        profile,
        address=args.address,
        spp_port=args.spp_port,
        fit=args.fit,
        dither=not args.no_dither,
        dry_run=args.dry_run,
    )
    await serve(bridge, bind=args.bind, port=args.port, mdns=not args.no_mdns)
    return 0


def _add_printer_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--model",
        required=True,
        choices=sorted(PROFILES),
        help="niimbot-b1 | nelko-p21 | aimotech-d30",
    )
    p.add_argument("--address", help="BLE or Bluetooth MAC")
    p.add_argument("--spp-port", help="Windows COM port for Aimotech SPP")
    p.add_argument(
        "--fit",
        choices=("contain", "width", "stretch"),
        default="contain",
        help="contain = whole page on one label (AirPrint default)",
    )
    p.add_argument("--no-dither", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--copies", type=int, default=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    sub.add_parser("scan")
    p_print = sub.add_parser("print")
    p_print.add_argument("file")
    _add_printer_args(p_print)
    p_serve = sub.add_parser("serve")
    _add_printer_args(p_serve)
    p_serve.add_argument("--bind", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--no-mdns", action="store_true")
    args = parser.parse_args(argv)
    _setup_log(args.verbose)
    if args.cmd == "self-test":
        return cmd_self_test()
    if args.cmd == "scan":
        return asyncio.run(cmd_scan())
    if args.cmd == "print":
        if not args.dry_run and not args.address and not args.spp_port:
            parser.error("print needs --address, --spp-port, or --dry-run")
        return asyncio.run(cmd_print(args))
    if args.cmd == "serve":
        if not args.dry_run and not args.address and not args.spp_port:
            parser.error("serve needs --address, --spp-port, or --dry-run")
        return asyncio.run(cmd_serve(args))
    return 2


if __name__ == "__main__":
    sys.exit(main())
