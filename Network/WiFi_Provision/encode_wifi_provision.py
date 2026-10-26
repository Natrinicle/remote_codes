#!/usr/bin/env python3
"""Route WiFi-provision encode jobs to a protocol backend.

Does not reimplement crypto. Prints dest / length maps only. Does not bind
sockets or send UDP. Do not pass a live SSID or PSK.

Add a backend later by dropping Network/WiFi_Provision/<Protocol>/encode_<protocol>.py
and one row in PROTOCOL_ALIASES / SKU_TO_BACKEND / BACKENDS below.

Example:
    ./encode_wifi_provision.py ogemray --ssid TestSSID --password TestPass
    ./encode_wifi_provision.py esptouch --ssid TestSSID --password TestPass
    ./encode_wifi_provision.py ap --ssid TestSSID --password TestPass
    ./encode_wifi_provision.py --sku 0396 --ssid TestSSID --password TestPass
    ./encode_wifi_provision.py --protocol esptouch --ssid TestSSID --password TestPass
    ./encode_wifi_provision.py self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent

# protocol alias / setupType -> backend key
PROTOCOL_ALIASES: dict[str, str] = {
    "ogemray": "ogemray",
    "smartconfig": "ogemray",
    "wifi": "ogemray",
    "esptouch": "esptouch",
    "esp_touch": "esptouch",
    "esptouchwifi": "esptouch",
}

SKU_TO_BACKEND: dict[str, str] = {
    "0396": "ogemray",
    "0385": "ogemray",
    "0384": "esptouch",
    "0397": "esptouch",
}

# backend key -> (relative script, default subcommand)
BACKENDS: dict[str, tuple[str, str]] = {
    "ogemray": ("Ogemray/encode_ogemray.py", "ogemray"),
    "esptouch": ("ESP_TOUCH/encode_esptouch.py", "esptouch"),
}

_MODULES: dict[str, ModuleType] = {}


def _norm(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def _load(backend: str) -> ModuleType:
    if backend in _MODULES:
        return _MODULES[backend]
    rel, _sub = BACKENDS[backend]
    path = HERE / rel
    spec = importlib.util.spec_from_file_location(f"wifi_provision_{backend}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODULES[backend] = mod
    return mod


def _invoke(mod: ModuleType, argv: list[str]) -> int:
    old = sys.argv[:]
    try:
        sys.argv = [str(Path(mod.__file__ or "encode")), *argv]
        result = mod.main()
        return 0 if result is None else int(result)
    finally:
        sys.argv = old


def self_test() -> None:
    _load("ogemray").self_test()
    _load("esptouch").self_test()


def _alias_backend(name: str) -> str | None:
    key = _norm(name)
    return PROTOCOL_ALIASES.get(key)


def _resolve(cmd: str | None, sku: str, protocol: str) -> tuple[str, str]:
    """Return (backend_key, backend_subcommand)."""
    votes: list[str] = []
    if cmd == "ap":
        if sku:
            mapped = SKU_TO_BACKEND.get(sku.strip())
            if mapped is None:
                raise ValueError(f"unknown SKU {sku}")
            if mapped != "ogemray":
                raise ValueError("ap is Ogemray Plan B (same blob, TCP transport)")
        if protocol:
            mapped = _alias_backend(protocol)
            if mapped is None:
                raise ValueError(f"unknown protocol {protocol}")
            if mapped != "ogemray":
                raise ValueError("ap is Ogemray Plan B (same blob, TCP transport)")
        return "ogemray", "ap"

    if cmd:
        mapped = _alias_backend(cmd)
        if mapped is None:
            raise ValueError(f"unknown command {cmd}")
        votes.append(mapped)
    if protocol:
        mapped = _alias_backend(protocol)
        if mapped is None:
            raise ValueError(f"unknown protocol {protocol}")
        votes.append(mapped)
    if sku:
        mapped = SKU_TO_BACKEND.get(sku.strip())
        if mapped is None:
            raise ValueError(f"unknown SKU {sku}")
        votes.append(mapped)
    if not votes:
        raise ValueError("need a command, --protocol, or --sku")
    if len(set(votes)) > 1:
        raise ValueError(f"conflicting backends: {votes}")
    backend = votes[0]
    return backend, BACKENDS[backend][1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cmd",
        nargs="?",
        help="ogemray | esptouch | ap | self-test | aliases (smartconfig, wifi, esp-touch)",
    )
    parser.add_argument(
        "--sku", default="", help="product SKU (0396, 0385, 0384, 0397)"
    )
    parser.add_argument(
        "--protocol",
        default="",
        help="protocol or setupType alias (ogemray, smartconfig, wifi, esptouch)",
    )
    parser.add_argument("--ssid", default="", help="UTF-8 SSID (use a test name)")
    parser.add_argument(
        "--password",
        default="",
        help="UTF-8 PSK (use a test value; this helper does not send)",
    )
    parser.add_argument("--user-number", type=int, default=0)
    parser.add_argument(
        "--token-hex",
        default="",
        help="32-byte token as hex when user-number is not 0",
    )
    parser.add_argument("--bssid", default="")
    parser.add_argument("--local-ip", default="")
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="ESP-TOUCH: include SSID bytes in DatumCode",
    )
    parser.add_argument(
        "--multicast",
        action="store_true",
        help="ESP-TOUCH: print dest 234.1.1.1 instead of 255.255.255.255",
    )
    args = parser.parse_args()

    if args.cmd == "self-test":
        self_test()
        print("ok")
        return 0

    try:
        backend, subcmd = _resolve(args.cmd, args.sku, args.protocol)
    except ValueError as exc:
        parser.error(str(exc))

    if not args.ssid or not args.password:
        parser.error("--ssid and --password are required (use test values)")

    mod = _load(backend)
    argv = [subcmd, "--ssid", args.ssid, "--password", args.password]
    if backend == "ogemray":
        argv += ["--user-number", str(args.user_number)]
        if args.token_hex:
            argv += ["--token-hex", args.token_hex]
    else:
        if args.bssid:
            argv += ["--bssid", args.bssid]
        if args.local_ip:
            argv += ["--local-ip", args.local_ip]
        if args.hidden:
            argv.append("--hidden")
        if args.multicast:
            argv.append("--multicast")
    return _invoke(mod, argv)


if __name__ == "__main__":
    raise SystemExit(main())
