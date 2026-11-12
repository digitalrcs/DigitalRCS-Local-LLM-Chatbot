# Windows voice software and downloads

Complete these steps on **the computer running Franky's bridge**, including when moving it to an AI server. Having LM Studio installed does not finish the speech setup. Franky needs software to recognize your question and separate software to speak the answer.

## 1. Install the Windows prerequisites

1. Install **64-bit Python 3.13** using the [Windows installer from python.org](https://www.python.org/downloads/windows/). Include the Python launcher. The setup also supports Python 3.11 and 3.12.
2. Install the latest **Microsoft Visual C++ v14 Redistributable, X64** from [Microsoft's official download page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). The page's X64 download is **vc_redist.x64.exe**; [direct Microsoft download](https://aka.ms/vc14/vc_redist.x64.exe). Open the installer and choose **Install**, or **Repair** if offered. Restart Windows if requested, then reopen the setup window.

The C++ runtime supports the native speech libraries; [ONNX Runtime documents this Windows requirement](https://onnxruntime.ai/docs/install/#requirements). Franky's setup installs Python packages but **does not install or repair this Windows runtime**. Installing it on your old PC does not install it on the AI server. You do not need the full Visual Studio development program.

## 2. Let START-HERE install the speech components

Extract the project to its permanent folder, then run **START-HERE.cmd** there. Keep Internet access available until setup finishes, and complete the provider/model selection when prompted.

| Component | What it does | How it is installed |
| --- | --- | --- |
| Kokoro ONNX and ONNX Runtime | Generate Franky's spoken replies | Setup installs the pinned Python packages in `.venv` |
| Phonemizer and eSpeak NG | Turn words into pronunciation symbols for Kokoro | Setup installs `phonemizer` and `espeakng-loader`, which normally supplies the eSpeak library and language data |
| Kokoro model and voice pack | Supply Liam and the other selectable voices | Setup downloads `kokoro-v1.0.onnx` and `voices-v1.0.bin` to `bridge/models/kokoro` (about 354 MB together) |
| faster-whisper and the English `base.en` and `tiny.en` models | Recognize the question Franky records (`base.en`) and hands-free wake phrases (`tiny.en`) | Setup installs the packages and downloads the models under `bridge/models` |
| LM Studio chat model | Write an answer to the recognized question | Download and load separately in LM Studio |

These speech libraries and model files are sometimes described as “voice drivers.” They are separate from the ESP32 firmware and from the USB driver used to flash the robot. Liam comes from the Kokoro voice pack; the default setup does not require adding Liam as a Windows system voice.

### Choosing a chat model for speed

Franky requests one to three spoken sentences. Compare models on your own hardware using the bridge's `Franky timing:` log lines, and keep the selected model loaded in LM Studio. The bridge can request reasoning off for Qwen3-family templates through `disable_thinking`; this does not turn off Gemma's reasoning. The default `max_output_tokens` is **1200**, including reasoning tokens. A limit of 256 can leave Gemma without enough room to produce an answer, even for a short question. Explicit saved limits are preserved; see [provider settings](PROVIDERS.md).

The default bridge uses CPU speech processing. Separate CUDA/cuDNN or FFmpeg installations are not prerequisites for this setup. LM Studio's chat model has its own hardware requirements.

When moving computers, run setup on the destination to create its own `.venv`. You may copy `bridge/models` to reuse downloaded speech models, but that does not replace package installation or the Windows runtime. See the [Windows AI-server guide](WINDOWS-SERVER.md).

### Hugging Face unauthenticated-download warning

The warning about unauthenticated requests to the HF Hub concerns downloading the speech-recognition models. It is not a voice-engine failure. If all readiness checks pass, Franky can run with the downloaded models; authentication does not make normal local conversations faster.

For authenticated downloads, open a separate PowerShell window **on the AI server**, using the same Windows account that runs START-FRANKY. For an installation at `C:\Data\FrankyChat`, run:

```powershell
Set-Location 'C:\Data\FrankyChat'
& .\.venv\Scripts\hf.exe auth login --no-add-to-git-credential
& .\.venv\Scripts\hf.exe auth whoami
```

Follow the browser sign-in instructions. If you choose to enter an access token instead, create a read token in your [Hugging Face token settings](https://huggingface.co/settings/tokens) and enter it only in the local login prompt. Do not paste it into a chat, project file, or GitHub. Git credential storage is unnecessary for Franky's downloads.

The [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/en/guides/cli) saves the login for that Windows account. An explicitly configured [`HF_TOKEN`](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables#hf_token) overrides the cached login; a separate environment variable is not required after a successful login. If `whoami` succeeds, stop the bridge with Ctrl+C and start START-FRANKY again. Do not upgrade the project's locked packages just to address this warning.

## 3. Verify speech before connecting Franky

1. Start **START-FRANKY.cmd** and leave its window open.
2. Open **http://localhost:8766** on that computer, or its LAN address from another computer.
3. Wait for **recognition**, **voice**, and **chat** to report ready.
4. Click **Listen to preview**. Confirm that you hear speech, then choose **Use this voice** to save your selection.
5. Run **CHECK-SETUP.cmd**, then ask Franky a short question after setting his bridge address.

**Setup complete** confirms that the setup script finished; it does not prove that Kokoro can synthesize speech. The preview is the actual voice test. A preview plays through the browser's computer or phone; Franky's replies play through the robot. A server without speakers can still serve Franky's audio, and you can preview from another computer.

## If a speech component is missing

Stop the bridge with **Ctrl+C** before repairing its installation. Use PowerShell in the extracted project folder; the commands below use that folder's Python environment.

### Voice fails while recognition and chat are ready

First check `bridge/models/kokoro`. It must contain both completed files: **kokoro-v1.0.onnx** and **voices-v1.0.bin**. If only `.part` files exist, the downloads have not finished. Kokoro may report `NO_SUCHFILE` for the missing final model even though Python, the packages, speech recognition, and LM Studio are working.

For an installation at `C:\Data\FrankyChat`, open PowerShell and run:

```powershell
Set-Location 'C:\Data\FrankyChat'
& .\.venv\Scripts\python.exe .\bridge\download_voice.py
```

Replace the folder if you installed elsewhere. Leave the window open until the command finishes successfully and **both final filenames exist**. The downloader retries unfinished files from the beginning, not from the partial size; already completed files are kept. **Do not rename `.part` files**: the downloader gives them their final names only after a successful download.

Then run **START-FRANKY.cmd**, **CHECK-SETUP.cmd**, and **Listen to preview**. This retry downloads the missing voice files without changing provider or voice settings. Reinstalling Python or choosing a different voice does not complete these downloads.

### Missing DLL or Visual C++ runtime

For errors mentioning `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll`, `MSVCP140.dll`, or a DLL load failure involving ONNX Runtime/CTranslate2, install or repair the **X64 C++ runtime** from step 1, then restart the bridge. A generic DLL error can have other causes, so keep the exact error if this does not fix it. Use 64-bit Python and the locked packages for this project.

### Missing Python package or interrupted model download

Run **START-HERE.cmd** again and complete its prompts. This retries the package and model installation. It can also change provider settings if you choose different values.

For an already configured installation, these focused retries keep the saved provider choice:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\bridge\requirements-lock.txt
.\.venv\Scripts\python.exe .\bridge\download_voice.py
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'bridge'); from server import recognizer, wake_recognizer; recognizer(); wake_recognizer(); print('English speech models ready')"
```

Run the commands in order and stop if one reports an error. The voice downloader skips existing final files; it retries an interrupted `.part` download. If an error identifies an existing Kokoro file as corrupt, move **that file** out of `bridge/models/kokoro` as a backup, then rerun the downloader. Do not replace the model filenames with files from a different Kokoro version.

### eSpeak NG library could not load

The current package normally includes eSpeak NG. First complete the package installation and C++ runtime steps above. If the error still explicitly asks for a system eSpeak installation, follow the [official eSpeak NG Windows instructions](https://github.com/espeak-ng/espeak-ng/blob/master/docs/guide.md#windows) and select the **x64 MSI** from its [releases](https://github.com/espeak-ng/espeak-ng/releases). Restart the bridge and retry a preview.

If the library is still not found, keep the exact error and installed library path when asking for help. The Kokoro dependency supports the advanced `PHONEMIZER_ESPEAK_LIBRARY` environment override; use the actual installed DLL path rather than guessing one. A stale override can also prevent use of the bundled library.

### Optional Windows speech engine

These instructions describe the default **Kokoro** engine. If you deliberately configured `TTS_ENGINE=windows`, the bridge uses Windows `System.Speech` and needs an enabled English voice available to that engine. Windows speech voices are a separate installation; they do not replace the Kokoro model files or add voices to Franky's Kokoro picker.

After any repair, restart **START-FRANKY.cmd** and check readiness. For Kokoro, test **Listen to preview** again. For the optional Windows engine, test a spoken reply on Franky; the Kokoro preview controls are unavailable in that mode. See [troubleshooting](TROUBLESHOOTING.md) if it still fails.
