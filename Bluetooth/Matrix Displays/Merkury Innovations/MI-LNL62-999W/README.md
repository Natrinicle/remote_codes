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
`0000af30`). The JieLi radio is dual-mode. BlueZ treats the **public**
address as Class `0x240414` audio-card (SPP/A2DP/AVRCP) with no
`Bearer.LE1`, so GATT on that object is empty. Connect the `0000af30`
advertiser, then discover `FFD0` / `FFD1`.

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
those play black. Firmware holds 8 slots (SpawnDev pads every
save to 8, ids 1..8). 2026-11-08 8-slot send: `0x15`, store 1,
8-frame cat blink (open/closed/open/open twice, ids 1..8), store
2, slideshow `0x12`, disconnect. FFD1 wrote 80 packets (MTU 514).
User-confirmed after disconnect: cat blink loops with no black
gaps, no `Te` / `St`.

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
   `bc02f108fb55` / `bc02f208fc55`.
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
slots). Pad to 8 frames, ids 1..8.

```text
./encode_mi_matrix.py reset
./encode_mi_matrix.py animation-start --count 8
./encode_mi_matrix.py animation-end --count 8
```

### Lamplight (APK ASCII, mapping unproven)

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
```

Write the printed hex to FFD1 without response. Pace picture blocks
(~25 ms in offe). This helper does not pace.

## Notes

- Own hardware only.
- Do not commit APKs or live MACs.
- Successor app MatrixPanel Plus was not unpacked this session.
