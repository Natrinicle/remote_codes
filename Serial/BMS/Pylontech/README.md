# Pylontech (RS485 console)

Pylontech US-series (and V2 / Pytes-labelled siblings) on RS485. Typical
**115200 8N1**. The console is ASCII. This helper only prints **read**
commands.

Do not send `togpro`, `setprt`, or `config` from this pack.

## Identification

| | |
|--|--|
| UART | 115200 8N1 RS485 |
| Read | `help` `pwr` `bat` |
| Skip | `togpro` `setprt` `config` |

```text
./encode_pylontech.py help
./encode_pylontech.py pwr
./encode_pylontech.py bat
./encode_pylontech.py self-test
```

Each command is ASCII plus CR.

## Notes

- Own hardware only.
- Read-only from this folder.
