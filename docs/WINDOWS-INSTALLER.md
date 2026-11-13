# Set up Franky on Windows

This guide is for **Franky 0.5.0-preview.1** on **Windows 10 or 11, Intel/AMD 64-bit**.

[Download the Windows installer](https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot/releases/download/v0.5.0-preview.1/DigitalRCS-Franky-0.5.0-preview.1-Setup.exe). Choose this `.exe` for normal setup. The source ZIP is for developers.

Speech recognition and voices are included. You do not need Python, a terminal, a Hugging Face login, or a firmware compiler. LM Studio and its chat models are separate downloads. Large models can take a while to download and load.

Three words you will see:

- **Bridge:** The Windows program that connects the robot's audio to speech recognition, answers, and voice output. The PC does the heavy work.
- **Chat model:** The AI program that writes answers. LM Studio runs it on your PC or another home-network PC. An online provider runs it on its own computers.
- **Firmware:** Software stored on the ESP32 robot. *Flashing* means installing or replacing that software.

Have your home Wi-Fi name and password ready. The robot needs **2.4 GHz Wi-Fi**. USB installation supports the **LAFVIN LA064 ESP32-S3 N16R8** kit and needs a USB **data** cable. You can skip USB installation if your robot already has working compatible Franky firmware.

## 1. Welcome — install and open the setup app

1. Open the downloaded installer and keep the suggested folder.
2. If Windows asks to install Microsoft support files for the speech libraries, approve the prompt or ask the person who manages the PC.
3. Leave **Open Franky setup and control panel** selected, then choose **Finish**.
4. Read **Welcome**, then choose **Next**. You can also choose a step from the left side.

This is an **unsigned community preview**. Windows may show an unknown-publisher or reputation warning. Check that you downloaded it from the project's release link above. Do not turn off Windows security. A school or work PC may need its administrator's permission.

Keep the setup window open while a task runs. Some buttons stay disabled until that task finishes.

## 2. Answers — choose where replies come from

For answers on this PC, keep **LM Studio — local PC or home network** in **Answer provider**.

1. Choose **Install LM Studio** if you do not have it. **Official download** opens its download website.
2. In LM Studio, download a chat model that fits your PC. Let the download finish, then load the model.
3. Return to Franky and choose **Start LM Studio**. This opens LM Studio and tries to start its local API server, which lets Franky ask it questions.
4. Choose **Find models**, select a **Chat model**, then choose **Save answer settings**.

If the server helper is unavailable, open LM Studio's Developer area and start the server there. Keep LM Studio and the selected model running. Franky does not choose model licenses or download a chat model for you.

Leave **LM Studio is on another PC or needs a token** unticked for normal local setup. If you already use LM Studio on another PC, tick it and enter that PC's **LM Studio API address**. For example, `http://192.168.1.20:1234/v1` uses an example address: replace it with that PC's real address. Its LM Studio server must allow home-network connections. Enter a token only if that server requires one.

You can instead choose an online provider:

| Choice in the app | What to know |
| --- | --- |
| **OpenRouter — supported free models** | Franky lists supported free model IDs. Account and rate limits still apply. |
| **Google Gemini — check account limits** | Availability and charges depend on your account and model. |
| **OpenAI API — metered usage** | API use is billed through your provider account. |

For an online provider, enter your own API key and read the consent checkbox. Tick it only if you agree to send conversation text to that provider and accept its limits and charges. Then use **Find models**, choose a model, and **Save answer settings**. Speech recognition and voice generation stay on your PC. There is no automatic switch to another provider.

Saved keys are protected for your Windows account. They are not sent to the robot. See [answer provider choices](PROVIDERS.md) for more detail.

If the bridge is already running, use **Try it → Stop bridge** before changing saved settings.

## 3. Voice — check the PC's speech

1. Choose **Prepare Franky's voice** and wait for it to finish.
2. Choose **Play voice preview**.
3. Listen through this PC's speakers. Check Windows volume and the selected sound output if you hear nothing.

The installer includes the speech files. This step checks and loads them; it can download replacements if files are missing. No Hugging Face login is needed.

The preview checks the PC's audio. You will test the robot's microphone and speaker in step 6.

## 4. Connect — save the PC's home-network address

1. Choose **Find this PC's addresses**.
2. Under **Robot / phone bridge address**, select the address for your home Wi-Fi or Ethernet connection. Avoid VPN and virtual-network entries.
3. Choose **Save bridge address**, then **Copy address** so you can use it on the robot.
4. Choose **Allow home-network access**. Windows may ask an administrator to approve it.

An address such as `http://192.168.1.20:8766` is an example. Use the address shown for **your** PC. The bridge uses port **8766**. LM Studio uses port **1234**. The robot needs the bridge address.

The firewall button allows the bridge on a **Private** Windows network, for devices on the local subnet. Use this on your trusted home network. It does not open an Internet router port.

The PC and robot need to reach each other on the home network. Guest Wi-Fi often blocks this. Do not put `localhost` into the robot's bridge setting: that name points back to whichever device is using it.

## 5. Robot — install firmware if needed, then connect Wi-Fi

**Already using compatible Franky firmware?** Skip the USB update and continue to the Wi-Fi instructions below. New users can install the included firmware without compiling anything.

Installer **0.5.0-preview.1** includes robot firmware **0.4.0-dev**. Seeing **0.4.0-dev** on the robot after this update is expected: the installer and robot have separate version numbers.

To install it over USB:

1. Open **Robot**. Connect the supported kit with a USB data cable. Close Arduino and any serial monitor.
2. Choose **Refresh USB ports**, then select **Robot USB / COM port**. If unsure which port is yours, unplug the robot, refresh, reconnect it, and refresh again. Do this before starting an update.
3. Tick the confirmation only if your board is the **LAFVIN LA064 ESP32-S3 N16R8** kit.
4. Choose **Install robot firmware** and read the confirmation before choosing **Yes**.
5. Keep the cable connected until the update finishes. If no port appears, choose **USB driver help**.

Flashing replaces the robot's firmware. The tool saves a private backup of its partition table and settings area first, and keeps the Franky settings region. It cannot promise to import factory-firmware settings. Keep that backup private because it may contain Wi-Fi details.

Now connect the robot to Wi-Fi:

1. Look at the robot's screen. If it already shows a normal home-network address, open that address on a PC or phone on the same network, then go to step 4 below.
2. If it cannot join Wi-Fi, wait about 20 seconds for setup mode. On your phone or PC, join Wi-Fi **DigitalRCS** with password **11181118**.
3. Stay connected even if your phone says there is no Internet. Open **http://192.168.4.1** in its browser.
4. Enter your home **2.4 GHz Wi-Fi** name and password. In **Voice bridge / AI server address**, enter the PC's bridge address saved on **Connect**, including `:8766`.
5. Choose **Save connection & restart**.
6. Reconnect your phone or PC to your home Wi-Fi. After the robot restarts, use the normal address shown on its screen for its settings page.

To reopen setup, hold **Page Up** for three seconds while Franky is idle. Do not hold **BOOT** while turning the robot on: that selects download mode. See [robot firmware and Wi-Fi setup](FIRMWARE.md) for more help.

## 6. Try it — ask your first question

1. Choose **Start bridge**.
2. Choose **Check readiness** and read the results for speech recognition, voice, and the chat model. Wait or fix the reported issue if a check is not ready.
3. Choose **Open voice page** to open the bridge's website.
4. On the robot, hold **BOOT**, ask a short question, then release it. Listen for Franky's reply.

Press **BOOT** during a reply to stop it. The software checks cannot prove that the robot hears you clearly or that its speaker works. Your spoken test checks that.

Hands-free listening is optional and experimental. To try it, enable it on the robot's settings page. Say **Hello Franky**, wait for the rising chime, then ask your question. See [hands-free conversations](HANDS-FREE.md).

## 7. Everyday use — start, stop, and look after Franky

Check the **Everyday use** page. If its checklist is incomplete, return to the named step and finish it. A firmware update is optional.

Each time you want to chat:

1. Keep the bridge PC awake and connected to your home network.
2. If using LM Studio, start its server and load your selected model. Keep the other PC awake too if it runs your model.
3. Open the **Start Franky** shortcut. It starts the bridge and opens the voice page.
4. Switch on the robot and ask a question.

Use **Franky Setup** to change settings. To stop the bridge, open **Try it** and choose **Stop bridge**. Closing the setup window leaves the bridge running. Franky does not automatically start when you log into Windows.

### Update

Stop the bridge and close the setup window. Download the new Windows installer and install it into the same folder. Your saved settings, protected keys, selected voice, and speech models are kept. Open setup and check readiness again. Update the robot's firmware only when the release instructions call for it.

### Uninstall

Stop the bridge and close setup. Open Windows **Settings → Apps**, find **Franky by DigitalRCS**, and choose **Uninstall**. You can also use the **Uninstall Franky** Start menu shortcut.

Uninstalling keeps settings, protected keys, speech models, logs, and private backups so a reinstall can reuse them. The default folder is `%LOCALAPPDATA%\Programs\Franky`. Delete the remaining folder yourself only if you also want to remove that saved data. Save any backups you need first.

LM Studio, its chat models, Microsoft runtime support, and USB drivers are separate. Franky's uninstaller does not remove them.

## Common fixes

| Problem | Try this |
| --- | --- |
| **Find models** cannot reach LM Studio | Load a model and start its API server. For another PC, check its address and network access. |
| The model list is empty | Load a chat model in LM Studio, or check the online provider's account, key, and limits. Then try **Find models** again. |
| Settings will not save while the bridge runs | Open **Try it**, choose **Stop bridge**, then save again. |
| The voice preview is silent | Check Windows volume, speakers, and sound output. Try **Prepare Franky's voice** again if preparation failed. |
| The robot cannot reach the bridge | Check the saved PC address, port **8766**, the firewall button, and that both devices can communicate on the same home network. Avoid isolated guest Wi-Fi. |
| No robot USB port appears | Try a USB data cable and another USB socket. Choose **USB driver help**, then refresh the ports. |
| Another Franky installation is running | Stop that copy from its own setup window before starting this one. |
| An update or uninstall says Franky is running | Finish any active task. Use **Stop bridge**, close setup, then retry. Never interrupt a firmware upload. |

Read the message when a step fails, fix that issue, and retry the step. A failed upload does not trigger an erase-all operation.

[More troubleshooting](TROUBLESHOOTING.md) · [All guides](README.md) · [Build the installer from source](BUILD-INSTALLER.md) · [Third-party licenses](../THIRD_PARTY_NOTICES.md)
