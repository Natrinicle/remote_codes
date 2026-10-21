# GoodWe (Modbus TCP function 165)

GoodWe hybrids on **Modbus TCP**. Holding/input reads use function
**165** (`0xA5`), not FC3. Meter polls on this family use function **32**.

No encoder in this folder: the A5 request body is model-specific.

USB UART (same function 165, CRC-16-Modbus on RTU) lives under
[Serial/Inverters/GoodWe](../../../Serial/Inverters/GoodWe/).

## Identification

| | |
|--|--|
| Function | **165** (`0xA5`) |
| Meter | function **32** |
| Transport | Modbus TCP |

## Notes

- Own hardware only.
- Do not send Voltronic QPIGS or SRNE `@256` blocks at a GoodWe A5 port.
