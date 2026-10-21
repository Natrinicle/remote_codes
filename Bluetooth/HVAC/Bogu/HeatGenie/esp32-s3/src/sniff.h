#pragma once

#include <Arduino.h>
#include <stddef.h>
#include <stdint.h>

// Listen-only blue-wire sniffer on HEATER_RX_GPIO (TX pad left as input).
// Never uart_write. Afterburner poll must stay paused while sniff_active().

void sniff_begin_sweep();
void sniff_begin_baud(int baud);
void sniff_stop();  // restore Afterburner uart_begin()
bool sniff_active();
void sniff_tick();
String sniff_status_line();
String sniff_last_hex();
const char *sniff_last_class();
int sniff_last_baud();
size_t sniff_last_n();

// GPIO pulse sample. Does not take the UART. Safe while poll is running
// (catches our own 0x78 TX if the pin is actually toggling).
void sniff_edges(uint32_t ms);

// HeatGenie AUTO_UPDATA ping (AA 00 65 02 14 1E …). Not heater ON.
// TX=HEATER_TX_GPIO, RX=HEATER_RX_GPIO on the same LV1 node, then 25000.
void ping_begin_sweep();
void ping_begin_baud(int baud);
bool ping_active();
void ping_tick();
