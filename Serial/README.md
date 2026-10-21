# Serial

USB UART, USB HID, and RS485 protocol notes for inverters and BMS packs.
Same type / brand / model tree as [Infrared](../Infrared/). These are not
Flipper `.ir` files.

Helpers print payloads. They do not open `/dev/ttyUSB0` or `/dev/hidraw0`.
Do not treat a CH340 USB-UART as Voltronic ASCII until the inverter answers
QPIGS.

LAN collectors (EyeBond UDP/TCP) stay under [Network](../Network/). BLE
stays under [Bluetooth](../Bluetooth/). JBD BLE `FF00` uses the same
`DD…77` bodies as [BMS/JBD](BMS/JBD/) UART.

## Code smell → family

| Smell | Family | Path |
|-------|--------|------|
| `hidraw`, Axpert, InfiniSolar, QPIGS / QPIRI / QMOD | Voltronic ASCII | [Inverters/Voltronic](Inverters/Voltronic/) |
| CH340 `1a86:7523`, FC3 `@256` / `@528` / `@554` / `@E204` | SRNE Modbus RTU | [Inverters/SRNE](Inverters/SRNE/) |
| EyeBond TCP 8899 / UDP 58899 / `set>server=` | SRNE inside EyeBond wrap | [Network/Inverters/EyeBond](../Network/Inverters/EyeBond/) |
| Modbus fn 165 (`0xA5`), meter=32 | GoodWe | [Inverters/GoodWe](Inverters/GoodWe/) |
| CAN `poll` / 29-bit IDs | Midnite | [Inverters/Midnite](Inverters/Midnite/) |
| Frame8851 / HGX | Sumry | [Inverters/Sumry](Inverters/Sumry/) |
| LXP / SNA / GridBoss | Luxpower | [Inverters/Luxpower](Inverters/Luxpower/) |
| `DD A5 03` / Xiaoxiang / `FF00` | JBD UART (BLE sibling) | [BMS/JBD](BMS/JBD/) |
| `pwr` / `bat` / `help` RS485 shell | Pylontech | [BMS/Pylontech](BMS/Pylontech/) |
| VE.Direct `Checksum` / `:7` | Victron | [BMS/Victron](BMS/Victron/) |
| FC3 start 37 count 17 on RS485 | Voltronic LIB BMS | [BMS/VoltronicLib](BMS/VoltronicLib/) |
| ha-voltronic-mqtt / `qpigs=` | Voltronic only | Wrong family for SRNE USB-UART |

## Gotchas

- USB serial (CH340) is not automatically Voltronic.
- USB HID hidraw is typically Voltronic ASCII. No baud on HID.
- EyeBond/SmartESS Wi-Fi is a wrap around the same SRNE RTU, not a second
  protocol. Direct `/dev/ttyUSB0` and EyeBond TCP 8899 must not share the UART.
- Modbus CRC is LSB-first, poly `0xA001`. Voltronic `$` CRC is a different
  nibble table (poly `0x1021`) and must not use Modbus CRC.
- Inter-frame gap on proven SRNE UART is about 0.35 s.

| Type | Path |
|------|------|
| Inverters | [Inverters](Inverters/) |
| BMS | [BMS](BMS/) |
