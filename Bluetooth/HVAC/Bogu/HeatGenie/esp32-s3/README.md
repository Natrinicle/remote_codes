# HeatGenie ESP32-S3 Super Mini

Half-duplex UART on **two Super Mini pads** (**GPIO5 TX**, **GPIO6 RX**) using
the **Afterburner / stock LCD** protocol from
[Ray Jones bluetoothheater](https://gitlab.com/mrjones.id.au/bluetoothheater/):
25000 8N1, 24-byte frames, CRC-16/MODBUS, header `0x76` (active, EEPROM save)
or `0x78` (passive, rotary — ECU ignores Pmin/Pmax). HeatGenie BLE `AA`+CCITT
frames are a different bus. `ping` can still send AUTO_UPDATA on this wire.

Advertises **HeatGenie-S3** Nordic UART. Runs **AP+STA**: SoftAP **HeatGenie-S3**
at `192.168.4.1`, plus STA on `WIFI_SSID_1` then `WIFI_SSID_2` from
`secrets.h`. Serves `http://heatgenie-s3.local/` (mDNS on STA) and ArduinoOTA
on port **3232**. Do not port-forward 80 or 3232.

## Wire

Heater controller plug is **5 V** on red, **GND** on black, **data** on blue
(one wire). ESP32 UART wants two pads on that same node: open-drain TX plus
input RX. ESP32-S3 GPIO is 3.3 V. Use a 5 V↔3.3 V shifter (BSS138). Do not
put 12 V or the blue wire straight on a GPIO.

| Super Mini | Shifter / heater |
|---|---|
| GND | black / controller GND |
| GPIO5 (TX, open-drain + pull-up) | BSS138 **LV1** |
| GPIO6 (RX, input + pull-up) | **same LV1** (jumper to GPIO5) |
| shifter HV1 | blue data |
| shifter HV / 5 V rail | controller red 5 V (not the 12 V heater feed) |

Unbind the phone HeatGenie app (one master on the wire). Until GPIO6 is
jumpered to LV1, `probe` / `ping` / `dump` stay deaf on RX (`echo=0`).

## Flash (USB, first time / partition table)

`partitions_ota.csv` is dual-OTA (`ota_0` / `ota_1`, 1.875 MB each). The first
image after a partition-table change must go over USB. Firmware calls
`esp_ota_mark_app_valid_cancel_rollback()` after BLE is up so a crash does
not jump to an empty slot. Later images use WiFi.

```bash
cd Bluetooth/HVAC/Bogu/HeatGenie/esp32-s3
cp secrets.example.h secrets.h   # SSIDs, OTA_PASSWORD, AP_PASS; gitignored
# ArduinoOTA --auth lives in gitignored platformio_override.ini
pio run -t upload -e s3-super-mini --upload-port /dev/ttyACM0
~/.platformio/penv/bin/esptool --chip esp32s3 --port /dev/ttyACM0 --no-stub --after watchdog-reset run
```

USB-C on the Super Mini, Espressif USB JTAG (`303a:1001`). Opening ACM0
(including `pio device monitor`) issues `USB_UART_CHIP_RESET` and leaves the
ROM in download (`boot:0x23`). After flash, leave the port closed and confirm
via BLE **HeatGenie-S3** (`status` / `dump` / `ota`). Identify the port by the
board USB serial from `esptool`; do not flash a port Rayforge already holds
(laser, CH340 `/dev/ttyUSB0`).

BLE address is typically USB MAC + 1, name **HeatGenie-S3**.

## OTA (after the USB flash)

ArduinoOTA hostname `heatgenie-s3`, port 3232. HTTP Basic user is `ota`;
password is `OTA_PASSWORD` in `secrets.h`. SoftAP SSID is `AP_SSID`
(default **HeatGenie-S3**); password is `AP_PASS`. UART polling pauses
while an OTA is in progress.

**STA (same LAN as `WIFI_SSID_1` / `WIFI_SSID_2`):**

```bash
# extra_configs loads gitignored platformio_override.ini (--auth).
# espota's own mDNS is flaky; prefer the IP from BLE `ota`.
pio run -t upload -e s3-ota --upload-port 192.168.x.y
```

SoftAP starts if STA is still down ~15 s after boot, or immediately on BLE
`ap`. **Phone next to the heater:** join **HeatGenie-S3**, then open
`http://192.168.4.1/update` and POST `firmware.bin` (the PlatformIO
`.pio/build/s3-super-mini/firmware.bin`). From a laptop on that AP:

```bash
pio run -t upload -e s3-ota --upload-port 192.168.4.1
```

BLE `ota` or `net` reports `ap=` / `sta=` / `ota=heatgenie-s3.local:3232`.
HTTP `/` and `/cmd` require the same Basic auth; `/status` is open on the LAN.

## Phone

1. nRF Connect / Serial Bluetooth Terminal → **HeatGenie-S3**
2. Nordic UART RX characteristic:
   `quiet` (release the blue wire; boot default so factory HeatGenie BLE
   owns the bus), `talk` (resume Super Mini UART poll),
   `sniff` (listen-only baud sweep), `sniff 9600`, `sniff stop`,
   `ping` (HeatGenie AUTO_UPDATA at 9600/115200/19200/4800), `ping 9600`,
   `edges`, `probe`,
   `on` (0xA0), `off` (0x05), `status`, `dump`, `poll`, `ota` / `net`, `ap`,
   `active` / `passive`, `thermo` / `hz`,
   `pmin 0.9`, `pmax 4.3`, `demand 23`, `alt 2070`, `volt 12`,
   `prime on` / `prime off`, `raw …` (arbitrary bus bytes)
3. TX notify is the live status line. `dump` is last TX 24 bytes plus RX hex
   (and last sniffer capture if any).

HTTP (on LAN): `POST /cmd` with `c=on|off|poll|hz|thermo`.

## Baud / frames

Fixed **25000** 8N1 (GitLab `BlueWireTask.cpp` `initBlueWireSerial`). Poll
every 1 s (`NVStorage` `FrameRate` default 1000). After TX, read up to 48
bytes (echo + reply) with a 50 ms timeout (`RX_DATA_TIMOUT`) and strip the
24-byte echo. Do not `uart_flush_input` after TX — that discarded the ~5 ms
heater reply when TX and RX were muxed on one pin. Boot is **passive 0x78**,
command `00`, no ON.
`pmin`/`pmax`/`volt`/`alt` switch to **active 0x76** for 10 frames
(`TxManage::queueSysUpdate`) so the ECU can store mixture, then return to 0x78.

`hz` is Fixed pump mode (`0xCD`, actual temp 0, demand = Tmin → Pmin).
That is the altitude lean: `pmin 0.9` then `hz`. Confirm a CRC-valid RX
(`run=` not `no heater`) before writing mixture.

## Sniffer (listen-only)

`sniff` pauses Afterburner TX, samples GPIO6 edges (~800 ms) to estimate
baud, then listens RX-only at 2400 / 4800 / 9600 / 19200 / 25000 / 38400 /
57600 / 115200 (2.5 s each). GPIO5 is left as input (never driven). Classify:

| class | meaning |
|---|---|
| silent | no bytes at that baud |
| hg-status / hg-cmd | HeatGenie AA + CRC-16-CCITT |
| ab-76 / ab-78 | Afterburner 24-byte CRC-16/MODBUS |
| aa-badcrc / ab-badcrc | header match, CRC fail (wrong baud or noise) |
| raw | bytes, no known header |

`edges` (1.2 s) samples GPIO6 **without** tearing down UART, so a live 1 s
poll still shows TX toggles once GPIO6 is on the same LV1 node. `sniff 115200`
locks one baud for 8 s. `sniff stop` restores 25000 TX+RX poll. HTTP
`GET /sniff` is the last capture (open on the LAN, same as `/status`).

If this Super Mini is the only UART master, a listen-only sweep is silent
at every baud — that is a valid result. `ping` sends HeatGenie AUTO_UPDATA
(`aa006502141ed095`) at 9600, 115200, 19200, then 4800, strips TX echo
(`echo=8` when GPIO6 is jumpered), and reports `class=hg-cmd` / `hg-status`
if the ECU answers. That is not heater ON. Do not send `on` / `pmin` from
the sniffer.
