# remote_codes

Infrared remotes captured with a Flipper Zero, plus BLE, LAN, and USB
serial protocol notes for devices that do not speak IR.

Copy a `.ir` file onto the Flipper SD card under `infrared/` (or a subfolder) and open it from **Infrared → Saved Remotes**. Parsed NEC entries work on stock firmware. The Carrier Air V file is raw 38 kHz because that remote sends a 36-bit state frame, not a one-shot NEC command.

BLE units are under [Bluetooth](Bluetooth/). LAN collectors and inverter
tunnels are under [Network](Network/). USB UART, USB HID, and RS485
inverter/BMS families are under [Serial](Serial/). Those trees are not
Flipper files; use the unit `encode_*.py`.

## Catalog

Browse from [Infrared](Infrared/), [Bluetooth](Bluetooth/),
[Network](Network/), or [Serial](Serial/): type → brand → model. Each of
those folders has its own README.

| Device | Path | File | Protocol |
|--------|------|------|----------|
| HAPPRUN H1 projector | [Infrared/Projectors/Haprun/H1](Infrared/Projectors/Haprun/H1/) | `Haprun_H1.ir` | NEC, address `0x02` |
| FUDONI GC888 projector | [Infrared/Projectors/Fudoni/GC888](Infrared/Projectors/Fudoni/GC888/) | `Fudoni_GC888.ir` | NECext, address `0x1608` |
| Carrier Air V ceiling cassette | [Infrared/HVAC/Carrier/Air V](Infrared/HVAC/Carrier/Air%20V/) | `Carrier_Air_V.ir` | 36-bit pulse-distance, 38 kHz |
| Sony UBP-X700 Ultra HD Blu-ray | [Infrared/Bluray_Players/Sony/UBP-X700](Infrared/Bluray_Players/Sony/UBP-X700/) | `Sony_UBP-X700.ir` | SIRC20 address `5A 1C` |
| ETD-360 solar street light | [Infrared/Lights/ETD/ETD-360](Infrared/Lights/ETD/ETD-360/) | `ETD_ETD-360.ir` | NEC, address `0x00` |
| BLS-70-25RC LED solar light bulb | [Infrared/Lights/BLS/BLS-70-25RC](Infrared/Lights/BLS/BLS-70-25RC/) | `BLS_BLS-70-25RC.ir` | NEC, address `0x80` |
| HeatGenie parking diesel heater | [Bluetooth/HVAC/Bogu/HeatGenie](Bluetooth/HVAC/Bogu/HeatGenie/) | `encode_heatgenie.py` | BLE 181A / 3A00-3A01, AA+CRC16 |
| EyeBond SmartESS Wi-Fi collector | [Network/Inverters/EyeBond/SmartESS](Network/Inverters/EyeBond/SmartESS/) | `encode_smartess.py` | UDP 58899 / TCP 8899, SRNE Modbus RTU |
| Ogemray SmartConfig | [Network/WiFi_Provision/Ogemray](Network/WiFi_Provision/Ogemray/) | `encode_ogemray.py` | dest `239.i.b0.b1` UDP 7070 `multicastmsg` |
| ESP-TOUCH (Espressif) | [Network/WiFi_Provision/ESP_TOUCH](Network/WiFi_Provision/ESP_TOUCH/) | `encode_esptouch.py` | GuideCode 515/514/513/512 UDP 7001 |
| Weight Gurus WiFi scale 0396 | [Network/Scales/Greater_Goods/0396](Network/Scales/Greater_Goods/0396/) | product card | Greater Goods SKU 0396; shouts via Ogemray / ESP-TOUCH helpers |
| SRNE hybrid USB UART | [Serial/Inverters/SRNE](Serial/Inverters/SRNE/) | `encode_srne.py` | Modbus RTU FC3/FC6, 9600 8N1 |
| Voltronic Axpert / InfiniSolar | [Serial/Inverters/Voltronic](Serial/Inverters/Voltronic/) | `encode_voltronic.py` | ASCII QPIGS HID or UART |
| JBD / Xiaoxiang BMS | [Bluetooth/BMS/JBD](Bluetooth/BMS/JBD/) | `encode_jbd.py` | BLE GATT `FF00` / `FF01` / `FF02`, `DD A5` / `77` |
| NIIMBOT B1 label printer | [Bluetooth/Printers/NIIMBOT/B1](Bluetooth/Printers/NIIMBOT/B1/) | `encode_niimbot.py` | BLE GATT `e7810a71` / `bef8d6c9`, `55 55` XOR |
| Nelko P21 label printer | [Bluetooth/Printers/Nelko/P21](Bluetooth/Printers/Nelko/P21/) | `encode_nelko.py` | RFCOMM ch1 TSPL2 (GATT `ff02` same bytes); CUPS [printer-driver-nelko](Bluetooth/Printers/Nelko/P21/cups/) |
| Aimotech D30 label printer | [Bluetooth/Printers/Aimotech/D30](Bluetooth/Printers/Aimotech/D30/) | `encode_aimotech.py` | Classic SPP `00001101`, ESC/POS `GS v 0`; CUPS [printer-driver-aimotech](Bluetooth/Printers/Aimotech/D30/cups/) |
| Label print bridge (Windows/Linux/phones) | [Bluetooth/Printers/label-bridge](Bluetooth/Printers/label-bridge/) | `labelbridge.py` | IPP/AirPrint + BLE/SPP client |

## Layout

```
Infrared/
  Bluray_Players/Sony/UBP-X700/
  HVAC/Carrier/Air V/
  Lights/BLS/BLS-70-25RC/
  Lights/ETD/ETD-360/
  Projectors/Fudoni/GC888/
  Projectors/Haprun/H1/
Bluetooth/
  HVAC/Bogu/HeatGenie/
  HVAC/Bogu/HeatGenie/esp32-s3/
  BMS/JBD/
  Inverters/Luxpower/
  Printers/NIIMBOT/B1/
  Printers/Nelko/P21/
  Printers/Nelko/P21/cups/
  Printers/Aimotech/D30/
  Printers/Aimotech/D30/cups/
  Printers/label-bridge/
Network/
  WiFi_Provision/Ogemray/
  WiFi_Provision/ESP_TOUCH/
  Inverters/EyeBond/SmartESS/
  Inverters/GoodWe/
  Inverters/Luxpower/
  Scales/Greater_Goods/0396/
Serial/
  Inverters/SRNE/
  Inverters/Voltronic/
  Inverters/GoodWe/
  Inverters/Luxpower/
  BMS/JBD/
  Printers/NIIMBOT/B1/
```

`Device type / brand / model`, same idea as Flipper-IRDB. Button names on ACs encode the full state (`Cool_75_Auto`) because those remotes do not send "temperature up" as an independent command. If a folder moves, every README that linked to it has to move with it.

## Adding another capture

IR:

1. Learn the remote on the Flipper (save as `.ir`).
2. Drop it in a new `Infrared/<type>/<brand>/<model>/` folder.
3. Add a README with a photo, the protocol, and a button map.
4. Prefer `Brand_Model.ir` filenames (underscores, no spaces) so they survive FAT and match Flipper-IRDB.

BLE: same type/brand/model tree under `Bluetooth/`. Put framing in `encode_*.py` and the unit README. Do not commit APKs. Recover unknown framing with **reverse-engineering-protocols**.

LAN: same tree under `Network/`. Helpers print payloads; they do not bind UDP 58899, 7070, 7001, or listen on TCP 8899 / 10001. Do not commit APKs, collector serials, site IPs, SSIDs, or PSKs. Do not port-forward those ports. A SmartConfig shout airs the PSK — print the dest map, do not send it from the helper.

Serial: same tree under `Serial/` for USB UART, USB HID, RS485, and CAN. Helpers print payloads; they do not open `/dev/ttyUSB0` or `/dev/hidraw0`. A CH340 stick is not automatically Voltronic. BLE GATT (including JBD `FF00`) lives under `Bluetooth/`.

Photos in this repo are deskewed, background-removed, and cleaned of dirt. Button artwork is not redrawn. Included user-manual pages ship as `manual-1.jpg`, `manual-2.jpg`, … (local rembg BiRefNet, original pixels).

## Agent toolkit

[`toolkit.yaml`](toolkit.yaml) marks this repo as an **agent toolkit**. Skills and
rules load when the repo is opened in Claude Code or Grok.

| Kind | Path |
|------|------|
| `flipper-ir-library` | [`.claude/skills/flipper-ir-library`](.claude/skills/flipper-ir-library/) (Grok: [`.grok/skills/…`](.grok/skills/flipper-ir-library/)) |
| `decoding-ir-protocols` | [`.claude/skills/decoding-ir-protocols`](.claude/skills/decoding-ir-protocols/) |
| `reverse-engineering-protocols` | [`.claude/skills/reverse-engineering-protocols`](.claude/skills/reverse-engineering-protocols/) |
| `decompile-mobile-app` | [`.claude/skills/decompile-mobile-app`](.claude/skills/decompile-mobile-app/) |
| `decompile-firmware` | [`.claude/skills/decompile-firmware`](.claude/skills/decompile-firmware/) |
| `cups-label-printer` | [`.claude/skills/cups-label-printer`](.claude/skills/cups-label-printer/) (REQUIRED `cups-custom-backend`) |
| `skill-toolkit-sync` | [`.claude/rules/skill-toolkit-sync.md`](.claude/rules/skill-toolkit-sync.md) |
| `skill-composition` | [`.claude/rules/skill-composition.md`](.claude/rules/skill-composition.md) |
| `pack-artifact-names` | [`.claude/rules/pack-artifact-names.md`](.claude/rules/pack-artifact-names.md) |
| `cups-label-queue` | [`.claude/rules/cups-label-queue.md`](.claude/rules/cups-label-queue.md) |

Use the skills for new captures: photos (cutout onto white for dense I/O; keep
camera files as `*.ignore.jpg`), included manuals (`classify_shots.py` then
`cutout_manual.py`), FCC plates, README tree, raw IR decode, encode scripts.
If Flipper saved `type: raw`, run
`python3 .claude/skills/flipper-ir-library/scripts/correct_parsed_ir.py UNIT.ir --write`
before HVAC decode. After a folder move, run
`python3 .claude/skills/flipper-ir-library/scripts/check_readme_links.py`.

Edits to a skill or rule are copied into this toolkit in the same turn; you
will be asked before other toolkit repos are updated.

## Checks

`.pre-commit-config.yaml` runs gitleaks and hygiene. IR captures and photos are excluded so `.ir` files stay byte-stable. `pre-commit install`.

## License

[CC0 1.0](LICENSE). Codes and photos are dedicated to the public domain. Brand names remain the manufacturers'.
