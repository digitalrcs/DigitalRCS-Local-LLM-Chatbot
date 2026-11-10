# Optional: run in an Administrator PowerShell on a trusted home network.
$ErrorActionPreference = 'Stop'
$name = 'DigitalRCS-Local-LLM-Chatbot'
if (-not (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $name -DisplayName 'DigitalRCS Local LLM Chatbot' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8766 -Profile Private -RemoteAddress LocalSubnet | Out-Null
}
Write-Host 'Home-network access enabled for TCP port 8766 on Private networks only.'
