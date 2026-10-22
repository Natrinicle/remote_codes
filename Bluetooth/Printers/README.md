# Printers (Bluetooth)

Label printers that speak BLE GATT or classic SPP. USB Type-C CDC
siblings live under [Serial/Printers](../../Serial/Printers/).

Helpers in the brand folders print payloads. They do not scan or
GATT-connect. The LAN client that rasters a page and writes those
payloads is [label-bridge](label-bridge/).

| Brand | Transport | Path |
|-------|-----------|------|
| NIIMBOT | BLE GATT `e7810a71` / `bef8d6c9` | [NIIMBOT](NIIMBOT/) |
| Nelko | BLE GATT `0000ff00` / write `ff02` TSPL | [Nelko](Nelko/) |
| Aimotech | Classic SPP `00001101`, `GS v 0` | [Aimotech](Aimotech/) |
| (all three) | IPP / AirPrint / web upload | [label-bridge](label-bridge/) |
