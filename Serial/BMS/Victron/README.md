# Victron (VE.Direct)

Victron BMV / MPPT / inverter accessories on the VE.Direct port. Typical
**19200 8N1**.

Text protocol: `key\\tvalue` lines, block terminated by `Checksum\\t` plus
a binary byte so the whole block sums to 0 mod 256.

HEX protocol: `:` + hex payload + two hex checksum digits + CR. Checksum
is the two's complement of the sum of the payload bytes.

```text
./encode_vedirect.py checksum 7f00
./encode_vedirect.py self-test
```

## Identification

| | |
|--|--|
| UART | 19200 8N1 |
| Text | `PID` `V` `I` `Checksum` |
| HEX | `:` payload checksum CR |

## Notes

- Own hardware only.
- VE.Direct is not Modbus RTU and not Voltronic ASCII.
