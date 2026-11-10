# Troubleshooting

Start with **CHECK-SETUP.cmd** while both programs are open. Read the error text before closing the window.

| Problem | What to try |
| --- | --- |
| Python not found | Install 64-bit Python 3.13 and its launcher, then run START-HERE again. |
| Setup download fails | Check Internet access, disk space, and retry START-HERE. Interrupted voice downloads are replaced on retry. |
| No models found | Load a chat model in LM Studio and start its API server. |
| Connection setup fails | Check the address ends in `/v1`, the port matches LM Studio, and the server is running. For another PC, enable its local-network server access. |
| Model is listed but replies fail | Test the model inside LM Studio; make sure it is a chat model and fits in memory. Some models take longer than the bridge's 50-second read timeout. |
| Port already in use | An existing bridge may already be running. Use its browser page or close its window before starting another copy. |
| Voice preview fails | Run START-HERE to finish voice downloads; check the bridge window for errors. |
| Saved voice did not change | Click **Use this voice**; preview alone does not select it. |
| Phone cannot open the bridge | Use the bridge PC's home-network address, not localhost. Check both devices share a reachable network and Windows permits Private-network traffic. |
| Robot says setup mode | Development firmware needs Wi-Fi and a bridge URL. Factory firmware is not supported by this preview. |
| Answers stop when PC sleeps | Keep the bridge and LM Studio PCs awake while using Franky. |
| Speech sounds odd | Try another voice; speech quality varies with text, names, punctuation, and accent. |

## LM Studio requires a token

If you enabled server authentication, provide its token as `LM_STUDIO_TOKEN` in the environment of the setup and bridge processes. Do not put a token in the URL or commit it to the project. This is an advanced option; the guided setup does not collect or store tokens.

## Optional Windows firewall rule

On a trusted home network only, open PowerShell as Administrator, move to the extracted project folder, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\allow-lan.ps1
```

The rule only allows TCP 8766 from the local subnet on a Private network. It does not change your network profile. The computer owner should decide whether a network is trusted. To remove the rule later:

```powershell
Remove-NetFirewallRule -Name DigitalRCS-Local-LLM-Chatbot
```

## Asking for help

Open a GitHub issue with your Windows version, Python version, release version, the step that failed, and the error message. Remove passwords, tokens, personal paths, and recordings before posting. Never upload full robot flash backups: they may contain saved Wi-Fi settings.
