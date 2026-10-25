# Nelko

Ezink pocket and desktop thermal printers driven by the Nelko Android
app (`com.nelko.printer`). P21 prints TSPL2 over **RFCOMM channel 1**
(primary). GATT `0000ff00` write `ff02` carries the same bytes; answers
are on `ff01`, and `ff03` is credit flow-control.

| Model | Path |
|-------|------|
| P21 | [P21](P21/) |
| P21 CUPS | [P21/cups](P21/cups/) (`printer-driver-nelko`) |
