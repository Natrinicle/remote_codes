"""BLE GATT and classic SPP transports. Optional deps load lazily."""

from __future__ import annotations

import asyncio
import logging
import socket
import sys
import time
from collections.abc import Awaitable, Callable

from profiles import Profile

log = logging.getLogger("labelbridge")


class TransportError(RuntimeError):
    pass


def _chunk(data: bytes, size: int) -> list[bytes]:
    if size < 1:
        return [data]
    return [data[i : i + size] for i in range(0, len(data), size)]


def bundle_frames(frames: list[bytes], limit: int) -> list[bytes]:
    if limit < 1:
        return list(frames)
    out: list[bytes] = []
    buf = bytearray()
    for frame in frames:
        if len(frame) > limit:
            if buf:
                out.append(bytes(buf))
                buf.clear()
            out.extend(_chunk(frame, limit))
            continue
        if buf and len(buf) + len(frame) > limit:
            out.append(bytes(buf))
            buf.clear()
        buf.extend(frame)
    if buf:
        out.append(bytes(buf))
    return out


async def scan_ble(timeout: float = 6.0) -> list[tuple[str, str]]:
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise TransportError("pip install bleak") from exc
    found: list[tuple[str, str]] = []
    devices = await BleakScanner.discover(timeout=timeout)
    for dev in devices:
        name = dev.name or ""
        found.append((dev.address, name))
    return found


async def send_ble(
    profile: Profile,
    address: str,
    frames: list[bytes],
    *,
    on_notify: Callable[[bytes], Awaitable[None] | None] | None = None,
) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:
        raise TransportError("pip install bleak") from exc
    if not profile.service or not profile.write_char:
        raise TransportError(f"{profile.key} has no GATT table")
    log.info("BLE %s %s: %s frames", profile.key, address, len(frames))
    async with BleakClient(address) as client:
        mtu = 23
        try:
            mtu = int(client.mtu_size)
        except (AttributeError, TypeError, ValueError):
            log.debug("BLE MTU unknown, using 23")
        limit = min(profile.bundle, max(20, mtu - 3))
        writes = bundle_frames(frames, limit)
        log.info("BLE MTU %s write %s B (%s writes)", mtu, limit, len(writes))
        if profile.notify_char:

            def _cb(_handle: int, data: bytearray) -> None:
                if not on_notify:
                    return
                result = on_notify(bytes(data))
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)

            await client.start_notify(profile.notify_char, _cb)
        for chunk in writes:
            await client.write_gatt_char(profile.write_char, chunk, response=False)
            await asyncio.sleep(profile.pace_s)
        await asyncio.sleep(0.3)


def _rfcomm_connect(address: str, channel: int = 1) -> socket.socket:
    if sys.platform == "win32":
        proto = getattr(socket, "BTPROTO_RFCOMM", 3)
        family = getattr(socket, "AF_BTH", 32)
        sock = socket.socket(family, socket.SOCK_STREAM, proto)
        sock.settimeout(15)
        sock.connect((address, channel))
        return sock
    if not hasattr(socket, "AF_BLUETOOTH"):
        raise TransportError("this Python build has no Bluetooth sockets")
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(15)
    sock.connect((address, channel))
    return sock


def send_spp(
    profile: Profile,
    *,
    address: str | None = None,
    port: str | None = None,
    frames: list[bytes],
) -> None:
    payload = b"".join(frames)
    chunks = _chunk(payload, profile.bundle)
    if port:
        try:
            import serial
        except ImportError as exc:
            raise TransportError("pip install pyserial") from exc
        log.info("SPP %s serial %s: %s bytes", profile.key, port, len(payload))
        with serial.Serial(port, 115200, timeout=2) as ser:
            for chunk in chunks:
                ser.write(chunk)
                time.sleep(profile.pace_s)
            ser.flush()
        return
    if not address:
        raise TransportError("SPP needs --address or --spp-port")
    log.info("SPP %s RFCOMM %s: %s bytes", profile.key, address, len(payload))
    sock = _rfcomm_connect(address)
    try:
        for chunk in chunks:
            sock.sendall(chunk)
            time.sleep(profile.pace_s)
    finally:
        sock.close()


def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [p.device for p in list_ports.comports()]


def self_test() -> None:
    frames = [b"\x01\x02", b"\x03", bytes(200)]
    bundled = bundle_frames(frames, 50)
    assert bundled[0] == b"\x01\x02\x03"
    assert all(len(part) <= 50 for part in bundled)
