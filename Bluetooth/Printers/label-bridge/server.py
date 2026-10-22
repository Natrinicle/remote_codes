"""LAN HTTP + IPP/AirPrint front end. Phones upload here; the PC talks BLE."""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ipp import (
    JOB_COMPLETED,
    OP_GET_JOBS,
    OP_GET_PRINTER_ATTRIBUTES,
    OP_PRINT_JOB,
    OP_VALIDATE_JOB,
    STATUS_OK,
    STATUS_OP_UNSUPPORTED,
    STATUS_SERVER,
    TAG_ENUM,
    TAG_INTEGER,
    TAG_URI,
    IppAttr,
    decode_ipp,
    encode_ipp,
    printer_attributes,
    response,
)
from jobs import build_job
from profiles import Profile
from raster import raster_image
from transport import TransportError, send_ble, send_spp
from urf import decode_urf

log = logging.getLogger("labelbridge")

FORMATS = (
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/urf",
    "application/octet-stream",
)
WEB_DIR = Path(__file__).resolve().parent / "web"
DEFAULT_PORT = 8631


class Bridge:
    def __init__(
        self,
        profile: Profile,
        *,
        address: str | None = None,
        spp_port: str | None = None,
        fit: str = "contain",
        dither: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.profile = profile
        self.address = address
        self.spp_port = spp_port
        self.fit = fit
        self.dither = dither
        self.dry_run = dry_run
        self.lock = asyncio.Lock()
        self.job_id = 0
        self.uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"label-bridge:{profile.key}"))

    def printer_uri(self, host: str, port: int) -> str:
        return f"ipp://{host}:{port}/ipp/print"

    async def print_bytes(self, blob: bytes, copies: int = 1) -> str:
        bitmap = _raster_blob(blob, self.profile, self.fit, self.dither)
        frames = build_job(self.profile, bitmap, copies=copies)
        async with self.lock:
            self.job_id += 1
            job = self.job_id
            if self.dry_run:
                log.info("dry-run job %s: %s frames", job, len(frames))
                return f"dry-run job {job}: {len(frames)} frames"
            await _send(self.profile, frames, self.address, self.spp_port)
        return f"job {job} sent ({bitmap.width}x{bitmap.height})"


def _raster_blob(blob: bytes, profile: Profile, fit: str, dither: bool):
    if blob[:8] == b"UNIRAST\x00":
        page = decode_urf(blob)[0]
        from raster import from_rgb

        return from_rgb(
            page.rgb,
            page.width,
            page.height,
            dpi=profile.dpi,
            width_dots=profile.width_dots,
            max_height=profile.default_height_dots,
            fit=fit,
            dither=dither,
        )
    return raster_image(
        blob,
        width_dots=profile.width_dots,
        max_height=profile.max_height_dots
        if fit == "width"
        else profile.default_height_dots,
        dpi=profile.dpi,
        fit=fit,
        dither=dither,
    )


async def _send(
    profile: Profile,
    frames: list[bytes],
    address: str | None,
    spp_port: str | None,
) -> None:
    if profile.transport == "ble-gatt":
        if not address:
            raise TransportError("BLE printer address is required")
        await send_ble(profile, address, frames)
        return
    await asyncio.to_thread(
        send_spp, profile, address=address, port=spp_port, frames=frames
    )


def _lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _mdns_properties(bridge: Bridge, host: str, port: int) -> dict[bytes, bytes]:
    uri_path = "ipp/print"
    return {
        b"txtvers": b"1",
        b"qtotal": b"1",
        b"rp": uri_path.encode(),
        b"ty": bridge.profile.title.encode(),
        b"product": f"({bridge.profile.title})".encode(),
        b"pdl": b"application/pdf,image/jpeg,image/png,image/urf",
        b"URF": f"V1.4,W8,SRGB24,RS{bridge.profile.dpi},CP1,DM3,PQ4".encode(),
        b"Color": b"F",
        b"Duplex": b"F",
        b"Copies": b"T",
        b"kind": b"label,document,photo",
        b"PaperMax": b"legal-A4",
        b"note": b"label-bridge LAN",
        b"priority": b"50",
        b"air": b"none",
        b"usb_MFG": bridge.profile.make.encode(),
        b"usb_MDL": bridge.profile.model.encode(),
        b"UUID": bridge.uuid.encode(),
        b"adminurl": f"http://{host}:{port}/".encode(),
        b"printer-type": b"0x8090",
        b"printer-state": b"3",
        b"Transparent": b"T",
        b"Binary": b"T",
    }


def start_mdns(bridge: Bridge, host: str, port: int):
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        log.warning("zeroconf missing; AirPrint discovery off")
        return None, None
    zc = Zeroconf()
    instance = bridge.profile.title
    info = ServiceInfo(
        "_ipp._tcp.local.",
        f"{instance}._ipp._tcp.local.",
        parsed_addresses=[host],
        port=port,
        properties=_mdns_properties(bridge, host, port),
        server=f"{socket.gethostname().split('.')[0]}.local.",
    )
    zc.register_service(info)
    try:
        from zeroconf import DNSPointer
        from zeroconf.const import _CLASS_IN, _DNS_OTHER_TTL, _TYPE_PTR

        ptr = DNSPointer(
            "_universal._sub._ipp._tcp.local.",
            _TYPE_PTR,
            _CLASS_IN,
            _DNS_OTHER_TTL,
            info.name,
        )
        zc.registry.async_add_records([ptr])
    except (ImportError, AttributeError, TypeError, RuntimeError):
        log.debug("AirPrint _universal PTR not registered")
    log.info("mDNS _ipp._tcp %s on %s:%s", instance, host, port)
    return zc, info


async def _read_headers(
    reader: asyncio.StreamReader,
) -> tuple[str, dict[str, str], bytes]:
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = await reader.read(1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > 64_000:
            raise ValueError("headers too large")
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1", "replace").split("\r\n")
    request = lines[0] if lines else ""
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return request, headers, rest


async def _read_body(
    reader: asyncio.StreamReader,
    headers: dict[str, str],
    rest: bytes,
    writer: asyncio.StreamWriter,
) -> bytes:
    if headers.get("expect", "").lower() == "100-continue":
        writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
        await writer.drain()
    length = int(headers.get("content-length", "0") or 0)
    body = rest
    while len(body) < length:
        chunk = await reader.read(length - len(body))
        if not chunk:
            break
        body += chunk
    return body[:length] if length else body


def _http(status: int, reason: str, body: bytes, content_type: str) -> bytes:
    headers = [
        f"HTTP/1.1 {status} {reason}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
        "Connection: close",
        "Cache-Control: no-store",
    ]
    return ("\r\n".join(headers) + "\r\n\r\n").encode("ascii") + body


def _multipart_file(body: bytes, content_type: str) -> bytes | None:
    if "multipart/form-data" not in content_type:
        return None
    # BytesParser() returns email.message.Message, which has no iter_parts.
    # EmailPolicy yields EmailMessage (phone FormData / curl -F).
    msg = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("ascii", "replace") + b"\r\n\r\n" + body
    )
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name in ("file", "document", "job"):
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes) and payload:
                return payload
    return None


async def _handle(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    bridge: Bridge,
    bind_host: str,
    port: int,
) -> None:
    try:
        request, headers, rest = await _read_headers(reader)
        parts = request.split()
        method = parts[0] if parts else "GET"
        path = parts[1] if len(parts) > 1 else "/"
        body = await _read_body(reader, headers, rest, writer)
        parsed = urlparse(path)
        route = parsed.path
        peer = writer.get_extra_info("peername")
        log.info("%s %s from %s", method, route, peer)
        if method == "GET" and route in ("/", "/index.html"):
            html = (WEB_DIR / "index.html").read_bytes()
            writer.write(_http(200, "OK", html, "text/html; charset=utf-8"))
        elif method == "GET" and route == "/healthz":
            writer.write(_http(200, "OK", b"ok\n", "text/plain"))
        elif method == "GET" and route == "/status":
            payload = (
                f"printer={bridge.profile.key}\n"
                f"title={bridge.profile.title}\n"
                f"address={bridge.address or ''}\n"
                f"dry_run={bridge.dry_run}\n"
            ).encode()
            writer.write(_http(200, "OK", payload, "text/plain; charset=utf-8"))
        elif method == "POST" and route in ("/print", "/api/print"):
            await _handle_upload(writer, bridge, body, headers, parsed)
        elif method in ("POST", "GET") and route.startswith(("/ipp/", "/printers/")):
            await _handle_ipp(writer, bridge, body, bind_host, port)
        else:
            writer.write(_http(404, "Not Found", b"not found\n", "text/plain"))
        await writer.drain()
    except Exception as exc:
        log.exception("request failed")
        try:
            writer.write(_http(500, "Error", str(exc).encode()[:200], "text/plain"))
            await writer.drain()
        except OSError:
            log.debug("could not write 500 to client")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            log.debug("client already closed")


async def _handle_upload(
    writer: asyncio.StreamWriter,
    bridge: Bridge,
    body: bytes,
    headers: dict[str, str],
    parsed,
) -> None:
    ctype = headers.get("content-type", "")
    blob = _multipart_file(body, ctype) or body
    qs = parse_qs(parsed.query)
    copies = int((qs.get("copies") or ["1"])[0])
    copies = max(1, min(copies, 5))
    if not blob:
        writer.write(_http(400, "Bad Request", b"empty job\n", "text/plain"))
        return
    try:
        msg = await bridge.print_bytes(blob, copies=copies)
        writer.write(_http(200, "OK", (msg + "\n").encode(), "text/plain"))
    except Exception as exc:
        log.exception("print failed")
        writer.write(_http(500, "Error", (f"{exc}\n").encode()[:400], "text/plain"))


async def _handle_ipp(
    writer: asyncio.StreamWriter,
    bridge: Bridge,
    body: bytes,
    host: str,
    port: int,
) -> None:
    if not body:
        writer.write(_http(400, "Bad Request", b"empty IPP\n", "text/plain"))
        return
    try:
        req = decode_ipp(body)
    except ValueError as exc:
        writer.write(_http(400, "Bad Request", str(exc).encode(), "text/plain"))
        return
    uri = bridge.printer_uri(host, port)
    printer = printer_attributes(
        name=bridge.profile.title,
        make=bridge.profile.make,
        model=bridge.profile.model,
        uri=uri,
        uuid=f"urn:uuid:{bridge.uuid}",
        state=3,
        media=bridge.profile.media,
        dpi=bridge.profile.dpi,
        formats=FORMATS,
    )
    if req.code in (OP_GET_PRINTER_ATTRIBUTES, OP_VALIDATE_JOB, OP_GET_JOBS):
        reply = response(req, status=STATUS_OK, printer=printer)
    elif req.code == OP_PRINT_JOB:
        try:
            copies = int(req.attrs().get("copies") or 1)
            copies = max(1, min(copies, 5))
            await bridge.print_bytes(req.data, copies=copies)
            job_id = bridge.job_id
            job = [
                IppAttr(TAG_INTEGER, "job-id", job_id),
                IppAttr(TAG_URI, "job-uri", f"{uri}/job/{job_id}"),
                IppAttr(TAG_ENUM, "job-state", JOB_COMPLETED),
            ]
            reply = response(req, status=STATUS_OK, job=job, printer=printer)
        except Exception:
            log.exception("IPP Print-Job failed")
            reply = response(req, status=STATUS_SERVER, printer=printer)
    else:
        reply = response(req, status=STATUS_OP_UNSUPPORTED, printer=printer)
    payload = encode_ipp(reply)
    writer.write(_http(200, "OK", payload, "application/ipp"))


async def serve(
    bridge: Bridge,
    *,
    bind: str = "0.0.0.0",
    port: int = DEFAULT_PORT,
    mdns: bool = True,
) -> None:
    lan = _lan_ip() if bind in ("0.0.0.0", "::") else bind
    zc = info = None
    if mdns:
        zc, info = start_mdns(bridge, lan, port)

    async def handler(reader, writer):
        await _handle(reader, writer, bridge, lan, port)

    server = await asyncio.start_server(handler, bind, port)
    socks = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    log.info(
        "listening %s  web http://%s:%s/  ipp ipp://%s:%s/ipp/print",
        socks,
        lan,
        port,
        lan,
        port,
    )
    try:
        async with server:
            await server.serve_forever()
    finally:
        if zc is not None and info is not None:
            zc.unregister_service(info)
            zc.close()


def self_test() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 16
    boundary = "----LabelBridgeTest"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="t.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + png
        + f"\r\n--{boundary}--\r\n".encode()
    )
    ctype = f"multipart/form-data; boundary={boundary}"
    got = _multipart_file(body, ctype)
    assert got == png
    assert _multipart_file(png, "image/png") is None
