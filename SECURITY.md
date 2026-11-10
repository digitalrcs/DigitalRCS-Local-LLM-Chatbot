# Security and privacy

This preview is intended for a trusted home LAN. The bridge binds to all network interfaces on TCP 8766 and has **no authentication**. Anyone with network access can request speech, chat, or change the voice. Do not port-forward it, expose it through a public tunnel, or run it on an untrusted/shared network.

The optional firewall helper limits access to the local subnet on Windows Private networks. LM Studio authentication is separate and does not authenticate bridge clients. Browser CORS is not an access-control substitute.

The bridge does not intentionally write uploaded audio or transcripts to disk. Models, connection settings, and voice selection are saved locally. LM Studio and dependencies have their own logging and download behavior. Initial installation requires Internet downloads.

Do not commit config.json, tokens, logs with private data, Wi-Fi settings, full flash backups, or model caches. Before reporting an issue, remove sensitive material. Use GitHub private vulnerability reporting when enabled; do not post exploit details or credentials in a public issue.

Optional online providers receive transcribed conversation text. LAN users who can reach the bridge can consume the selected account’s quota or credits. Keys are entered only in the local console and optionally protected using Windows DPAPI in ignored `bridge/.secrets`; they are never exposed through HTTP. Environment keys override protected files. LM Studio is the default; there is no automatic cloud or paid fallback.
