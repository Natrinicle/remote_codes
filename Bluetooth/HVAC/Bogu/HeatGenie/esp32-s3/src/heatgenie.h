#pragma once

#include <Arduino.h>
#include <stddef.h>
#include <stdint.h>

// HeatGenie / Bogu AA+CRC16 frames (same as BLE 3A01/3A00).

struct HgStatus {
  bool valid;
  uint8_t mode;
  const char *mode_name;
  float volts;
  uint16_t altitude;
  int cabin_f;
  int shell_f;
  float pump_hz;
  float glow;
  float fan;
  uint16_t error;
  const char *error_name;
};

uint16_t hg_crc16(const uint8_t *data, size_t n);
void hg_cmd(uint8_t cmd, uint8_t a0, uint8_t a1, uint8_t a2, uint8_t out[8]);
void hg_auto_updata(uint8_t out[8]);
void hg_key(uint8_t a0, uint8_t out[8]);  // unique A1 1-255
bool hg_decode_status(const uint8_t *frame, size_t len, HgStatus *st);
const char *hg_mode_name(uint8_t mode);
