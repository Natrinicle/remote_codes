#include "heatgenie.h"

#include <esp_system.h>
#include <string.h>

namespace {

// CRC-16-CCITT nibble table from HeatGenie app-service.js Ee(), init 0.
const uint16_t kCrcNibble[16] = {
    0,     4129,  8258,  12387, 16516, 20645, 24774, 28903,
    33032, 37161, 41290, 45419, 49548, 53677, 57806, 61935,
};

const char *kMode[] = {"reset",     "ignite", "auto",     "manual", "cooldown",
                       "standby",   "error",  "pump",     "vent",   "start-stop"};

}  // namespace

uint16_t hg_crc16(const uint8_t *data, size_t n) {
  uint16_t acc = 0;
  for (size_t i = 0; i < n; i++) {
    uint8_t b = data[i];
    uint16_t nib = (acc >> 12) & 65535;
    acc = (uint16_t)((acc << 4) & 65535);
    acc ^= kCrcNibble[15 & ((nib & 65535) ^ (b >> 4))];
    nib = (uint16_t)((acc & 65535) >> 12);
    acc = (uint16_t)((acc << 4) & 65535);
    acc ^= kCrcNibble[15 & ((nib & 65535) ^ (15 & b))];
  }
  return acc & 65535;
}

void hg_cmd(uint8_t cmd, uint8_t a0, uint8_t a1, uint8_t a2, uint8_t out[8]) {
  out[0] = 0xAA;
  out[1] = 0x00;
  out[2] = cmd;
  out[3] = a0;
  out[4] = a1;
  out[5] = a2;
  uint16_t c = hg_crc16(out, 6);
  out[6] = (uint8_t)(c >> 8);
  out[7] = (uint8_t)(c & 255);
}

void hg_auto_updata(uint8_t out[8]) {
  hg_cmd(101, 2, 20, 30, out);  // ADDR_TYPE_REG, 2s, 30
}

void hg_key(uint8_t a0, uint8_t out[8]) {
  uint8_t r = (uint8_t)(1 + (esp_random() % 255));
  hg_cmd(97, a0, r, 0, out);  // DB0_DN_CMD
}

const char *hg_mode_name(uint8_t mode) {
  if (mode < 10) {
    return kMode[mode];
  }
  return "unknown";
}

bool hg_decode_status(const uint8_t *frame, size_t len, HgStatus *st) {
  memset(st, 0, sizeof(*st));
  if (len < 52 || frame[0] != 0xAA || frame[7] != 0xF2) {
    return false;
  }
  if (hg_crc16(frame, len) != 0) {
    return false;
  }
  const uint8_t *p = frame + 8;
  auto u16 = [&](int off) -> uint16_t {
    return (uint16_t)(p[off] | (p[off + 1] << 8));
  };
  uint16_t cabin = u16(6);
  uint16_t shell = u16(8);
  uint16_t err = u16(20);
  st->valid = true;
  st->mode = (uint8_t)(p[0] & 15);
  st->mode_name = hg_mode_name(st->mode);
  st->volts = u16(2) / 10.0f;
  st->altitude = u16(4);
  st->cabin_f = (int)((320 + 1.8f * cabin) / 10);
  st->shell_f = (int)((320 + 1.8f * shell) / 10);
  st->pump_hz = u16(10) / 10.0f;
  st->glow = u16(12) / 10.0f;
  st->fan = u16(14) / 10.0f;
  st->error = err;
  st->error_name = (err == 512) ? "E-10" : "";
  return true;
}
