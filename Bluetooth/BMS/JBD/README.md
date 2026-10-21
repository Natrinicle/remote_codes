# JBD / Xiaoxiang (BLE)

JBD (Xiaoxiang) BMS over Bluetooth LE. Service **FF00**, notify **FF01**,
write **FF02**. Bodies are `DD…77`.

Replies start `DD 03` (or the command echo) and end `77`. Notify chunks
can fragment; reassemble until `DD…77`.

Helpers print payloads. They do not GATT-connect. One BLE central at a
time on a pack.

USB UART 9600 8N1 uses the **same** bodies:
[Serial/BMS/JBD](../../../Serial/BMS/JBD/).

## Identification

| | |
|--|--|
| Transport | BLE GATT |
| Service | `FF00` |
| Notify (RX) | `FF01` |
| Write (TX) | `FF02` |
| Basic info | `DD A5 03 00 FF FD 77` |
| Cell volts | `DD A5 04 00 FF FC 77` |
| HW version | `DD A5 05 00 FF FB 77` |
| Resistance | `DD A5 F6 00 FF 0A 77` |
| Reply | starts `DD`, ends `77` |

```text
./encode_jbd.py basic
./encode_jbd.py cells
./encode_jbd.py self-test
```

Checksum is the 16-bit one's complement of CMD+LEN+data, stored big-endian
before the trailing `77`. Write the printed hex to `FF02`.

## Notes

- Own hardware only.
- One BLE central at a time. UART and BLE must not fight over the same pack.
- Some modules stop advertising at 0 A; wake with charge or discharge current.
