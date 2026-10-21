#include "sniff.h"

#include <driver/gpio.h>
#include <driver/uart.h>
#include <string.h>

#include "afterburner.h"
#include "heater_pins.h"
#include "heatgenie.h"

extern void notify(const String &s);
extern void uart_begin();

namespace {

static const int kUart = UART_NUM_1;
static const int kRxBuf = 512;
static const uint32_t kEdgeMs = 800;
static const uint32_t kDwellMs = 2500;
static const uint32_t kLockMs = 8000;
static const int kBauds[] = {2400, 4800, 9600, 19200, 25000, 38400, 57600, 115200};
static const int kNBauds = (int)(sizeof(kBauds) / sizeof(kBauds[0]));

enum SnState { SN_IDLE, SN_EDGES, SN_UART };

static SnState state = SN_IDLE;
static int lock_baud;  // 0 = sweep
static int baud_i;
static int cur_baud;
static uint32_t t0_ms;
static uint32_t dwell_ms;
static uint8_t cap[256];
static size_t cap_n;
static uint8_t last_cap[256];
static size_t last_n;
static int last_baud;
static const char *last_class = "none";
static uint32_t edges;
static uint32_t min_dt_us;
static int first_lvl;
static int last_lvl;
static int prev_lvl;
static uint32_t last_edge_us;
static bool saw_edge;

enum PingState { PING_IDLE, PING_WAIT };
static const int kPingBauds[] = {9600, 115200, 19200, 4800};
static const int kNPing = (int)(sizeof(kPingBauds) / sizeof(kPingBauds[0]));
static const uint32_t kPingDwellMs = 600;
static PingState ping_st = PING_IDLE;
static int ping_i;
static int ping_lock;  // 0 = sweep
static int ping_baud;
static uint8_t ping_tx[8];
static uint8_t ping_rx[128];
static size_t ping_n;
static uint32_t ping_t0;

static String hex_prefix(const uint8_t *p, size_t n, size_t max_bytes);
static const char *classify(const uint8_t *p, size_t n);

static void pins_txrx() {
  gpio_set_direction((gpio_num_t)HEATER_TX_GPIO, GPIO_MODE_INPUT_OUTPUT_OD);
  gpio_pulldown_dis((gpio_num_t)HEATER_TX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_TX_GPIO);
  gpio_set_direction((gpio_num_t)HEATER_RX_GPIO, GPIO_MODE_INPUT);
  gpio_pulldown_dis((gpio_num_t)HEATER_RX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_RX_GPIO);
}

static void pins_listen() {
  gpio_set_direction((gpio_num_t)HEATER_TX_GPIO, GPIO_MODE_INPUT);
  gpio_pulldown_dis((gpio_num_t)HEATER_TX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_TX_GPIO);
  gpio_set_direction((gpio_num_t)HEATER_RX_GPIO, GPIO_MODE_INPUT);
  gpio_pulldown_dis((gpio_num_t)HEATER_RX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_RX_GPIO);
}

static void uart_hd(int baud) {
  uart_driver_delete((uart_port_t)kUart);
  gpio_reset_pin((gpio_num_t)HEATER_TX_GPIO);
  gpio_reset_pin((gpio_num_t)HEATER_RX_GPIO);
  uart_config_t cfg = {};
  cfg.baud_rate = baud;
  cfg.data_bits = UART_DATA_8_BITS;
  cfg.parity = UART_PARITY_DISABLE;
  cfg.stop_bits = UART_STOP_BITS_1;
  cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  cfg.source_clk = UART_SCLK_DEFAULT;
  uart_param_config((uart_port_t)kUart, &cfg);
  uart_set_pin((uart_port_t)kUart, HEATER_TX_GPIO, HEATER_RX_GPIO, UART_PIN_NO_CHANGE,
               UART_PIN_NO_CHANGE);
  uart_driver_install((uart_port_t)kUart, kRxBuf, 256, 0, nullptr, 0);
  pins_txrx();
}

static void ping_send() {
  hg_auto_updata(ping_tx);
  ping_n = 0;
  uart_hd(ping_baud);
  delay(4);
  uart_flush_input((uart_port_t)kUart);
  uart_write_bytes((uart_port_t)kUart, ping_tx, 8);
  uart_wait_tx_done((uart_port_t)kUart, pdMS_TO_TICKS(50));
  ping_t0 = millis();
}

static void ping_collect() {
  size_t avail = 0;
  uart_get_buffered_data_len((uart_port_t)kUart, &avail);
  if (!avail || ping_n >= sizeof(ping_rx)) {
    return;
  }
  size_t room = sizeof(ping_rx) - ping_n;
  size_t want = avail < room ? avail : room;
  int n = uart_read_bytes((uart_port_t)kUart, ping_rx + ping_n, want, 0);
  if (n > 0) {
    ping_n += (size_t)n;
  }
}

static void ping_report() {
  const uint8_t *p = ping_rx;
  size_t n = ping_n;
  size_t echo = 0;
  // Same LV1 node echoes TX into RX. Strip our 8-byte AUTO_UPDATA if present.
  if (n >= 8 && memcmp(ping_rx, ping_tx, 8) == 0) {
    echo = 8;
    p += 8;
    n -= 8;
  }
  last_n = n;
  if (last_n) {
    memcpy(last_cap, p, last_n < sizeof(last_cap) ? last_n : sizeof(last_cap));
    if (last_n > sizeof(last_cap)) {
      last_n = sizeof(last_cap);
    }
  }
  last_baud = ping_baud;
  last_class = classify(p, n);
  char line[192];
  snprintf(line, sizeof(line), "ping baud=%d n=%u echo=%u class=%s hex=", ping_baud,
           (unsigned)n, (unsigned)echo, last_class);
  String s = line;
  s += hex_prefix(p, n, 24);
  notify(s);
}

static int ping_baud_at(int i) {
  if (ping_lock > 0) {
    return ping_lock;
  }
  if (i < 0 || i >= kNPing) {
    return 0;
  }
  return kPingBauds[i];
}

static void ping_finish() {
  ping_st = PING_IDLE;
  uart_begin();
  notify("ping done");
}

static String hex_prefix(const uint8_t *p, size_t n, size_t max_bytes) {
  size_t m = n < max_bytes ? n : max_bytes;
  String s;
  s.reserve(m * 2);
  for (size_t i = 0; i < m; i++) {
    char b[3];
    snprintf(b, sizeof(b), "%02x", p[i]);
    s += b;
  }
  if (n > m) {
    s += "..";
  }
  return s;
}

static const char *classify(const uint8_t *p, size_t n) {
  if (n == 0) {
    return "silent";
  }
  bool aa = false;
  bool abhdr = false;
  for (size_t i = 0; i + 8 <= n; i++) {
    if (p[i] != 0xAA) {
      continue;
    }
    aa = true;
    if (i + 52 <= n && p[i + 7] == 0xF2 && hg_crc16(p + i, 52) == 0) {
      return "hg-status";
    }
    if (p[i + 1] == 0x00 && hg_crc16(p + i, 8) == 0) {
      return "hg-cmd";
    }
  }
  for (size_t i = 0; i + (size_t)kAbFrame <= n; i++) {
    if (p[i] != 0x76 && p[i] != 0x78) {
      continue;
    }
    abhdr = true;
    if (ab_verify_crc(p + i)) {
      return p[i] == 0x76 ? "ab-76" : "ab-78";
    }
  }
  if (aa) {
    return "aa-badcrc";
  }
  if (abhdr) {
    return "ab-badcrc";
  }
  return "raw";
}

static void gpio_listen() {
  uart_driver_delete((uart_port_t)kUart);
  gpio_reset_pin((gpio_num_t)HEATER_TX_GPIO);
  gpio_reset_pin((gpio_num_t)HEATER_RX_GPIO);
  pins_listen();
}

static void uart_listen(int baud) {
  uart_driver_delete((uart_port_t)kUart);
  gpio_reset_pin((gpio_num_t)HEATER_TX_GPIO);
  gpio_reset_pin((gpio_num_t)HEATER_RX_GPIO);
  uart_config_t cfg = {};
  cfg.baud_rate = baud;
  cfg.data_bits = UART_DATA_8_BITS;
  cfg.parity = UART_PARITY_DISABLE;
  cfg.stop_bits = UART_STOP_BITS_1;
  cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  cfg.source_clk = UART_SCLK_DEFAULT;
  uart_param_config((uart_port_t)kUart, &cfg);
  // TX pad stays input so listen-only never drives the 5 V bus.
  uart_set_pin((uart_port_t)kUart, UART_PIN_NO_CHANGE, HEATER_RX_GPIO, UART_PIN_NO_CHANGE,
               UART_PIN_NO_CHANGE);
  uart_driver_install((uart_port_t)kUart, kRxBuf, 0, 0, nullptr, 0);
  pins_listen();
  uart_flush_input((uart_port_t)kUart);
}

static void edge_reset() {
  edges = 0;
  min_dt_us = 0xFFFFFFFFu;
  saw_edge = false;
  first_lvl = gpio_get_level((gpio_num_t)HEATER_RX_GPIO);
  prev_lvl = first_lvl;
  last_lvl = first_lvl;
  last_edge_us = micros();
}

static void edge_sample() {
  int v = gpio_get_level((gpio_num_t)HEATER_RX_GPIO);
  last_lvl = v;
  if (v == prev_lvl) {
    return;
  }
  uint32_t now = micros();
  uint32_t dt = now - last_edge_us;
  last_edge_us = now;
  prev_lvl = v;
  edges++;
  // Ignore sub-3 us glitches; 115200 bit is ~8.7 us, 25000 is 40 us.
  if (dt >= 3 && dt < min_dt_us) {
    min_dt_us = dt;
    saw_edge = true;
  }
}

static uint32_t est_baud() {
  if (!saw_edge || min_dt_us == 0 || min_dt_us == 0xFFFFFFFFu) {
    return 0;
  }
  return 1000000u / min_dt_us;
}

static void report_edges() {
  char line[128];
  snprintf(line, sizeof(line),
           "sniff edges=%u min_us=%u est_baud=%u first=%d last=%d", (unsigned)edges,
           saw_edge ? (unsigned)min_dt_us : 0, (unsigned)est_baud(), first_lvl, last_lvl);
  notify(String(line));
}

static void save_cap(int baud) {
  last_n = cap_n;
  if (last_n) {
    memcpy(last_cap, cap, last_n);
  }
  last_baud = baud;
  last_class = classify(last_cap, last_n);
}

static void report_uart() {
  save_cap(cur_baud);
  char line[192];
  snprintf(line, sizeof(line), "sniff baud=%d n=%u class=%s hex=", cur_baud, (unsigned)cap_n,
           last_class);
  String s = line;
  s += hex_prefix(cap, cap_n, 24);
  notify(s);
}

static void finish() {
  state = SN_IDLE;
  uart_begin();
  notify("sniff done");
}

static int baud_at(int i) {
  if (lock_baud > 0) {
    return lock_baud;
  }
  if (i < 0 || i >= kNBauds) {
    return 0;
  }
  return kBauds[i];
}

}  // namespace

void sniff_begin_sweep() {
  lock_baud = 0;
  baud_i = 0;
  cap_n = 0;
  state = SN_EDGES;
  gpio_listen();
  edge_reset();
  t0_ms = millis();
  notify("sniff start listen-only sweep");
}

void sniff_begin_baud(int baud) {
  if (baud < 300 || baud > 1000000) {
    notify("sniff bad baud");
    return;
  }
  lock_baud = baud;
  baud_i = 0;
  cap_n = 0;
  state = SN_EDGES;
  gpio_listen();
  edge_reset();
  t0_ms = millis();
  char line[64];
  snprintf(line, sizeof(line), "sniff start listen-only baud=%d", baud);
  notify(String(line));
}

void sniff_stop() {
  if (state == SN_IDLE) {
    notify("sniff idle");
    return;
  }
  if (state == SN_UART) {
    report_uart();
  } else if (state == SN_EDGES) {
    report_edges();
  }
  finish();
}

bool sniff_active() { return state != SN_IDLE; }

void sniff_tick() {
  if (state == SN_IDLE) {
    return;
  }
  if (state == SN_EDGES) {
    // Tight-sample in 20 ms slices so 8.7–40 us bits are visible, while
    // loop() can still run ArduinoOTA / NimBLE.
    uint32_t slice = millis();
    while (millis() - slice < 20 && millis() - t0_ms < kEdgeMs) {
      edge_sample();
    }
    if (millis() - t0_ms < kEdgeMs) {
      return;
    }
    report_edges();
    state = SN_UART;
    cap_n = 0;
    cur_baud = baud_at(baud_i);
    dwell_ms = lock_baud > 0 ? kLockMs : kDwellMs;
    uart_listen(cur_baud);
    t0_ms = millis();
    return;
  }
  if (state == SN_UART) {
    size_t avail = 0;
    uart_get_buffered_data_len((uart_port_t)kUart, &avail);
    if (avail && cap_n < sizeof(cap)) {
      size_t room = sizeof(cap) - cap_n;
      size_t want = avail < room ? avail : room;
      int n = uart_read_bytes((uart_port_t)kUart, cap + cap_n, want, 0);
      if (n > 0) {
        cap_n += (size_t)n;
      }
    }
    if (millis() - t0_ms < dwell_ms) {
      return;
    }
    report_uart();
    if (lock_baud > 0) {
      finish();
      return;
    }
    baud_i++;
    if (baud_i >= kNBauds) {
      finish();
      return;
    }
    cap_n = 0;
    cur_baud = baud_at(baud_i);
    uart_listen(cur_baud);
    t0_ms = millis();
  }
}

String sniff_status_line() {
  char line[128];
  if (state == SN_EDGES) {
    snprintf(line, sizeof(line), "sniff edges t=%u n_edge=%u",
             (unsigned)(millis() - t0_ms), (unsigned)edges);
    return String(line);
  }
  if (state == SN_UART) {
    snprintf(line, sizeof(line), "sniff baud=%d t=%u n=%u", cur_baud,
             (unsigned)(millis() - t0_ms), (unsigned)cap_n);
    return String(line);
  }
  snprintf(line, sizeof(line), "sniff last baud=%d n=%u class=%s", last_baud, (unsigned)last_n,
           last_class);
  return String(line);
}

String sniff_last_hex() { return hex_prefix(last_cap, last_n, last_n); }

const char *sniff_last_class() { return last_class; }

int sniff_last_baud() { return last_baud; }

size_t sniff_last_n() { return last_n; }

void sniff_edges(uint32_t ms) {
  // Sample RX on the LV1 node. Do not reset the pin, so a live Afterburner
  // poll still toggles it if GPIO6 is jumpered to the same shifter as GPIO5.
  uint32_t t0 = millis();
  edges = 0;
  min_dt_us = 0xFFFFFFFFu;
  saw_edge = false;
  first_lvl = gpio_get_level((gpio_num_t)HEATER_RX_GPIO);
  prev_lvl = first_lvl;
  last_lvl = first_lvl;
  last_edge_us = micros();
  while (millis() - t0 < ms) {
    edge_sample();
  }
  last_class = "edges";
  last_baud = 0;
  last_n = 0;
  report_edges();
}

void ping_begin_sweep() {
  if (state != SN_IDLE) {
    sniff_stop();
  }
  ping_lock = 0;
  ping_i = 0;
  ping_baud = ping_baud_at(0);
  ping_st = PING_WAIT;
  notify("ping AUTO_UPDATA 9600/115200/19200/4800");
  ping_send();
}

void ping_begin_baud(int baud) {
  if (baud < 300 || baud > 1000000) {
    notify("ping bad baud");
    return;
  }
  if (state != SN_IDLE) {
    sniff_stop();
  }
  ping_lock = baud;
  ping_i = 0;
  ping_baud = baud;
  ping_st = PING_WAIT;
  char line[64];
  snprintf(line, sizeof(line), "ping AUTO_UPDATA baud=%d", baud);
  notify(String(line));
  ping_send();
}

bool ping_active() { return ping_st != PING_IDLE; }

void ping_tick() {
  if (ping_st != PING_WAIT) {
    return;
  }
  ping_collect();
  if (millis() - ping_t0 < kPingDwellMs) {
    return;
  }
  ping_report();
  if (ping_lock > 0) {
    ping_finish();
    return;
  }
  ping_i++;
  if (ping_i >= kNPing) {
    ping_finish();
    return;
  }
  ping_baud = ping_baud_at(ping_i);
  ping_send();
}
