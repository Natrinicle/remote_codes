---
name: cups-label-printer
description: Use when packaging CUPS drivers for Bluetooth label printers (Nelko P21, Aimotech D30) or their KDE queues.
---

# CUPS label-printer packaging

**REQUIRED SUB-SKILL:** **cups-custom-backend** for KDE list vs Add Printer,
0700 backends, dash-MAC URIs, last-seen cache, and `retry-job`.

This skill only names the catalog trees. Do not grow
**reverse-engineering-protocols**. Protocol bytes stay in the unit encoder
and cups README.

## Exemplars

| Unit | Tree | Scheme | Job language |
|------|------|--------|--------------|
| Nelko P21 | `Bluetooth/Printers/Nelko/P21/cups/` | `nelko://` | TSPL2 |
| Aimotech / Phomemo D30 | `Bluetooth/Printers/Aimotech/D30/cups/` | `aimotech://` | ESC/POS `GS v 0` |

Follow persist in `aimotech_bt.py` / `aimotech-setup-printer` (0.3.7+):
`/var/cache/cups/<scheme>.devices`, write cache only on `live_seen`,
`lpadmin -D` + `printer-error-policy=retry-job`, `--mac` while off.

Mirror that pattern when touching Nelko (`nelko.devices`). Keep name
allow/deny so discovery never offers OGRPHY/JBD a TSPL URI or Nelko a
D30 URI.

Pack rule **cups-label-queue**.

## Do not

- Invent GATT `FFE0` on D30. D30 print path is classic SPP `00001101`.
- Send TSPL to Aimotech / D30.
- `bluetoothctl pair`.
- Commit `.deb` builds, live MACs, or camera `IMG*.jpg`.
- Copy this skill into the general pack (catalog paths live here).
- Treat live RFCOMM on D30 as proven until a job ejects.

## Related

**cups-custom-backend**, **pack-artifact-names**, unit `encode_nelko.py` /
`encode_aimotech.py`. Palace: `printer-driver-nelko`, `printer-driver-aimotech`,
`cups-custom-backend`.
