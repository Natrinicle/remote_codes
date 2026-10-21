# GoodWe (Modbus function 165)

GoodWe hybrids on UART or Modbus TCP. Holding/input reads use function
**165** (`0xA5`), not FC3. Meter polls on this family use function **32**.

CRC on RTU is CRC-16-Modbus (same poly as [SRNE](../SRNE/)). Count stays
small (~20 registers).

No encoder in this folder: the A5 request body is model-specific. Use a
Modbus client that can send function 165, or extend `encode_srne.py`'s CRC
helper once a unit is on the bench.

## Identification

| | |
|--|--|
| Function | **165** (`0xA5`) |
| Meter | function **32** |
| Transport | USB UART or Modbus TCP |
| CRC (RTU) | CRC-16-Modbus, LSB first |

## Notes

- Own hardware only.
- Do not send Voltronic QPIGS or SRNE `@256` blocks at a GoodWe A5 port.
