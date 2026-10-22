# NIIMBOT B1 (BLE)

BLE protocol for the NIIMBOT B1 203 dpi thermal label printer (retail
20–48 mm, 1500 mAh, Type-C + BLE). Official Android app is **NIIMBOT**
(`com.gengcon.android.jccloudprinter`). Home-line app is **NIIM**
(`com.niimbot.cxprinter`). Desktop installer is on niimbot.com
downloadCenter (Windows B1 series).

Recovered from the vendor OSS APK (`JCYDY_GOOGLE.apk`): Flutter
`niimbot_connector` / `NiimbotBluetoothPrinter` plus native
`com.gengcon.www.jcprintersdk` (`B1PrinterInfoGetter` /
`B1PrinterInfoSetter`, `CommandId`, `sendPrintStart`, `sendPageStart`,
`HeartbeatThread`, `checkSumConsistent`, `xorEnd`,
`MyBluetoothGattCallback.writeCharacteristic`). Compact GATT UUID bytes
were not in unpacked `libapp.so` / `libdatajar.so` strings (packed SDK
zip is malformed). This pack uses the family UART-style table below. Do
not send HeatGenie `181A` / `FFE0` / `AA55` here.

Helpers print payloads. They do not scan or GATT-connect. Frames are
**unproven on a live B1 this session**.

USB Type-C CDC sibling (same `55 55` bytes, VID/PID not recovered):
[Serial/Printers/NIIMBOT/B1](../../../../Serial/Printers/NIIMBOT/B1/).
LAN IPP / phone web upload: [label-bridge](../../label-bridge/).

## Identification

| | |
|--|--|
| Maker | Wuhan Jingchen Intelligent Identification Technology |
| Apps | NIIMBOT `com.gengcon.android.jccloudprinter`; NIIM `com.niimbot.cxprinter` |
| Advertised name | starts `B1` (B1 and B1 Pro share this prefix) |
| Model id (`0x40` key `08`) | B1 = 4096 (`0x1000`); B1 Pro = 4097 (`0x1001`); B1 SE = 4098 (`0x1002`) |
| Task | B1 / B1 SE = `b1` (protocol 3, 203 dpi, 384 px); B1 Pro = `v4` (protocol 5, 300 dpi, 567 px) |
| Printhead | 384 dots / 48 mm @ 203 dpi |
| Pairing | PIN `0000` or `1234` |
| RFID | 13.56 MHz consumable tag (`0x1A`) |
| Series ids (app JSON) | `10003,10040,10043` → B1, B1 Pro, B1 SE |

Query `PrinterInfo 0x40[08]` after connect. The advertised name cannot
tell B1 from B1 Pro.

## GATT

Some units also advertise ISSC UART `49535343-…`. Replies still arrive
on `bef8d6c9-…`. One characteristic is TX and RX.

| | UUID | Role |
|--|------|------|
| Service | `e7810a71-73ae-499d-8c15-faa9aef0c3f2` | UART-style |
| Char | `bef8d6c9-9c21-4c9e-b632-bd58c1009f9f` | notify + write **without** response |

Classic SPP `00001101-0000-1000-8000-00805f9b34fb` is in the SDK for
other models (B21 SPP tree). B1 is the GATT `B1Printer*` path.

Buffer notifications and cut on `55 55`. Several frames can share one
notify; one frame can split across notifies. Unsolicited `0xD3` / `0xE0`
can appear mid-exchange.

WRITE_NO_RESPONSE has no per-write ack. B1 drops bitmap rows if unpaced
(clips around 120 px). Pace about **10 ms** per write. Concatenate frames
up to ~240 B per write within the MTU. This helper does not pace or
bundle; it prints hex.

A unit can show two BLE addresses. One central at a time.

## Frames

```
55 55 | cmd | len | data[len] | bcc | AA AA
```

`bcc` is `cmd XOR len XOR each data byte`. Multi-byte integers in setup
are **big-endian** except the `0x85` black-pixel total (little-endian).
Total size is `len + 7`.

Connect (`0xC1`) prepends `03` to the whole frame:
`03 55 55 C1 01 01 C1 AA AA`. No other command gets that prefix.

| Request | Name | Typical payload | Response |
|---------|------|-----------------|----------|
| `0xC1` | Connect | `01` (+ `03` prefix) | `0xC2` |
| `0xA5` | PrinterStatusData | `01` | `0xB5` |
| `0x40` | PrinterInfo | key `u8` | `0x40 + key` |
| `0xDC` | Heartbeat | `04` | `0xD9` (type `04`) |
| `0x21` | SetDensity | `01`–`05` (default `03`) | `0x31` |
| `0x23` | SetLabelType | `01` (gap stock) | `0x33` |
| `0x01` | PrintStart | 7 bytes (`b1`) or 9 bytes (`v4`) | `0x02` |
| `0x03` | PageStart | `01` (`b1` only) | `0x04` |
| `0x13` | SetPageSize | 6 bytes (`b1`) or 13 bytes (`v4`) | `0x14` |
| `0x84` | PrintEmptyRow | `row:u16` + `count:u8` | none |
| `0x85` | PrintBitmapRow | total-mode header + 1bpp row | none |
| `0xE3` | PageEnd | `01` | `0xE4` |
| `0xA3` | PrintStatus | `01` | `0xB3` (`page:u16`, print %, feed %) |
| `0xF3` | PrintEnd | `01` | `0xF4` (`data[0]==0` refused) |
| `0x1A` | RfidInfo | `01` | `0x1B` |
| `0xDA` | CancelPrint | `01` | `0xD0` |
| `0xDB` | PrintError | (unsolicited / out of order) | — |

PrinterInfo keys used in the B1 handshake: `08` model, `0b` serial,
`0d` MAC, `0a` battery, `07` shutdown, `03` label, `0c` hw, `09` sw.
Also `01` density, `02` speed, `0f` area.

Bitmap row (`0x85`, **total mode**):

`row:u16 | 00 | black_lo black_hi | run | row_bytes`

`row_bytes` is `ceil(width/8)`, 1 bit per pixel, MSB first, set = black.
`black_*` is the popcount of that row, little-endian. `run` repeats the
row (keep ≤ 200). Empty runs use `0x84` instead of a zero bitmap.

Do **not** send the 4-byte SetPageSize form on B1 (blank first page or
runaway copies). Use 6 bytes: `H:u16 | W:u16 | copies:u16`.

Do **not** mix `b1` and `v4`. `v4` is 9-byte PrintStart (pages + zeros +
speed + flag), no PageStart, 13-byte SetPageSize. Default `--task b1`.

## Print flow (`b1`, protocol 3)

Handshake is required. Without it, density / page-size **ack** and the
printer never images: no `0xE4`, status stuck, paper idle.

```
Connect 0xC1 (prefix 03)
PrinterStatusData 0xA5[1]
PrinterInfo 0x40 for 08 0b 0d 0a 07 03 0c 09
Heartbeat 0xDC[04]
SetDensity 0x21
SetLabelType 0x23
PrintStart 0x01  7 bytes [pages_hi pages_lo 00 00 00 00 00]
PageStart 0x03[1]
SetPageSize 0x13  6 bytes [H W copies]
rows 0x84 / 0x85
PageEnd 0xE3[1]
poll PrintStatus 0xA3 until page >= 1  (timeout ~25 s)
PrintEnd 0xF3[1]
```

Poll after `0xE4`. Ending the job at PageEnd cuts the label off.
`PrintStart` pages and SetPageSize copies should match for N identical
labels (bitmap crosses the air once).

```text
./encode_niimbot.py self-test
./encode_niimbot.py connect
./encode_niimbot.py handshake
./encode_niimbot.py density 3
./encode_niimbot.py print-seq --height 320 --width 384
./encode_niimbot.py --task v4 print-start --pages 1 --speed 3
./encode_niimbot.py decode 555521010323aaaa
```

## Notes

- Own hardware / own copy only. Do not commit APKs.
- Default encoder task is `b1` (B1 384 px / 203 dpi).
- Width must not exceed the printhead (384 on B1, 567 on B1 Pro).
- Official vendor APK names: `JCYDY_GOOGLE.apk`, `JCYDY.apk`,
  `chenyin.apk` on `oss.niimbot.com`. iOS: App Store `id1359104615`
  (NIIMBOT), `id1556769120` (NIIM).
