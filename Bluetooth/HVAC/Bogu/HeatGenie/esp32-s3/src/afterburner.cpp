#include "afterburner.h"

#include <string.h>

// CRC-16/MODBUS (poly 0x8005 reflected). Matches Ray Jones
// src/Utility/MODBUS-CRC16.cpp and the V9 protocol PDF captures.

uint16_t ab_crc16(const uint8_t *data, size_t n) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= data[i];
    for (int b = 0; b < 8; b++) {
      if (crc & 1) {
        crc = (uint16_t)((crc >> 1) ^ 0xA001);
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

void ab_set_crc(uint8_t frame[kAbFrame]) {
  uint16_t c = ab_crc16(frame, 22);
  frame[22] = (uint8_t)(c >> 8);
  frame[23] = (uint8_t)(c & 0xFF);
}

bool ab_verify_crc(const uint8_t *frame) {
  return ab_crc16(frame, 22) == (uint16_t)((frame[22] << 8) | frame[23]);
}

bool ab_crc_selftest() {
  // V9 PDF "Power On" rotary capture; CRC DC ED.
  static const uint8_t kSample[24] = {
      0x78, 0x16, 0x00, 0x16, 0x23, 0x10, 0x37, 0x06, 0x90, 0x11, 0x94, 0xF0,
      0x01, 0x32, 0x08, 0x23, 0x05, 0x00, 0x01, 0x2C, 0x0D, 0xAC, 0xDC, 0xED};
  return ab_verify_crc(kSample);
}

void ab_defaults(AbTx *tx) {
  memset(tx, 0, sizeof(*tx));
  // BlueWireTask.cpp defaults when no OEM controller is present.
  tx->header = 0x78;  // passive until a tune write
  tx->command = 0x00;
  tx->actual_c = 22;
  tx->demand = 23;
  tx->pmin_hz = 1.6f;
  tx->pmax_hz = 5.5f;
  tx->fan_min = 1680;
  tx->fan_max = 4500;
  tx->volt_x10 = 120;
  tx->fan_sensor = 1;
  tx->thermostat = true;
  tx->tmin_c = 8;
  tx->tmax_c = 35;
  tx->glow_drive = 5;
  tx->prime = false;
  tx->altitude_m = 3500;
  tx->altitude_sensor = false;
}

static uint8_t hz_byte(float hz) {
  int v = (int)(hz * 10.f + 0.5f);
  if (v < 0) {
    v = 0;
  }
  if (v > 255) {
    v = 255;
  }
  return (uint8_t)v;
}

void ab_encode_tx(const AbTx *tx, uint8_t frame[kAbFrame]) {
  memset(frame, 0, kAbFrame);
  frame[0] = tx->header;
  frame[1] = 0x16;
  frame[2] = tx->command;
  frame[3] = (uint8_t)tx->actual_c;
  frame[4] = (uint8_t)tx->demand;
  frame[5] = hz_byte(tx->pmin_hz);
  frame[6] = hz_byte(tx->pmax_hz);
  frame[7] = (uint8_t)(tx->fan_min >> 8);
  frame[8] = (uint8_t)(tx->fan_min & 0xFF);
  frame[9] = (uint8_t)(tx->fan_max >> 8);
  frame[10] = (uint8_t)(tx->fan_max & 0xFF);
  frame[11] = tx->volt_x10;
  frame[12] = tx->fan_sensor;
  frame[13] = tx->thermostat ? 0x32 : 0xCD;
  frame[14] = (uint8_t)tx->tmin_c;
  frame[15] = (uint8_t)tx->tmax_c;
  frame[16] = tx->glow_drive;
  frame[17] = tx->prime ? 0x5A : 0x00;
  if (tx->altitude_sensor) {
    frame[18] = 0xEB;
    frame[19] = 0x47;
  } else {
    frame[18] = 0x01;
    frame[19] = 0x2C;
  }
  frame[20] = (uint8_t)(((uint16_t)tx->altitude_m) >> 8);
  frame[21] = (uint8_t)(((uint16_t)tx->altitude_m) & 0xFF);
  if (!tx->thermostat) {
    // Fixed Hz: actual temp must be 0 (TxManage.cpp).
    frame[3] = 0;
  }
  ab_set_crc(frame);
}

const char *ab_run_name(uint8_t run) {
  switch (run) {
    case 0:
      return "standby";
    case 1:
      return "start-ack";
    case 2:
      return "igniting";
    case 3:
      return "ignite-pause";
    case 4:
      return "ignited";
    case 5:
      return "running";
    case 6:
      return "stopping";
    case 7:
      return "shutdown";
    case 8:
      return "cooling";
    default:
      return "unknown";
  }
}

const char *ab_err_name(uint8_t err) {
  // Protocol.h Heater.ErrState: 0/1 idle, 2+ = E-0n+1. Indices 11–13 are
  // Afterburner SmartError labels in Protocol.cpp Errstates[].
  switch (err) {
    case 0:
    case 1:
      return "";
    case 2:
      return "E-01";
    case 3:
      return "E-02";
    case 4:
      return "E-03";
    case 5:
      return "E-04";
    case 6:
      return "E-05";
    case 7:
      return "E-06";
    case 8:
      return "E-07";
    case 9:
      return "E-08";
    case 10:
      return "E-09";
    case 11:
      return "E-10";
    case 12:
      return "E-11";
    case 13:
      return "E-12";
    default:
      return "E-??";
  }
}

bool ab_decode_rx(const uint8_t *frame, size_t n, AbRx *st) {
  memset(st, 0, sizeof(*st));
  if (n < (size_t)kAbFrame) {
    return false;
  }
  if (frame[0] != 0x76 && frame[0] != 0x78) {
    return false;
  }
  if (frame[1] != 0x16) {
    return false;
  }
  if (!ab_verify_crc(frame)) {
    return false;
  }
  auto be16 = [&](int i) -> uint16_t {
    return (uint16_t)((frame[i] << 8) | frame[i + 1]);
  };
  st->valid = true;
  st->run = frame[2];
  st->err = frame[3];
  st->stored_err = frame[17];
  st->err_name = ab_err_name(st->err);
  st->volts = be16(4) / 10.0f + 0.6f;  // Protocol.cpp diode compensation
  st->fan_rpm = be16(6);
  st->fan_v = st->run ? be16(8) / 10.0f : 0;
  st->shell_c = (int16_t)be16(10);
  st->glow_v = be16(12) / 10.0f;
  st->glow_a = be16(14) / 100.0f;
  st->pump_hz = frame[16] / 10.0f;
  st->pump_fixed_hz = frame[19] / 10.0f;
  // Protocol.cpp getRunStateEx: runstate 2 with pump 0 is glow preheat.
  if (st->run == 2 && frame[16] == 0) {
    st->run_name = "glow";
  } else {
    st->run_name = ab_run_name(st->run);
  }
  return true;
}
