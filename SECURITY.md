# Security and privacy

This preview is intended for a trusted home LAN. The bridge binds to all network interfaces on TCP 8766 and has **no authentication**. Anyone with network access can request speech, chat, or change the voice. Do not port-forward it, expose it through a public tunnel, or run it on an untrusted/shared network.

The optional firewall helper limits access to the local subnet on Windows Private networks. LM Studio authentication is separate and does not authenticate bridge clients. Browser CORS is not an access-control substitute.

The bridge does not intentionally write uploaded audio or transcripts to disk. Models, connection settings, and voice selection are saved locally. LM Studio and dependencies have their own logging and download behavior. Initial installation requires Internet downloads.

Optional hands-free mode samples room audio while unpaused and sends speech-like snippets to the local bridge. Wake recognition never calls the chat provider. Wake/pause phrases are not authentication, and TV audio or recognition mistakes can trigger them. Pause stops new capture and persists across restarts; an already-uploaded snippet may finish local recognition but its result is discarded. See [hands-free operation](docs/HANDS-FREE.md).

Do not commit config.json, tokens, logs with private data, Wi-Fi settings, full flash backups, or model caches. Before reporting an issue, remove sensitive material. Use GitHub private vulnerability reporting when enabled; do not post exploit details or credentials in a public issue.

Optional online providers receive transcribed conversation text. LAN users who can reach the bridge can consume the selected account’s quota or credits. Keys are entered in the local setup app's masked field or the manual console and protected using Windows DPAPI in ignored `bridge/.secrets` when saved; they are never exposed through HTTP. The native app passes setup requests to a private child process over stdin, not through command-line arguments or a web endpoint. Environment keys override protected files. LM Studio is the default; there is no automatic cloud or paid fallback.

The Windows installer runs as the current user. Its signed Microsoft runtime prerequisite and optional home-network firewall step can request administrator approval. The main Franky installer is an unsigned preview. Confirm that downloads came from this repository's release; do not disable Windows security to install it. Models, saved settings, protected keys, and private firmware backups are intentionally kept after uninstall so a reinstall can reuse them. Remove the remaining installation folder yourself if you also want to remove that data.
