# NIIMBOT B1 (USB)

NIIMBOT B1 over **USB Type-C CDC**. Typical Linux node is `/dev/ttyACM0`.
Bodies are the same `55 55 | cmd | len | data | xor-bcc | AA AA` frames
as BLE.

The encoder and full opcode table live under
[Bluetooth/Printers/NIIMBOT/B1](../../../../Bluetooth/Printers/NIIMBOT/B1/).
Write the printed hex to the CDC device. Do not open CDC and GATT on the
same printer at once.

Official app strings include `UsbManager`, `vendorId`, `productId`,
`portSerial`, and `_showSerialUseGuide`. **VID/PID values were not in
plaintext** in the unpacked APK. Do not guess a chip id.

## Identification

| | |
|--|--|
| Transport | USB Type-C CDC ACM |
| Framing | `55 55` … `AA AA`, XOR bcc |
| Connect | `03 55 55 C1 01 01 C1 AA AA` |
| VID/PID | unknown (not recovered) |

```text
../../../../Bluetooth/Printers/NIIMBOT/B1/encode_niimbot.py self-test
../../../../Bluetooth/Printers/NIIMBOT/B1/encode_niimbot.py connect
../../../../Bluetooth/Printers/NIIMBOT/B1/encode_niimbot.py print-seq --height 320 --width 384
```

## Notes

- Own hardware only.
- UART and BLE must not fight over the same printer.
- Handshake, PageStart, and 6-byte SetPageSize still apply on CDC for
  task `b1`.
