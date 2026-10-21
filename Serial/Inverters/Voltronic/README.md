# Voltronic (USB HID / UART ASCII)

Axpert, InfiniSolar, and other Voltronic-labelled hybrids. Queries are
ASCII (`QPIGS`, `QPIRI`, `QMOD`, `QPIWS`) plus a checksum and CR.

Transport is **USB HID hidraw** (no baud) or USB UART (often 2400 or 9600
8N1). This is not Modbus. An SRNE inverter on a CH340 stick will not
answer QPIGS.

## Identification

| | |
|--|--|
| Commands | `QPIGS` `QPIRI` `QMOD` `QPIWS` `QPI` `QVFW` |
| HID | `/dev/hidraw0` (VID/PID on the inverter, no baud) |
| UART | 2400 or 9600 8N1 |
| `$` suffix | CRC-16 nibble table, poly `0x1021` (not Modbus) |
| `@` suffix | 8-bit sum |
| none | command + CR only |

CRC high/low bytes that would be `0x0D`, `0x0A`, or `0x28` (`(`) are
incremented so the frame never embeds CR/LF/ `(`.

```text
./encode_voltronic.py qpigs
./encode_voltronic.py qpiri --check @
./encode_voltronic.py raw QPIWS
./encode_voltronic.py self-test
```

`ha-voltronic-mqtt` (QPIGS/QPIRI) matches this family only.

## Notes

- Own hardware / own USB only.
- Do not send Voltronic ASCII at an SRNE Modbus UART.
