#include <Arduino.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <ArduinoOTA.h>
#include <Update.h>
#include <esp_ota_ops.h>
#include <driver/gpio.h>
#include <driver/uart.h>
#include <NimBLEDevice.h>
#include <string.h>

#include "afterburner.h"
#include "heater_pins.h"
#include "sniff.h"

#if __has_include("../secrets.h")
#include "../secrets.h"
#else
#include "../secrets.example.h"
#endif

#ifndef OTA_PASSWORD
#define OTA_PASSWORD "change-me-ota"
#endif
#ifndef AP_SSID
#define AP_SSID "HeatGenie-S3"
#endif
#ifndef AP_PASS
#define AP_PASS "change-me-ap"
#endif

static const int kUartNum = UART_NUM_1;
static const int kBufSize = 512;
static const int kBaud = 25000;
static const uint32_t kPollMs = 1000;  // NVStorage FrameRate default
static const int kRxTimeoutMs = 50;    // BlueWireTask.cpp RX_DATA_TIMOUT

static WiFiMulti wifi_multi;
static WebServer http(80);
static AbTx tx{};
static AbRx last_rx_st{};
static NimBLECharacteristic *ble_tx;
static uint8_t last_rx[256];
static size_t last_rx_n;
static uint8_t last_tx[kAbFrame];
static int cmd_left;
static int active_left;
static uint32_t tx_count;
static uint32_t rx_ok;
static uint32_t crc_fail;
static bool ota_busy;
static bool http_started;
static bool ap_started;
static uint32_t boot_ms;
// Factory HeatGenie BLE owns the blue wire until BLE `talk`.
static bool uart_quiet = true;

void notify(const String &s);
static bool handle_cmd(String cmd);

static void uart_pins_idle() {
  // TX open-drain: only pulls blue low. RX is input on the same LV1 node.
  gpio_set_direction((gpio_num_t)HEATER_TX_GPIO, GPIO_MODE_INPUT_OUTPUT_OD);
  gpio_pulldown_dis((gpio_num_t)HEATER_TX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_TX_GPIO);
  gpio_set_direction((gpio_num_t)HEATER_RX_GPIO, GPIO_MODE_INPUT);
  gpio_pulldown_dis((gpio_num_t)HEATER_RX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_RX_GPIO);
}

static void uart_release() {
  uart_driver_delete((uart_port_t)kUartNum);
  gpio_reset_pin((gpio_num_t)HEATER_TX_GPIO);
  gpio_reset_pin((gpio_num_t)HEATER_RX_GPIO);
  gpio_set_direction((gpio_num_t)HEATER_TX_GPIO, GPIO_MODE_INPUT);
  gpio_set_direction((gpio_num_t)HEATER_RX_GPIO, GPIO_MODE_INPUT);
  gpio_pulldown_dis((gpio_num_t)HEATER_TX_GPIO);
  gpio_pulldown_dis((gpio_num_t)HEATER_RX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_TX_GPIO);
  gpio_pullup_en((gpio_num_t)HEATER_RX_GPIO);
}

void uart_begin() {
  if (uart_quiet) {
    uart_release();
    return;
  }
  uart_driver_delete((uart_port_t)kUartNum);
  gpio_reset_pin((gpio_num_t)HEATER_TX_GPIO);
  gpio_reset_pin((gpio_num_t)HEATER_RX_GPIO);
  uart_config_t cfg = {};
  cfg.baud_rate = kBaud;
  cfg.data_bits = UART_DATA_8_BITS;
  cfg.parity = UART_PARITY_DISABLE;
  cfg.stop_bits = UART_STOP_BITS_1;
  cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  cfg.source_clk = UART_SCLK_DEFAULT;
  uart_param_config((uart_port_t)kUartNum, &cfg);
  uart_set_pin((uart_port_t)kUartNum, HEATER_TX_GPIO, HEATER_RX_GPIO, UART_PIN_NO_CHANGE,
               UART_PIN_NO_CHANGE);
  uart_driver_install((uart_port_t)kUartNum, kBufSize, kBufSize, 0, nullptr, 0);
  uart_pins_idle();
}

static size_t skip_echo(uint8_t *buf, size_t n, const uint8_t *tx, size_t tn) {
  if (tn && n >= tn && memcmp(buf, tx, tn) == 0) {
    size_t rest = n - tn;
    if (rest) {
      memmove(buf, buf + tn, rest);
    }
    return rest;
  }
  return n;
}

static void gpio_probe() {
  uart_driver_delete((uart_port_t)kUartNum);
  gpio_reset_pin((gpio_num_t)HEATER_TX_GPIO);
  gpio_reset_pin((gpio_num_t)HEATER_RX_GPIO);
  gpio_set_direction((gpio_num_t)HEATER_TX_GPIO, GPIO_MODE_INPUT);
  gpio_set_direction((gpio_num_t)HEATER_RX_GPIO, GPIO_MODE_INPUT);
  gpio_pulldown_dis((gpio_num_t)HEATER_TX_GPIO);
  gpio_pulldown_dis((gpio_num_t)HEATER_RX_GPIO);
  gpio_pullup_dis((gpio_num_t)HEATER_TX_GPIO);
  gpio_pullup_dis((gpio_num_t)HEATER_RX_GPIO);
  delay(2);
  int first = gpio_get_level((gpio_num_t)HEATER_RX_GPIO);
  uint32_t edges = 0;
  int prev = first;
  uint32_t t0 = millis();
  while (millis() - t0 < 400) {
    int v = gpio_get_level((gpio_num_t)HEATER_RX_GPIO);
    if (v != prev) {
      edges++;
      prev = v;
    }
  }
  int last = gpio_get_level((gpio_num_t)HEATER_RX_GPIO);
  char line[128];
  snprintf(line, sizeof(line), "probe tx=%d rx=%d first=%d last=%d edges_400ms=%u",
           HEATER_TX_GPIO, HEATER_RX_GPIO, first, last, (unsigned)edges);
  Serial.println(line);
  notify(String(line));
  uart_begin();
}

static String hex_of(const uint8_t *p, size_t n) {
  String s;
  s.reserve(n * 2);
  for (size_t i = 0; i < n; i++) {
    char b[3];
    snprintf(b, sizeof(b), "%02x", p[i]);
    s += b;
  }
  return s;
}

static bool parse_hex(const String &in, uint8_t *out, size_t *n, size_t max) {
  String h;
  for (size_t i = 0; i < in.length(); i++) {
    char c = in[i];
    if (c == ' ' || c == ':' || c == '\n' || c == '\r') {
      continue;
    }
    h += c;
  }
  if (h.length() < 2 || (h.length() & 1) || h.length() / 2 > max) {
    return false;
  }
  *n = h.length() / 2;
  for (size_t i = 0; i < *n; i++) {
    char tmp[3] = {h[i * 2], h[i * 2 + 1], 0};
    out[i] = (uint8_t)strtoul(tmp, nullptr, 16);
  }
  return true;
}

static String status_text() {
  if (sniff_active()) {
    return sniff_status_line();
  }
  if (uart_quiet) {
    return "quiet factory BLE owns bus (talk to resume UART)";
  }
  char line[256];
  if (!last_rx_st.valid) {
    snprintf(line, sizeof(line),
             "no heater baud=%d tx=%u rx=%u crc_fail=%u hdr=%02x pmin=%.1f pmax=%.1f",
             kBaud, (unsigned)tx_count, (unsigned)rx_ok, (unsigned)crc_fail, tx.header,
             tx.pmin_hz, tx.pmax_hz);
    return String(line);
  }
  snprintf(line, sizeof(line),
           "run=%s err=%u%s V=%.1f shell=%dC pump=%.1fHz fixed=%.1fHz glow=%.1fV/%.2fA "
           "fan=%urpm pmin=%.1f pmax=%.1f hdr=%02x %s",
           last_rx_st.run_name, last_rx_st.err, last_rx_st.err_name, last_rx_st.volts,
           last_rx_st.shell_c, last_rx_st.pump_hz, last_rx_st.pump_fixed_hz, last_rx_st.glow_v,
           last_rx_st.glow_a, last_rx_st.fan_rpm, tx.pmin_hz, tx.pmax_hz, tx.header,
           tx.thermostat ? "thermo" : "hz");
  return String(line);
}

void notify(const String &s) {
  Serial.println(s);
  if (ble_tx) {
    ble_tx->setValue(s.c_str());
    ble_tx->notify();
  }
}

static String net_text() {
  String s = "ap=";
  s += WiFi.softAPIP().toString();
  if (WiFi.status() == WL_CONNECTED) {
    s += " sta=";
    s += WiFi.localIP().toString();
    s += " ssid=";
    s += WiFi.SSID();
  } else {
    s += " sta=down";
  }
  s += " ota=heatgenie-s3.local:3232";
  return s;
}

static bool http_auth() {
  if (http.authenticate("ota", OTA_PASSWORD)) {
    return true;
  }
  http.requestAuthentication();
  return false;
}

static void queue_cmd(uint8_t cmd, int frames) {
  tx.command = cmd;
  cmd_left = frames;
}

static void queue_active(int frames) {
  active_left = frames;
  tx.header = 0x76;
}

static bool find_rx(const uint8_t *buf, size_t n, AbRx *st) {
  for (size_t i = 0; i + (size_t)kAbFrame <= n; i++) {
    if (buf[i] != 0x76 && buf[i] != 0x78) {
      continue;
    }
    if (ab_decode_rx(buf + i, kAbFrame, st)) {
      return true;
    }
    crc_fail++;
  }
  return false;
}

static void poll_heater() {
  // TxManage.cpp: ON/OFF stay asserted until the heater runstate shows it.
  if (cmd_left > 0 && last_rx_st.valid) {
    if (tx.command == 0xA0 && last_rx_st.run >= 1) {
      cmd_left = 0;
      tx.command = 0x00;
    } else if (tx.command == 0x05 && last_rx_st.run == 0) {
      cmd_left = 0;
      tx.command = 0x00;
    }
  }
  if (cmd_left > 0) {
    cmd_left--;
    if (cmd_left == 0) {
      tx.command = 0x00;
    }
  }
  if (active_left > 0) {
    active_left--;
    tx.header = 0x76;
    if (active_left == 0) {
      tx.header = 0x78;
    }
  } else {
    tx.header = 0x78;
  }

  uint8_t frame[kAbFrame];
  ab_encode_tx(&tx, frame);
  memcpy(last_tx, frame, kAbFrame);

  uart_flush_input((uart_port_t)kUartNum);
  uart_write_bytes((uart_port_t)kUartNum, frame, kAbFrame);
  uart_wait_tx_done((uart_port_t)kUartNum, pdMS_TO_TICKS(50));
  tx_count++;
  // TX and RX share LV1, so the FIFO hears our 24-byte echo then the ECU.
  // Do not uart_flush_input after TX: that discarded the ~5 ms reply.
  uint8_t buf[kAbFrame * 2];
  int n = uart_read_bytes((uart_port_t)kUartNum, buf, sizeof(buf),
                          pdMS_TO_TICKS(kRxTimeoutMs));
  if (n < 0) {
    n = 0;
  }
  n = (int)skip_echo(buf, (size_t)n, frame, (size_t)kAbFrame);
  last_rx_n = (size_t)n;
  if (n) {
    memcpy(last_rx, buf, (size_t)n);
  }
  AbRx st{};
  if (n && find_rx(buf, (size_t)n, &st)) {
    last_rx_st = st;
    rx_ok++;
  }
}

static bool handle_cmd(String cmd) {
  cmd.trim();
  String lower = cmd;
  lower.toLowerCase();
  const bool tx_cmd =
      lower == "on" || lower == "off" || lower == "poll" || lower == "active" ||
      lower == "passive" || lower == "thermo" || lower == "hz" ||
      lower.startsWith("prime") || lower.startsWith("pmin ") ||
      lower.startsWith("pmax ") || lower.startsWith("demand ") ||
      lower.startsWith("alt ") || lower.startsWith("volt ") ||
      lower.startsWith("raw ");
  if (sniff_active() && tx_cmd) {
    notify("sniff busy");
    return true;
  }
  if (uart_quiet && (tx_cmd || lower == "ping" || lower.startsWith("ping "))) {
    notify("quiet — send talk");
    return true;
  }
  if (lower == "quiet") {
    uart_quiet = true;
    if (sniff_active()) {
      sniff_stop();
    }
    uart_release();
    notify(status_text());
    return true;
  } else if (lower == "talk") {
    uart_quiet = false;
    if (sniff_active()) {
      sniff_stop();
    }
    uart_begin();
    notify(status_text());
    return true;
  }
  if (lower == "on") {
    queue_cmd(0xA0, 8);
  } else if (lower == "off") {
    queue_cmd(0x05, 8);
  } else if (lower == "probe") {
    if (sniff_active()) {
      sniff_stop();
    }
    gpio_probe();
    return true;
  } else if (lower == "edges") {
    // 1.2 s so a 1 s Afterburner poll can still toggle the LV1 node.
    sniff_edges(1200);
    return true;
  } else if (lower == "ping") {
    ping_begin_sweep();
    return true;
  } else if (lower.startsWith("ping ")) {
    ping_begin_baud(lower.substring(5).toInt());
    return true;
  } else if (lower == "sniff" || lower == "listen") {
    sniff_begin_sweep();
    return true;
  } else if (lower.startsWith("sniff ")) {
    String a = lower.substring(6);
    a.trim();
    if (a == "stop" || a == "off" || a == "end") {
      sniff_stop();
    } else if (a == "sweep") {
      sniff_begin_sweep();
    } else {
      sniff_begin_baud(a.toInt());
    }
    return true;
  } else if (lower == "status") {
    notify(status_text());
    return true;
  } else if (lower == "ota" || lower == "net") {
    notify(net_text());
    return true;
  } else if (lower == "ap") {
    ap_started = true;
    notify(net_text());
    return true;
  } else if (lower == "dump") {
    notify(String("tx ") + hex_of(last_tx, kAbFrame) + " rx " + last_rx_n + " " +
           hex_of(last_rx, last_rx_n));
    if (sniff_last_n() || strcmp(sniff_last_class(), "none") != 0) {
      notify(String("sniff last baud=") + String(sniff_last_baud()) + " n=" +
             String((unsigned)sniff_last_n()) + " class=" + sniff_last_class() +
             " hex=" + sniff_last_hex());
    }
    return true;
  } else if (lower == "poll") {
    poll_heater();
  } else if (lower == "active") {
    queue_active(10);
  } else if (lower == "passive") {
    active_left = 0;
    tx.header = 0x78;
  } else if (lower == "thermo") {
    tx.thermostat = true;
    tx.actual_c = 22;
  } else if (lower == "hz") {
    // DemandManager: Fixed Hz demand is 8–35, interpolated by the ECU
    // onto Pmin–Pmax. Tmin → Pmin (altitude lean).
    tx.thermostat = false;
    tx.actual_c = 0;
    tx.demand = tx.tmin_c;
  } else if (lower == "prime on") {
    tx.prime = true;
  } else if (lower == "prime off") {
    tx.prime = false;
  } else if (lower.startsWith("pmin ")) {
    tx.pmin_hz = lower.substring(5).toFloat();
    queue_active(10);
  } else if (lower.startsWith("pmax ")) {
    tx.pmax_hz = lower.substring(5).toFloat();
    queue_active(10);
  } else if (lower.startsWith("demand ")) {
    tx.demand = (int8_t)lower.substring(7).toInt();
  } else if (lower.startsWith("alt ")) {
    tx.altitude_m = (int16_t)lower.substring(4).toInt();
    tx.altitude_sensor = true;
    queue_active(10);
  } else if (lower.startsWith("volt ")) {
    int v = lower.substring(5).toInt();
    if (v == 12) {
      tx.volt_x10 = 120;
    } else if (v == 24) {
      tx.volt_x10 = 240;
    }
    queue_active(10);
  } else if (lower.startsWith("raw ")) {
    uint8_t raw[128];
    size_t rn = 0;
    if (!parse_hex(lower.substring(4), raw, &rn, sizeof(raw))) {
      notify("bad raw hex");
      return false;
    }
    uart_flush_input((uart_port_t)kUartNum);
    uart_write_bytes((uart_port_t)kUartNum, raw, rn);
    uart_wait_tx_done((uart_port_t)kUartNum, pdMS_TO_TICKS(50));
    uint8_t buf[128];
    int n = uart_read_bytes((uart_port_t)kUartNum, buf, sizeof(buf), pdMS_TO_TICKS(50));
    if (n < 0) {
      n = 0;
    }
    n = (int)skip_echo(buf, (size_t)n, raw, rn);
    last_rx_n = (size_t)n;
    if (n > 0) {
      memcpy(last_rx, buf, (size_t)n);
      AbRx st{};
      if (find_rx(buf, (size_t)n, &st)) {
        last_rx_st = st;
      }
    }
  } else {
    return false;
  }
  if (sniff_active()) {
    notify(status_text());
    return true;
  }
  poll_heater();
  notify(status_text());
  return true;
}

class BleCb : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic *c, NimBLEConnInfo & /*info*/) override {
    handle_cmd(String(c->getValue().c_str()));
  }
};

static BleCb ble_cb;

static void poll_serial_cmd() {
  static String line;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      if (line.length()) {
        handle_cmd(line);
        line = "";
      }
    } else if (line.length() < 200) {
      line += c;
    }
  }
}

static void ble_start() {
  NimBLEDevice::init("HeatGenie-S3");
  NimBLEDevice::setPower(ESP_PWR_LVL_P6);
  NimBLEServer *server = NimBLEDevice::createServer();
  NimBLEService *svc =
      server->createService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
  NimBLECharacteristic *rx = svc->createCharacteristic(
      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E",
      NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
  ble_tx = svc->createCharacteristic("6E400003-B5A3-F393-E0A9-E50E24DCCA9E",
                                     NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::READ);
  rx->setCallbacks(&ble_cb);
  server->advertiseOnDisconnect(true);
  server->start();
  NimBLEAdvertising *adv = NimBLEDevice::getAdvertising();
  adv->enableScanResponse(true);
  adv->addServiceUUID(svc->getUUID());
  adv->setName("HeatGenie-S3");
  adv->start();
}

static void http_page() {
  if (!http_auth()) {
    return;
  }
  String html = "<!doctype html><meta name=viewport content='width=device-width'>"
                "<h1>HeatGenie-S3 Afterburner</h1><pre>";
  html += status_text();
  html += "\n";
  html += net_text();
  html += "</pre><p>";
  for (const char *c :
       {"quiet", "talk", "ping", "sniff", "edges", "probe", "status", "poll", "on", "off",
        "hz", "thermo", "passive"}) {
    html += "<form method=post action='/cmd'><button name=c value='";
    html += c;
    html += "'>";
    html += c;
    html += "</button></form> ";
  }
  html += "</p><p><a href=/update>OTA firmware</a></p>";
  http.send(200, "text/html", html);
}

static void ota_begin() {
  ArduinoOTA.setHostname("heatgenie-s3");
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { ota_busy = true; });
  ArduinoOTA.onEnd([]() { ota_busy = false; });
  ArduinoOTA.onError([](ota_error_t) { ota_busy = false; });
  ArduinoOTA.begin();
}

static void net_start_services() {
  if (http_started) {
    return;
  }
  http.begin();
  MDNS.begin("heatgenie-s3");
  ota_begin();
  http_started = true;
  Serial.println(net_text());
}

static void wifi_tick() {
  wifi_multi.run();
  if (WiFi.status() == WL_CONNECTED) {
    net_start_services();
  }
  static bool ap_radio;
  if (!ap_radio &&
      (ap_started || (millis() - boot_ms >= 15000 && WiFi.status() != WL_CONNECTED))) {
    ap_radio = true;
    ap_started = true;
    WiFi.mode(WIFI_AP_STA);
    delay(100);
    WiFi.softAP(AP_SSID, AP_PASS, 1);
    net_start_services();
  }
}

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("HeatGenie-S3 quiet boot — factory BLE owns bus until talk");
  if (!ab_crc_selftest()) {
    Serial.println("CRC self-test FAIL vs Ray V9 Power-On capture");
  } else {
    Serial.println("CRC self-test OK");
  }

  ab_defaults(&tx);
  // No ON at boot. Passive 0x78 so Pmin/Pmax are not written until `pmin`/`active`.

  // NimBLE first. WIFI_AP_STA + softAP before ble_start left this S3 with
  // CDC serial (esptool 0x75) but no HeatGenie-S3 ads and no SoftAP.
  ble_start();
  Serial.println("BLE advertising HeatGenie-S3");
  // Dual-OTA: boot_app0 leaves this slot pending-verify. An unconfirmed
  // crash (or rollback timer) jumps to empty ota_1 and BLE ads stop.
  esp_ota_mark_app_valid_cancel_rollback();
  gpio_probe();
  boot_ms = millis();

  // STA via WiFiMulti in loop (same as the last BLE-live image). SoftAP and
  // ArduinoOTA wait until STA is up, or 15 s, so NimBLE can advertise first.
  WiFi.persistent(false);
  WiFi.setSleep(false);
  wifi_multi.addAP(WIFI_SSID_1, WIFI_PASS_1);
  wifi_multi.addAP(WIFI_SSID_2, WIFI_PASS_2);

  http.on("/", HTTP_GET, http_page);
  http.on("/cmd", HTTP_POST, []() {
    if (!http_auth()) {
      return;
    }
    handle_cmd(http.arg("c"));
    http.sendHeader("Location", "/");
    http.send(303);
  });
  http.on("/status", HTTP_GET, []() { http.send(200, "text/plain", status_text() + "\n" + net_text()); });
  http.on("/sniff", HTTP_GET, []() {
    String s = sniff_status_line();
    s += "\nclass=";
    s += sniff_last_class();
    s += " baud=";
    s += sniff_last_baud();
    s += " n=";
    s += sniff_last_n();
    s += "\nhex=";
    s += sniff_last_hex();
    s += "\n";
    http.send(200, "text/plain", s);
  });
  http.on("/update", HTTP_GET, []() {
    if (!http_auth()) {
      return;
    }
    http.send(200, "text/html",
              "<!doctype html><meta name=viewport content='width=device-width'>"
              "<h1>HeatGenie-S3 OTA</h1>"
              "<form method=post action=/update enctype=multipart/form-data>"
              "<input type=file name=firmware accept=.bin>"
              "<button>Upload firmware.bin</button></form>");
  });
  http.on(
      "/update", HTTP_POST,
      []() {
        if (!http_auth()) {
          return;
        }
        bool ok = !Update.hasError();
        http.send(200, "text/plain", ok ? "OK, rebooting" : "FAIL");
        delay(400);
        if (ok) {
          ESP.restart();
        }
      },
      []() {
        HTTPUpload &u = http.upload();
        if (u.status == UPLOAD_FILE_START) {
          if (!http.authenticate("ota", OTA_PASSWORD)) {
            return;
          }
          ota_busy = true;
          if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
            Update.printError(Serial);
          }
        } else if (u.status == UPLOAD_FILE_WRITE) {
          if (Update.write(u.buf, u.currentSize) != u.currentSize) {
            Update.printError(Serial);
          }
        } else if (u.status == UPLOAD_FILE_END) {
          if (!Update.end(true)) {
            Update.printError(Serial);
          }
          ota_busy = false;
        }
      });
}

void loop() {
  wifi_tick();
  if (http_started) {
    ArduinoOTA.handle();
    http.handleClient();
  }
  static bool sta_note;
  if (!sta_note && WiFi.status() == WL_CONNECTED) {
    sta_note = true;
    notify(net_text());
  }
  poll_serial_cmd();

  if (ota_busy && sniff_active()) {
    sniff_stop();
  }
  if (sniff_active()) {
    sniff_tick();
    delay(5);
    return;
  }
  if (ping_active()) {
    ping_tick();
    delay(5);
    return;
  }

  static uint32_t last_poll;
  if (!ota_busy && !uart_quiet && millis() - last_poll >= kPollMs) {
    last_poll = millis();
    poll_heater();
    static uint32_t last_note;
    if (millis() - last_note > 2000) {
      last_note = millis();
      notify(status_text());
    }
  }
  delay(5);
}
