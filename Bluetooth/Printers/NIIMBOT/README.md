# NIIMBOT (BLE)

Wuhan Jingchen thermal label printers. Framing is `55 55 | cmd | len |
data | xor-bcc | AA AA` on a single GATT characteristic (write without
response + notify).

B1 (203 dpi, protocol 3) is the packed encoder. USB Type-C uses the same
bytes: [Serial/Printers/NIIMBOT](../../../Serial/Printers/NIIMBOT/).

| Model | Path |
|-------|------|
| B1 | [B1](B1/) |
