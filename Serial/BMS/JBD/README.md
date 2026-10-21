# JBD / Xiaoxiang (UART)

JBD (Xiaoxiang) BMS over USB UART. Typical **9600 8N1**. The BLE app path
uses GATT `FF00` / `FF01` / `FF02` with the **same** `DD…77` bodies.

Replies start `DD 03` (or the command echo) and end `77`. Notify/UART
chunks can fragment; reassemble until `DD…77`.

Helpers print payloads. They do not open the serial device. Do not GATT-
connect a pack from two centrals at once; UART is a separate physical path.

## Identification

| | |
|--|--|
| UART | 9600 8N1 |
| BLE sibling | service `FF00`, notify `FF01`, write `FF02` |
| Basic info | `DD A5 03 00 FF FD 77` |
| Cell volts | `DD A5 04 00 FF FC 77` |
| HW version | `DD A5 05 00 FF FB 77` |
| Resistance | `DD A5 F6 00 FF 0A 77` |
| Reply | starts `DD`, ends `77` |

```text
./encode_jbd_uart.py basic
./encode_jbd_uart.py cells
./encode_jbd_uart.py self-test
```

Checksum is the 16-bit one's complement of CMD+LEN+data, stored big-endian
before the trailing `77`.

## Notes

- Own hardware only.
- One BLE central at a time. UART and BLE must not fight over the same pack.
