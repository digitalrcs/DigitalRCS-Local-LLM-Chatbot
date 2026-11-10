$ErrorActionPreference = 'Stop'
$port = (Read-Host 'Kit COM port, for example COM9').Trim().ToUpperInvariant()
if ($port -notmatch '^COM[1-9][0-9]*$') { throw 'Enter a port such as COM9.' }
& "$PSScriptRoot/flash-firmware.ps1" -Port $port
