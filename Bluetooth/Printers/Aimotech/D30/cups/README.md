# CUPS driver for Aimotech D30 (Print Master)

Package name **printer-driver-aimotech**. Userspace backend + filter +
PPD/drv. The backend opens **RFCOMM channel 1**, sends the Print Master
handshake (`1F 11 38` / `12` / `13` / `07`), then writes `ESC @` +
`GS v 0` + `ESC d 23`. Same framing as `encode_aimotech.py`.

This is the native CUPS path. The label-bridge IPP server on :8631 is
a phone/LAN path and is not this driver. This is not a Windows WHQL
or kernel module. Do not send Nelko `SIZE`/`GAP` TSPL here. Do not
invent GATT `FFE0`.

URI: `aimotech://AA-BB-CC-DD-EE-FF` (dash-separated MAC). CUPS treats
colons in the host as a port, so `lpadmin` rejects colon-form URIs.
The backend still parses colon, dash, and 12-hex forms; RFCOMM uses
colon MACs. Do not put a live MAC in the pack. Match BLE name **D30**
/ Print Master / Phomemo / Quin. Do not offer a Nelko P21 this URI.

Frames are recovered from Print Master 5.23.1. **Live D30 eject is
unproven** in this pack revision.

## Who does what

| Step | Who | Interface |
|------|-----|-----------|
| Install the driver | root, once | `dpkg -i`, `make install`, or rpm |
| Add the queue | `lpadmin` group | CUPS web, GNOME, KDE, system-config-printer, `lpadmin`, `aimotech-setup-printer` |
| Print | anyone CUPS allows to print | `lp`, `lpr`, Print dialogs |

The backend installs mode **0700** owned by root so cupsd runs it as
root. Job submitters do not need `sudo` and do not need the
`bluetooth` group. On Debian the default cupsd policy allows local
`lp` / `lpr` for Create-Job/Print-Job. `cups-files.conf` `SystemGroup
root lpadmin` is for adding printers, not for printing.

Keep the printer **unpaired** in bluetoothctl. A raw RFCOMM socket
does not need a pair.

## Files

| File | Installs as |
|------|-------------|
| `backend-aimotech` | `/usr/lib/cups/backend/aimotech` (mode **0700**, owner root) |
| `rastertoaimotech.py` | `/usr/lib/cups/filter/rastertoaimotech` (mode 0755) |
| `aimotech_bt.py` | `/usr/share/printer-driver-aimotech/aimotech_bt.py` |
| `encode_aimotech.py` | `/usr/share/printer-driver-aimotech/encode_aimotech.py` |
| `aimotech.drv` | `/usr/share/cups/drv/aimotech.drv` (`lpinfo -m` → `drv:///aimotech.drv/aimotechd30.ppd`) |
| `Aimotech_D30.ppd` | `/usr/share/ppd/aimotech/Aimotech_D30.ppd` |
| `aimotech-setup-printer` | `/usr/bin/aimotech-setup-printer` |
| `printer-driver-aimotech.ppd-updater` | `/usr/share/cups/ppd-updaters/` |

Filter needs Python 3 and Pillow (`python3-pil`). Backend is stdlib
(`AF_BLUETOOTH`). PDF: `poppler-utils` (`pdftoppm`) or `pypdfium2`.
Do not ship a global `mime.convs` that would steal PNG/raster jobs
from other printers; filters bind through the PPD/`drv` only.

## Install the driver (root, once)

From this directory:

```
make check
make deb
sudo dpkg -i printer-driver-aimotech_0.3.7_all.deb
sudo apt-get install -f
```

Generic prefix:

```
sudo make install PREFIX=/usr
```

RPM spec: `rpm/printer-driver-aimotech.spec` (`python3-pillow` on Fedora).

Debian Depends: `cups` `python3-pil`. Recommends: `bluez`
`poppler-utils`. Suggests: `cups-bsd` `system-config-printer`.

The `.deb` is a **build artifact**. Commit `debian/` source, the
Makefile, drv, PPD, backend, filter, and setup helper. Do not commit
`*.deb`.

After install, `lpinfo -m` lists `drv:///aimotech.drv/aimotechd30.ppd`.
Power the D30; `lpinfo -v` lists `aimotech://` for BlueZ names in the
D30 family (never nelko/p21 or ogrphy/jbd). After a successful
discover, the backend writes `/var/cache/cups/aimotech.devices` so
`lpinfo -v` still lists that printer when it is off.

## Add the queue (lpadmin, once)

The CUPS dest is what KDE System Settings → Printers shows. It stays
when the D30 is powered off. **Add Printer** is live Get-Devices; that
list is empty until BlueZ has seen the printer this boot (or the
last-seen cache exists). Prefer the setup helper, including while the
printer is off:

```
aimotech-setup-printer --list
aimotech-setup-printer
aimotech-setup-printer --mac 01:23:45:67:89:AB
```

```
lpadmin -p AimotechD30 -E -v aimotech://01-23-45-67-89-AB \
  -m drv:///aimotech.drv/aimotechd30.ppd \
  -D AimotechD30 -o printer-error-policy=retry-job
```

`retry-job` keeps jobs in the queue until the printer is back.
Description (`-D`) is the title in KDE's printer list.

Common UIs (same driver, same backend):

- CUPS web: http://localhost:631/admin → Add Printer
- GNOME Settings → Printers
- KDE System Settings → Printers (the queue list, not Add Printer)
- `system-config-printer`

Pick the discovered `aimotech://` device (or type the URI) and the
**Aimotech D30 Print Master SPP** driver. KDE 6.7's Add Printer
connection page has no `aimotech` scheme; if that UI says the feature
is not available, use `aimotech-setup-printer` then reopen System
Settings. The list title is Description (for example **D30 Print
Master SPP**), not only the queue name.

## Print (LPR permissions, no root)

```
lp -d AimotechD30 photo.png
lpr -P AimotechD30 photo.png
```

Media is 12×40 mm at 203 dpi (96×320 dots on a 12 mm head). The filter
contain-fits the page onto one label. Raster packing is img2Nv
invert=true (bottom-right to top-left).

## Dry-run from the pack (no root)

```
make check
./rastertoaimotech.py 1 user title 1 '' /path/to/label.png > /tmp/d30-cups.bin
./aimotech-setup-printer --list
./aimotech-setup-printer --dry-run --mac 01:23:45:67:89:AB
```

`DEVICE_URI=aimotech://01-23-45-67-89-AB ./backend-aimotech 1 user title 1 '' /tmp/d30-cups.bin`
sends that job. Ask before a live send; the backend writes RFCOMM.

## Checks

```
make check
./aimotech_bt.py self-test
./rastertoaimotech.py self-test
./backend-aimotech self-test
../encode_aimotech.py self-test
```

## Troubleshooting

CUPS ignores a world-executable backend. Keep `aimotech` mode 0700.

`lpadmin` rejects colon MACs as a port. Advertise dash hosts
(`aimotech://AA-BB-CC-DD-EE-FF`). The backend still parses colon, dash,
and 12-hex forms.

If Add Printer shows no `aimotech://` device, the printer is off and
there is no last-seen cache yet, BlueZ has not seen it this boot, or
the name is not in the D30 family. Pass `--mac` to
`aimotech-setup-printer`. Discovery never prints the placeholder MAC.
The backend (root) also reads `/var/lib/bluetooth` and
`/var/cache/cups/aimotech.devices` when those paths are listable.

If jobs fail after packaging, check `/var/log/cups/error_log`. An
AppArmor `cupsd` profile that blocks Bluetooth may need a local
exception. Do not `bluetoothctl pair`. Do not TSPL this printer. Do
not TSPL OGRPHY.
