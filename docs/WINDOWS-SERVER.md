# Move Franky's bridge and website to a Windows AI server

Run the voice bridge and LM Studio together on your Windows AI server. The voice picker, readiness dashboard, and connection information are part of the bridge: starting one program serves the website too. No IIS installation or separate website deployment is needed.

This worked example uses **192.168.5.250** as the AI server's home-network address. Replace it if your server uses a different address. These are installation instructions; they do not mean the software has already been deployed or tested on your server.

| Setting | Value for this server | Where it belongs |
| --- | --- | --- |
| LM Studio address | `http://127.0.0.1:1234/v1` | Provider setup **on the AI server** |
| Advertised bridge address | `http://192.168.5.250:8766` | **SET-BRIDGE-ADDRESS.cmd**, then displayed in the dashboard |
| Website from your PC/phone | `http://192.168.5.250:8766` | Browser address bar |
| Website on the AI server itself | `http://localhost:8766` | Browser on the server |
| Voice bridge / AI server address | `http://192.168.5.250:8766` | Franky's existing device setup page |

`127.0.0.1` means the computer running that program. Never enter it as the robot's bridge address. Port **1234** is LM Studio; port **8766** is Franky's bridge and website. Franky's Wi-Fi, volume, brightness, Talk, Stop, and listening settings page continues to run **on the ESP32 at the address shown on its screen**.

## 1. Copy the release to the AI server

1. Download the **Windows ZIP** from the [GitHub releases](https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot/releases). Use version **0.3.3-preview.1 or newer** for these instructions.
2. Copy the ZIP to the AI server, then use **Extract All**. Put the extracted program in a permanent writable folder, for example `C:\Apps\Franky`. That folder should contain `START-HERE.cmd`, `START-FRANKY.cmd`, and `SET-BRIDGE-ADDRESS.cmd` directly.
3. Install **64-bit Python 3.13**, including the Python launcher, if it is not already present. The bridge's primary Windows setup target is Python 3.13 on x64.

Do not transfer the old `.venv` folder: setup creates a new environment for the server. The source release excludes your local settings, credentials, downloaded models, logs, and firmware binaries.

Optional: copy only `bridge/voice_settings.json` to preserve the chosen voice. You can also copy the old `bridge/models` directory to the same location before setup to reuse downloaded speech files; otherwise setup downloads them. LM Studio's own chat models are managed separately by LM Studio and can stay where they already are on the AI server.

Do not copy `bridge/.secrets` between computers or Windows users. Those optional credentials are protected for the original Windows user/machine. Re-enter any needed provider credentials locally on the destination. Default LM Studio mode needs no paid cloud account.

## 2. Prepare LM Studio on the AI server

1. Open LM Studio on **192.168.5.250** and load the chat model you want Franky to use.
2. Start its API server, normally on port **1234**.
3. Confirm the loaded model can answer in LM Studio.

Because the bridge will run on the same machine, it uses `http://127.0.0.1:1234/v1`. Franky does not need to reach LM Studio's port directly. If you configured another API port, use that port during provider setup. If your LM Studio server requires authentication, configure `LM_STUDIO_TOKEN` locally for the Windows user that runs the bridge; do not place it in the advertised URL or robot settings.

## 3. Install and record the server address

1. In `C:\Apps\Franky`, double-click **START-HERE.cmd**.
2. Select **LM Studio**. Enter **`http://127.0.0.1:1234/v1`** when asked for the LM Studio address.
3. Select the exact chat model from the displayed list. Let the Python and speech-file setup finish.
4. Double-click **SET-BRIDGE-ADDRESS.cmd**. Enter **`http://192.168.5.250:8766`** and save it.
5. Double-click **START-FRANKY.cmd**, keeping its window open.
6. On the server, open **`http://localhost:8766`**. Wait for the speech readiness checks to finish, then try a voice preview.

The page's **Connection settings** displays the advertised bridge address and the separate LM Studio address. Saving the advertised address does not change Windows networking, the listen port, firewall rules, or Franky's stored device settings. Restart the bridge after changing configuration so the dashboard uses the new values.

Keep `192.168.5.250` stable using your existing static address or a DHCP reservation. The bridge listens on port 8766 on the server's interfaces. The advertised address is the reachable URL you give to the robot and other browsers.

## 4. Allow access from your home network

On the AI server, open **PowerShell as Administrator** and run:

```powershell
Set-Location 'C:\Apps\Franky'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\allow-lan.ps1
```

This enables inbound TCP **8766** for the **Private** Windows network profile and **LocalSubnet** clients only. Use it on the trusted home-network adapter. Do not forward this port through your Internet router; the bridge has no login.

If the server uses a Domain profile, or Franky/your PC is on a different routed subnet or VLAN, the supplied rule may not match. Have your network administrator scope a TCP 8766 rule to the correct trusted profile and client address/subnet, and check inter-VLAN routing. Do not solve this by disabling the firewall or allowing unrestricted public access.

From your normal PC, open **`http://192.168.5.250:8766`**. You should see the same voice/readiness page. A preview plays on the browser's computer or phone; normal robot replies play on Franky's speaker.

## 5. Point Franky at the new server

1. Keep the old bridge installation available until you have verified the new server.
2. Open the **device address shown on Franky's LCD**, not the bridge website. Note the old bridge address in case you need to roll back.
3. Under **A place on your network**, set **Voice bridge / AI server address** to **`http://192.168.5.250:8766`**.
4. Keep the existing Wi-Fi name. Leave the Wi-Fi password blank to retain it for that same network.
5. Choose **Save connection & restart**. If Franky is in an active conversation, choose **Stop current reply** first. Passive wake listening does not block settings in the new firmware.
6. After reconnecting, ask a short question. Check voice playback, a spoken volume change, hands-free follow-up, and BOOT/web Stop.

Changing the server address alone does not require another flash on compatible Franky firmware. The new Stop and passive-listening controls require the updated firmware from this version; see [FIRMWARE.md](FIRMWARE.md). The release is source-only, so build/flash is separate from installing the Windows bridge.

Once the robot works through the AI server, stop the old PC bridge with **Ctrl+C**. Keep its folder as a rollback copy until you are satisfied.

## 6. Verify and troubleshoot

Run **CHECK-SETUP.cmd** on the AI server. It reports cached recognition, voice, and chat availability. A listed chat model does not prove generation speed, quota, or end-to-end audio quality; the spoken test above is still needed.

From another Windows PC, this checks the bridge port:

```powershell
Test-NetConnection 192.168.5.250 -Port 8766
```

- **Works on localhost but not another PC:** check the Windows firewall profile, LocalSubnet scope, routing, and whether the IP is still 192.168.5.250.
- **Website works but chat is unavailable:** check LM Studio's API server, loaded model, exact model ID, and local port. Restart the bridge after changing provider configuration.
- **Website shows the old address:** rerun SET-BRIDGE-ADDRESS and restart the bridge. A `BRIDGE_PUBLIC_URL` environment override takes precedence over the saved address.
- **LM Studio address unexpectedly stays on another PC:** check `LM_STUDIO_URL` and `LM_STUDIO_MODEL` environment overrides on the AI server.
- **Speech service needs attention:** leave startup time for local model preparation; see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if it remains unavailable.
- **Robot cannot connect but the browser can:** confirm it uses **8766**, not **1234**, and is on a network allowed to reach the server.

## Everyday operation and rollback

Keep the AI server awake, LM Studio's API server/model available, and the Franky bridge running. After a Windows reboot, start LM Studio and **START-FRANKY.cmd** again. This release does not install an automatic Windows service or startup task.

To roll back, start the old PC bridge and restore its saved address on Franky's device page. The migration does not erase robot Wi-Fi settings or remove the old installation.
