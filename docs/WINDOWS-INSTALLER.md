# Franky's Windows setup app

The all-in-one **Setup.exe** is for Windows 10/11 on an Intel or AMD 64-bit PC. It installs Franky's bridge, website, private Python runtime, speech libraries, English hearing models, Kokoro voices, and an optional USB firmware tool. You do not need to install Python, use a terminal, or compile the robot firmware.

LM Studio and its chat model are a separate choice. An online provider instead needs your own account and key. Initial LM Studio/model downloads can take longer than a few minutes; setup cannot make a large model fit a small PC.

## Start here

1. Download the **Setup.exe** asset, then open it. The source ZIP is for development and manual installation.
2. Keep the suggested installation folder. If Windows asks to install Microsoft speech-library support, approve that prompt or ask the person who manages the PC. The main setup runs as your Windows user.
3. Leave **Open Franky setup** selected at the end. Use the steps down the left side of the window.

This community preview is not code-signed by DigitalRCS. Windows may show an unknown-publisher or reputation prompt. Confirm that your download came from this project's release and matches its checksum; do not turn off Windows security. Organization-managed PCs may require an administrator to allow the app.

## Choose where answers come from

**LM Studio on this PC** keeps the conversation local. Use the install button, open LM Studio, and choose a chat model that LM Studio says fits your PC. Let its download finish. Return to Franky, start LM Studio's connection, choose **Find models**, select the model, and save. The wizard can open LM Studio and start its local server; it does not accept model licenses or choose a large model for you.

If LM Studio already runs on another computer, expand **LM Studio is on another PC or needs a token** and enter that computer's address, such as `http://192.168.1.20:1234/v1`. Keep that computer and LM Studio running. This also works with an existing AI server such as `http://192.168.5.250:1234/v1` when its LM Studio server permits LAN connections.

For **OpenRouter free models**, **Gemini**, or **OpenAI**, read the online-provider note, enter your key in the masked field, then find and save a model. These services receive conversation text. Availability, account limits, and charges depend on the service; there is no automatic provider switching. OpenRouter choices are restricted to free model IDs. Keys are encrypted for your Windows account and never sent to the robot or included in packages. See [provider choices](PROVIDERS.md).

## Check the voice

The normal installer includes all required speech files. **Prepare voice** checks them, and **Play preview** sends a short sample to this PC's speakers. If a file is missing, setup can download it again. You do not need a Hugging Face account for these public models. With the bundled models, normal recognition loads directly from disk.

A ready message confirms the software loaded. Listen to the preview yourself to check the speaker and volume.

## Connect Franky

Choose your home Wi-Fi or Ethernet address from the list. VPN/virtual-network addresses may also be listed. Save the address shown for Franky, then use **Allow home-network access**. Windows may ask an administrator to approve this step. It allows port 8766 only on a Private network and for local-subnet devices; it does not expose Franky to the Internet.

For a new supported robot, the USB page can install the included **LAFVIN LA064 ESP32-S3 N16R8** firmware:

1. Connect the robot with a USB data cable and refresh the port list.
2. Select its port. If unsure, unplug it, refresh, reconnect it, and refresh again.
3. Confirm the exact supported kit, then choose **Install robot software**. This replaces firmware; it preserves the Franky settings region and saves a private backup first. It does not guarantee importing settings from factory firmware.
4. Keep the cable connected until the upload finishes. If no port appears, use the official USB-driver help link.

You can skip USB flashing if Franky already has working compatible firmware. The bundled firmware is **0.4.0-dev**; this installer does not require rebuilding it.

For first-time Wi-Fi setup, join the **DigitalRCS** setup network (password **11181118**) shown on the robot and open **http://192.168.4.1**. Enter your home **2.4 GHz Wi-Fi** and the bridge address displayed by the wizard. After saving, reconnect your PC/phone to the home network. The device's screen shows its normal address. See [firmware setup](FIRMWARE.md) if the kit is not connected yet.

## Try it and use it every day

Choose **Start bridge**, wait for the three readiness checks, and open the voice page. Ask Franky a short question after his ready chime. The setup app cannot confirm microphone/speaker quality without your spoken test.

Use the **Start Franky** shortcut for everyday use and **Franky Setup** to change settings. The bridge keeps running when you close the setup window; reopen setup and use **Stop bridge** to stop the copy it started. Keep this PC awake and your chosen answer service available. Startup at Windows login is not enabled automatically.

The setup app uses the answer service and address you saved in its window, even if a terminal previously set different provider/address environment variables. A bridge launched through the manual `.cmd` scripts still uses their documented environment overrides. If another copy of Franky is already running, stop it from its original window before starting this installation.

## Retry, update, or uninstall

- If a step fails, read its message and retry that step. A failed upload never triggers an erase-all operation.
- Stop the bridge before installing an update. Existing provider settings, encrypted keys, selected voice, and speech models are preserved.
- Use Windows **Installed apps → Franky → Uninstall**. Models, settings, protected keys, and private backups remain in the installation folder so a reinstall can reuse them. Delete that remaining folder yourself only if you want to remove this local data too.
- LM Studio, its models, Microsoft runtime support, and USB drivers are separate programs and are not removed by Franky's uninstaller.

## Build the installer from source

The builder needs Python 3.13 x64 with the project's locked requirements, the Windows .NET Framework C# compiler, and Inno Setup 6. It builds into ignored `dist/installer` and does not copy a developer virtual environment or configuration.

1. Run `python scripts/prepare-installer-assets.py` with the development environment to prepare the pinned public models, flash utility, runtime-support installer, and notices.
2. Prepare the tested firmware's four separate images plus their manifest under `dist/installer-assets/firmware`; include corresponding source/relink materials under `dist/installer-assets`.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-installer.ps1`.

The builder verifies the pinned portable CPython archive, Microsoft signature, firmware hashes, and staged runtime. It records asset provenance and payload hashes. Rebuilding requires network access for the build inputs. Inspect the resulting package before publishing. The source ZIP remains available separately.

All bundled components retain their own licenses. See [third-party notices](../THIRD_PARTY_NOTICES.md), the installed `third-party` folder, package license directories, and the firmware source/relink companion. The optional LM Studio application and its chat models are not redistributed in Franky's installer.
