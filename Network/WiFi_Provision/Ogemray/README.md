# Ogemray SmartConfig

Wi-Fi provision that encodes SSID + PSK in the **IPv4 multicast
destination**, not in UDP length.

Use [`encode_ogemray.py`](encode_ogemray.py) to print dest maps. The
script does not bind ports or send packets. A live shout airs the SSID
and PSK; keep `--ssid` / `--password` as test values.

## Recovered from

Greater Goods Weight Gurus SKU **0396** and **0385** (`setupType` `wifi`),
app `com.dmdbrands.gurus.weight`. AP prefix `gg_SmartScale_`. Product
card: [Scales/Greater_Goods/0396](../../Scales/Greater_Goods/0396/).

The 2018 Greater Goods support note called this a proprietary protocol
similar to TI SmartConfig. The APK class is
`ogemray.android.smartconnection.SmartConfig`.

## Plan A — multicast dests

`StartSmartConfig` builds a headered blob, CRC-16 (table poly 0x1021,
init **4129**), then `(b XOR 0x5C) + 158` (Java byte wrap). Each
encrypted pair is sent as:

| | |
|--|--|
| Dest | `239.{pair_index}.{b0}.{b1}` |
| UDP dest port | **7070** |
| Bind (app) | MulticastSocket **7777** |
| Payload | ASCII `multicastmsg` (12 B, constant) |
| Interval | 20 ms |
| TTL | 4 |

802.11 DA is `01:00:5E` plus the lower 23 bits of that IPv4. Header:

```
[total_len][ssid_len][pwd_len][extra_len][0][0] + SSID + PWD + extra + CRC16_BE
```

`total_len` is the unpadded size when the buffer is padded to even.
`extra` is empty when `userNumber` is 0; otherwise 1 + 32-byte token
(33 bytes).

```
./encode_ogemray.py ogemray --ssid TestSSID --password TestPass
```

## Plan B — AP

Join `gg_SmartScale_*`, then TCP **`192.168.1.1:10001`** with the same
encrypted blob as Plan A (`ConfigByAP.asynSmartConfigByAP`).

```
./encode_ogemray.py ap --ssid TestSSID --password TestPass
```

Router (SKU / alias dispatch):
[`../encode_wifi_provision.py`](../encode_wifi_provision.py).

```
../encode_wifi_provision.py --sku 0396 --ssid TestSSID --password TestPass
../encode_wifi_provision.py ap --ssid TestSSID --password TestPass
./encode_ogemray.py self-test
```

Do not commit APKs, live SSIDs, or PSKs. Do not port-forward 7070, 7777,
or 10001.
