"""Minimal IPP/1.1 codec for Print-Job and Get-Printer-Attributes.

RFC 8011 binary. Enough for AirPrint, Mopria, and Windows IPP.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TAG_UNSUPPORTED = 0x10
TAG_INTEGER = 0x21
TAG_BOOLEAN = 0x22
TAG_ENUM = 0x23
TAG_OCTET = 0x30
TAG_TEXT = 0x41
TAG_TEXTLANG = 0x42
TAG_KEYWORD = 0x44
TAG_URI = 0x45
TAG_CHARSET = 0x47
TAG_LANGUAGE = 0x48
TAG_MIME = 0x49
TAG_NAME = 0x4A

GRP_OPERATION = 0x01
GRP_JOB = 0x02
GRP_END = 0x03
GRP_PRINTER = 0x04
GRP_UNSUPPORTED = 0x05

OP_PRINT_JOB = 0x0002
OP_VALIDATE_JOB = 0x0004
OP_CREATE_JOB = 0x0005
OP_SEND_DOCUMENT = 0x0006
OP_CANCEL_JOB = 0x0008
OP_GET_JOB_ATTRIBUTES = 0x0009
OP_GET_JOBS = 0x000A
OP_GET_PRINTER_ATTRIBUTES = 0x000B
OP_CUPS_GET_PRINTERS = 0x4002

STATUS_OK = 0x0000
STATUS_CLIENT_BAD = 0x0400
STATUS_NOT_FOUND = 0x0406
STATUS_NOT_POSSIBLE = 0x0404
STATUS_SERVER = 0x0500
STATUS_OP_UNSUPPORTED = 0x0501

JOB_PENDING = 3
JOB_PROCESSING = 5
JOB_CANCELED = 7
JOB_ABORTED = 8
JOB_COMPLETED = 9

PRINTER_IDLE = 3
PRINTER_PROCESSING = 4
PRINTER_STOPPED = 5


@dataclass
class IppAttr:
    tag: int
    name: str
    value: object


@dataclass
class IppMessage:
    version: tuple[int, int] = (1, 1)
    code: int = 0
    request_id: int = 1
    groups: list[tuple[int, list[IppAttr]]] = field(default_factory=list)
    data: bytes = b""

    def attrs(self) -> dict[str, object]:
        found: dict[str, object] = {}
        for _tag, items in self.groups:
            for item in items:
                found.setdefault(item.name, item.value)
        return found


def _read_u16(buf: bytes, i: int) -> tuple[int, int]:
    return (buf[i] << 8) | buf[i + 1], i + 2


def _read_u32(buf: bytes, i: int) -> tuple[int, int]:
    return (
        (buf[i] << 24) | (buf[i + 1] << 16) | (buf[i + 2] << 8) | buf[i + 3],
        i + 4,
    )


def decode_ipp(buf: bytes) -> IppMessage:
    if len(buf) < 8:
        raise ValueError("IPP too short")
    version = (buf[0], buf[1])
    code = (buf[2] << 8) | buf[3]
    request_id = (buf[4] << 24) | (buf[5] << 16) | (buf[6] << 8) | buf[7]
    i = 8
    groups: list[tuple[int, list[IppAttr]]] = []
    current: list[IppAttr] | None = None
    last_name = ""
    while i < len(buf):
        tag = buf[i]
        i += 1
        if tag == GRP_END:
            break
        if tag in (GRP_OPERATION, GRP_JOB, GRP_PRINTER, GRP_UNSUPPORTED):
            current = []
            groups.append((tag, current))
            continue
        if current is None:
            raise ValueError("IPP attribute outside a group")
        if i + 2 > len(buf):
            raise ValueError("truncated IPP name length")
        nlen, i = _read_u16(buf, i)
        name = buf[i : i + nlen].decode("utf-8", "replace")
        i += nlen
        if not name:
            name = last_name
        else:
            last_name = name
        vlen, i = _read_u16(buf, i)
        raw = buf[i : i + vlen]
        i += vlen
        value: object
        if tag in (TAG_INTEGER, TAG_ENUM) and len(raw) == 4:
            value = int.from_bytes(raw, "big", signed=True)
        elif tag == TAG_BOOLEAN and len(raw) == 1:
            value = raw[0] != 0
        elif tag in (
            TAG_KEYWORD,
            TAG_URI,
            TAG_CHARSET,
            TAG_LANGUAGE,
            TAG_MIME,
            TAG_TEXT,
            TAG_TEXTLANG,
            TAG_NAME,
        ):
            value = raw.decode("utf-8", "replace")
        else:
            value = raw
        current.append(IppAttr(tag, name, value))
    return IppMessage(version, code, request_id, groups, buf[i:])


def _put_value(tag: int, value: object) -> bytes:
    if tag in (TAG_INTEGER, TAG_ENUM):
        return int(value).to_bytes(4, "big", signed=True)
    if tag == TAG_BOOLEAN:
        return bytes((1 if value else 0,))
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def encode_ipp(msg: IppMessage) -> bytes:
    out = bytearray()
    out.append(msg.version[0])
    out.append(msg.version[1])
    out.append((msg.code >> 8) & 0xFF)
    out.append(msg.code & 0xFF)
    out += msg.request_id.to_bytes(4, "big")
    for group_tag, items in msg.groups:
        out.append(group_tag)
        last = ""
        for item in items:
            out.append(item.tag)
            name = item.name if item.name != last else ""
            last = item.name
            nb = name.encode("utf-8")
            out += len(nb).to_bytes(2, "big")
            out += nb
            raw = _put_value(item.tag, item.value)
            out += len(raw).to_bytes(2, "big")
            out += raw
    out.append(GRP_END)
    out += msg.data
    return bytes(out)


def _a(tag: int, name: str, value: object) -> IppAttr:
    return IppAttr(tag, name, value)


def printer_attributes(
    *,
    name: str,
    make: str,
    model: str,
    uri: str,
    uuid: str,
    state: int,
    media: str,
    dpi: int,
    formats: tuple[str, ...],
) -> list[IppAttr]:
    ops = (
        OP_PRINT_JOB,
        OP_VALIDATE_JOB,
        OP_GET_JOBS,
        OP_GET_PRINTER_ATTRIBUTES,
    )
    attrs = [
        _a(TAG_TEXT, "printer-name", name),
        _a(TAG_TEXT, "printer-info", f"{make} {model}"),
        _a(TAG_TEXT, "printer-make-and-model", f"{make} {model}"),
        _a(TAG_URI, "printer-uri-supported", uri),
        _a(TAG_KEYWORD, "uri-security-supported", "none"),
        _a(TAG_KEYWORD, "uri-authentication-supported", "none"),
        _a(TAG_URI, "printer-uuid", uuid),
        _a(TAG_ENUM, "printer-state", state),
        _a(TAG_KEYWORD, "printer-state-reasons", "none"),
        _a(TAG_BOOLEAN, "printer-is-accepting-jobs", True),
        _a(TAG_INTEGER, "queued-job-count", 0),
        _a(TAG_CHARSET, "charset-configured", "utf-8"),
        _a(TAG_CHARSET, "charset-supported", "utf-8"),
        _a(TAG_LANGUAGE, "generated-natural-language-supported", "en"),
        _a(TAG_LANGUAGE, "natural-language-configured", "en"),
        _a(TAG_MIME, "document-format-default", "image/png"),
        _a(TAG_KEYWORD, "pdl-override-supported", "attempted"),
        _a(TAG_KEYWORD, "ipp-versions-supported", "1.1"),
        _a(TAG_KEYWORD, "ipp-versions-supported", "2.0"),
        _a(TAG_KEYWORD, "printer-kind", "label"),
        _a(TAG_KEYWORD, "print-color-mode-supported", "monochrome"),
        _a(TAG_KEYWORD, "print-color-mode-default", "monochrome"),
        _a(TAG_KEYWORD, "media-default", media),
        _a(TAG_KEYWORD, "media-supported", media),
        _a(TAG_KEYWORD, "media-ready", media),
        _a(TAG_INTEGER, "copies-default", 1),
        _a(TAG_INTEGER, "copies-supported", 1),
        _a(TAG_INTEGER, "copies-supported", 5),
        _a(
            TAG_KEYWORD,
            "urf-supported",
            f"V1.4,W8,SRGB24,RS{dpi},CP1,DM3,PQ4,IS1",
        ),
        _a(TAG_KEYWORD, "compression-supported", "none"),
    ]
    for fmt in formats:
        attrs.append(_a(TAG_MIME, "document-format-supported", fmt))
    for op in ops:
        attrs.append(_a(TAG_ENUM, "operations-supported", op))
    return attrs


def response(
    request: IppMessage,
    *,
    status: int,
    printer: list[IppAttr] | None = None,
    job: list[IppAttr] | None = None,
) -> IppMessage:
    groups: list[tuple[int, list[IppAttr]]] = [
        (
            GRP_OPERATION,
            [
                _a(TAG_CHARSET, "attributes-charset", "utf-8"),
                _a(TAG_LANGUAGE, "attributes-natural-language", "en"),
                _a(
                    TAG_TEXT, "status-message", "ok" if status == STATUS_OK else "error"
                ),
            ],
        )
    ]
    if job:
        groups.append((GRP_JOB, job))
    if printer:
        groups.append((GRP_PRINTER, printer))
    return IppMessage(request.version, status, request.request_id, groups, b"")


def self_test() -> None:
    req = IppMessage(
        (1, 1),
        OP_GET_PRINTER_ATTRIBUTES,
        7,
        [
            (
                GRP_OPERATION,
                [
                    _a(TAG_CHARSET, "attributes-charset", "utf-8"),
                    _a(TAG_LANGUAGE, "attributes-natural-language", "en"),
                    _a(TAG_URI, "printer-uri", "ipp://127.0.0.1:8631/ipp/print"),
                ],
            )
        ],
        b"",
    )
    blob = encode_ipp(req)
    back = decode_ipp(blob)
    assert back.code == OP_GET_PRINTER_ATTRIBUTES
    assert back.request_id == 7
    assert back.attrs()["printer-uri"].endswith("/ipp/print")
    job = encode_ipp(IppMessage((1, 1), OP_PRINT_JOB, 1, req.groups, b"\x89PNG"))
    decoded = decode_ipp(job)
    assert decoded.data == b"\x89PNG"
