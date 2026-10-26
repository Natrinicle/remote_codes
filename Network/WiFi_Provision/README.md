# WiFi provision

Print-only dest / length maps for LAN Wi-Fi provision shouts. Helpers do
not bind sockets or send UDP. Do not pass a live SSID or PSK.

Product cards (brand / SKU) stay under [Scales](../Scales/) and other
device trees. Protocol bytes live here so a second product can reuse them.

| Protocol | Path | Helper |
|----------|------|--------|
| Ogemray SmartConfig | [Ogemray](Ogemray/) | [`encode_ogemray.py`](Ogemray/encode_ogemray.py) |
| ESP-TOUCH (Espressif) | [ESP_TOUCH](ESP_TOUCH/) | [`encode_esptouch.py`](ESP_TOUCH/encode_esptouch.py) |
| Router | this folder | [`encode_wifi_provision.py`](encode_wifi_provision.py) |

## Routing table

[`encode_wifi_provision.py`](encode_wifi_provision.py) does not reimplement
crypto. It dispatches on protocol alias, SKU, or `setupType`.

| Match | Backend |
|-------|---------|
| `ogemray`, `smartconfig`, `wifi` | [Ogemray/encode_ogemray.py](Ogemray/encode_ogemray.py) |
| `esptouch`, `esp-touch`, `esp_touch`, `espTouchWifi` | [ESP_TOUCH/encode_esptouch.py](ESP_TOUCH/encode_esptouch.py) |
| SKU **0396**, **0385** (`setupType` `wifi`) | Ogemray |
| SKU **0384**, **0397** (`setupType` `espTouchWifi`) | ESP-TOUCH |
| cmd `ap` | Ogemray `ap` (same blob, TCP **192.168.1.1:10001**) |
| `self-test` | both backends; prints `ok` once |

Example products recovered from: Greater Goods Weight Gurus
(`com.dmdbrands.gurus.weight`). Product card:
[Scales/Greater_Goods/0396](../Scales/Greater_Goods/0396/).

## Commands

```
./encode_wifi_provision.py ogemray --ssid TestSSID --password TestPass
./encode_wifi_provision.py esptouch --ssid TestSSID --password TestPass
./encode_wifi_provision.py ap --ssid TestSSID --password TestPass
./encode_wifi_provision.py --sku 0396 --ssid TestSSID --password TestPass
./encode_wifi_provision.py --protocol esptouch --ssid TestSSID --password TestPass \
    --bssid AA:BB:CC:DD:EE:FF --local-ip 192.0.2.10
./encode_wifi_provision.py self-test
```

Or call a backend directly:

```
./Ogemray/encode_ogemray.py ogemray --ssid TestSSID --password TestPass
./ESP_TOUCH/encode_esptouch.py esptouch --ssid TestSSID --password TestPass
```

## Add a backend

Drop `Network/WiFi_Provision/<Protocol>/encode_<protocol>.py` next to that
protocol’s README, then add one row each in `PROTOCOL_ALIASES` /
`SKU_TO_BACKEND` / `BACKENDS` inside `encode_wifi_provision.py`. Pack rule:
[pack-artifact-names](../../.claude/rules/pack-artifact-names.md).

Do not commit APKs, live SSIDs, or PSKs. Do not port-forward 7070, 7001,
7777, 8888, or 10001.
