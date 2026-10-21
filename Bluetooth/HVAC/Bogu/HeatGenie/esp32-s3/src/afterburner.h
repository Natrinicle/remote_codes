#pragma once

#include <stddef.h>
#include <stdint.h>

// Afterburner / stock LCD blue-wire frames.
// Source of truth: gitlab.com/mrjones.id.au/bluetoothheater
//   src/Protocol/Protocol.h  Controller/Heater unions
//   src/Utility/MODBUS-CRC16.cpp
//   src/Protocol/TxManage.cpp  (0x76 vs 0x78, ON 0xA0, OFF 0x05)
//   src/Protocol/BlueWireTask.cpp  (25000 8N1, ~1 s poll, 50 ms RX timeout)
// 24 bytes, CRC-16/MODBUS over the first 22, MSB at [22] LSB at [23].
// Header 0x76 = active (ECU may save Pmin/Pmax to EEPROM).
// Header 0x78 = passive (rotary; ECU ignores bytes 5–11).

static const int kAbFrame = 24;

struct AbRx {
  bool valid;
  uint8_t run;
  const char *run_name;
  uint8_t err;
  uint8_t stored_err;
  const char *err_name;
  float volts;
  uint16_t fan_rpm;
  float fan_v;
  int16_t shell_c;
  float glow_v;
  float glow_a;
  float pump_hz;
  float pump_fixed_hz;
};

struct AbTx {
  uint8_t header;  // 0x76 active, 0x78 passive
  uint8_t command;  // 0x00 NOP, 0xA0 start, 0x05 stop
  int8_t actual_c;
  int8_t demand;  // degC in thermo; 8–35 mapped to Pmin–Pmax in Hz mode
  float pmin_hz;
  float pmax_hz;
  uint16_t fan_min;
  uint16_t fan_max;
  uint8_t volt_x10;  // 120 or 240
  uint8_t fan_sensor;
  bool thermostat;  // true=0x32, false=0xCD Fixed Hz
  int8_t tmin_c;
  int8_t tmax_c;
  uint8_t glow_drive;
  bool prime;
  int16_t altitude_m;
  bool altitude_sensor;
};

uint16_t ab_crc16(const uint8_t *data, size_t n);
void ab_set_crc(uint8_t frame[kAbFrame]);
bool ab_verify_crc(const uint8_t *frame);
void ab_defaults(AbTx *tx);
void ab_encode_tx(const AbTx *tx, uint8_t frame[kAbFrame]);
bool ab_decode_rx(const uint8_t *frame, size_t n, AbRx *st);
bool ab_crc_selftest();
const char *ab_run_name(uint8_t run);
const char *ab_err_name(uint8_t err);
