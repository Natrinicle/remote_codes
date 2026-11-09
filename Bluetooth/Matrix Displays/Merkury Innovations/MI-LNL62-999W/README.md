# MI-LNL62-999W (BLE)

BLE protocol for the Merkury Innovations Multicolor Matrix LED Display
(SKU **MI-LNL62-999W**, 9" USB 5V/2A, 16×16 RGB). Paper quick-start says
download **MI Matrix Panel**. That app is `com.fulllight.ledpixel` 1.0.2
(Flutter AOT `libapp.so`, `package:MIMatrixPanel`,
`flutter_reactive_ble` `writeCharacteristicWithoutResponse`). Play
listings for that name were gone; a later store title is MatrixPanel Plus
(`com.wzjledaxc.ledplus`).

Recovered from the 1.0.2 XAPK `libapp.so` ASCII `BC…55` strings plus
community snoops ([offe/mi-led-display](https://github.com/offe/mi-led-display)
`protocol.txt` / `store_image_commands.txt`, SpawnDev.MatrixLEDDisplay
GATT table). Helpers print payloads. They do not scan or GATT-connect.

Live FFD1 writes work on the BLE advertisement (service UUID
`0000af30`). That UUID is **host/radio firmware**: BlueZ still finds
this unit as the `0000af30` advertiser. The **app**
(`com.fulllight.ledpixel` 1.0.2) matches advertised name
`MI Matrix Display` and does **not** contain `0000af30` as a scan
UUID. `startScanBle` `withServices` is unrecovered (empty list vs
`[FFD0]`). The JieLi radio is dual-mode. BlueZ treats the **public**
address as Class `0x240414` audio-card (SPP/A2DP/AVRCP) with no
`Bearer.LE1`, so GATT on that object is empty. Connect the
`0000af30` advertiser, then discover `FFD0` / `FFD1`.

Default ATT MTU is 23 (20-byte payload). Picture blocks are 101 bytes.
Request a larger MTU before those writes (this unit negotiated 514 after
BlueZ `_acquire_mtu`). Write FFD1 **without** response. Pace blocks
about 25 ms.

2026-11-08: FFD1 picture writes show a 16×16 orange cat. `store` slots
1/2 **append** to the on-device playlist; leftover text/animation
frames (`Te` / `St` / blanks) still cycle with the cat. Slideshow is
mode `0x12`. Graffiti start (`01`+`0D`) plus per-pixel paint, then
mode `0x13`, holds a still **while the LE link stays up** (re-paint
loop). 2026-11-08 user-confirmed: static orange cat, no blink, no
`Te`/`St` while that hold is connected. 2026-11-08 persist send:
opcode `0x02` 4-frame cat blink (open / closed / open / open), store
1/2, slideshow `0x12`, then disconnect. FFD1 wrote 40 packets (MTU
514). User-confirmed after disconnect: cat, then `Te`, then `St`,
then black, then loop. Short mode `0x15` (`bc00151555`) is the
saved-data reset (APK ASCII, offe first post-connect write,
SpawnDev.MatrixLEDDisplay `Command.Reset` before store). Per-slot
`FavoriteClear0..3` / `deletePreset` still have no recovered
`BC…55` frame. 2026-11-08 wipe send: `0x15`, store 1, 4-frame cat
blink, store 2, slideshow `0x12`, disconnect. FFD1 wrote 40
packets (MTU 514). User-confirmed after disconnect: cat face,
black, cat with different eyes, black, repeat. `Te` / `St` are
gone. A 4-frame clip (ids 2..5) leaves empty slideshow slots;
those play black. **8 is the no-black lower fill**, not a hard
max. SpawnDev pads every GIF save to 8 (client; `imageIndex 1 -
??`). 2026-11-08 8-slot send: `0x15`, store 1, 8-frame cat blink
(open/closed/open/open twice, ids 1..8), store 2, slideshow
`0x12`, disconnect. FFD1 wrote 80 packets (MTU 514).
User-confirmed after disconnect: cat blink loops with no black
gaps, no `Te` / `St`. 2026-11-09 count=12 ids 1..12 (cyan 1–8,
orange 9, magenta A, yellow B, green C): FFD1 wrote 120 packets
(MTU 514). User-confirmed after disconnect: cyan 3–8, orange 9,
purple A, then B/C twice; cyan 1 and 2 never appeared; the
second B/C had a second upper counting bar that shifted the
original down one line. Extra frames past 8 play. Count 12
is not a clean persist length (ids 11–12 look like they
overwrite 1–2). 2026-11-09 count=10 ids 1..10 (cyan 1–8 with
a white left column on 1 and 2, orange 9, magenta A): FFD1
wrote 100 packets (MTU 514), store 2, slideshow `0x12`.
User-confirmed after disconnect: cyan 1 and 2 with a left
vertical bar; cyan 1–8 with a cyan bottom bar; orange 9 with
a cyan top bar and orange bottom bar; purple A with a cyan
top bar and purple bottom bar; every bottom bar 10 pixels
wide. 10 is a clean persist length on this unit. Top ticks
were encoded white; on 9 and A they read cyan on the panel.
2026-11-09 count=11 ids 1..11 (cyan 1–8 with a white left
column on 1 and 2, orange 9, magenta A, yellow B): FFD1
wrote 110 packets (MTU 514), start `bc02f10bfe55`, end
`bc02f20bff55`, store 2, slideshow `0x12`, disconnect
clean. User-confirmed after disconnect: a heart swapping
colors. That is not the 11-frame glyph clip. Count 11 is
not a clean persist length. Best fit: firmware factory or
demo (or `NN` greater than 10 treated as a built-in
selector). The 1.0.2 AOT has no named factory clip titles
for opcode `0x02`; ASCII `heart` is Flutter
`SpinKitPumpingHeart`, not a LED clip.
A later persist count=10 (center digits 1–A, top ticks, no
side columns or bottom bar) wrote 100 FFD1 packets while the
heart was still looping; the panel stayed on the heart. Host
FFD1 writes are not proof the demo yielded. Exit the demo
first: power off `bcff000055`, power on `bcff010155`, live
mode `0x13` (`bc00131355`), a live picture opcode `0x0F`
with no store (solid red is proven), then reset `0x15`, then
persist. Encoder `persist-prep` prints the first three.
2026-11-09 retry with that prefix: user-confirmed counting
1 to A in different colors.
2026-11-09 count=11 after that demo-exit (ids 1..11, 110
packets, mint B): user-confirmed B has a corrupted frame and
shifts for a second frame. Count 11 is not a clean persist
length. Persist animation on this unit is **8 frames
minimum** (empty ids play black) and **10 frames maximum**.
Later demo-exit sends omit the live solid-red picture.

## Identification

| | |
|--|--|
| Maker | Merkury Innovations |
| Paper app | MI Matrix Panel |
| APK | `com.fulllight.ledpixel` 1.0.2 (`versionCode` 10) |
| Advertised name | `MI Matrix Display` |
| SoC | JieLi AC696N (`AC696N_V160-@20220526`) |
| Grid | 16×16 RGB (256 pixels, row-major) |
| Power | USB 5V/2A |

Camera originals in this folder (`IMG20261108101406.jpg` leaflet,
`IMG20261108101443.jpg` / `IMG20261108101447.jpg` unit off,
`IMG20261108101513.jpg` lit 16×16) stay gitignored. Do not commit APKs.

One BLE central at a time. Unbind the phone app before a laptop holds
the link.

## Supported devices (MI Matrix Panel 1.0.2)

The app lists BLE advertisements whose GAP name equals
`MI Matrix Display` (trim). That is the only advertised-name literal
in the 1.0.2 AOT. App title `MI Matrix Panel` is **not** a scan name.
Reject copy: `Device not supported`.

`0000af30` is **not** in the AOT (no ASCII, UTF-16, 128-bit Bluetooth
UUID, or `MOVZ #0xAF30`). Live BlueZ still finds this unit as the
`0000af30` advertiser; that is radio/firmware, **not** an app scan
filter. `startScanBle` `withServices` is unrecovered (empty list vs
`[FFD0]`). `FFD0` / `FFD1` / `FFD2` exist; `FFD0` sits next to notify
setup. No manufacturer / OUI / JieLi / `F4:CB:B4` filter in this AOT.

Grid size `8x8` / `24x24` / `32x32` does not change pairing. Factory
pictures are 16×16. 32×32 PNGs are rhythm UI, not extra BLE types.

Print the catalog without scanning:

```text
./encode_mi_matrix.py devices --list
./encode_mi_matrix.py devices match "MI Matrix Display"
```

Optional `devices match NAME [MAC]`: the MAC argument is ignored.
This APK has no MAC/OUI filter.

| Connection type | Filter | UUID / name / OUI | Notes |
|-----------------|--------|-------------------|--------|
| LE scan | Name equality (AOT) | Name `MI Matrix Display` | Only advertised-name literal. Reject copy: `Device not supported`. |
| LE scan service UUID | Unrecovered | **Not** `0000af30` in AOT. Maybe empty list or `FFD0` | Host/radio still advertises `0000af30`. |
| Manufacturer / OUI | None in AOT | — | `manufacturerData` is a plugin field only. |
| GATT connect | Scan `deviceId` | Service `FFD0`, TX `FFD1` write-without-response, RX `FFD2` notify | Reconnect keys: last name + last id. |
| Classic SPP/A2DP | Not used by this APK | — | Dual-mode radio is firmware; app is LE-only. |

## GATT

Service `0000ffd0-0000-1000-8000-00805f9b34fb`

| Char | UUID | Role |
|------|------|------|
| TX | `0000ffd1-0000-1000-8000-00805f9b34fb` | write **without** response |
| RX | `0000ffd2-0000-1000-8000-00805f9b34fb` | notify (CCCD `2902`) |

APK Dart: `writeOrderWithoutResponse`, `sendPictureStart`,
`writePicture`, `writeAnimationPicture`, `writeTextPicture`,
`LamplightOrderHelper`, `PowerOff`. Strings `FFD0` / `FFD1` / `FFD2`
are in `libapp.so`.

The radio is dual-mode (Classic SPP `00001101`, A2DP, AVRCP, plus BLE).
If `ble.discover` returns no services while BlueZ says Connected, drop
the Classic path and reconnect LE-only.

## Factory presets

MI Matrix Panel 1.0.2 ships **382 untitled 16×16** factory pixel JSON
blobs in the AOT. They are not sent as JSON. The app `writePicture` /
`sendPictureStart` path is opcode `0x0F` (already packed) then store
1/2. This pack does not embed those blobs. No title strings sit next
to the JSON.

| Symbol | Wire | Notes |
|--------|------|-------|
| Factory pictures | picture `0x0F` then store | 382 × 16×16; untitled |
| `FavoriteClear0..3` | **Unrecovered** | no ASCII `BC…55` |
| `FavoriteStore0..3` | **Unrecovered** as distinct frames | store 1/2 hex may be a subset |
| `FavoriteRecall0..3` | **Unrecovered** | |
| Animation | opcode `0x02` (packed) | persist min 8 max 10. Count 11: factory heart, or B corrupted plus an extra shifted frame after demo-exit. Demo-exit: `persist-prep` then `0x15` |
| Lamplight `01` / `04` / `05` / `06` / `dual` | packed hex | enum id `breathe` exists; name↔hex unproven |
| Light effect 1–7 | **Unrecovered** | identifiers only (`effect1`…`effect7`) |
| Music / rhythm | **Unrecovered** BLE | 10 bundled mp3 names below |

Bundled mp3s: `Alls_Fair_In_Love`, `Attic_Secrets`, `Baltic_Levity`,
`Barroom_Ballet`, `Battle_Ready`, `Circus_of_Freaks`, `City_Sunshine`,
`Fancy_Family`, `Happy_Whistling_Ukulele`, `Horns`. 32×32
`rhythm_picture_*` PNGs are the visualizer atlas, not a 32×32 lamp.

GIF / graphic persist copy in the AOT (typos `GlF` / `theMatrix`)
uses picture/animation store. That is not a second device class.

```text
./encode_mi_matrix.py presets --list
```

## Frames

```
BC | body… | 55
```

Picture start/end and the eight picture blocks take **sum8 of the bytes
between `BC` and the checksum** as the last body byte. Short modes
`BC 00 MODE MODE 55` are the same rule (`00+MODE`). Graffiti pixels use
QQ = `(index - 1) & 0xFF` (offe example: index 0 red → QQ `FF`), not a
sum.

### Power (APK is source of truth)

| | Hex | Source |
|--|-----|--------|
| Off | `bcff000055` | APK `BCFF000055` |
| On | `bcff010155` | APK `BCFF010155` |

offe `protocol.txt` has `BC FF 00 FF 55` / `BC FF 01 00 55`. Those are
`offe-off` / `offe-on` on the helper. Prefer the APK duplicates until a
live write proves otherwise.

### Short modes

`BC 00 MODE MODE 55`

| MODE | Hex | Meaning |
|------|-----|---------|
| `01` | `bc00010155` | graffiti start (send with `0D`) |
| `0D` | `bc000d0d55` | graffiti start (send with `01`) |
| `12` | `bc00121255` | slideshow (APK + offe) |
| `13` | `bc00131355` | mode-like (APK) |
| `15` | `bc00151555` | reset saved playlist (APK + offe + SpawnDev) |

### Graffiti pixel

```
BC 01 01 00 PP RR GG BB QQ 55
```

`PP` is 0–255 (row-major). QQ is `(PP - 1) & 0xFF`. Red top-left:
`bc01010000ff0000ff55`.

### Picture (16×16)

1. Start `bc0ff1080855` (`0F+F1+08 = 08`)
2. Eight blocks, block index **1..8**, each 32 RGB pixels (2 rows):
   `BC 0F NN <96 RGB> sum8 55`
3. End `bc0ff2080955` (`0F+F2+08 = 09`)

offe's `draw_picture.py` omits the block sum8; `store_image_commands.txt`
snoops include it, matching start/end. This helper emits the checksum.

Store after a picture (APK ASCII; offe persist sequence). Picture
end without store does not replace the on-device playlist.

| Slot | Hex |
|------|-----|
| 1 | `bc0011f10355` |
| 2 | `bc0011f20455` |

offe then sends slideshow `bc00121255`. Skip that for a still image.

### Animation (16×16 clip)

Opcode `0x02` (`writeAnimationPicture` in the 1.0.2 AOT). offe HCI
snoops (per-packet ATT Write Command, handle 0x0003) of a 4-frame
save:

1. Start `bc02f104f755` (`02+F1+04 = F7`). The `04` is the clip
   frame count.
2. Eight 102-byte blocks for **one** frame, same 32-pixel RGB slices
   as picture: `BC 02 FF BB <96 RGB> sum8 55`. `BB` is block 1..8.
   `FF` is the frame id. offe’s first clip used ids **2..(1+N)**
   (a 4-frame dolphin started at `02`, then `03`, …). Live 8-slot
   fill uses ids **1..8**.
3. End `bc02f204f855` (`02+F2+04 = F8`). Count 8 is
   `bc02f108fb55` / `bc02f208fc55`. Count 10 is
   `bc02f10afd55` / `bc02f20afe55`. Count 11 is
   `bc02f10bfe55` / `bc02f20bff55` (wire accepted; persist
   without demo-exit is the factory heart; with demo-exit B
   is corrupted plus an extra shifted frame). Count 12 is
   `bc02f10cff55` / `bc02f20c0055`.
4. Repeat start + 8 blocks + end for each remaining frame (same
   count byte).
5. Store 1, store 2, then slideshow `0x12` so the clip survives
   disconnect.

Picture or animation store **appends** leftover playlist items
(`Te` / `St` / black). Wipe first with reset `0x15`, wait ~500 ms,
then store enable (`F1`), send the clip, store disable (`F2`),
slideshow `0x12`. Dart still names `FavoriteClear0..3` /
`deletePreset`; those are not ASCII `BC…55` literals. After
reset, a 4-frame clip still shows black between cats (empty
slots). Pad to **8–10** frames, ids 1..N. Opcode count `NN`
is 1..255 (`animation-start --count`). Persist animation on
this unit is **8 minimum** (empty ids play black) and **10
maximum**. 12 overwrites ids 1–2 and glitches the last pair.
Count 11 without demo-exit played a color-swapping heart.
Count 11 with demo-exit: B corrupted plus an extra shifted
frame. After the heart, persist with only `0x15` stayed on
the heart. Demo-exit is power off/on, live `0x13`, then
`0x15`, then persist. First success also sent a live solid
red picture before `0x15`; later sends omit that picture.
Demo-exit then persist count=10: user-confirmed 1–A.

```text
./encode_mi_matrix.py persist-prep
./encode_mi_matrix.py reset
./encode_mi_matrix.py animation-start --count 8
./encode_mi_matrix.py animation-end --count 8
./encode_mi_matrix.py animation-start --count 10
./encode_mi_matrix.py animation-end --count 10
```

### Lamplight (APK ASCII, mapping unproven)

Keep the lamp CLI. AOT has enum id `breathe`; name↔hex is **unproven**.
Light-effect modes 1–7 are identifiers only; wire bytes unrecovered.

| Name | Hex |
|------|-----|
| `01` | `bc0a01010c55` |
| `04` | `bc0a01040055` |
| `05` | `bc0a01050155` |
| `06` | `bc0a01060255` |
| `dual` | `bc0a0202ff0000ffffff0e55` |

```text
./encode_mi_matrix.py self-test
./encode_mi_matrix.py on
./encode_mi_matrix.py graffiti-start
./encode_mi_matrix.py pixel --index 0 --rgb ff0000
./encode_mi_matrix.py solid --rgb ff0000
./encode_mi_matrix.py decode bcff010155
./encode_mi_matrix.py devices --list
./encode_mi_matrix.py devices match "MI Matrix Display"
./encode_mi_matrix.py presets --list
```

Write the printed hex to FFD1 without response. Pace picture blocks
(~25 ms in offe). This helper does not pace.

## Notes

- Own hardware only.
- Do not commit APKs or live MACs.
- Successor app MatrixPanel Plus was not unpacked this session.
