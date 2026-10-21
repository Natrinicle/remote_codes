# GoodWe (UART Modbus function 165)

GoodWe hybrids on **USB UART**. Holding/input reads use function **165**
(`0xA5`), not FC3. Meter polls on this family use function **32**.

CRC on RTU is CRC-16-Modbus (same poly as [SRNE](../SRNE/)). Count stays
small (~20 registers).

No encoder in this folder: the A5 request body is model-specific.

Modbus TCP (same function 165) lives under
[Network/Inverters/GoodWe](../../../Network/Inverters/GoodWe/).

## Identification

| | |
|--|--|
| Function | **165** (`0xA5`) |
| Meter | function **32** |
| Transport | USB UART |
| CRC | CRC-16-Modbus, LSB first |

## Notes

- Own hardware only.
- Do not send Voltronic QPIGS or SRNE `@256` blocks at a GoodWe A5 port.
