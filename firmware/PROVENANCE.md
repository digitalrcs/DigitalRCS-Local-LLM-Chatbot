# Firmware origin and dependency record

The `Franky` application, setup page, control logic, audio adapter, HTTP client, and frog drawing generator were newly written for DigitalRCS in November 2026. They were not copied or translated from XiaoKe firmware. The new firmware does not include XiaoKe's source, register tables, fonts, images, or web pages.

The project previously developed a separate XiaoKe-based prototype. That history is acknowledged; this is a documented replacement implementation, not a claim of a legally supervised clean-room process or a guarantee of non-infringement.

## Inputs used for this implementation

- Functional requirements: English voice conversation, Franky identity, DigitalRCS setup hotspot, local bridge, adjustable volume/brightness, male voice selection, and an expressive frog face.
- Hardware pin facts from the [official LAFVIN connection guide](https://lafvin-ai-chatbot.readthedocs.io/en/latest/Tutorial/2.hardware_connect.html).
- The documented DigitalRCS PC bridge request/response contract in `docs/ARCHITECTURE.md`.
- Arduino-ESP32's public Wi-Fi, I2S, GPIO/PWM, Preferences, and HTTP APIs.
- Espressif's licensed ES8311 and ES7210 codec interfaces and drivers.

## Included third-party code

`Franky/src/codec/` contains a selected, unmodified set of Espressif `esp_codec_dev` files from `espressif/esp-adf`, commit `74e6be93f007faa411dab985a2b7613725506790`. Files are flattened into one directory for Arduino's recursive sketch compilation. Their bytes and copyright headers are preserved. `codec-provenance.json` records original paths and SHA-256 values. The Apache 2.0 license is included in that directory.

No code from the separately inspected `arduino-audio-driver` library is included or used.

## Build dependencies

| Component | Pinned version | Terms/source |
| --- | --- | --- |
| Arduino-ESP32 | 4.0.0-alpha1 | LGPL-2.1-or-later core plus separately licensed bundled ESP-IDF components; [source](https://github.com/espressif/arduino-esp32/tree/4.0.0-alpha1) |
| ArduinoJson | 7.4.3 | MIT; [source](https://github.com/bblanchon/ArduinoJson) |
| Adafruit GFX | 1.12.6 | BSD; [source](https://github.com/adafruit/Adafruit-GFX-Library) |
| Adafruit ST7735/ST7789 | 1.11.0 | MIT notice in upstream README; [source](https://github.com/adafruit/Adafruit-ST7735-Library) |
| Adafruit BusIO | 1.17.4 | MIT; [source](https://github.com/adafruit/Adafruit_BusIO) |

These build dependencies are downloaded by Arduino CLI; they are not relabeled as DigitalRCS code. The firmware currently pins an alpha core, so this remains a development preview. Rebuilding and testing against a stable core is a future compatibility task.

Original application files and frog artwork are MIT-licensed. Third-party files retain their own licenses. Publishing compiled firmware requires the corresponding dependency notices and applicable source/relinking materials; the development source package provides reproducible build instructions and does not present inherited firmware as our own.

## Artwork

`scripts/generate_frog.py` defines original geometric frog poses. It produces matching LCD drawing operations (`FrogArt.h`) and SVG previews. There are no downloaded character assets or embedded Chinese fonts. The small status text uses the display library's standard font.
