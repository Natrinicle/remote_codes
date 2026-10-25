# Serial

Wired host ports: USB UART, USB HID, RS485, and CAN. Same type / brand /
model tree as [Infrared](../Infrared/). These are not Flipper `.ir` files.

This tree is **not** BLE or LAN. Radio lives under
[Bluetooth](../Bluetooth/). LAN collectors live under
[Network](../Network/).

Helpers print payloads. They do not open `/dev/ttyUSB0`, `/dev/hidraw0`,
or a CAN socket. Do not treat a CH340 USB-UART as Voltronic ASCII until
the inverter answers QPIGS.

## Code smell → family

| Smell | Family | Path |
|-------|--------|------|
| `hidraw`, Axpert, InfiniSolar, QPIGS / QPIRI / QMOD | Voltronic ASCII | [Inverters/Voltronic](Inverters/Voltronic/) |
| CH340 `1a86:7523`, FC3 `@256` / `@528` / `@554` / `@E204` | SRNE Modbus RTU | [Inverters/SRNE](Inverters/SRNE/) |
| EyeBond TCP 8899 / UDP 58899 / `set>server=` | SRNE inside EyeBond wrap | [Network/Inverters/EyeBond](../Network/Inverters/EyeBond/) |
| Modbus fn 165 (`0xA5`) on UART | GoodWe UART | [Inverters/GoodWe](Inverters/GoodWe/) |
| Modbus fn 165 (`0xA5`) on TCP | GoodWe TCP | [Network/Inverters/GoodWe](../Network/Inverters/GoodWe/) |
| CAN `poll` / 29-bit IDs | Midnite | [Inverters/Midnite](Inverters/Midnite/) |
| Frame8851 / HGX | Sumry | [Inverters/Sumry](Inverters/Sumry/) |
| LXP / SNA / GridBoss on UART | Luxpower UART | [Inverters/Luxpower](Inverters/Luxpower/) |
| LXP / SNA / GridBoss on TCP | Luxpower TCP | [Network/Inverters/Luxpower](../Network/Inverters/Luxpower/) |
| LXP / SNA / GridBoss on BLE | Luxpower BLE | [Bluetooth/Inverters/Luxpower](../Bluetooth/Inverters/Luxpower/) |
| `DD A5 03` / Xiaoxiang on UART | JBD UART | [BMS/JBD](BMS/JBD/) |
| `DD A5 03` / Xiaoxiang / GATT `FF00` | JBD BLE | [Bluetooth/BMS/JBD](../Bluetooth/BMS/JBD/) |
| `55 55` XOR bcc, B1 thermal, GATT `e7810a71` | NIIMBOT BLE | [Bluetooth/Printers/NIIMBOT/B1](../Bluetooth/Printers/NIIMBOT/B1/) |
| Type-C CDC, same `55 55` frames | NIIMBOT USB | [Printers/NIIMBOT/B1](Printers/NIIMBOT/B1/) |
| `SIZE` / `GAP` / `BITMAP` TSPL2, RFCOMM ch1 | Nelko P21 | [Bluetooth/Printers/Nelko/P21](../Bluetooth/Printers/Nelko/P21/) |
| `1F 11` / `GS v 0` (`1D 76 30`), SPP `00001101` | Aimotech D30 | [Bluetooth/Printers/Aimotech/D30](../Bluetooth/Printers/Aimotech/D30/) |
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
- Midnite is CAN (`can0`), not `/dev/ttyUSB0`.

| Type | Path |
|------|------|
| Inverters | [Inverters](Inverters/) |
| BMS | [BMS](BMS/) |
| Printers | [Printers](Printers/) |
