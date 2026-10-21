# SRNE (USB UART Modbus RTU)

Direct USB serial to SRNE hybrid inverters (Sungoldpower SPH split-phase,
and other SRNE-labelled single/split/three-phase boxes). Typical adapter is
QinHeng CH340 (`1a86:7523`) → `/dev/ttyUSB0`.

This is **Modbus RTU**, not Voltronic QPIGS. A QPIGS poller on the same
stick is the wrong family.

LAN sibling: the same RTU rides inside EyeBond FC=4 on
[Network/Inverters/EyeBond/SmartESS](../../../Network/Inverters/EyeBond/SmartESS/).
Use this folder when the inverter USB port is attached to the host. Do not
open the UART and the EyeBond TCP session at the same time.

Helpers print payloads. They do not open the serial device.

## Identification

| | |
|--|--|
| OEM | SRNE |
| Proven unit | Sungoldpower SPH10048P split-phase |
| USB | CH340 `1a86:7523` → `/dev/ttyUSB0` |
| UART | **9600 8N1**, exclusive open, DSR/DTR off |
| Slave | **1** |
| Read | function **3** |
| Write | function **6** (print only here) |
| CRC | CRC-16-Modbus, init `0xFFFF`, poly `0xA001`, little-endian on the wire |
| Gap | ~0.35 s between frames |

## Holding-register blocks

| Name | Start | Count | Use |
|------|-------|-------|-----|
| cfg | 256 | 18 | SoC, batt V/A, PV1+PV2 |
| live | 528 | 18 | mode, L1 AC out, load %, inverter °C |
| phase | 554 | 14 | L2 watts / load % |
| e204 | 0xE204 | 2 | output priority + AC-charge limit (E205) |
| e20a | 0xE20A | 2 | max charge A + AC range (E20B) |
| e20f | 0xE20F | 1 | charge priority |

cfg (`@256`):

| Off | Scale | Notes |
|-----|-------|--------|
| 0 | 1 | SoC % |
| 1 | /10 | battery V (signed) |
| 2 | /10 | battery A (signed). **+discharge / −charge** on the proven box |
| 7 | /10 | PV1 V |
| 9 | 1 | PV1 W |
| 15 | /10 | PV2 V |
| 17 | 1 | PV2 W |

live (`@528`): mode, L1 watts at off 11, L1 load % at 15, inverter °C /10 at 17.

phase (`@554`): L2 watts at off 8; L2 load % at 12. Total AC out = L1 + L2
from the **same round**.

e204: reg0 output priority (`1` = LINE/UTI on the proven box). reg1 E205 is
AC-charge current limit in **0.1 A** (raw `0` = 0.0 A, raw `400` = 40.0 A).

e20a: reg0 max charge A /10. reg1 E20B AC input range (`0` APL, `1` UPS).

e20f: charge priority.

## Proven TX (slave 1)

```text
./encode_srne.py read cfg     # 010301000012c43b
./encode_srne.py read live    # 010302100012c5ba
./encode_srne.py read phase   # 0103022a000ee47e
./encode_srne.py read e204    # 0103e2040002b3b2
./encode_srne.py read e20a    # 0103e20a0002d271
./encode_srne.py read e20f    # 0103e20f00018271
./encode_srne.py write e205 0 # 0106e2050000afb3  (print only)
./encode_srne.py self-test
```

FC6 writes are not sent by this helper. Do not write E208/E20B unless the
operator names those registers. Inter-frame gap ~0.35 s on the proven UART.

## Notes

- Own hardware / own USB only.
- Host `stty` may show 9600 but stay in cooked mode (`icanon`/`echo`); use a
  raw exclusive serial open for RTU.
- Do not commit site IPs, collector serials, or APKs.
