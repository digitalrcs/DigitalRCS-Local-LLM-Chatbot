# Run Franky on your Windows AI server

You can run Franky's PC helper and website on the same Windows computer as LM Studio. That computer is the **AI server**. Your normal PC can then be switched off while Franky uses the server.

The website comes with the bridge. You do not need IIS or a separate website installer.

This example uses **192.168.5.250** for the AI server. Use your server's own home-network address if it is different. These are instructions, not a claim that your server has already been updated.

## 1. Install Franky on the server

1. On the AI server, download **[Franky Setup.exe](https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot/releases/download/v0.5.0-preview.1/DigitalRCS-Franky-0.5.0-preview.1-Setup.exe)**.
2. Open it and keep the suggested folder. It includes Python and the speech files. If Windows asks for an administrator's password to install Microsoft runtime support, ask the person who manages the server.
3. Open **Franky Setup** when installation finishes. The [easy setup guide](WINDOWS-INSTALLER.md) explains all seven pages.

If you are updating an existing installation, first use **Stop bridge** and close its setup window. For an old command-window installation, press **Ctrl+C** in its running window. Keep the old folder until the new installation works.

## 2. Connect to LM Studio

1. Open LM Studio on the AI server. Download or load the chat model you want to use.
2. Ask it a short question inside LM Studio to check that it can answer.
3. Start LM Studio's server in its **Developer** tab. See the [official server guide](https://lmstudio.ai/docs/developer/core/server).
4. On Franky Setup's **Answers** page, choose **LM Studio**. When both programs run on the AI server, the usual address is **`http://127.0.0.1:1234/v1`**.
5. Click **Find models**, choose the model, then **Save answer settings**.

`127.0.0.1` means “this computer.” It works here because the bridge and LM Studio are on the same server. If LM Studio uses another port or requires a token, tick **LM Studio is on another PC or needs a token** to show those fields. Keep tokens out of addresses and robot settings.

## 3. Check the voice and choose the server address

1. On **Voice**, click **Prepare Franky's voice**, then **Play voice preview**.
2. On **Connect**, click **Find this PC's addresses**. Choose the server's home Ethernet or Wi-Fi address, such as **`http://192.168.5.250:8766`**. Avoid VPN and virtual-network adapters.
3. Click **Save bridge address**, then **Allow home-network access**. Windows may ask an administrator to approve this step.
4. Skip **Robot** if Franky already has compatible working firmware. Moving the bridge to a server does not require another USB flash.
5. On **Try it**, click **Start bridge**, then **Check readiness**. Give the speech models time to load. Check again if they are still starting.

If the server has no speakers, open **`http://192.168.5.250:8766`** on your normal PC or phone. Choose a voice and play a preview there. A browser preview plays on the device running that browser.

The network button allows port **8766** on Windows **Private** networks for nearby devices on the same subnet. Use your trusted home network. If the website only works on the server itself, check the Windows network profile and firewall with the person who manages the server. Do not turn off the firewall or forward this port through your Internet router.

## 4. Tell the robot where the server is

1. Note Franky's old bridge address so you can switch back if needed.
2. In a browser, open **the device address shown on Franky's screen**. This is the robot's settings page, which is different from the voice website.
3. Under **A place on your network**, set **Voice bridge / AI server address** to **`http://192.168.5.250:8766`**.
4. Keep the same Wi-Fi name. Leave the Wi-Fi password blank to keep the saved password for that same network.
5. Choose **Save connection & restart**. If Franky is answering a question, use **Stop current reply** first.
6. Let Franky reconnect, then **hold BOOT while asking a short question and release it to send**. Listen for the answer. Try **Stop** and a volume command too.

For a robot that has not joined your home Wi-Fi yet, use [first-time robot setup](WINDOWS-INSTALLER.md). It explains the **DigitalRCS** setup network and the home **2.4 GHz** Wi-Fi choice.

## Which address goes where?

| What you are setting up | Example address |
| --- | --- |
| LM Studio inside Franky Setup on the AI server | `http://127.0.0.1:1234/v1` |
| Bridge address saved on the Connect page and on the robot | `http://192.168.5.250:8766` |
| Voice website from another PC or phone | `http://192.168.5.250:8766` |
| Voice website on the AI server itself | `http://localhost:8766` |
| Robot settings page | The address shown on Franky's screen |

Port **1234** belongs to LM Studio. Port **8766** belongs to Franky's bridge and website. Never use `localhost` or `127.0.0.1` as the robot's bridge address: from the robot, those mean the robot itself.

Saving the bridge address does not change Windows networking or update the robot automatically. Keep the server's address stable; a router address reservation is one way to do that. Ask the person who manages your network if you need help.

## Every day

Start LM Studio and its selected model/server, then use **Start Franky** on the AI server. Keep the server awake. Setup does not add an automatic Windows service or start the programs at login.

To stop the installed copy, open **Franky Setup**, go to **Try it**, and click **Stop bridge**. Closing the setup window alone leaves its bridge running.

Once everything works through the server, stop the old PC's bridge. Keep its folder for a while. To switch back, start the old bridge and put its old address back into the robot's settings.

## If something does not work

| What you see | What to try |
| --- | --- |
| Website opens on the server, but not your phone/PC | Check the server address, home-network profile and firewall. Guest Wi-Fi can block devices from talking. |
| Website opens, but chat is unavailable | Start LM Studio's server and load the selected model. Check the model on **Answers**, save, and restart the bridge. |
| Voice or listening is not ready | Use **Prepare Franky's voice**, wait for it to finish, then try a preview. See [voice help](VOICE-SETUP.md). |
| Website shows the old bridge address | Stop the bridge, save the new address on **Connect**, then start it again. Update the robot separately. |
| Robot cannot connect | Check that its bridge address ends in **8766**, and that it can reach the same home network as the server. |
| Another Franky copy is already running | Stop it from the original setup or command window, then start the copy you want to use. |

A ready message checks software availability. A real spoken question is still needed to test the microphone, speakers, and chat response. See [troubleshooting](TROUBLESHOOTING.md) for more help.

## Moving settings from an older manual installation

This section is optional. New users can skip it.

- Do not copy `.venv` or `.runtime` from another machine. Run Setup.exe on the destination instead.
- Your old manual folder is not imported automatically into a new default installer folder. Choose the provider/model again in Franky Setup. Stop both copies before moving settings files.
- You can copy `bridge/voice_settings.json` to keep a voice choice. The installer already contains the standard speech models; LM Studio manages its chat models separately.
- Do not transfer `bridge/.secrets` between computers or Windows users. Windows protects these keys for their original account/machine. Re-enter any needed provider key in the destination setup app.
- Manual launchers still use environment overrides such as `LM_STUDIO_URL`, `LM_STUDIO_MODEL`, and `BRIDGE_PUBLIC_URL`. The native setup app uses the routing choices saved in its own window. See [configuration details](ARCHITECTURE.md#configuration).
- If you prefer the ZIP/command-window route, follow [manual installation](INSTALL.md), use **SET-BRIDGE-ADDRESS.cmd** for the advertised address, and keep **START-FRANKY.cmd** open while the bridge runs.

For a Domain network, routed subnet, or VLAN, the supplied Private/LocalSubnet firewall rule may not match. Have the network administrator choose a rule limited to the intended clients. An optional advanced connection check is `Test-NetConnection 192.168.5.250 -Port 8766` in PowerShell.
