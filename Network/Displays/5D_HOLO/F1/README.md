# 5D HOLO F1 (Holofan HTTP)

Wi-Fi SoftAP holographic fan. Control is Holofan HTTP `:80` plus WebSocket
`:9000`. This is **not** the Android MissYou UDP 50xxx stack.

Helpers print dest-hex, geometry, `holo-fan` argv, and curl recipes. They
do not join the AP, POST, or play. Do not pack SSIDs, PSKs, or personal
MACs. Do not format the TF/SD card. Do not send `switcher=off` unless the
operator names it (blanks the live disc).

Encoder: [`encode_holofan.py`](encode_holofan.py). Sibling video packer is
[Oblokos/holo-fan-toolkit](https://github.com/Oblokos/holo-fan-toolkit)
(`holo-fan`). OpenAPI (upload omitted):
[daveismith/beancell-holo](https://github.com/daveismith/beancell-holo)
`docs/display-openapi.yaml`.

## Identification

| | |
|--|--|
| Brand | 5D HOLO (ftlled) |
| Model | **F1** firmware **1.1.0** |
| SoftAP | SSID prefix **`5D_`**, WPA3-SAE |
| AP | `http://192.168.4.1` (DHCP client usually `192.168.4.2/24`) |
| HTTP | TCP **80** JSON |
| WebSocket | TCP **9000** path `/` (`/ws` is HTTP 404) |
| Chip | Espressif |
| iOS | 5D HoLo, bundle `com.dmz.-D-HoLo99`, App Store `6563141154` |
| Windows | `5D HoLo.exe` (`/ctrl/session`, `/DCIM/upload`, `/ctrl/play?action=status`, `/info`) |
| Not this wire | Android MissYou UDP 50xxx |

```text
./encode_holofan.py devices --list
./encode_holofan.py devices match 5D_TEST
```

Open ports on the AP: **80** and **9000** only.

## Session

IP-based. No cookie. Call `GET /ctrl/session` before `/ctrl/get`, `/DCIM`,
`/ctrl/play`, and each ~2.8 MB `POST /DCIM/upload`. Session can expire
across sequential large POSTs (`code` 1 No active session).

```text
./encode_holofan.py curl-session
# curl -sS -m 5 http://192.168.4.1/ctrl/session
# {"code":0,"desc":"Session success"}
```

`GET /ctrl/session?action=quit` ends the session.

## Geometry (F1)

Windows `5D HoLo.exe` modelCombo:

| Model | lights | lines | colorDeep | disc diameter `(lights-1)*2` |
|-------|--------|-------|-----------|------------------------------|
| **F1** | **116** | **520** | **6** | **230** |
| F-MINI12 | 48 | 300 | 5 | 94 |

Encoding F1 media as 48/300/5 (or unofficial header/pad) **scrambles** the
disc. Official on-disk: **812-byte LUT header** + frames + pad the file to
**28800** (`0x7080`). F1 frame block **138880**. Proven Wi-Fi cap: **20
frames** = **2793600** bytes.

```text
./encode_holofan.py geometry --model F1
./encode_holofan.py encode-cmd --model F1 --video swim.mp4 --out swim.bin
```

Shipped disc flags:

```text
holo-fan --video swim.mp4 --out swim.bin --video-fit disc --fit-scale 0.95 \
  --rotate 0 --lights 116 --lines 520 --color-deep 6 --frames 20 \
  --header official --padding official
```

`--rotate 0` is upright on F1. `--rotate 180` is the kitten flip (180° ≡
H+V). Encoder disc path ends `fps=20,vflip,format=bgr24`. `--fit-scale`
`>1` zooms/crops; `<1` pads black. `1.25` clipped ~10%/side on diameter
230.

9-frame official (~1267200) returns play then falls to `01fish.bin` within
~2 s. Stay at 20 frames for F1 Wi-Fi.

## Upload

`POST /DCIM/upload` multipart (OpenAPI omits this URI; iOS 5D HoLo uses it):

| Field | Value |
|-------|--------|
| `name` (text) | hex UTF-8 of dest filename (`30koi.bin` → `33306b6f692e62696e`) |
| `file` | the `.bin`, `Content-Type application/octet-stream` |

```text
./encode_holofan.py dest-hex 30koi.bin
./encode_holofan.py curl-upload --name 30koi.bin --file 30koi.bin
```

PUT is HTTP 405. Success `{code:0, desc:download file success}`.

| code | meaning |
|------|---------|
| 0 | download file success |
| 1 | no session |
| 2 | no filename |
| 3 | no boundary |
| 5 | missing filename or Content-Type |
| 6 | create failed (ASCII dest instead of hex) |
| 7 | truncated/partial `.bin` |
| 8 | too large, or a failed **overwrite that deletes the dest** |

Do **not** POST overwrite a playing dest. Retry as a **new** filename.
Do not send tiny probe `.bin` files.

`GET /DCIM` can return `files:[]` while the SD is writing. Re-session and
list again.

## Play

`GET /DCIM/<hex>?act=play`. `switcher` must be `on`. Set URL is
`GET /ctrl/set?loop=one` (not `k=`/`v=`).

```text
./encode_holofan.py curl-play --name 30koi.bin
```

After a new converter `.bin`, the **first** play can still report stock
`01fish.bin` (`total=9`). Re-GET session, `loop=one`, replay the hex URI.
Converter clips stick with `current=<hex>` `progress=0` `state=ing`
`total=0`.

Stock play totals (this firmware): `01fish.bin` total=9, `07Pikachu.bin`
total=29.

`GET /ctrl/set?switcher=off` blanks the live hologram. Do not send it
unless named.

## Scramble recovery

LED garbage while status names a dest is the **on-card dest or converter
of that dest**, not play rewriting a good file. `act=play` is GET.

Recovery:

```text
./encode_holofan.py curl-recover --name 26cat.bin
```

1. `GET /ctrl/session`
2. `GET /ctrl/set?loop=one`
3. Play a proven dest (upright F1 cat used `--rotate 0 --fit-scale 0.95`
   official 2793600)
4. Confirm visually. Then retry the intended clip as a **new** dest.

Identical local bytes under a new dest name can play clean after a garbled
dest of the same payload. Local `cmp` does not prove the on-card copy.

## Post-write verify (none over HTTP)

`GET /DCIM` is hex **names only** (no size, no hash). `?detail=1` is the
same list. `GET /DCIM/<hex>` without `act=play` is `{code:2, desc:no filename}`.
`HEAD` is HTTP 405. `GET /file/<hex>` is `Nothing matches the given URI`.
OpenAPI `act` enum is only `play`. Windows `5D HoLo.exe` has no download.

These **hang** (0 bytes). Do not use them:

- `GET /DCIM/upload?filename=`
- `GET /DCIM/download?name=<hex>`
- `GET /DCIM/<hex>?action=download`

Byte check is pull the TF/SD and `sha256sum` against the local `.bin`.
Do not format the card.

Usable Wi-Fi gates: POST `code` 0, dest appears in `/DCIM` after the empty
list lag, re-session + `loop=one` + play, then **look**.

## WebSocket

`ws://192.168.4.1:9000/` — 101, first text `{code:0, desc:handle success}`,
then unsolicited `{cmd:onPlayInfoUpdate, current, progress, state, total}`
about every 2.1 s. JSON `{cmd:heartbeat, msgId:"1"}` needs **both** `msgId`
and `cmd`. Do not send WebSocket ping **control** frames.

## Config

`GET /ctrl/get?k=all` keys: brightness, angle, volum, ble, ssid, switcher,
loop. `GET /info` → model + `sw`. `GET /ping` → model, sw, mac, group.

## Factory presets

```text
./encode_holofan.py presets --list
```

Includes `01fish.bin` (lifelike 3D swim, total=9). User dests are hex of
the `.bin` filename (`26cat.bin`, `30koi.bin`, …).

## Lifelike encode

The disc is a spinning LED radius. High-emission frames clip to a white
cookie (long-exposure fish pixels 253–255 when PNG mean luma ~220). Budget:

- PNG mean luma **45–140**
- fill fraction about **0.06–0.45**
- luma CV **≥ 0.18**
- no emission shaders; keyed light + shadowless fills
- **native mesh** (real carp/koi), not a silhouette, morph, or primitive fins
- in-place swim, not a 1 rev/s 2D orbit of a still
- 20 fps, 20 frames for the F1 Wi-Fi cap
- independent adversary grades frames; producer does not grade
- cap three reds, then the mesh/plan is wrong

Blender (Debian 5.2-class) gotchas recovered on this path: enable Cycles
after `read_factory_settings(use_empty=True)`; skip OIDN if the enum is
empty; `ShaderNodeCombineColor` not `CombineRGB`; rotate with
`obj.data.transform`; shadowless via `obj.visible_shadow = False`; a global
Backfacing→Translucent MixShader turned a hollow body into a dark ghost —
Principled only.

Example CC-BY-4.0 kohaku mesh (credit required if shared): Sketchfab
[Koi Fish](https://sketchfab.com/3d-models/koi-fish-3e1b80c3653f43349252aab3b4fb1d86)
by SDPM Esare, object `node_id39`. Do not commit the mesh or `.bin` into
this pack.

Grok Imagine `reference_to_video` / grok-imagine-3d may be blocked under
ZDR (HTTP 400 deferred). Keep ZDR; use local Blender.

## Do not

- Format the TF/SD
- `switcher=off` unless named
- Overwrite a playing dest (code 8 deletes it)
- Retry a garbled dest in place — new filename
- Use hanging download URIs
- Port-forward 80 or 9000
- Commit APKs, `.bin` blobs, SSIDs, or PSKs
- Encode F1 as F-MINI12 48/300/5

```text
./encode_holofan.py self-test
# ok
```
