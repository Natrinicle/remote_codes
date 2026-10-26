---
paths:
  - "Infrared/**"
  - "Bluetooth/**"
  - "Network/**"
  - "Serial/**"
  - "**/*.ir"
  - "**/encode_*.py"
---

# Pack artifact names

Name new remote_codes protocol helpers and folders by **protocol or wire
family**, not retail app or SKU, when the bytes are reusable.

- `encode_<protocol>.py` sits next to that protocol’s README.
- Folder `Type/Protocol/` for a reusable shout, or `Type/Brand/Model/` for a
  **product card**. Product cards may exist without an encoder.
- If several backends shout the same job (WiFi provision, BMS, printer job),
  add a thin router with an explicit table (protocol alias, SKU, setupType).
  A new backend is one `Type/<Protocol>/encode_<protocol>.py` plus one row
  in that table.
- READMEs name **example products recovered from** (brand, SKU, app id) so
  the catalog still finds Weight Gurus / Nelko / and other recovered units.
- IR captures stay `Brand_Model.ir` (flipper-ir-library). Do not rename
  existing HeatGenie / Nelko / JBD encoders under this rule’s first landing.
- No APKs, live SSIDs, PSKs, or personal MACs in the pack.
