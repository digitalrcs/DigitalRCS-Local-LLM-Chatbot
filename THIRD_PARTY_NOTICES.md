# Credits and third-party components

## Project origin

The development robot uses an English/local adaptation of [Wu Yu-chu's (achir1015) XiaoKe firmware for LAFVIN](https://github.com/achir1015/esp32s3-lafvin-ai-chatbot). The upstream README credits Wu Yu-chu and Claude AI. At the time this preview was prepared, that repository did not include a license granting redistribution of modified firmware. **Its source, compiled firmware, and embedded fonts remain excluded.** The replacement in `firmware/Franky` is newly written and has a separate [provenance record](firmware/PROVENANCE.md).

LAFVIN manufactures the LA064 kit. [Official hardware documentation](https://lafvin-ai-chatbot.readthedocs.io/en/latest/Tutorial/2.hardware_connect.html) is provided by LAFVIN. DigitalRCS is an independent community project and is not endorsed by LAFVIN, LM Studio, or the upstream firmware author.

## Windows installer components

The optional Windows Setup.exe bundles third-party runtime and speech components to simplify installation. Their original license files remain in the installed runtime's package directories and `third-party` folder, alongside asset provenance and firmware source/relink materials. The project's MIT license does not replace those terms.

- A private CPython 3.13.18 runtime from [Astral's python-build-standalone](https://github.com/astral-sh/python-build-standalone), with its Python and bundled-component notices retained.
- The packages pinned in `bridge/requirements-lock.txt`, installed freshly for Windows x64 at build time; package metadata and included license files are retained. eSpeak NG's speech library and data are used through espeakng-loader and keep their upstream terms.
- The English Systran faster-whisper `base.en` and `tiny.en` conversions, with MIT notices and pinned revision/hash records; Kokoro-82M ONNX weights and voice files, with model-card/Apache-2.0 notices and kokoro-onnx MIT attribution.
- Espressif esptool 5.2.0 for optional USB flashing, with its GPL license and matching upstream source archive. The firmware carries its separate dependency/source/relink materials.
- Microsoft's signed Visual C++ Redistributable under Microsoft's redistribution terms. Only that prerequisite and the explicitly requested firewall operation need administrator access.

LM Studio and its chat models are not bundled. Its optional install/download flow uses the vendor's separately distributed application and terms.

## Source ZIP and separately downloaded components

The MIT license in this repository covers only its original included code and documentation. Dependencies and downloaded models retain their own terms; the release ZIP does not bundle their source, packages, model weights, or licenses as if they were DigitalRCS-owned.

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [Whisper](https://github.com/openai/whisper): English speech recognition.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M): speech model; consult its model card and license.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx): local ONNX speech runtime and voice asset distribution. The download script uses its `model-files-v1.1` release assets.
- [LM Studio](https://lmstudio.ai/): separately installed local model application, governed by its own terms. Chat models have their own licenses.
- Python packages listed in `bridge/requirements-lock.txt`, including FastAPI, Uvicorn, NumPy, ONNX Runtime, and their dependencies: installed separately by the user.

Do not apply this project's MIT license to an upstream component or infer firmware redistribution permission from hardware ownership.

## Replacement firmware dependencies

The included Espressif ES8311/ES7210 driver files retain their original Apache 2.0 headers and [full license](firmware/Franky/src/codec/LICENSE). Exact source paths, revision and hashes are recorded in [codec-provenance.json](firmware/codec-provenance.json). Arduino-ESP32 and Adafruit/ArduinoJson build dependencies retain their licenses and are installed separately. See [firmware provenance](firmware/PROVENANCE.md). Original frog artwork is by DigitalRCS under MIT.
