// SPDX-License-Identifier: MIT
#pragma once
// Pin facts: LAFVIN LA064 official hardware connection guide; see PROVENANCE.md.
namespace Board {
constexpr int sda=1, scl=2, mclk=38, bclk=14, ws=13;
constexpr int audioOut=45, audioIn=12, amplifier=48;
constexpr int lcdClock=41, lcdData=40, lcdCS=47, lcdDC=39, backlight=42;
constexpr int talk=0; // ESP32-S3 BOOT button, active low. Never hold during power-on.
constexpr int pageUp=20, pageDown=19;
}
