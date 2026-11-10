param([string]$Cli = 'C:/Program Files/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe', [switch]$Install)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath $Cli)) {
    $command = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if (-not $command) { throw 'Install Arduino IDE 2 or put arduino-cli on PATH.' }
    $Cli = $command.Source
}
New-Item -ItemType Directory -Force '.arduino-user' | Out-Null
$config = Join-Path $root '.arduino-user/cli.json'
@{ directories = @{ user = (Join-Path $root '.arduino-user') }; board_manager = @{ additional_urls = @('https://espressif.github.io/arduino-esp32/package_esp32_index.json') } } | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $config
function Run-Cli([string[]]$Arguments) {
    & $Cli --config-file $config @Arguments
    if ($LASTEXITCODE) { throw 'Arduino command failed. Read the error above.' }
}
if ($Install) {
    Run-Cli @('core', 'update-index')
    Run-Cli @('core', 'install', 'esp32:esp32@4.0.0-alpha1')
    Run-Cli @('lib', 'install', 'ArduinoJson@7.4.3', 'Adafruit GFX Library@1.12.6', 'Adafruit ST7735 and ST7789 Library@1.11.0', 'Adafruit BusIO@1.17.4')
}
Run-Cli @('compile', '--jobs', '4', '--fqbn', 'esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi,CDCOnBoot=default', '--build-path', (Join-Path $root 'build-firmware'), (Join-Path $root 'firmware/Franky'))
Write-Host 'Firmware built. This does not flash the robot.'
