# Printers (Serial)

USB Type-C CDC / UART label printers. BLE GATT siblings live under
[Bluetooth/Printers](../../Bluetooth/Printers/).

Helpers print payloads. They do not open `/dev/ttyACM0`.

| Brand | Transport | Path |
|-------|-----------|------|
| NIIMBOT | USB Type-C CDC, `55 55` XOR | [NIIMBOT](NIIMBOT/) |
