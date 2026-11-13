# Credits and third-party components

## Project origin

The development robot uses an English/local adaptation of [Wu Yu-chu's (achir1015) XiaoKe firmware for LAFVIN](https://github.com/achir1015/esp32s3-lafvin-ai-chatbot). The upstream README credits Wu Yu-chu and Claude AI. At the time this preview was prepared, that repository did not include a license granting redistribution of modified firmware. **Its source, compiled firmware, and embedded fonts remain excluded.** The replacement in `firmware/Franky` is newly written and has a separate [provenance record](firmware/PROVENANCE.md).

LAFVIN manufactures the LA064 kit. [Official hardware documentation](https://lafvin-ai-chatbot.readthedocs.io/en/latest/Tutorial/2.hardware_connect.html) is provided by LAFVIN. DigitalRCS is an independent community project and is not endorsed by LAFVIN, LM Studio, or the upstream firmware author.

## Windows installer components

The optional Windows Setup.exe bundles third-party runtime and speech components to simplify installation. Their original license files remain in the installed runtime's package directories and `third-party` folder, alongside asset provenance and firmware source/relink materials. The project's MIT license does not replace those terms.

- A private CPython 3.13.18 runtime from [Astral's python-build-standalone](https://github.com/astral-sh/python-build-standalone), with its Python and bundled-component notices retained.
- The packages pinned in `bridge/requirements-lock.txt`, installed freshly for Windows x64 at build time; package metadata and included license files are retained. eSpeak NG's speech library and data are used through espeakng-loader and keep their upstream terms.
- PyAV 18.1.0's Python bindings use BSD terms; its bundled FFmpeg 8.1.2, x264/x265 and other native libraries retain their separate GPL/LGPL and other component terms. Matching PyAV/vendor sources, patches, codec sources and original license texts are included under `third-party`. No commercial codec-license exception is assumed.
- PyAV's MSYS2 runtime DLLs are accompanied by `pyav-msys2-runtime-sources.zip`: GCC 16.1.0-5 runtime sources and the GCC Runtime Library Exception 3.1, libiconv 1.19-1 library sources under LGPL-2.1-or-later, winpthreads `14.0.0.r92.g818fa6510-1` with MIT/BSD notices, and zlib 1.3.2-2 with its zlib notice. The archive preserves upstream source packages, build recipes/patches, package metadata and a comparison against the shipped DLLs. See [MSYS2 build instructions](https://www.msys2.org/wiki/Creating-Packages/) and the installed `third-party/notices/PYAV-MSYS2-RUNTIME.md`.
- The English Systran faster-whisper `base.en` and `tiny.en` conversions, with MIT notices and pinned revision/hash records; Kokoro-82M ONNX weights and voice files, with model-card/Apache-2.0 notices and kokoro-onnx MIT attribution.
- Espressif esptool 5.2.0 for optional USB flashing, with its GPL license and matching upstream source archive. The firmware carries its separate dependency/source/relink materials.
- Microsoft's signed Visual C++ Redistributable under Microsoft's redistribution terms. Only that prerequisite and the explicitly requested firewall operation need administrator access.

LM Studio and its chat models are not bundled. Its optional install/download flow uses the vendor's separately distributed application and terms.

## Source ZIP and separately downloaded components

The MIT license in this repository covers only its original included code and documentation. Dependencies and downloaded models retain their own terms; the Windows source-code ZIP does not bundle their source, packages, model weights, or licenses as if they were DigitalRCS-owned. The separate `Bundled-Sources.zip` release companion contains matching third-party sources and notices for the installer.

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [Whisper](https://github.com/openai/whisper): English speech recognition.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M): speech model; consult its model card and license.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx): local ONNX speech runtime and voice asset distribution. The download script uses its `model-files-v1.1` release assets.
- [LM Studio](https://lmstudio.ai/): separately installed local model application, governed by its own terms. Chat models have their own licenses.
- Python packages listed in `bridge/requirements-lock.txt`, including FastAPI, Uvicorn, NumPy, ONNX Runtime, and their dependencies: installed separately by the user.

Do not apply this project's MIT license to an upstream component or infer firmware redistribution permission from hardware ownership.

## Replacement firmware dependencies

The included Espressif ES8311/ES7210 driver files retain their original Apache 2.0 headers and [full license](firmware/Franky/src/codec/LICENSE). Exact source paths, revision and hashes are recorded in [codec-provenance.json](firmware/codec-provenance.json). Arduino-ESP32 and Adafruit/ArduinoJson build dependencies retain their licenses and are installed separately. See [firmware provenance](firmware/PROVENANCE.md). Original frog artwork is by DigitalRCS under MIT.

The installer includes `Franky-0.4.0-firmware-relink-sources.zip`, with application/Arduino sources, relocatable objects and instructions to rebuild or replace the Arduino core using the pinned external SDK/compiler. `Franky-0.4.0-sdk-notices.zip` supplies notices and pinned source links for SDK components identified in the reference firmware's link map. These companions do not bundle the external SDK/compiler binaries or claim to recreate a complete historical SDK build environment.
