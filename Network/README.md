# Network

LAN and Wi-Fi collector protocol notes, grouped by device type. Same
type / brand / model tree as [Infrared](../Infrared/). These are not
Flipper `.ir` files. Direct USB UART / HID / RS485 / CAN live under
[Serial](../Serial/). BLE GATT lives under [Bluetooth](../Bluetooth/).

Helpers print payloads. They do not bind hijack ports. Do not
port-forward collector UDP or TCP.

Reusable provision shouts sit under [WiFi_Provision](WiFi_Provision/).
[Scales](Scales/) folders are product cards that point at those
protocols. [Displays](Displays/) is Holofan HTTP holographic fans
(print-only `encode_holofan.py`; do not join the SoftAP from the helper).

| Type | Path |
|------|------|
| Displays | [Displays](Displays/) |
| WiFi provision | [WiFi_Provision](WiFi_Provision/) |
| Inverters | [Inverters](Inverters/) |
| Scales | [Scales](Scales/) |
