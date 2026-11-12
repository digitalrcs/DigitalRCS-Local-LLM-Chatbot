# Set up DigitalRCS Local LLM Chatbot

This guide is for someone who has never installed a programming project. Follow the steps in order. You can stop after trying the voices on your computer.

**Start with the PC bridge and voice picker using this guide.** To replace the software inside a LAFVIN LA064 kit, follow the separate [firmware build and setup guide](FIRMWARE.md). New firmware source is included; it is a development preview and is separate from the earlier XiaoKe adaptation.

## 1. Get ready

You need:

- A Windows 10 or 11 computer with a 64-bit Intel or AMD processor, a speaker or headphones, and an Internet connection for setup. Windows on ARM is not tested.
- Several GB of free space for Python and speech files, plus enough room and memory for your chosen LM Studio model.
- [LM Studio](https://lmstudio.ai/) on this computer or another computer on your home network.
- [Python 3.13 for Windows](https://www.python.org/downloads/windows/). Look for a **3.13** release and choose **Windows installer (64-bit)**. Use the normal installer, not the embeddable package. Include the Python launcher if offered. Newer Python versions are not tested here.

Python is the program that runs the bridge. You do not need to learn Python to use it. If this is a family or school computer, ask the person who manages it to help with software installation or firewall settings.

## 2. Put the download in a normal folder

1. Open the project's [Releases page](https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot/releases).
2. Download the Windows ZIP listed under the release assets.
3. Right-click the ZIP and choose **Extract All**. Pick a folder you can find again, such as `Documents\DigitalRCS-Chatbot`.
4. Open the extracted folder. You should see `START-HERE.cmd`, `START-FRANKY.cmd`, and `README.md`.

Do not run files from inside the ZIP. Keep this folder: it will also hold the downloaded speech models and your settings. Windows may show the files without `.cmd`; look for the same names.

## 3. Prepare LM Studio

1. Open LM Studio and download a chat model that your computer can run. A chat model writes answers; an embedding model is not suitable here.
2. Load that model. Send it a short message inside LM Studio to confirm it can answer.
3. Open LM Studio's **Developer** tab and start its API server. The [official server guide](https://lmstudio.ai/docs/developer/core/server) shows this step.
4. Leave LM Studio open.

There are two roles: the **bridge computer** runs this download; the **LM Studio computer** writes the AI replies. One computer can do both jobs.

| Your arrangement | Address to enter during setup |
| --- | --- |
| Both programs on the same PC | `http://127.0.0.1:1234/v1` |
| LM Studio on a different PC | `http://YOUR-LM-STUDIO-PC-ADDRESS:1234/v1` |

`127.0.0.1` means “this computer.” For two computers, replace the placeholder with the LM Studio computer's local address. Use the actual port shown in LM Studio if you changed it from 1234. Enable [Serve on Local Network](https://lmstudio.ai/docs/developer/core/server/serve-on-network) in LM Studio for the two-computer arrangement. Both PCs must be on the same reachable home network; guest Wi-Fi may block them from talking.

## 4. Run the guided setup

1. Double-click **START-HERE.cmd**.
2. Wait while the setup window installs the bridge's required software. This can take several minutes.
3. At the provider choice, press **Enter** for LM Studio. Then enter the LM Studio address. If both programs are on this PC, press **Enter** to accept the displayed default.
4. Choose the number beside your chat model. The wizard saves that choice for you.
5. Wait for the voice and English recognition downloads. The Kokoro files alone are about 354 MB. A slow connection may take longer.
6. Look for **Setup complete**. Then press a key to close the window.

If you see an error, read it before closing. Running setup again retries installation and downloads; it does not erase your chosen voice. You can also rerun it to select another LM Studio address or model. Restart the bridge afterward.

## 5. Start Franky's voice bridge

1. Double-click **START-FRANKY.cmd**.
2. Leave its window open. This is the running bridge.
3. Open your browser and go to **http://localhost:8766**.
4. Choose a voice, then click **Listen to preview**. The first preview may take longer while the speech model loads.
5. When you find a voice you like, click **Use this voice**. A preview by itself does not save the selection.

**Success looks like:** the voice page opens, a preview plays, and your saved voice is still selected after refreshing the page. Liam is the default. Try the other American and British voices to compare.

This page previews speech; it is not a microphone chat interface. Full spoken robot conversation needs the [new Franky firmware](FIRMWARE.md). The PC installation alone does not update your robot.

## 6. Check the connection

With the bridge and your selected provider ready, double-click **CHECK-SETUP.cmd**. It checks that the provider lists the selected model and the bridge responds. It also lists possible bridge addresses for other devices on your network. A listed address may belong to a VPN or virtual adapter, so use your home Wi-Fi or Ethernet address.

A successful check does not guarantee that the model can generate a reply or that robot audio works. It helps locate basic connection problems.

## 7. Connect the robot or select an online provider

For the LAFVIN LA064 kit, follow [FIRMWARE.md](FIRMWARE.md). It covers the new frog face, USB build/flash tools, DigitalRCS setup Wi-Fi, and the bridge address. Keep a private backup before replacing existing firmware.

LM Studio stays the default. To choose OpenAI, OpenRouter free models, or Gemini, use **CHANGE-PROVIDER.cmd** and the [provider guide](PROVIDERS.md). Keys are entered privately on the PC. No keys belong in the robot firmware or GitHub repository.

## Everyday use

1. Start LM Studio and load your chat model.
2. Start its API server.
3. Double-click **START-FRANKY.cmd**.
4. Keep the programs running and the PC awake.

To stop, click the bridge window and press **Ctrl+C**. To move to another computer, copy the release ZIP and run setup there; do not copy the `.venv` folder. To uninstall, stop the bridge and delete the extracted folder. LM Studio, its models, and Python are separate installations.

For a dedicated Windows machine running both LM Studio and the bridge, use the [AI-server migration guide](WINDOWS-SERVER.md). It covers the shared website, the advertised LAN address, firewall access, the robot's connection settings, and rollback.

## A few useful words

| Word | Meaning |
| --- | --- |
| Bridge | The program that connects the robot's audio to the AI and voice tools |
| Model | A downloaded file containing what the AI learned |
| Local | Processing on your computer or home network |
| Server | A program waiting for requests from another program or device |
| Firmware | The software stored inside the robot |
| Port | The number after the colon in a server address |

Need help? Start with [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
