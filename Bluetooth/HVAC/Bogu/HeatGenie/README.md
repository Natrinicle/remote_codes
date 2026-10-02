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
| 97 | button: 1 ON, 2 OFF, **5 CLEAR**, **9 BLOW/vent**. **A1 must be a new 1–255 random each press.** |
| 99 / 100 | GET_REG_ADDR / GET_REG_VAL (para type 3 / short 243) |
| 101 | auto report: `[2, 20, 30]` start, `[2, 0, 30]` stop |
| 102 | SHORT_PARA: run mode / target temp / gear |

Constant (恒温) mode: `SHORT_RUN_MODE` + `RUN_MODE_AUTO` → `aa00660000001961`.
Target 70°F: `SHORT_TARGET_TEMP`, unit flag 1, value 70 → `aa00660101463562` (app range 50–104°F).

### Advanced para (hidden types)

No altitude/高原 fueling knob in the APK. Pump **stroke** is an advanced setting
(password `bogu1234` in the app), not live Hz.

Byte at para offset 4:

| Bits | Field | Values |
|------|--------|--------|
| 0–1 | runMode | preserved on save |
| 2–3 | watt | 2 / 3 / 5 / 8 kW |
| 4–5 | oil pump type | **16 / 22 / 28 µL** (app says ML) |
| 6–7 | battery | **12V / 24V / AU** |

Physical **ZM25-12V22ml** → tell the ECU **12V + 22µL**. Do **not** select 16µL
on a 22µL pump (ECU would pulse more → worse flood). `oilPumpFreq` in the
status dump is telemetry (Hz×10), not a setpoint. Lower **gear** for less rate.

Other types in the same para/reg maps: aimGear 1–10, start-stop temps,
7-day timers, vent (`CMD_BLOW_ON`), temp unit C/F. Write para via
`heaterSendRawData` to longAddr `F3` after a read-modify of the dump.

ACK: `AA 00 41 d rand …` (`d=0` ok, `d=1` repeat — ignored). Cancel ON within ~1–2 s using a **different** random OFF; the panel shows `CLER` then cooldown. After that window the unit finishes ignition/heat before another OFF is taken.

`./encode_heatgenie.py on` / `off` / `vent` / `clear` pick a random A1 unless you pass `--rand`.

### Errors (E-10) — wait for cooldown, not a 12V reset

`errorCode` **512 = E-10** (two ignition failures). The ECU locks **while cooldown
purges excess fuel** (mode 4, fan spinning). A 12V power cut is **not** required
once that fan drops to 0.

Then a **new** A1 random is accepted even if the last status still shows mode 6 /
512:

- `vent` (`CMD_BLOW_ON=9`) → mode 8, error 0, fan ~445, pump 0 (live 2026-10-02).
- `on` starts a new ignition pair (mode 6/512 → ignite, error 0).
- `clear` had no ACK during E-10.

If vent is ignored, wait **~60 s** and send a **different** random (still in
cooldown). The start heard after a BLE disconnect is the ECU’s own second
ignition of the pair, not a leftover laptop write.

Ads drop during ignition. BlueZ may keep GATT (`Connected: yes`) while Bleak
reports DeviceNotFound — use the existing BlueZ path or wait for ads.

Live para after an E-10 write: **12V + 22µL + 2kW**. Constant 70°F is below the
on-unit probe (~83–94°F); use ≥90–95°F or manual gear. No-flame pattern: glow
82–88, fan 100→255, pump 1.2 Hz, **shell falling**. Drying: vent plus ceramic
heat on the metal body; confirm pump stays 0 Hz.

Status notify is 52 bytes: `AA 09 FF … F2` + 40-byte register map (temps are
**tenths of °C**). App °F = `trunc((320 + 1.8 * raw) / 10)`.

```text
./encode_heatgenie.py self-test
./encode_heatgenie.py auto
./encode_heatgenie.py vent
./encode_heatgenie.py decode aa09ff…
```

Known-good auto-report start: `aa006502141ed095`.
