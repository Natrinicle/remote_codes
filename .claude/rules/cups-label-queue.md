---
paths:
  - "**/Bluetooth/Printers/**/cups/**"
  - "**/backend-nelko"
  - "**/backend-aimotech"
  - "**/*-setup-printer"
---

# CUPS label queue (remote_codes)

When editing `Bluetooth/Printers/**/cups/**`:

1. Load **cups-label-printer** then **cups-custom-backend**.
2. Keep backend mode 0700 in the Makefile / packaging.
3. Dash-MAC URI hosts. Last-seen `/var/cache/cups/<scheme>.devices`; write
   only when live BlueZ returned names.
4. Setup helper: `-D` Description and `-o printer-error-policy=retry-job`.
5. `--mac` while the printer is off. Empty Get-Devices is not a missing dest.
6. Name allow/deny stays in `*_bt.py`. Never TSPL OGRPHY/JBD. Never TSPL D30.
7. Do not invent `FFE0`. Do not commit `.deb` or live MACs.
