# HeatGenie (Bogu parking diesel heater)

BLE protocol for the HeatGenie / “AirHeater genie” app (`uni.UNIC97AE27`).
Recovered from the 1.1.1 uni-app bundle (`app-service.js`), then live-proven
on a unit that advertises as its MAC.

This is **not** Vevor/AirHeaterBLE `FFE0`/`AA55`. Do not send those frames here.

Flipper IR does not apply. Use `encode_heatgenie.py` plus a BLE central
(write no-response to `3A01`, notify on `3A00`).

## Identification

| | |
|--|--|
| App | HeatGenie (`uni.UNIC97AE27`) |
| Maker | Wenzhou Bogu Intelligent Technology |
| Advertised name | colon-separated MAC, e.g. `C1:02:A3:AE:FE:BC` |
| Name filter | byte0 `0xC1`, byte4 `0xFE` (or name contains `boygu`) |
| Ad service | `0000181a-0000-1000-8000-00805f9b34fb` |

One BLE central at a time. Unbind the phone (app Device Management, or
panel Set+Power 3s) before a laptop holds the link.

The on-unit temp probe can read several °F above a sensor outside the
heater box when ducting is uninsulated. That is placement, not a second scale.

## GATT

Service `0000181a-0000-1000-8000-00805f9b34fb`

| Char | UUID | Role |
|------|------|------|
| RX | `00003a00-0000-1000-8000-00805f9b34fb` | notify (heater → host) |
| TX | `00003a01-0000-1000-8000-00805f9b34fb` | write **without** response |

## Frames

CRC-16-CCITT nibble table, init 0. TX: CRC over all-but-last-2, stored big-endian.
RX: CRC of the **full** frame must be 0.

8-byte command: `AA 00 CMD A0 A1 A2 CRC_HI CRC_LO`

| CMD | Meaning |
|-----|---------|
| 97 | button: 1 ON, 2 OFF (A1 = random) |
| 101 | auto report: `[2, 20, 30]` start, `[2, 0, 30]` stop |

Status notify is 52 bytes: `AA 09 FF … F2` + 40-byte register map (temps are
**tenths of °C**). App °F = `trunc((320 + 1.8 * raw) / 10)`.

```text
./encode_heatgenie.py self-test
./encode_heatgenie.py auto
./encode_heatgenie.py decode aa09ff…
```

Known-good auto-report start: `aa006502141ed095`.
