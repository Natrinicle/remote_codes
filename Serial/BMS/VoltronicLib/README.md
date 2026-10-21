# Voltronic LIB (RS485 Modbus)

Voltronic inverter-attached LIB BMS on RS485. Framing is Modbus RTU FC3,
slave 1, CRC-16-Modbus (same poly as [SRNE](../../Inverters/SRNE/)).

Typical **9600 8N1**.

| Name | Start | Count | Use |
|------|-------|-------|-----|
| soc | 37 | 17 | SoC and pack summary |
| cells | 16 | 21 | cell voltages |
| limits | 112 | 5 | max charge / discharge |

```text
./encode_voltroniclib.py soc
./encode_voltroniclib.py cells
./encode_voltroniclib.py limits
./encode_voltroniclib.py self-test
```

## Notes

- Own hardware only.
- This is the BMS RS485 dialect, not the inverter QPIGS ASCII port.
