# EyeBond

Wi-Fi collectors used by the SmartESS app (`com.eybond.smartclient.ess`).
The dongle phones home to dessmonitor.com. Local hijack is UDP **58899**
then TCP **8899** initiated by the collector.

Inner UART on this pack's unit is **SRNE Modbus RTU**. Other EyeBond
tunnels (PI17/PI18, SMG) exist; do not assume them.

| Model | Path |
|-------|------|
| SmartESS | [SmartESS](SmartESS/) |
