# MELK-OA10 (BLE)

BLE protocol for MELK-OA10 RGBIC LED strips that pair with **Magic
Lantern** (`wl.smartled.rgb` 6.11.10, Play / iOS 1479587050,
[magiclantern.app](https://magiclantern.app)). Sibling stack is duoCo
StripX (`com.easylink.colorful`).

Recovered from Home Assistant core issue
[#145934](https://github.com/home-assistant/core/issues/145934) (FFF3
sniff), duoCo StripX `library/src/duoco_stripx/protocol.py`
([wxx9248/Corner-Floor-Lamp-Controller](https://github.com/wxx9248/Corner-Floor-Lamp-Controller)),
AzraelSec `rs-duoco-stripx`, then live-proven on an OA10 that Magic
Lantern already controlled. Helpers print payloads. They do not scan or
GATT-connect.

Analog ELK-BLEDOM color frames (`7E 00 05 03 RR GG BB 00 EF`,
`[7]=0x00`) share the same 9-byte envelope and show up in some MELK-OA10
listings. On this RGBIC unit that render target is wrong: sRGB orange
`255,140,40` displayed teal. Pack RGB always uses `[7]=0x10`.

Do not commit APKs. Do not pack live MACs.

## Identification

| | |
|--|--|
| Maker | MELK (Magic Lantern / 亿联智控 / newwavex.com.cn) |
| App | Magic Lantern (`wl.smartled.rgb` 6.11.10) |
| Sibling app | duoCo StripX (`com.easylink.colorful`) |
| Advertised name | `MELK-OA10` plus last MAC octet (spaces padded). Some firmware prints `MELK-OA10W`. |
| GAP 2A00 | `MELK-OA10` padded with spaces |
| Manufacturer company id | 992 |
| ATT MTU | 23 (9-byte frames fit) |

One BLE central at a time. Unbind the phone app before a laptop holds
the link. Write-without-response “success” is not visual proof.

## GATT

Service `0000fff0-0000-1000-8000-00805f9b34fb`

| Char | UUID | Role |
|------|------|------|
| TX | `0000fff3-0000-1000-8000-00805f9b34fb` | write **without** response |
| RX | `0000fff4-0000-1000-8000-00805f9b34fb` | notify (do not subscribe for solids) |

Pace writes about 30 ms. FFF3 readback on this unit is the last 9-byte
`7E…EF` frame plus ASCII `2021` plus NULs. StripX docs treated FFF3 as a
constant device-id string; this firmware echoes the last command.

## Frames

Nine bytes, no checksum:

```
7E | 7 body bytes | EF
```

| Command | Hex | Notes |
|---------|-----|-------|
| Power on (Magic Lantern sniff) | `7E 04 04 F0 00 01 FF 00 EF` | Default `on` |
| Power on (StripX v=1) | `7E 04 04 01 00 01 FF 00 EF` | `on --stripx` |
| Power off | `7E 04 04 00 00 00 FF 00 EF` | |
| Brightness 0–100 | `7E 04 01 xx MODE FF FF 00 EF` | LightMode: 0 SingleRGB, 1 MultipleRGB, 2 CCT, 3 WhiteBlack |
| Solid RGB | `7E 07 05 03 RR GG BB 10 EF` | **`[7]=0x10` is the RGB render target** |
| Warn orange | `7E 07 05 03 FF 16 00 10 EF` | `255,22,0` user-confirmed 2026-11-08 |
| Critical red | `7E 07 05 03 FF 00 00 10 EF` | |
| RGB black | `7E 07 05 03 00 00 00 10 EF` | Visual off without power-off |
| CCT pair | `7E 06 05 02 WW CW FF 08 EF` | `[7]=0x08`. `cct 0 0` zeros WW/CW; RGB-only ICs no-op |
| Effect | `7E 05 03 mode 06 FF FF 00 EF` | |
| Speed | `7E 04 02 xx FF FF FF 00 EF` | |

Opcode `0x83` is StripX `system_time` (`7E 07 83 HH MM SS WD FF EF`).
A truncated analog login `7E 07 83` is that RTC setter, not a pairing
key. Do not send it truncated.

### Do not send (NVRAM)

Expert frames persist IC count / pin order. Do not add them to the
helper CLI. Do not send them to “fix” color.

| Name | Prefix |
|------|--------|
| `symphony` | `7E 07 21` |
| `pin_sequence` | `7E 06 81` |

Music amp uses `[7]=0x20`. Analog color uses `[7]=0x00`.

### LED balance

Pure red / green / blue with `[7]=0x10` look correct. Packed warn orange
is **`255,22,0`**, not sRGB `255,140,40` (too much green, and 40 blue
cools it, on this WS2812).

```text
./encode_magic_lantern.py on
./encode_magic_lantern.py rgb 255,0,0
./encode_magic_lantern.py warn
./encode_magic_lantern.py brightness 100 --mode 1
./encode_magic_lantern.py cct 0 0
./encode_magic_lantern.py decode 7e070503ff160010ef
./encode_magic_lantern.py self-test
```

Write the printed hex to FFF3 without response.

## Notes

- Own hardware only.
- Analog `[7]=0x00` records on FFF3 and can look teal / chase on RGBIC.
- Home Assistant `elkbledom` lists MELK-OA10; those analog frames are the
  wrong family for this Magic Lantern RGBIC unit.
- Do not send `pin_sequence` / `symphony`.
