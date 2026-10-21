# Midnite (CAN)

Midnite Classic / related charge controllers on a CAN bus, not USB UART.

Host framing is 29-bit CAN. Poll by numeric address; replies are data
frames with hex type/id. This is not Modbus RTU and not Voltronic ASCII.

No encoder in this folder: frames need a CAN socket (`can0`), not
`/dev/ttyUSB0`.

## Identification

| | |
|--|--|
| Transport | CAN (not UART) |
| IDs | 29-bit |
| Poll | address + optional RTR |

## Notes

- Own hardware only.
- A CH340 stick is the wrong adapter for this family.
