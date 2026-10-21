# Luxpower (UART / TCP / BLE)

Luxpower LXP / SNA / ACS / GridBoss hybrids. Transport is USB UART, TCP,
or a BLE connection depending on the box.

This is not Voltronic QPIGS and not SRNE Modbus `@256`. No encoder in this
folder until a unit is on the bench.

## Identification

| | |
|--|--|
| Models | LXP, SNA, ACS, GridBoss |
| Transport | UART, TCP, or BLE |

## Notes

- Own hardware only.
- BLE and TCP are different reaches of the same inverter family; do not
  mix them with an SRNE CH340 session.
