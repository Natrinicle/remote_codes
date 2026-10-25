# CUPS driver for Nelko P21

Package name **printer-driver-nelko**. Userspace backend + filter +
PPD/drv. The backend opens **RFCOMM channel 1** and writes the same
TSPL2 job that ejected on a live P21 (SIZE 14×40, DIRECTION 1,1,
DENSITY 15, BITMAP mode 1, 0-bit black).

This is the native CUPS path. The label-bridge IPP server on :8631 is
a phone/LAN path and is not this driver. This is not a Windows WHQL
or kernel module.

URI: `nelko://AA-BB-CC-DD-EE-FF` (dash-separated MAC). CUPS treats
colons in the host as a port, so `lpadmin` rejects
`nelko://AA:BB:CC:DD:EE:FF`. The backend still parses colon, dash, and
12-hex forms; RFCOMM uses colon MACs. Do not put a live MAC in the
pack. Match BLE name **P21**. Do not send TSPL to other `0000ff00`
devices.

## Who does what

| Step | Who | Interface |
|------|-----|-----------|
| Install the driver | root, once | `dpkg -i`, `make install`, or rpm |
| Add the queue | `lpadmin` group | CUPS web, GNOME, KDE, system-config-printer, `lpadmin`, `nelko-setup-printer` |
| Print | anyone CUPS allows to print | `lp`, `lpr`, Print dialogs |

The backend installs mode **0700** owned by root so cupsd runs it as
root. Job submitters do not need `sudo` and do not need the
`bluetooth` group. On Debian the default cupsd policy allows local
`lp` / `lpr` for Create-Job/Print-Job. `cups-files.conf` `SystemGroup
root lpadmin` is for adding printers, not for printing.

Keep the printer **unpaired** in bluetoothctl. BlueZ `Device.Connect()`
on this JieLi dual-mode unit tries BR/EDR, hits
`org.bluez.Error.BREDR.ProfileUnavailable`, and tears down LE. A raw
RFCOMM socket does not need a pair.

## Files

| File | Installs as |
|------|-------------|
| `backend-nelko` | `/usr/lib/cups/backend/nelko` (mode **0700**, owner root) |
| `rastertonelko.py` | `/usr/lib/cups/filter/rastertonelko` (mode 0755) |
| `nelko_bt.py` | `/usr/share/printer-driver-nelko/nelko_bt.py` |
| `nelko.drv` | `/usr/share/cups/drv/nelko.drv` (`lpinfo -m` → `drv:///nelko.drv/nelkop21.ppd`) |
| `Nelko_P21.ppd` | `/usr/share/ppd/nelko/Nelko_P21.ppd` |
| `nelko-setup-printer` | `/usr/bin/nelko-setup-printer` |
| `printer-driver-nelko.ppd-updater` | `/usr/share/cups/ppd-updaters/` |

Filter needs Python 3 and Pillow (`python3-pil`). Backend is stdlib
(`AF_BLUETOOTH`). PDF: `poppler-utils` (`pdftoppm`) or `pypdfium2`.
Do not ship a global `mime.convs` that would steal PNG/raster jobs
from other printers; filters bind through the PPD/`drv` only.

## Install the driver (root, once)

From this directory:

```
make check
make deb
sudo dpkg -i printer-driver-nelko_0.3.6_all.deb
sudo apt-get install -f
```

Generic prefix:

```
sudo make install PREFIX=/usr
```

RPM spec: `rpm/printer-driver-nelko.spec` (`python3-pillow` on Fedora).

Debian Depends: `cups` `python3-pil`. Recommends: `bluez`
`poppler-utils`. Suggests: `cups-bsd` `system-config-printer`.

After install, `lpinfo -m` lists `drv:///nelko.drv/nelkop21.ppd`.
Power the P21; `lpinfo -v` lists `nelko://` for BlueZ names in the P21
family (never ogrphy/jbd).

## Add the queue (lpadmin, once)

Any of these, after the package is installed. Replace the MAC.

```
nelko-setup-printer --list
nelko-setup-printer
nelko-setup-printer --mac 01:23:45:67:89:AB
```

```
lpadmin -p NelkoP21 -E -v nelko://01-23-45-67-89-AB \
  -m drv:///nelko.drv/nelkop21.ppd
```

Common UIs (same driver, same backend):

- CUPS web: http://localhost:631/admin → Add Printer
- GNOME Settings → Printers
- KDE print-manager
- `system-config-printer`

Pick the discovered `nelko://` device (or type the URI) and the
**Nelko P21 RFCOMM TSPL** driver.

## Print (LPR permissions, no root)

```
lp -d NelkoP21 photo.png
lp -d NelkoP21 -o NelkoDensity=15 note.pdf
lpr -P NelkoP21 photo.png
```

Media is 14×40 mm at 203 dpi (96×320 dots on a 12 mm head). The filter
contain-fits the page onto one label.

## Dry-run from the pack (no root)

```
make check
./rastertonelko.py 1 user title 1 '' /path/to/label.png > /tmp/p21-cups.tspl
./nelko-setup-printer --list
./nelko-setup-printer --dry-run --mac 01:23:45:67:89:AB
```

`DEVICE_URI=nelko://01-23-45-67-89-AB ./backend-nelko 1 user title 1 '' /tmp/p21-cups.tspl`
sends that job. Ask before a live send; the backend writes RFCOMM.

## Checks

```
make check
./nelko_bt.py self-test
./rastertonelko.py self-test
./backend-nelko self-test
../encode_nelko.py self-test
```

## Troubleshooting

CUPS ignores a world-executable backend. Keep `nelko` mode 0700.

`lpadmin` rejects colon MACs (`nelko://AA:BB:CC:DD:EE:FF`) as a port.
Advertise dash hosts (`nelko://AA-BB-CC-DD-EE-FF`). The backend still
parses colon, dash, and 12-hex forms.

If Add Printer shows no `nelko://` device, the printer is off, BlueZ
has not seen it yet, or the name is not in the P21 family. Type the
URI. Discovery never prints the placeholder MAC. The backend (root)
also reads `/var/lib/bluetooth` cache when that directory is
listable.

If jobs fail after packaging, check `/var/log/cups/error_log`. An
AppArmor `cupsd` profile that blocks Bluetooth may need a local
exception. Do not `bluetoothctl pair`. Do not TSPL OGRPHY.
