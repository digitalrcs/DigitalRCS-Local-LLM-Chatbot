# Troubleshooting

## Start here

If you used [Windows Setup.exe](WINDOWS-INSTALLER.md), open **Franky Setup → Try it**, choose **Start bridge**, then **Check readiness**. Keep LM Studio and the selected model running if you use local answers. Read which check needs attention:

- **Speech recognition** or **Voice:** open **Voice**, choose **Prepare Franky's voice**, then **Play voice preview**.
- **Chat model:** open **Answers**, check the selected provider and use **Find models**. Stop the bridge before saving changed answer settings.
- **Checks pass but the robot is quiet:** check the robot's Wi-Fi and bridge address, then hold **BOOT** while asking a short question and release it.

For a source ZIP/manual installation, start **START-FRANKY.cmd**, then run **CHECK-SETUP.cmd**. Read the error text before closing its window.

The bridge page at **http://localhost:8766** shows separate speech recognition, voice, and chat checks. Speech models load in the background when the bridge starts. Leave the window open while they prepare; failed checks and provider availability refresh about every 30 seconds. A successful model-list check is not a full conversation test: use a voice preview, then ask Franky a short question.

The setup app's **Open voice page** opens that page. Closing the setup app leaves its bridge running; use **Stop bridge** to stop that copy. For errors without a useful on-screen explanation, its log is `logs/bridge.log` inside the installation folder.

## Common problems

| Problem | What to try |
| --- | --- |
| Python not found in a manual installation | Install 64-bit Python 3.13 and its launcher, then run START-HERE again. Setup.exe includes its own Python; rerun the installer if those application files are missing. |
| Setup download fails | Check Internet access and disk space, then retry the failed step. For speech files in the setup app, use **Prepare Franky's voice**. For a manual installation, retry START-HERE. |
| Manual setup says cancelled | Existing provider settings were kept. Run START-HERE again and complete a provider choice; cancellation does not finish a fresh installation. |
| No models found | For local answers, load a chat model in LM Studio and start its API server. For an online provider, check its key/account and use **Find models** again. |
| LM Studio connection setup fails | Check the address ends in `/v1`, the port matches LM Studio, and the server is running. For another PC, enable its local-network server access. |
| Model is listed but replies fail | Test the model inside LM Studio; make sure it is a chat model and fits in memory. Some models take longer than the bridge's 50-second read timeout. |
| Port already in use | An existing bridge may already be running. Use its browser page, or stop it using **Stop bridge** in its setup app or **Ctrl+C** in its original command window. Closing the setup window alone does not stop it. |
| Voice preview fails | Check the PC's output device and volume, then retry **Prepare Franky's voice** and **Play voice preview**. For further repairs, see [voice setup](VOICE-SETUP.md#if-a-speech-component-is-missing). |
| Voice fails or reports NO_SUCHFILE; recognition and chat work; only Kokoro .part files exist | The model downloads are unfinished. In the setup app, retry **Prepare Franky's voice**. For a manual installation, follow the [Kokoro download retry](VOICE-SETUP.md#voice-fails-while-recognition-and-chat-are-ready). Wait for completion, restart the bridge, and preview. Do not rename `.part` files. |
| Missing VCRUNTIME/MSVCP DLL or native speech-library load error | Install or repair the [Microsoft X64 C++ runtime](VOICE-SETUP.md#missing-dll-or-visual-c-runtime). Setup.exe includes its installer; manual START-HERE does not. A generic DLL error may need further diagnosis. |
| eSpeak NG cannot load | The Python package normally bundles it. Use the [eSpeak-specific steps](VOICE-SETUP.md#espeak-ng-library-could-not-load), including the official x64 installer only if needed. |
| Saved voice did not change | Click **Use this voice**; preview alone does not select it. |
| Phone cannot open the bridge | Use the bridge PC's home-network address, not localhost. Check both devices share a reachable network and Windows permits Private-network traffic. |
| Robot says setup mode | Enter home 2.4 GHz Wi-Fi and the PC bridge address on port 8766. Follow [Connect Franky](FIRMWARE.md#connect-franky). Installing the PC software changes robot firmware only if you also use the optional **Install robot firmware** step. |
| No robot USB port appears | Use a USB data cable, choose **Refresh USB ports**, and compare the list before/after plugging it in. The **USB driver help** link is on the setup app's **Robot** step. |
| Hello Franky gets no response | Hands-free is off on a fresh installation. Enable it on the robot's device page, then say the wake phrase separately and wait for the chime. See [hands-free setup](HANDS-FREE.md). |
| Answers stop when PC sleeps | Keep the bridge PC awake. If using local answers, keep the LM Studio PC and its model running too. |
| Speech sounds odd | Try another voice; speech quality varies with text, names, punctuation, and accent. |

## LM Studio requires a token

In **Franky Setup → Answers**, select **LM Studio is on another PC or needs a token**, then enter the token in the masked **API key** field and save the answer settings. For a manual installation, provide `LM_STUDIO_TOKEN` in the environment of the setup and bridge processes. Do not put a token in the URL or commit it to the project.

## Optional Windows firewall rule

In the setup app, choose **Allow home-network access** on **Connect**. The PowerShell steps below are the manual alternative.

On a trusted home network only, open PowerShell as Administrator, move to the extracted project folder, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\allow-lan.ps1
```

The rule only allows TCP 8766 from the local subnet on a Private network. It does not change your network profile. The computer owner should decide whether a network is trusted. To remove the rule later:

```powershell
Remove-NetFirewallRule -Name DigitalRCS-Local-LLM-Chatbot
```

## Asking for help

Open a GitHub issue with your Windows version, Franky release version, whether you used Setup.exe or the source ZIP, the step that failed, and the error message. For a manual installation, include your Python version too. Remove passwords, tokens, personal paths, and recordings before posting. Never upload full robot flash backups: they may contain saved Wi-Fi settings.

For online provider keys, quotas, and free-tier limitations, see [PROVIDERS.md](PROVIDERS.md). LM Studio remains the default and errors never cause an automatic paid fallback.
