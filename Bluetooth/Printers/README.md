# Printers (Bluetooth)

Label printers that speak BLE GATT or classic SPP. USB Type-C CDC
siblings live under [Serial/Printers](../../Serial/Printers/).

Helpers in the brand folders print payloads. They do not scan or
GATT-connect. The LAN client that rasters a page and writes those
payloads is [label-bridge](label-bridge/).

| Brand | Transport | Path |
|-------|-----------|------|
| NIIMBOT | BLE GATT `e7810a71` / `bef8d6c9` | [NIIMBOT](NIIMBOT/) |
| Nelko | RFCOMM ch1 TSPL2 (GATT `ff02` same bytes); CUPS `printer-driver-nelko` | [Nelko](Nelko/) |
| Aimotech | Classic SPP `00001101`, `GS v 0`; CUPS `printer-driver-aimotech` | [Aimotech](Aimotech/) |
| (all three) | IPP / AirPrint / web upload | [label-bridge](label-bridge/) |

KDE System Settings → Printers lists **configured CUPS dests** (they
stay when the printer is off). Add Printer is live Get-Devices. See
[Nelko P21 cups](Nelko/P21/cups/) and [Aimotech D30 cups](Aimotech/D30/cups/).
