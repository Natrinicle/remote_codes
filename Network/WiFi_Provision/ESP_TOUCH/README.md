# ESP-TOUCH

Espressif length-coding Wi-Fi provision. GuideCode and DatumCode become
**UDP payload lengths**, not multicast dest octets.

Use [`encode_esptouch.py`](encode_esptouch.py) to print dest / length
maps. The script does not bind ports or send packets. A live shout airs
the SSID and PSK; keep `--ssid` / `--password` as test values.

## Recovered from

Greater Goods SKU **0384** and **0397** (`setupType` `espTouchWifi`),
app `com.dmdbrands.gurus.weight` (`com.greatergoods.ggesptouchlib`).
Product card: [Scales/Greater_Goods/0396](../../Scales/Greater_Goods/0396/).

ESP-TOUCH is Espressif’s protocol. This pack’s locked vectors are from
that Greater Goods app, not from Espressif’s own sample.

## Length coding

| | |
|--|--|
| GuideCode `getU8s` | **515, 514, 513, 512** filled with `0x31` |
| DatumCode `EXTRA_LEN` | **40** (`u16 + 40`) |
| UDP dest | **255.255.255.255:7001** (or `234.n.n.n` when broadcast is off) |
| Listen (app) | **18266** |
| Intervals | 8 ms |
| Guide / data / send windows | 2000 / 4000 / 90000 ms |

```
./encode_esptouch.py esptouch --ssid TestSSID --password TestPass \
    --bssid AA:BB:CC:DD:EE:FF --local-ip 192.0.2.10
```

After join, the recovered app opens TCP **:10001** and AES-ECB PKCS5 with
key ASCII `Test20190000000000000000`, JSON `{request:bind,dmac,token}`.
This helper prints the shout lengths only.

Router (SKU / alias dispatch):
[`../encode_wifi_provision.py`](../encode_wifi_provision.py).

```
../encode_wifi_provision.py --sku 0384 --ssid TestSSID --password TestPass
../encode_wifi_provision.py --protocol esptouch --ssid TestSSID --password TestPass \
    --bssid AA:BB:CC:DD:EE:FF --local-ip 192.0.2.10
./encode_esptouch.py self-test
```

Do not commit APKs, live SSIDs, or PSKs. Do not port-forward 7001 or 18266.
