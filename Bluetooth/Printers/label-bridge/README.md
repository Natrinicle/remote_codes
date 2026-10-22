# Label print bridge

Userspace print path for the three packed label printers. A Windows,
Linux, or macOS computer that can see the printer over Bluetooth
rasters the page and writes the recovered wire protocol. Phones on the
same Wi‑Fi print through that computer.

This is **not** a WHQL kernel driver, an App Store app, or an AirPrint
accessory that talks Bluetooth from the phone. iPhone apps that open
BLE GATT need a paid Apple developer account. The LAN bridge does not.

Helpers in the brand folders still print payloads only. This client is
the one that opens BLE or RFCOMM.

| Printer | Transport | Packed encoder |
|---------|-----------|----------------|
| [NIIMBOT B1](../NIIMBOT/B1/) | BLE GATT `e7810a71` / `bef8d6c9` | `encode_niimbot.py` |
| [Nelko P21](../Nelko/P21/) | BLE GATT `0000ff00` / `ff02` | `encode_nelko.py` |
| [Aimotech D30](../Aimotech/D30/) | Classic SPP `00001101` | `encode_aimotech.py` |

Frames are recovered from the official apps. Live print on a unit is
**unproven in the pack session** until someone runs `print` against a
powered printer.

## What each OS actually uses

| Client | How it prints |
|--------|----------------|
| Windows | Run the bridge on that PC. Add an IPP printer at `http://127.0.0.1:8631/ipp/print`, or open the web page, or `labelbridge.py print`. |
| Android | Same Wi‑Fi as the PC. Chrome to `http://PC:8631/`, or the system print sheet via Mopria/IPP. Official vendor apps still work as a fallback. |
| iPhone / iPad | Same Wi‑Fi. Safari to `http://PC:8631/` (photo upload), or AirPrint if the phone sees the Bonjour `_ipp._tcp` name. No Apple developer fee. |
| Linux / macOS | Same `serve` process, or copy `cups/backend-labelbridge` to the CUPS backend directory. |

Web Bluetooth in Chrome cannot open classic SPP (Aimotech) and is
blocked on plain `http://LAN` (not a secure context). The upload page
avoids that: the phone never speaks Bluetooth.

Do **not** port-forward 8631. The IPP listener is a LAN print service
with no login, which is how home AirPrint works.

## Install (Windows)

1. Python 3.11+ from python.org, with **Add python.exe to PATH**.
2. Pair the printer in Windows Bluetooth settings. NIIMBOT PIN is
   `0000` or `1234`. Aimotech shows up as a serial (COM) port.
3. In this folder:

```
py -3 -m pip install -r requirements.txt
py -3 labelbridge.py scan
py -3 labelbridge.py serve --model nelko-p21 --address AA:BB:CC:DD:EE:FF
```

Allow Python through the private-network firewall when Windows asks.
`print-server.bat` installs requirements and runs `serve`; pass the
same `--model` / `--address` flags.

Aimotech on Windows:

```
py -3 labelbridge.py serve --model aimotech-d30 --spp-port COM7
```

COM port list is on the last lines of `scan` (`COMx (serial)`).

## Install (Linux / macOS)

```
python3 -m pip install -r requirements.txt
python3 labelbridge.py scan
python3 labelbridge.py serve --model niimbot-b1 --address AA:BB:CC:DD:EE:FF
```

CUPS (as root), URI includes the Bluetooth address:

```
install -m 0755 cups/backend-labelbridge /usr/lib/cups/backend/labelbridge
lpadmin -p NelkoP21 -v labelbridge://nelko-p21/AA:BB:CC:DD:EE:FF -E
```

## CLI

```
./labelbridge.py self-test
./labelbridge.py scan
./labelbridge.py print photo.png --model nelko-p21 --address AA:BB:… --fit width
./labelbridge.py print photo.png --model nelko-p21 --dry-run
./labelbridge.py serve --model nelko-p21 --address AA:BB:… --bind 0.0.0.0 --port 8631
```

`--fit contain` (default on `serve`) scales the whole page onto one
label. `--fit width` keeps aspect and lets the label grow in the feed
direction (capped). `--dry-run` rasters and encodes and does not open
Bluetooth.

`--bind 127.0.0.1` keeps IPP on the PC. Phones need `0.0.0.0` (default)
on a private LAN.

## IPP / AirPrint

- Queue: `ipp://PC:8631/ipp/print` (also `http://PC:8631/ipp/print`)
- PDLs: PNG, JPEG, PDF (`pypdfium2`), Apple URF
- mDNS type `_ipp._tcp`, TXT `URF=` + `pdl` includes `image/urf`
- `_universal` subtype is best-effort (python-zeroconf)

If the iPhone print sheet is empty, open Safari to `http://PC:8631/`
and upload the photo. Windows “The printer that I want isn’t listed” →
IPP URL works without Bonjour.

## Limits

- One job at a time. One BLE central at a time on the printer.
- 12 mm heads (P21, D30) make a narrow strip of a phone photo. Design
  labels at 96×N dots, 203 dpi, or accept contain-fit.
- NIIMBOT B1 is 384 dots / 48 mm. Handshake and 10 ms write pacing come
  from that encoder README.
- Aimotech D30 in Print Master 5.23.1 is classic SPP. There is no GATT
  table to pack. Pairing + COM/RFCOMM is required.
- Official vendor iOS/Android apps remain the vendor-supported path.

## Checks

```
python3 labelbridge.py self-test
```
