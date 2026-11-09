# MELK

RGBIC LED controllers that advertise `MELK-*` and speak Magic Lantern /
duoCo StripX 9-byte `7E…EF` frames on GATT `FFF0`. Magic Lantern
6.11.10 accepts GAP names that start with `MELK-` and, in this
`duoCoStrip` build, whose BLE address string contains `BE`.

The OA10 helper is the protocol encoder for every `MELK-*` name the app
would accept. Product card [OA10](OA10/) is the recovered RGBIC unit
(`MELK-OA10` / `MELK-OA10W`, generic `MELK-`, no DeviceName `MELK-OA`).

`./encode_magic_lantern.py devices --list` prints the filter, GATT,
DeviceName prefixes, and feature gates. `devices match NAME [MAC]`
applies the same rules (MAC check skipped when the address is omitted).

| Prefix / check | Scenes | Mic UI | Notes | Encoder |
|----------------|--------|--------|-------|---------|
| `MELK-` generic (OA10 / OA10W) | hide | show | no DeviceName `MELK-OA`; OA10W matches W-regex | [OA10 `encode_magic_lantern.py`](OA10/encode_magic_lantern.py) |
| `MELK-OB` | hide | hide | DeviceName | same |
| `MELK-OC` | show | show | DeviceName | same |
| `MELK-OE` | hide | hide | DeviceName | same |
| `MELK-OT` | show | show | DeviceName | same |
| `MELK-TX` | hide | hide | DeviceName | same |
| `^MELK-.+W.*` | — | — | RGBIC / W-suffix, CASE_INSENSITIVE | same |
| `^MELK-.+CT.*` | — | — | CCT family, CASE_INSENSITIVE | same |
| name contains `MELK-DYDS` | — | — | extra effect 156 Exploding star; not OA10 default | same |

Analog `ELK-BLEDOM` is not a Magic Lantern-supported family. Do not add
an analog card. Analog `[7]=0x00` is the wrong RGBIC render target.

| Model | Path |
|-------|------|
| OA10 | [OA10](OA10/) |
