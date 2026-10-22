# Nelko P21 (BLE)

Pocket thermal label printer, 203 dpi, 12 mm printhead. Official Android
app is **Nelko** (`com.nelko.printer` 4.10.1). Cloud catalog
`command` **0** is TSPL. Labelnize and Polono rebrands share the same
JSON (`isEncrypt` 1 is RFID paper, not TSPL payload encryption).

Recovered from this APK (`Nelko_4.10.1_APKPure.apk`): native DEX
`LabelCommand` / `BluetoothHelper.convertPrintData2Bytes` plus BLE
adapter `p313.Ooo`. Helpers print payloads. They do not scan or
GATT-connect. Frames are **unproven on a live P21 this session**.

USB `UsbDevice` listing exists in `com.print.myprinter`. VID/PID was
not recovered from this build, so there is no Serial sibling. LAN IPP /
phone web upload: [label-bridge](../../label-bridge/).

## Identification

| | |
|--|--|
| Maker | Nelko (Ezink / print SDK in the APK) |
| App | Nelko `com.nelko.printer` |
| Cloud model | P21, dpi 203, maxWidth 12 mm, command 0, rfidProtocol 1 |
| Default paper | 14×40 mm GAP, defaultGap 5 mm |
| Transport profile | TSPL (default). AY_ESC / POCKET / YZY_ESC are other models |
| Same TSPL family | P31S, P22, P24, PL80E, PM220, PM220S |

Do not send NIIMBOT `55 55` XOR or Aimotech `GS v 0` here.

## GATT

P21-family pocket BLE (`p313.Ooo`). Request MTU **512**. Connect rejects
classic-only devices (`getType` not LE or dual). Write type **1**
(WRITE_NO_RESPONSE). Pace about **10 ms** on write failure retry.

| | UUID | Role |
|--|------|------|
| Service | `0000ff00-0000-1000-8000-00805f9b34fb` | printer |
| Write | `0000ff02-0000-1000-8000-00805f9b34fb` | TX |
| Notify | `0000ff03-0000-1000-8000-00805f9b34fb` | RX |
| Read | `0000ff01-0000-1000-8000-00805f9b34fb` | RX |

Classic SPP `00001101-0000-1000-8000-00805f9b34fb` is also in the app.
Same TSPL bytes on either path.

Other MCU tables in the same APK (other models, not P21 default):

| Family | Services |
|--------|----------|
| BaiRui | `ff00`, `ff10`, `18f0`, `fee7`, `ff80`, `fff0`, ISSC `49535343-fe7d-4ae5-8fa9-9fafd205e455` |
| JieLi | `1800`, `ff00`, `ae3a`, `ae00` (OTA write `ae01` / notify `ae02`) |
| Inkjet S1 | `ff00`/`ff02`/`ff01`/`ff03` plus classic `00001112` / `00002223` / `00003334`; name prefix `S1_` |

## TSPL

GB18030 (ASCII for this helper). Job from
`BluetoothHelper.convertPrintData2Bytes`:

```
SIZE {w} mm,{h} mm
GAP {gap} mm,0 mm
DIRECTION 0,0
DENSITY {0-15}
CLS
BITMAP x,y,widthBytes,height,mode,<1bpp>
PRINT {copies}
```

`DIRECTION` FORWARD=0, MIRROR NORMAL=0. `BITMAP` mode 0 overwrite, 1 OR,
2 XOR. Payload is 1bpp MSB-first, `widthBytes * height` bytes, then
CRLF. Status query is binary `ESC ! ?` (`1b213f`). Type query is
`~!T\r\n`.

`NativeLib.encryptV2` is a license write (`TestCommandActivity`), not
the print path.

## Helper

```
./encode_nelko.py self-test
./encode_nelko.py job --width-mm 12 --height-mm 40 --payload 80
./encode_nelko.py status
```
