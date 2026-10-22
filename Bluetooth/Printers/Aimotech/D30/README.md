# Aimotech D30 (Bluetooth SPP)

12 mm 203 dpi thermal label printer. Official Android app is **Print
Master** (`com.project.aimotech.printmaster` 5.23.1, 小标打印). The
printer SDK is `com.project.aimotech.printer` (Quin / Labelife). Phomemo
D30 units use the same `D30Printer` class.

Recovered from this XAPK (`PrintMaster_5.23.1_APKPure.xapk`). Helpers
print payloads. They do not scan, GATT-connect, or open RFCOMM. Frames
are **unproven on a live D30 this session**.

This APK's connect path is **classic SPP**, not GATT. Dual-mode BLE
GATT UUIDs were not in the decompiled printer package. Do not invent
`FFE0`. LAN IPP / phone web upload (PC holds the RFCOMM socket):
[label-bridge](../../label-bridge/).

## Identification

| | |
|--|--|
| Maker | Aimotech (Quin / Phomemo family) |
| App | Print Master `com.project.aimotech.printmaster` |
| Class | `D30Printer` extends `QuinPrinter` |
| Printhead | 96 dots / 12 mm (`D30Printer.N = 12`) |
| Catalog | DefaultPrinter.json series D30 (largest group) |

TSPL ASCII (`CXTspl` / `B246DPrinter` / `M128Printer`) is a different
family in the same APK. This folder is the D30 `GS v 0` path. Do not
send NIIMBOT `55 55` XOR or Nelko `SIZE`/`GAP` TSPL here.

## Bluetooth

`BluetoothKit.m` always constructs `BluetoothSPP`. Discovery is classic
`startDiscovery` / `ACTION_FOUND`.

| | UUID | Role |
|--|------|------|
| RFCOMM SPP | `00001101-0000-1000-8000-00805f9b34fb` | default socket |
| Insecure RFCOMM | `fa87c0d0-afac-11de-8a39-0800200c9a66` | only when `BluetoothService.f49933f` is true |

Writes go `QueueBluetooth` → `BluetoothKit.B` → `BluetoothSPP.k`.

## Frames

After connect (`PrinterKit`):

```
1F 11 38
1F 11 12
1F 11 13
1F 11 07
```

Print (`D30Printer.q1`, `PrinterInfo.f48163n` path):

```
ESC @                         1B 40
GS v 0 m=0 + img2Nv           1D 76 30 00 | xL xH yL yH | raster
ESC d 23                      1B 64 17
```

`img2Nv(bitmap, 128, true)` prefixes little-endian width-bytes and
height, then 1bpp packed **bottom-right to top-left**. Dark is red
channel `< 128`. Multi-copy `r1` uses `1F 11 21` plus a copies byte
when `f49845p != 0`.

`InsSet.Y` is `{29, 118, 48, 0}`. `DtsUtil.f18847w` in `ESC d` is
**100** (`0x64`).

## Helper

```
./encode_aimotech.py self-test
./encode_aimotech.py handshake
./encode_aimotech.py print-seq --width-bytes 12 --height 1
./encode_aimotech.py decode 1d7630000c000100000000000000000000000000
```
