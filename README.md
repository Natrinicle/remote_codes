# remote_codes

Infrared remotes captured with a Flipper Zero, plus BLE protocol notes
for devices that do not speak IR.

Copy a `.ir` file onto the Flipper SD card under `infrared/` (or a subfolder) and open it from **Infrared → Saved Remotes**. Parsed NEC entries work on stock firmware. The Carrier Air V file is raw 38 kHz because that remote sends a 36-bit state frame, not a one-shot NEC command.

BLE units are under [Bluetooth](Bluetooth/). They are not Flipper files; use the unit `encode_*.py` and a BLE central.

## Catalog

Browse from [Infrared](Infrared/) or [Bluetooth](Bluetooth/): type → brand → model. Each of those folders has its own README.

| Device | Path | File | Protocol |
|--------|------|------|----------|
| HAPPRUN H1 projector | [Infrared/Projectors/Haprun/H1](Infrared/Projectors/Haprun/H1/) | `Haprun_H1.ir` | NEC, address `0x02` |
| Carrier Air V ceiling cassette | [Infrared/HVAC/Carrier/Air V](Infrared/HVAC/Carrier/Air%20V/) | `Carrier_Air_V.ir` | 36-bit pulse-distance, 38 kHz |
| Sony UBP-X700 Ultra HD Blu-ray | [Infrared/Bluray_Players/Sony/UBP-X700](Infrared/Bluray_Players/Sony/UBP-X700/) | `Sony_UBP-X700.ir` | SIRC20 address `5A 1C` |
| HeatGenie parking diesel heater | [Bluetooth/HVAC/Bogu/HeatGenie](Bluetooth/HVAC/Bogu/HeatGenie/) | `encode_heatgenie.py` | BLE 181A / 3A00-3A01, AA+CRC16 |

## Layout

```
Infrared/
  Bluray_Players/Sony/UBP-X700/
  HVAC/Carrier/Air V/
  Projectors/Haprun/H1/
Bluetooth/
  HVAC/Bogu/HeatGenie/
```

`Device type / brand / model`, same idea as Flipper-IRDB. Button names on ACs encode the full state (`Cool_75_Auto`) because those remotes do not send "temperature up" as an independent command. If a folder moves, every README that linked to it has to move with it.

## Adding another capture

IR:

1. Learn the remote on the Flipper (save as `.ir`).
2. Drop it in a new `Infrared/<type>/<brand>/<model>/` folder.
3. Add a README with a photo, the protocol, and a button map.
4. Prefer `Brand_Model.ir` filenames (underscores, no spaces) so they survive FAT and match Flipper-IRDB.

BLE: same type/brand/model tree under `Bluetooth/`. Put framing in `encode_*.py` and the unit README. Do not commit APKs. Recover unknown framing with **reverse-engineering-protocols**.

Photos in this repo are deskewed, background-removed, and cleaned of dirt. Button artwork is not redrawn.

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
| `skill-toolkit-sync` | [`.claude/rules/skill-toolkit-sync.md`](.claude/rules/skill-toolkit-sync.md) |
| `skill-composition` | [`.claude/rules/skill-composition.md`](.claude/rules/skill-composition.md) |

Use the skills for new captures: photos (cutout onto white for dense I/O; keep
camera files as `*.ignore.jpg`), FCC plates, README tree, raw IR decode, encode
scripts. After a folder move, run
`python3 .claude/skills/flipper-ir-library/scripts/check_readme_links.py`.

Edits to a skill or rule are copied into this toolkit in the same turn; you
will be asked before other toolkit repos are updated.

## License

[CC0 1.0](LICENSE). Codes and photos are dedicated to the public domain. Brand names remain the manufacturers'.
