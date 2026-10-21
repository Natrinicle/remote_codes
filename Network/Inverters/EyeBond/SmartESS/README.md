# SmartESS (EyeBond Wi-Fi collector)

Local LAN protocol for the SmartESS Android app
(`com.eybond.smartclient.ess`) and the EyeBond Wi-Fi collector/dongle that
phones home to dessmonitor.com.

Flipper IR does not apply. BLE does not apply. Use
[`encode_smartess.py`](encode_smartess.py) to build the UDP hijack string and
the TCP EyeBond frames. The script prints payloads; it does not bind ports or
send packets.

## Identification

| | |
|--|--|
| App | SmartESS |
| Android package | `com.eybond.smartclient.ess` |
| Collector | EyeBond Wi-Fi dongle (UART to the inverter) |
| Cloud | dessmonitor.com |
| UDP | **58899** ASCII hijack |
| TCP | **8899** EyeBond session (collector **initiates**) |
| Inner UART | **9600-8-1-0** on this family |
| Proven inner protocol | **SRNE Modbus RTU FC3** inside EyeBond FC=4. Unwrapped UART: [Serial/Inverters/SRNE](../../../../Serial/Inverters/SRNE/) |

Other EyeBond tunnels exist (PI17/PI18 ASCII, SMG Modbus). PI17 `GS` / PI30
`QPIGS` returned empty FC=4 on the collector this map was taken from. Do not
assume Voltronic ASCII until a dongle answers it.

No rating plate was packed with this unit. Transcribe FCC / collector serial
in the unit README when a photo exists; do not invent them.

## Local hijack

Same L2 as the collector. Wi-Fi client isolation and unpublished Docker
ports break the return TCP. The IP in the UDP body must be a **fixed RFC1918**
address the collector can route to (`0.0.0.0` in that string fails).

| Direction | Protocol | Port | Payload |
|-----------|----------|------|---------|
| listener → collector | UDP | 58899 | `set>server=<listener-lan-ip>:8899;` |
| collector → listener | TCP | 8899 | EyeBond frames |

Hijack about once a second until TCP is up. **Stop UDP** while the session is
live — a later `set>server` reconnects and drops the poll.

Broadcast `255.255.255.255` plus the subnet broadcast. Optional unicast to a
reserved collector DHCP address (reserve the **dongle**, not the inverter
serial).

Do **not** port-forward 58899 or 8899.

Local poll is a few seconds. Cloud default is **5 minutes**.

```text
./encode_smartess.py hijack 192.0.2.10
# set>server=192.0.2.10:8899;
```

## EyeBond TCP framing

8-byte header, then payload. Multi-byte fields are big-endian.

| Offset | Field |
|--------|--------|
| 0–1 | transaction id (`tid`), start at 1, skip 0 |
| 2–3 | `devcode` |
| 4–5 | `wire` = total_len − 6 |
| 6 | address |
| 7 | function |
| 8… | payload |

| FC | Role | Header addr | `devcode` | Payload |
|----|------|-------------|-----------|---------|
| 1 | heartbeat | 1 (mgmt) | 0 | `YY MM DD HH MM SS 00 3C` (year since 2000; last byte 60 s) |
| 2 | collector query | 1 | 1 | `02 05 06 0e` |
| 4 | forward UART | **0xFF** | **0x0001** (SRNE here) | inner Modbus RTU |

Heartbeat first, then FC2, then FC4 polls. Do not idle after the collector's
PN heartbeat — waiting let the peer FIN.

A dummy date **2026-01-01 00:00:00** kept the session on a box with no NTP. A
live UTC stamp closed TCP on an earlier probe. Use `--dummy-date` until the
listener has trustworthy time.

```text
./encode_smartess.py heartbeat --dummy-date
./encode_smartess.py query
./encode_smartess.py decode 00010000000a01011a0101000000003c
```

Some FC=4 replies prefix the RTU with `FF 04`. Strip that before CRC.

## SRNE holding registers (this family)

Inner RTU: slave **1**, function **3**, CRC-16-Modbus (init `0xFFFF`, poly
`0xA001`, CRC little-endian on the wire). One FC4 in flight; retry replaces
`tid` so a late original is leftover.

Blocks match `ha-eybond-local` `srne_modbus/base.json`:

| Name | Start | Count | What we use |
|------|-------|-------|-------------|
| cfg | 256 | 18 | SoC, batt V/A, PV1+PV2 |
| live | 528 | 18 | mode, L1 AC out, load %, inverter °C |
| phase | 554 | 14 | L2 watts added to AC out |

cfg (`@256`):

| Reg | Scale | Notes |
|-----|-------|--------|
| 0 | 1 | SoC % |
| 1 | /10 | battery V (signed) |
| 2 | /10 | battery A (signed). **+discharge / −charge** on this box |
| 7 | /10 | PV1 V |
| 9 | 1 | PV1 W |
| 15 | /10 | PV2 V |
| 17 | 1 | PV2 W |

live (`@528`):

| Reg | Scale | Notes |
|-----|-------|--------|
| 0 | 1 | mode |
| 11 | 1 | AC out W (L1 this poll) |
| 15 | 1 | load % (L1) |
| 17 | /10 | inverter °C |

phase (`@554`): reg 8 is L2 watts; reg 12 is L2 load %. Total AC out = L1 + L2
from the **same round**. Mixing a previous phase reading inflates the HUD.

Product identity showed up at holding **@53** as an `SR-…` string on the
probed inverter. Do not treat that as PI17.

```text
./encode_smartess.py read cfg
./encode_smartess.py read live
./encode_smartess.py read phase
./encode_smartess.py self-test
```

SRNE FC6/16 writes are not mapped on this EyeBond path. Direct USB UART FC6
is [Serial/Inverters/SRNE](../../../../Serial/Inverters/SRNE/) (print-only).
Serial `SET` (PI17-style) is ignored on this dongle. No HTTP write surface.

## Integrations (same UDP/TCP)

- [ha-dessmonitor](https://github.com/andreas-glaser/ha-dessmonitor) — **Local network only**, read-only (`docs/LOCAL_MODE.md`).
- [home-assistant-dess-monitor-local](https://github.com/Antoxa1081/home-assistant-dess-monitor-local) — EyBond transport.
- [ha-smartess-local](https://github.com/ubombi/ha-smartess-local) — reverse-engineered from the Android app; some writes on tested hardware.
- [ha-eybond-local](https://github.com/lewei50/ha-eybond-local) — SRNE register blocks above.

ha-dessmonitor tunnel code `2452` tries P17/PI18 first. Cloud family `2376` is
SMG Modbus. Code `258` is ambiguous. Devcode **518** has cloud telemetry; local
protocol not verified.

## Notes

- Own hardware / own LAN only.
- Block outbound to dessmonitor.com at the router **after** local TCP is
  proven if the goal is LAN-only. Keep LAN so 58899/8899 still work.
- Do not commit APKs or collector serials.
