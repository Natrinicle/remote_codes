#pragma once

// One blue wire at the heater. Two Super Mini pads: TX drives, RX listens.
// Jumper both to shifter LV1 (HV1 = blue).
#ifndef HEATER_TX_GPIO
#define HEATER_TX_GPIO 5
#endif
#ifndef HEATER_RX_GPIO
#define HEATER_RX_GPIO 6
#endif
