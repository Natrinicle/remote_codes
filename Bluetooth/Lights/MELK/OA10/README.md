# MELK-OA10 (BLE)

BLE protocol for MELK-OA10 RGBIC LED strips that pair with **Magic
Lantern** (`wl.smartled.rgb` 6.11.10, Play / iOS 1479587050,
[magiclantern.app](https://magiclantern.app)). Sibling stack is duoCo
StripX (`com.easylink.colorful`).

Recovered from Home Assistant core issue
[#145934](https://github.com/home-assistant/core/issues/145934) (FFF3
sniff), duoCo StripX `library/src/duoco_stripx/protocol.py`
([wxx9248/Corner-Floor-Lamp-Controller](https://github.com/wxx9248/Corner-Floor-Lamp-Controller)),
AzraelSec `rs-duoco-stripx`, live-proven RGB solids on an OA10 that Magic
Lantern already controlled, then named effects and sound-sensitive modes
from jadx of the same APK (`com.easylink.colorful`). Helpers print
payloads. They do not scan or GATT-connect.

`RGBWControl` is only RGB / W / CCT channel flags. Named effects live in
`ModeFragment` plus `R.array.modes_group0`…`8`. Wire builders live in
`BluetoothLEService`.

Analog ELK-BLEDOM color frames (`7E 00 05 03 RR GG BB 00 EF`,
`[7]=0x00`) share the same 9-byte envelope and show up in some MELK-OA10
listings. On this RGBIC unit that render target is wrong: sRGB orange
`255,140,40` displayed teal. Pack RGB always uses `[7]=0x10`.

Do not commit APKs. Do not pack live MACs.

## Identification

| | |
|--|--|
| Maker | MELK (Magic Lantern / 亿联智控 / newwavex.com.cn) |
| App | Magic Lantern (`wl.smartled.rgb` 6.11.10) |
| Sibling app | duoCo StripX (`com.easylink.colorful`) |
| Advertised name | `MELK-OA10` plus last MAC octet (spaces padded). Some firmware prints `MELK-OA10W`. |
| GAP 2A00 | `MELK-OA10` padded with spaces |
| Manufacturer company id | 992 (advertised; the app does not filter on it) |
| ATT MTU | 23 (9-byte frames fit) |
| App scan | GAP name `startsWith("MELK-")` plus address substring `"BE"` |

One BLE central at a time. Unbind the phone app before a laptop holds
the link. Write-without-response “success” is not visual proof.

## Supported devices (Magic Lantern 6.11.10)

The app lists BLE advertisements whose GAP name `startsWith("MELK-")`
(`Global.NAME_FILTER`). `Global.NAME_BROADCAST_FILTER` is `"MELK_"` and
is unused in this APK.

This build (`DUO_CO_STRIP_CHANNEL` = `duoCoStrip`, not `smartled`) then
hides a row unless the BLE address string contains `"BE"`
(`IllegalDeviceUtil` / `unShowIllegalDevice`). That is a substring
check, not an OUI table. Company id **992** may still appear in
advertisements; `DeviceScanRecordParser` does not filter on it. GATT
UUIDs below are discovered after connect; they are not a scan filter.

Print the catalog without scanning:

```text
./encode_magic_lantern.py devices --list
./encode_magic_lantern.py devices match MELK-OA10 00:BE:00:00:00:00
```

OA10 / OA10W are **generic** `MELK-` names. There is no `MELK-OA`
DeviceName constant. Family SKUs that share this 9-byte `7E…EF` wire,
FFF0/FFF3/FFF4, and `MELK-` advertisement prefix use this same encoder.

| Prefix / check | Role | Scenes tab | Mic UI |
|----------------|------|------------|--------|
| `MELK-` (generic; OA10, OA10W) | scan accept | hide | show |
| `MELK-OB` | DeviceName | hide | hide |
| `MELK-OC` | DeviceName | show | show |
| `MELK-OE` | DeviceName | hide | hide |
| `MELK-OT` | DeviceName | show | show |
| `MELK-TX` | DeviceName | hide | hide |
| `^MELK-.+W.*` (CASE_INSENSITIVE) | RGBIC / W-suffix | — | — |
| `^MELK-.+CT.*` (CASE_INSENSITIVE) | CCT family | — | — |
| name contains `MELK-DYDS` | extra effect 156 Exploding star | — | — |

DYDS is not the OA10 default. Analog `ELK-BLEDOM` names are not Magic
Lantern-supported devices (the APK bundles analog ELK classes, but
`processScanResult` only accepts `MELK-`). Analog `[7]=0x00` remains
the wrong RGBIC render target on this unit.

## GATT

Service `0000fff0-0000-1000-8000-00805f9b34fb`

| Char | UUID | Role |
|------|------|------|
| TX | `0000fff3-0000-1000-8000-00805f9b34fb` | write **without** response |
| RX | `0000fff4-0000-1000-8000-00805f9b34fb` | notify (do not subscribe for solids) |

Pace writes about 30 ms. FFF3 readback on this unit is the last 9-byte
`7E…EF` frame plus ASCII `2021` plus NULs. StripX docs treated FFF3 as a
constant device-id string; this firmware echoes the last command.

## Frames

Nine bytes, no checksum:

```
7E | 7 body bytes | EF
```

| Command | Hex | Notes |
|---------|-----|-------|
| Power on (Magic Lantern sniff) | `7E 04 04 F0 00 01 FF 00 EF` | Default `on` |
| Power on (StripX v=1) | `7E 04 04 01 00 01 FF 00 EF` | `on --stripx` |
| Power off | `7E 04 04 00 00 00 FF 00 EF` | |
| Brightness 0–100 | `7E 04 01 xx MODE FF FF 00 EF` | LightMode: 0 SingleRGB, 1 MultipleRGB, 2 CCT, 3 WhiteBlack |
| Solid RGB | `7E 07 05 03 RR GG BB 10 EF` | **`[7]=0x10` is the RGB render target** |
| Warn orange | `7E 07 05 03 FF 16 00 10 EF` | `255,22,0` user-confirmed 2026-11-08 |
| Critical red | `7E 07 05 03 FF 00 00 10 EF` | |
| RGB black | `7E 07 05 03 00 00 00 10 EF` | Visual off without power-off |
| CCT pair | `7E 06 05 02 WW CW FF 08 EF` | `[7]=0x08`. `cct 0 0` zeros WW/CW; RGB-only ICs no-op |
| Effect | `7E 05 03 MODE 06 FF FF 00 EF` | Named aliases below. `BluetoothLEService.changeMode` |
| Speed | `7E 04 02 xx FF FF FF 00 EF` | |
| Scene | `7E 05 31 SCENE 07 FF FF 01 EF` | Opcode `0x31`. Magic Lantern hides this wheel on OA10 |
| External mic on/off | `7E 04 07 01/00 FF FF FF 00 EF` | `mic on` / `mic off` |
| Mic sensitivity 0–100 | `7E 04 06 xx FF FF FF 00 EF` | |
| Mic EQ / sound mode | `7E 07 03 (mode+128) 04 FF FF 00 EF` | Energic/Rhythm/Spectrum/Rolling |
| Music amp | `7E 07 05 03 RR GG BB 20 EF` | Same RGB layout as solids with `[7]=0x20` |

Opcode `0x83` is StripX `system_time` (`7E 07 83 HH MM SS WD FF EF`).
A truncated analog login `7E 07 83` is that RTC setter, not a pairing
key. Do not send it truncated.

### Do not send (NVRAM)

Expert frames persist IC count / pin order. Do not add them to the
helper CLI. Do not send them to “fix” color.

| Name | Prefix |
|------|--------|
| `symphony` | `7E 07 21` |
| `pin_sequence` | `7E 06 81` |

Analog color uses `[7]=0x00`.

## Named effects

213 names from `R.array.modes_group0`…`7` plus matching
`modes_group*_command` MODE bytes. `ModePagerAdapter` parses the command
string as `int` and `ModeFragment.sendCMD` calls
`BluetoothUtil.sendMode`. Duplicate display names keep a `-<MODE>` slug.

`./encode_magic_lantern.py effect auto-play` → `7e05030006ffff00ef`

`./encode_magic_lantern.py effect --list` prints the same catalog.

#### Basic (47)

| Name | Slug | MODE |
|------|------|--------|
| Auto Play | `auto-play` | 0 |
| Magic Forward | `magic-forward` | 1 |
| Magic Back | `magic-back` | 2 |
| 7-Color Energy | `7-color-energy` | 212 |
| 7-Color Jump | `7-color-jump` | 193 |
| R-G-B Jump | `r-g-b-jump` | 194 |
| Y-C-P Jump | `y-c-p-jump` | 195 |
| 7-Color Strobe | `7-color-strobe` | 196 |
| R-G-B Strobe | `r-g-b-strobe` | 197 |
| Y-C-P Strobe | `y-c-p-strobe` | 198 |
| 7-Color Gradual | `7-color-gradual` | 199 |
| R-Y Gradual | `r-y-gradual` | 200 |
| R-P Gradual | `r-p-gradual` | 201 |
| G-C Gradual | `g-c-gradual` | 202 |
| G-Y Gradual | `g-y-gradual` | 203 |
| B-P Gradual | `b-p-gradual` | 204 |
| Red Marquee | `red-marquee` | 205 |
| Green Marquee | `green-marquee` | 206 |
| Blue Marquee | `blue-marquee` | 207 |
| Yellow Marquee | `yellow-marquee` | 208 |
| Cyan Marquee | `cyan-marquee` | 209 |
| Purple Marquee | `purple-marquee` | 210 |
| White Marquee | `white-marquee` | 211 |
| 7-Color Race | `7-color-race` | 77 |
| 7-Color Race Back | `7-color-race-back` | 78 |
| R-G-B Race | `r-g-b-race` | 79 |
| R-G-B Race Back | `r-g-b-race-back` | 80 |
| Y-C-P Race | `y-c-p-race` | 81 |
| Y-C-P Race Back | `y-c-p-race-back` | 82 |
| 7-Color Wave | `7-color-wave` | 83 |
| 7-Color Wave Back | `7-color-wave-back` | 84 |
| R-G-B Wave | `r-g-b-wave` | 85 |
| R-G-B Wave Back | `r-g-b-wave-back` | 86 |
| Y-C-P Wave | `y-c-p-wave` | 87 |
| Y-C-P Wave Back | `y-c-p-wave-back` | 88 |
| 7-Color Flush | `7-color-flush` | 181 |
| 7-Color Flush Back | `7-color-flush-back` | 182 |
| R-G-B Flush | `r-g-b-flush` | 183 |
| R-G-B Flush Back | `r-g-b-flush-back` | 184 |
| Y-C-P Flush | `y-c-p-flush` | 185 |
| Y-C-P Flush Back | `y-c-p-flush-back` | 186 |
| 7-Color Flush Close | `7-color-flush-close` | 187 |
| 7-Color Flush Open | `7-color-flush-open` | 188 |
| R-G-B Flush Close | `r-g-b-flush-close` | 189 |
| R-G-B Flush Open | `r-g-b-flush-open` | 190 |
| Y-C-P Flush Close | `y-c-p-flush-close` | 191 |
| Y-C-P Flush Open | `y-c-p-flush-open` | 192 |
#### Curtain (20)

| Name | Slug | MODE |
|------|------|--------|
| 7-Color Close | `7-color-close` | 57 |
| 7-Color Open | `7-color-open` | 58 |
| R-G-B Close | `r-g-b-close` | 59 |
| R-G-B Open | `r-g-b-open` | 60 |
| Y-C-P Close | `y-c-p-close` | 61 |
| Y-C-P Open | `y-c-p-open` | 62 |
| Red Close | `red-close` | 63 |
| Red Open | `red-open` | 64 |
| Green Close | `green-close` | 65 |
| Green Open | `green-open` | 66 |
| Blue Close | `blue-close` | 67 |
| Blue Open | `blue-open` | 68 |
| Yellow Close | `yellow-close` | 69 |
| Yellow Open | `yellow-open` | 70 |
| Cyan Close | `cyan-close` | 71 |
| Cyan Open | `cyan-open` | 72 |
| Purple Close | `purple-close` | 73 |
| Purple Open | `purple-open` | 74 |
| White Close | `white-close` | 75 |
| White Open | `white-open` | 76 |
#### Trans (20)

| Name | Slug | MODE |
|------|------|--------|
| 7-Color Trans | `7-color-trans` | 3 |
| 7-Color Trans Back | `7-color-trans-back` | 4 |
| R-G-B Trans | `r-g-b-trans` | 5 |
| R-G-B Trans Back | `r-g-b-trans-back` | 6 |
| Y-C-P Trans | `y-c-p-trans` | 7 |
| Y-C-P Trans Back | `y-c-p-trans-back` | 8 |
| 6-Color to Red | `6-color-to-red` | 9 |
| 6-Color to Red Back | `6-color-to-red-back` | 10 |
| 6-Color to Green | `6-color-to-green` | 11 |
| 6-Color to Green Back | `6-color-to-green-back` | 12 |
| 6-Color to Blue | `6-color-to-blue` | 13 |
| 6-Color to Blue Back | `6-color-to-blue-back` | 14 |
| 6-Color to Cyan | `6-color-to-cyan` | 15 |
| 6-Color to Cyan Back | `6-color-to-cyan-back` | 16 |
| 6-Color to Yellow | `6-color-to-yellow` | 17 |
| 6-Color to Yellow Back | `6-color-to-yellow-back` | 18 |
| 6-Color to Purple | `6-color-to-purple` | 19 |
| 6-Color to Purple Back | `6-color-to-purple-back` | 20 |
| 6-Color to White | `6-color-to-white` | 21 |
| 6-Color to White Back | `6-color-to-white-back` | 22 |
#### Water (18)

| Name | Slug | MODE |
|------|------|--------|
| 7-Color Water | `7-color-water` | 39 |
| 7-Color Water Back | `7-color-water-back` | 40 |
| R-G-B Water | `r-g-b-water` | 41 |
| R-G-B Water Back | `r-g-b-water-back` | 42 |
| Y-C-P Water | `y-c-p-water` | 43 |
| Y-C-P Water Back | `y-c-p-water-back` | 44 |
| R-G Water | `r-g-water` | 45 |
| R-G Water Back | `r-g-water-back` | 46 |
| G-B Water | `g-b-water` | 47 |
| G-B Water Back | `g-b-water-back` | 48 |
| Y-B Water | `y-b-water` | 49 |
| Y-B Water Back | `y-b-water-back` | 50 |
| Y-C Water | `y-c-water` | 51 |
| Y-C Water Back | `y-c-water-back` | 52 |
| C-P Water | `c-p-water` | 53 |
| C-P Water Back | `c-p-water-back` | 54 |
| White Water | `white-water` | 55 |
| White Water Back | `white-water-back` | 56 |
#### Flow (24)

| Name | Slug | MODE |
|------|------|--------|
| W-R-W Flow | `w-r-w-flow` | 143 |
| W-R-W Flow Back | `w-r-w-flow-back` | 144 |
| W-G-W Flow | `w-g-w-flow` | 145 |
| W-G-W Flow Back | `w-g-w-flow-back` | 146 |
| W-B-W Flow | `w-b-w-flow` | 147 |
| W-B-W Flow Back | `w-b-w-flow-back` | 148 |
| W-Y-W Flow | `w-y-w-flow` | 149 |
| W-Y-W Flow Back | `w-y-w-flow-back` | 150 |
| W-C-W Flow | `w-c-w-flow` | 151 |
| W-C-W Flow Back | `w-c-w-flow-back` | 152 |
| W-P-W Flow | `w-p-w-flow` | 153 |
| W-P-W Flow Back | `w-p-w-flow-back` | 154 |
| R-W-R Flow | `r-w-r-flow` | 155 |
| R-W-R Flow Back | `r-w-r-flow-back` | 156 |
| G-W-G Flow | `g-w-g-flow` | 157 |
| G-W-G Flow Back | `g-w-g-flow-back` | 158 |
| B-W-B Flow | `b-w-b-flow` | 159 |
| B-W-B Flow Back | `b-w-b-flow-back` | 160 |
| Y-W-Y Flow | `y-w-y-flow` | 161 |
| Y-W-Y Flow Back | `y-w-y-flow-back` | 162 |
| C-W-C Flow | `c-w-c-flow` | 163 |
| C-W-C Flow Back | `c-w-c-flow-back` | 164 |
| P-W-P Flow | `p-w-p-flow` | 165 |
| P-W-P Flow Back | `p-w-p-flow-back` | 166 |
#### Tail (16)

| Name | Slug | MODE |
|------|------|--------|
| 7-Color Tail | `7-color-tail` | 23 |
| 7-Color Tail Back | `7-color-tail-back` | 24 |
| Red Tail | `red-tail` | 25 |
| Red Tail Back | `red-tail-back` | 26 |
| Green Tail | `green-tail` | 27 |
| Green Tail Back | `green-tail-back` | 28 |
| Blue Tail | `blue-tail` | 29 |
| Blue Tail Back | `blue-tail-back` | 30 |
| Yellow Tail | `yellow-tail` | 31 |
| Yellow Tail Back | `yellow-tail-back` | 32 |
| Cyan Tail | `cyan-tail` | 33 |
| Cyan Tail Back | `cyan-tail-back` | 34 |
| Purple Tail | `purple-tail` | 35 |
| Purple Tail Back | `purple-tail-back` | 36 |
| White Tail | `white-tail` | 37 |
| White Tail Back | `white-tail-back` | 38 |
#### Run (34)

| Name | Slug | MODE |
|------|------|--------|
| Red Running | `red-running` | 89 |
| Green Running | `green-running` | 91 |
| Blue Running | `blue-running` | 93 |
| Yellow Running | `yellow-running` | 95 |
| Cyan Running | `cyan-running` | 97 |
| Purple Running | `purple-running` | 99 |
| White Running | `white-running` | 101 |
| 7-Color Running | `7-color-running` | 103 |
| R-G-B Running | `r-g-b-running` | 105 |
| Y-C-P Running | `y-c-p-running` | 107 |
| B-P-C-Y Running | `b-p-c-y-running` | 109 |
| B-G-C-Y Running | `b-g-c-y-running` | 111 |
| Red-Dot in White Running | `red-dot-in-white-running` | 113 |
| Green-Dot in Red Running | `green-dot-in-red-running-115` | 115 |
| Blue-Dot in Green Running | `blue-dot-in-green-running` | 117 |
| Yellow-Dot in Blue Running | `yellow-dot-in-blue-running` | 119 |
| Cyan-Dot in Yellow Running | `cyan-dot-in-yellow-running-121` | 121 |
| Purple-Dot in Cyan Running | `purple-dot-in-cyan-running` | 123 |
| White-Dot in Purple Running | `white-dot-in-purple-running` | 125 |
| White-Dot in Red Running | `white-dot-in-red-running` | 127 |
| 7-Color in Red Running | `7-color-in-red-running` | 129 |
| 7-Color in Green Running | `7-color-in-green-running` | 131 |
| 7-Color in Blue Running | `7-color-in-blue-running` | 133 |
| 7-Color in Yellow Running | `7-color-in-yellow-running` | 135 |
| 7-Color in Cyan Running | `7-color-in-cyan-running` | 137 |
| 7-Color in Purple Running | `7-color-in-purple-running` | 139 |
| 7-Color in White Running | `7-color-in-white-running` | 141 |
| Green-Dot in Blue Running | `green-dot-in-blue-running` | 167 |
| Green-Dot in Red Running | `green-dot-in-red-running-169` | 169 |
| Red-Dot in Blue Running | `red-dot-in-blue-running` | 171 |
| Cyan-Dot in Yellow Running | `cyan-dot-in-yellow-running-173` | 173 |
| Yellow-Dot in Purple Running | `yellow-dot-in-purple-running` | 175 |
| White-Dot in Yelllow Running | `white-dot-in-yelllow-running` | 177 |
| Yellow-Dot in White Running | `yellow-dot-in-white-running` | 179 |
#### RunBack (34)

| Name | Slug | MODE |
|------|------|--------|
| Red Run Back | `red-run-back` | 90 |
| Green Run Back | `green-run-back` | 92 |
| Blue Run Back | `blue-run-back` | 94 |
| Yellow Run Back | `yellow-run-back` | 96 |
| Cyan Run Back | `cyan-run-back` | 98 |
| Purple Run Back | `purple-run-back` | 100 |
| White Run Back | `white-run-back` | 102 |
| 7-Color Run Back | `7-color-run-back` | 104 |
| R-G-B Run Back | `r-g-b-run-back` | 106 |
| Y-C-P Run Back | `y-c-p-run-back` | 108 |
| B-P-C-Y Run Back | `b-p-c-y-run-back` | 110 |
| B-G-C-Y Run Back | `b-g-c-y-run-back` | 112 |
| Red-Dot in White Run Back | `red-dot-in-white-run-back` | 114 |
| Green-Dot in Red Run Back | `green-dot-in-red-run-back-116` | 116 |
| Blue-Dot in Green Run Back | `blue-dot-in-green-run-back` | 118 |
| Yellow-Dot in Blue Run Back | `yellow-dot-in-blue-run-back` | 120 |
| Cyan-Dot in Yellow Run Back | `cyan-dot-in-yellow-run-back-122` | 122 |
| Purple-Dot in Cyan Run Back | `purple-dot-in-cyan-run-back` | 124 |
| White-Dot in Purple Run Back | `white-dot-in-purple-run-back` | 126 |
| White-Dot in Red Run Back | `white-dot-in-red-run-back` | 128 |
| 7-Color in Red Run Back | `7-color-in-red-run-back` | 130 |
| 7-Color in Green Run Back | `7-color-in-green-run-back` | 132 |
| 7-Color in Blue Run Back | `7-color-in-blue-run-back` | 134 |
| 7-Color in Yellow Run Back | `7-color-in-yellow-run-back` | 136 |
| 7-Color in Cyan Run Back | `7-color-in-cyan-run-back` | 138 |
| 7-Color in Purple Run Back | `7-color-in-purple-run-back` | 140 |
| 7-Color in White Run Back | `7-color-in-white-run-back` | 142 |
| Green-Dot in Blue Run Back | `green-dot-in-blue-run-back` | 168 |
| Green-Dot in Red Run Back | `green-dot-in-red-run-back-170` | 170 |
| Red-Dot in Blue Run Back | `red-dot-in-blue-run-back` | 172 |
| Cyan-Dot in Yellow Run Back | `cyan-dot-in-yellow-run-back-174` | 174 |
| Yellow-Dot in Purple Run Back | `yellow-dot-in-purple-run-back` | 176 |
| White-Dot in Yelllow Run Back | `white-dot-in-yelllow-run-back` | 178 |
| Yellow-Dot in White Run Back | `yellow-dot-in-white-run-back` | 180 |

## Scenes

28 names from `R.array.modes_group8`. These use **scene** opcode `0x31`,
not the effect envelope. Magic Lantern **hides** this wheel on OA10
(`ListUtil.isContainsBuiltInScene` is true only for `MELK-OC` /
`MELK-OT` prefixes; `isShowBuiltInScene` then drops the last tab). Frames
are still in `BluetoothLEService.changeScene`. Unproven on OA10 firmware.

`./encode_magic_lantern.py scene rainbow` → `7e05310b07ffff01ef`

| Name | Slug | SCENE |
|------|------|--------|
| Sunrise | `sunrise` | 1 |
| Sunset | `sunset` | 2 |
| Birthday | `birthday` | 3 |
| Candlelight | `candlelight` | 4 |
| Fireworks | `fireworks` | 5 |
| Party | `party` | 6 |
| Datiny | `datiny` | 7 |
| Starry sky | `starry-sky` | 8 |
| Romantic | `romantic` | 9 |
| Disco | `disco` | 10 |
| Rainbow | `rainbow` | 11 |
| Movie | `movie` | 12 |
| Christmas | `christmas` | 13 |
| Flowing | `flowing` | 14 |
| Sleeping | `sleeping` | 15 |
| Ocean | `ocean` | 16 |
| Forest | `forest` | 17 |
| Reading | `reading` | 18 |
| Working | `working` | 19 |
| Dazzle | `dazzle` | 20 |
| Gentle | `gentle` | 21 |
| Wedding | `wedding` | 22 |
| Snow | `snow` | 23 |
| Fire | `fire` | 24 |
| Lightning | `lightning` | 25 |
| Valentine's Day | `valentines-day` | 26 |
| Hallowmas | `hallowmas` | 27 |
| Warnning | `warnning` | 28 |

## Sound-sensitive modes

`StreamingFragment` radios map to `BluetoothUtil.ExternalMicEqMode`.
`BluetoothLEService.changeExternalMicEqMode` adds 128 to that value.

| Name | Slug | mode | Wire byte | Frame |
|------|------|------|-----------|-------|
| Energic | `energic` | 0 | `0x80` | `7E 07 03 80 04 FF FF 00 EF` |
| Rhythm | `rhythm` | 1 | `0x81` | `7E 07 03 81 04 FF FF 00 EF` |
| Spectrum | `spectrum` | 2 | `0x82` | `7E 07 03 82 04 FF FF 00 EF` |
| Rolling | `rolling` | 3 | `0x83` | `7E 07 03 83 04 FF FF 00 EF` |
| Energic two | `energic-two` | 4 | `0x84` | `7E 07 03 84 04 FF FF 00 EF` |
| Rhythm two | `rhythm-two` | 5 | `0x85` | `7E 07 03 85 04 FF FF 00 EF` |
| Spectrum two | `spectrum-two` | 6 | `0x86` | `7E 07 03 86 04 FF FF 00 EF` |
| Rolling two | `rolling-two` | 7 | `0x87` | `7E 07 03 87 04 FF FF 00 EF` |

Phone-mic / local-music paths stream RGB through **music amp**
(`[7]=0x20`) instead of a MODE byte. `mic on` enables the strip mic
before `mic-eq`. `ListUtil.isContainsSupportedMic` hides mic UI only for
`MELK-OE` / `MELK-OB` / `MELK-TX` prefixes; OA10 keeps the mic tab.

### LED balance

Pure red / green / blue with `[7]=0x10` look correct. Packed warn orange
is **`255,22,0`**, not sRGB `255,140,40` (too much green, and 40 blue
cools it, on this WS2812).

```text
./encode_magic_lantern.py on
./encode_magic_lantern.py rgb 255,0,0
./encode_magic_lantern.py warn
./encode_magic_lantern.py brightness 100 --mode 1
./encode_magic_lantern.py cct 0 0
./encode_magic_lantern.py effect auto-play
./encode_magic_lantern.py effect 7-color-jump
./encode_magic_lantern.py scene rainbow
./encode_magic_lantern.py mic on
./encode_magic_lantern.py mic-eq rhythm
./encode_magic_lantern.py mic-sensitivity 50
./encode_magic_lantern.py music-amp 255,0,0
./encode_magic_lantern.py decode 7e070503ff160010ef
./encode_magic_lantern.py devices --list
./encode_magic_lantern.py devices match MELK-OA10 00:BE:00:00:00:00
./encode_magic_lantern.py self-test
```

Write the printed hex to FFF3 without response.

## Notes

- Own hardware only.
- Analog `[7]=0x00` records on FFF3 and can look teal / chase on RGBIC.
- Home Assistant `elkbledom` lists MELK-OA10; those analog frames are the
  wrong family for this Magic Lantern RGBIC unit.
- Do not send `pin_sequence` / `symphony`.
- Named effects recovered from APK 6.11.10
  SHA-256 `7530ae09d5b849ed4f59e19994c36ebd639fe02304b21f74482ae46b60e387c0`.
  Live-unproven except the RGB solids / warn orange already confirmed.
