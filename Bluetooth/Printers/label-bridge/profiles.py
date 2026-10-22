"""Printer profiles for the label-bridge client.

Wire bytes come from the sibling encode_*.py helpers. This module is
identification and transport only.
"""

from __future__ import annotations

from dataclasses import dataclass

NIIMBOT_SERVICE = "e7810a71-73ae-499d-8c15-faa9aef0c3f2"
NIIMBOT_CHAR = "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"
NELKO_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"
NELKO_WRITE = "0000ff02-0000-1000-8000-00805f9b34fb"
NELKO_NOTIFY = "0000ff03-0000-1000-8000-00805f9b34fb"
NELKO_READ = "0000ff01-0000-1000-8000-00805f9b34fb"
SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class Profile:
    key: str
    title: str
    make: str
    model: str
    transport: str  # ble-gatt | spp
    dpi: int
    width_dots: int
    default_height_dots: int
    max_height_dots: int
    name_prefixes: tuple[str, ...]
    service: str | None = None
    write_char: str | None = None
    notify_char: str | None = None
    pace_s: float = 0.01
    bundle: int = 240
    mtu: int = 512
    spp_uuid: str = SPP_UUID
    media: str = "oe_label_1.5x0.47in"


PROFILES: dict[str, Profile] = {
    "niimbot-b1": Profile(
        key="niimbot-b1",
        title="NIIMBOT B1",
        make="NIIMBOT",
        model="B1",
        transport="ble-gatt",
        dpi=203,
        width_dots=384,
        default_height_dots=320,
        max_height_dots=1600,
        name_prefixes=("B1", "B21", "D11", "D110"),
        service=NIIMBOT_SERVICE,
        write_char=NIIMBOT_CHAR,
        notify_char=NIIMBOT_CHAR,
        pace_s=0.01,
        bundle=240,
        media="oe_label_1.89x1.57in",
    ),
    "nelko-p21": Profile(
        key="nelko-p21",
        title="Nelko P21",
        make="Nelko",
        model="P21",
        transport="ble-gatt",
        dpi=203,
        width_dots=96,
        default_height_dots=320,
        max_height_dots=1600,
        name_prefixes=("P21", "P31", "P22", "P24", "Nelko", "PL80"),
        service=NELKO_SERVICE,
        write_char=NELKO_WRITE,
        notify_char=NELKO_NOTIFY,
        pace_s=0.008,
        bundle=480,
        mtu=512,
        media="oe_label_0.47x1.57in",
    ),
    "aimotech-d30": Profile(
        key="aimotech-d30",
        title="Aimotech D30",
        make="Aimotech",
        model="D30",
        transport="spp",
        dpi=203,
        width_dots=96,
        default_height_dots=320,
        max_height_dots=1600,
        name_prefixes=("D30", "Phomemo", "Aimo", "P12", "Q30"),
        pace_s=0.02,
        bundle=512,
        media="oe_label_0.47x1.57in",
    ),
}


def get_profile(key: str) -> Profile:
    try:
        return PROFILES[key]
    except KeyError as exc:
        known = ", ".join(sorted(PROFILES))
        raise KeyError(f"unknown printer {key!r}; choose {known}") from exc


def match_ble_name(name: str | None) -> list[str]:
    if not name:
        return []
    hits: list[str] = []
    for key, prof in PROFILES.items():
        if any(
            name.startswith(prefix) or prefix.lower() in name.lower()
            for prefix in prof.name_prefixes
        ):
            hits.append(key)
    return hits
