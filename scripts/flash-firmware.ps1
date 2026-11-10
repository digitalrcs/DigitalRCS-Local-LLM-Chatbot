param([Parameter(Mandatory=$true)][string]$Port, [string]$Cli = 'C:/Program Files/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
if (-not (Test-Path 'build-firmware/Franky.ino.bin')) { throw 'Build the firmware first. Read docs/FIRMWARE.md.' }
if (-not (Test-Path -LiteralPath $Cli)) { $Cli = (Get-Command arduino-cli -ErrorAction Stop).Source }
Write-Host "Replacing firmware on $Port. Existing flash/NVS is not erased. Keep your private backup."
& $Cli --config-file '.arduino-user/cli.json' upload --port $Port --fqbn 'esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi,CDCOnBoot=default,UploadSpeed=115200' --input-dir build-firmware firmware/Franky
if ($LASTEXITCODE) { throw 'Upload failed. Read the error above; do not erase the device to troubleshoot.' }
