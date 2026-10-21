# JBD / Xiaoxiang (UART)

JBD (Xiaoxiang) BMS over **USB UART**. Typical **9600 8N1**. Bodies are
`DD…77`.

The payload helper and BLE GATT path (`FF00` / `FF01` / `FF02`) live under
[Bluetooth/BMS/JBD](../../../Bluetooth/BMS/JBD/). UART writes the same
printed hex to the serial device.

Replies start `DD` and end `77`. UART chunks can fragment; reassemble
until `DD…77`.

## Identification

| | |
|--|--|
| Transport | USB UART 9600 8N1 |
| Basic info | `DD A5 03 00 FF FD 77` |
| Cell volts | `DD A5 04 00 FF FC 77` |
| Reply | starts `DD`, ends `77` |

```text
../../../Bluetooth/BMS/JBD/encode_jbd.py basic
../../../Bluetooth/BMS/JBD/encode_jbd.py self-test
```

## Notes

- Own hardware only.
- UART and BLE must not fight over the same pack.
