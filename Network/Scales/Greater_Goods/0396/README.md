# Weight Gurus WiFi Smart Body scale (0396)

[Greater Goods](../) · [Scales](../../) · [Network](../../../)

Greater Goods SKU **0396**, sold as Weight Gurus WiFi Scale. Radio is a
MediaTek **MT7681**. The Android app is **Weight Gurus**
(`com.dmdbrands.gurus.weight`). Provision is 2.4 GHz only.

This folder is a **product card**. Flipper IR does not apply. BLE does
not apply. Provision shouts live under
[Network/WiFi_Provision](../../../WiFi_Provision/):

| This SKU | Protocol | Helper |
|----------|----------|--------|
| 0396 / 0385 (`setupType` `wifi`) | [Ogemray](../../../WiFi_Provision/Ogemray/) | [`encode_ogemray.py`](../../../WiFi_Provision/Ogemray/encode_ogemray.py) |
| siblings 0384 / 0397 (`espTouchWifi`) | [ESP-TOUCH](../../../WiFi_Provision/ESP_TOUCH/) | [`encode_esptouch.py`](../../../WiFi_Provision/ESP_TOUCH/encode_esptouch.py) |
| SKU / alias dispatch | [WiFi_Provision](../../../WiFi_Provision/) | [`encode_wifi_provision.py`](../../../WiFi_Provision/encode_wifi_provision.py) |

Helpers print dest maps and UDP-length lists. They do not bind ports or
send packets. A live shout airs the SSID and PSK; keep `--ssid` /
`--password` as test values.

## Identification

| | |
|--|--|
| Retail name | Weight Gurus WiFi Scale |
| OEM | Greater Goods |
| SKU | 0396 |
| App | Weight Gurus `com.dmdbrands.gurus.weight` |
| Radio | MT7681 |
| App `setupType` | `wifi` (Ogemray, same as 0385) |
| AP backup SSID prefix | `gg_SmartScale_` |
| Error **t204** | WiFi chip cannot broadcast the scale AP |

Sibling SKUs in the same app: **0385** also `wifi` / Ogemray; **0384**
and **0397** are `espTouchWifi`.

## Plan A — Ogemray SmartConfig (0396)

Dest `239.{pair_index}.{b0}.{b1}`, UDP **7070**, payload ASCII
`multicastmsg`. Full frame notes:
[Ogemray README](../../../WiFi_Provision/Ogemray/).

```
../../../WiFi_Provision/encode_wifi_provision.py --sku 0396 \
    --ssid TestSSID --password TestPass
../../../WiFi_Provision/Ogemray/encode_ogemray.py ogemray \
    --ssid TestSSID --password TestPass
```

## Plan B — scale AP

Join `gg_SmartScale_*`, then TCP **`192.168.1.1:10001`** with the same
Ogemray blob. Error **t204** means the chip cannot broadcast that AP.

```
../../../WiFi_Provision/encode_wifi_provision.py ap \
    --ssid TestSSID --password TestPass
```

## ESP-TOUCH (0384 / 0397)

Same app, different `setupType`. GuideCode **515, 514, 513, 512**,
DatumCode `EXTRA_LEN` 40, UDP **7001**. Notes:
[ESP-TOUCH README](../../../WiFi_Provision/ESP_TOUCH/).

```
../../../WiFi_Provision/encode_wifi_provision.py --sku 0384 \
    --ssid TestSSID --password TestPass
```

## MT7681 chip SMTCN v1 (not in the app)

The module can listen for MediaTek IoTManager SMTCN v1: sync dests
`234.18.18.18` / `234.19.19.19` / `234.20.20.20`, data
`234.{0x15+i}.{b0}.{b1}`, UDP **8888**, payload 19 B
`MUTICAST TEST DATA`, AES-128-ECB key ASCII `McdwCnwCdss2_18p`.
Weight Gurus does not ship `libSmartConnection.so`. There is no SMTCN
helper in this pack.

```
../../../WiFi_Provision/encode_wifi_provision.py self-test
```

Do not commit APKs, live SSIDs, or PSKs. Do not port-forward 7070,
7001, 7777, 8888, or 10001.
