# SPDX-License-Identifier: MIT
# Build-only: creates an isolated payload and installer; installs nothing globally.
[CmdletBinding()]
param(
    [string]$RuntimeZip,
    [string]$VCRedist,
    [string]$Esptool,
    [string]$FirmwareDirectory,
    [string]$ModelsDirectory,
    [string]$AssetManifest,
    [switch]$SkipPayloadBuild,
    [string]$OutputDirectory,
    [string]$BuildPython,
    [string]$InnoCompiler,
    [string]$CSharpCompiler
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$stageRoot = Join-Path $repoRoot 'dist\installer'
$payload = Join-Path $stageRoot 'payload'
$payloadFiles = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($generated in @('FrankySetup.exe', 'installer/assets-manifest.json', 'installer/PACKAGED-ASSETS.md', 'installer/payload-files.json')) { $null = $payloadFiles.Add($generated) }
$assetRoot = Join-Path $repoRoot 'dist\installer-assets'
$runtimeVersion = '3.13.18'
$runtimeBuild = '20261110'
$runtimeName = 'cpython-3.13.18+20261110-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
$runtimeUrl = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.13.18%2B20261110-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
$runtimeHash = '2e0fed09d48989f64c9305da9ff2d37a41c0d13ab2aa6283405b2b620dfbf805'
if (-not $RuntimeZip) { $RuntimeZip = Join-Path $assetRoot $runtimeName }
if (-not $VCRedist) { $VCRedist = Join-Path $assetRoot 'vc_redist.x64.exe' }
if (-not $Esptool) { $Esptool = Join-Path $assetRoot 'esptool.exe' }
if (-not $FirmwareDirectory) { $FirmwareDirectory = Join-Path $assetRoot 'firmware' }
if (-not $ModelsDirectory) { $ModelsDirectory = Join-Path $assetRoot 'models' }
if (-not $AssetManifest) { $AssetManifest = Join-Path $assetRoot 'assets.json' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $stageRoot 'output' }
if (-not $BuildPython) { $BuildPython = Join-Path $repoRoot '.venv\Scripts\python.exe' }
if (-not $CSharpCompiler) { $CSharpCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe' }
if (-not $InnoCompiler) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    $InnoCompiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Require-File([string]$Path, [string]$Purpose) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Purpose was not found: $Path" }
}
function Copy-PayloadFile([string]$Source, [string]$Relative) {
    $destination = [IO.Path]::GetFullPath((Join-Path $payload $Relative))
    if (-not $destination.StartsWith($payload + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Payload path escapes its staging directory: $Relative"
    }
    Require-File $Source 'Payload input'
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $destination -Force
    $null = $payloadFiles.Add($Relative.Replace('\', '/'))
}
function Hash-File([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Write-Utf8([string]$Path, [string]$Text) { [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false)) }
function Test-Exit([string]$Action) { if ($LASTEXITCODE -ne 0) { throw "$Action failed with exit code $LASTEXITCODE" } }

Require-File $BuildPython 'Build Python 3.13 x64'
Require-File $CSharpCompiler 'C# compiler'
Require-File $InnoCompiler 'Inno Setup compiler'
& $BuildPython -I -c "import sys,struct; assert sys.version_info[:2] == (3,13) and struct.calcsize('P') == 8, 'Use Python 3.13 x64 for wheel selection'"
Test-Exit 'Build Python check'
New-Item -ItemType Directory -Force -Path $stageRoot, $assetRoot, $OutputDirectory | Out-Null

# The fixed staging path is the only directory this script can delete recursively.
if (-not $SkipPayloadBuild) {
    if (Test-Path -LiteralPath $payload) {
        $resolved = (Resolve-Path -LiteralPath $payload).Path
        $expected = [IO.Path]::GetFullPath((Join-Path $repoRoot 'dist\installer\payload'))
        if ($resolved -ne $expected -or (Get-Item -LiteralPath $payload -Force).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
            throw 'Refusing to replace an unexpected payload path.'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $payload | Out-Null
    if (-not (Test-Path -LiteralPath $RuntimeZip)) {
        if ([IO.Path]::GetFullPath($RuntimeZip) -ne [IO.Path]::GetFullPath((Join-Path $assetRoot $runtimeName))) {
            throw 'The supplied -RuntimeZip archive does not exist.'
        }
        Write-Host "Downloading pinned CPython $runtimeVersion portable runtime..."
        Invoke-WebRequest -Uri $runtimeUrl -OutFile ($RuntimeZip + '.part')
        if ((Hash-File ($RuntimeZip + '.part')) -ne $runtimeHash) { throw 'Runtime download SHA-256 mismatch.' }
        Move-Item -LiteralPath ($RuntimeZip + '.part') -Destination $RuntimeZip
    }
    if ((Hash-File $RuntimeZip) -ne $runtimeHash) { throw 'Runtime archive SHA-256 mismatch.' }
    $extractScript = @'
from pathlib import Path
import shutil, sys, tarfile
archive, target = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
target.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, "r:gz") as source:
    for entry in source:
        parts = Path(entry.name).parts
        if not parts or parts[0] != "python" or ".." in parts or Path(entry.name).is_absolute():
            raise ValueError("Unexpected runtime archive path")
        if not (entry.isdir() or entry.isfile()):
            raise ValueError("Runtime archive contains a link or special file")
        dest = target.joinpath(*parts[1:])
        if not dest.is_relative_to(target):
            raise ValueError("Runtime archive path escaped its destination")
        if entry.isdir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(entry) as inp, dest.open("wb") as out:
                shutil.copyfileobj(inp, out)
'@
    $extractPath = Join-Path $stageRoot 'extract-runtime.py'
    Write-Utf8 $extractPath $extractScript
    & $BuildPython -I $extractPath $RuntimeZip (Join-Path $payload '.runtime')
    Test-Exit 'Runtime extraction'
    & $BuildPython -m pip install --no-compile --target (Join-Path $payload '.runtime\Lib\site-packages') -r (Join-Path $repoRoot 'bridge\requirements-lock.txt') --report (Join-Path $stageRoot 'pip-install-report.json')
    Test-Exit 'Fresh wheel installation'
}

$runtimePython = Join-Path $payload '.runtime\python.exe'
Require-File $runtimePython 'Staged private runtime (omit -SkipPayloadBuild on the first build)'
Require-File $RuntimeZip 'Pinned runtime archive'
if ((Hash-File $RuntimeZip) -ne $runtimeHash) { throw 'Runtime archive SHA-256 mismatch.' }
& $runtimePython -I -c "import sys,struct,fastapi,uvicorn,numpy,onnxruntime,ctranslate2,faster_whisper,kokoro_onnx; assert sys.version_info[:3] == (3,13,18) and struct.calcsize('P') == 8; print('Private runtime and speech imports passed')"
Test-Exit 'Private runtime smoke check'

# Reuse the source release's explicit allowlist, never a recursive repository copy.
$sourceData = & $BuildPython -I -c "import json,runpy,sys; p=runpy.run_path(sys.argv[1]); print(json.dumps({'version':p['VERSION'],'files':p['FILES']}))" (Join-Path $repoRoot 'scripts\package.py')
Test-Exit 'Source allowlist loading'
$sourceData = $sourceData | ConvertFrom-Json
$sourceFiles = @($sourceData.files) + @('installer/FrankySetup.cs', 'installer/worker.py', 'installer/bridge_runner.py', 'installer/flash_robot.py', 'installer/FrankySetup.iss', 'scripts/build-installer.ps1')
foreach ($relative in ($sourceFiles | Sort-Object -Unique)) {
    if ($relative -match '(^|[\\/])(\.git|\.venv|\.secrets|private-backups)([\\/]|$)' -or $relative -match '^bridge/(config\.json|voice_settings\.json)') {
        throw "Private state found in the source allowlist: $relative"
    }
    $source = [IO.Path]::GetFullPath((Join-Path $repoRoot $relative))
    if (-not $source.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Source allowlist path escapes repository: $relative"
    }
    Copy-PayloadFile $source $relative
}

Require-File $AssetManifest 'External-assets manifest'
$externalAssets = Get-Content -LiteralPath $AssetManifest -Raw | ConvertFrom-Json
$externalAssetRoot = Split-Path ([IO.Path]::GetFullPath($AssetManifest)) -Parent
function Test-AssetHash([string]$Name, [string]$Path) {
    $entry = @($externalAssets.assets | Where-Object { $_.name -eq $Name })
    if ($entry.Count -ne 1 -or $entry[0].sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw "Missing unique asset checksum: $Name" }
    if ((Hash-File $Path) -ne $entry[0].sha256) { throw "External asset checksum mismatch: $Name" }
}
Require-File $VCRedist 'Microsoft X64 redistributable'
Require-File $Esptool 'Standalone esptool executable'
Test-AssetHash 'vc_redist.x64.exe' $VCRedist
Test-AssetHash 'esptool.exe' $Esptool
$signature = Get-AuthenticodeSignature -LiteralPath $VCRedist
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
    throw 'The VC++ redistributable must carry a valid Microsoft signature.'
}
Copy-PayloadFile $VCRedist 'installer/tools/vc_redist.x64.exe'
Copy-PayloadFile $Esptool 'installer/tools/esptool.exe'

$firmwareManifestPath = Join-Path $FirmwareDirectory 'manifest.json'
Require-File $firmwareManifestPath 'Supported firmware manifest'
$firmware = Get-Content -LiteralPath $firmwareManifestPath -Raw | ConvertFrom-Json
if ($firmware.chip -ne 'esp32s3' -or $firmware.flash_size -ne '16MB' -or @($firmware.files).Count -ne 4) { throw 'Unsupported firmware manifest.' }
$offsets = @()
foreach ($entry in $firmware.files) {
    if ($entry.name -notmatch '^[A-Za-z0-9_.-]+\.bin$') { throw 'Invalid firmware filename.' }
    $offset = if ([string]$entry.offset -match '^0x[0-9a-fA-F]+$') { [Convert]::ToInt32(([string]$entry.offset).Substring(2), 16) } else { [int]$entry.offset }
    $offsets += $offset
    $file = Join-Path $FirmwareDirectory $entry.name
    Require-File $file 'Firmware image'
    if ((Hash-File $file) -ne $entry.sha256) { throw "Firmware checksum mismatch: $($entry.name)" }
    if ($offset -eq 0xe000 -and (Get-Item -LiteralPath $file).Length -ne 8192) { throw 'boot_app0 must be 8192 bytes.' }
    Copy-PayloadFile $file ('installer/firmware/' + $entry.name)
}
if ((@($offsets | Sort-Object -Unique) -join ',') -ne '0,32768,57344,65536') { throw 'Unexpected ESP32-S3 firmware offsets.' }
Copy-PayloadFile $firmwareManifestPath 'installer/firmware/manifest.json'

foreach ($relative in @('kokoro/kokoro-v1.0.onnx', 'kokoro/voices-v1.0.bin')) {
    Test-AssetHash ([IO.Path]::GetFileName($relative)) (Join-Path $ModelsDirectory $relative)
    Copy-PayloadFile (Join-Path $ModelsDirectory $relative) ('bridge/models/' + $relative)
}
foreach ($model in @('whisper-base.en', 'whisper-tiny.en')) {
    $directory = [IO.Path]::GetFullPath((Join-Path $ModelsDirectory $model))
    $modelAsset = @($externalAssets.assets | Where-Object { $_.name -eq $model })
    if ($modelAsset.Count -ne 1) { throw "Missing unique model provenance: $model" }
    foreach ($required in @('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt')) { Require-File (Join-Path $directory $required) "$model model file" }
    foreach ($file in Get-ChildItem -LiteralPath $directory -File -Force) {
        if ($file.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Materialize model snapshot links before packaging.' }
        if ($file.Name.StartsWith('.') -or $file.Attributes.HasFlag([IO.FileAttributes]::Hidden)) { continue }
        $fileAsset = @($modelAsset[0].files | Where-Object { $_.name -eq $file.Name })
        if ($fileAsset.Count -ne 1 -or (Hash-File $file.FullName) -ne $fileAsset[0].sha256) { throw "Missing or mismatched model checksum: $model/$($file.Name)" }
        Copy-PayloadFile $file.FullName ('bridge/models/' + $model + '/' + $file.Name)
    }
}

# Only manifest-listed source archives and explicit notice files are redistributed.
foreach ($asset in $externalAssets.assets) {
    if ($asset.name -match '^[A-Za-z0-9_.+-]+\.(zip|tar\.gz|tgz)$') {
        $archive = Join-Path $externalAssetRoot $asset.name
        Require-File $archive 'Corresponding source archive'
        Test-AssetHash $asset.name $archive
        Copy-PayloadFile $archive ('third-party/' + $asset.name)
    }
}
$noticeDirectory = Join-Path $externalAssetRoot 'notices'
if (-not (Test-Path -LiteralPath $noticeDirectory -PathType Container)) { throw 'External asset notices directory is missing.' }
foreach ($file in Get-ChildItem -LiteralPath $noticeDirectory -File) {
    if ($file.Extension -notin @('.txt', '.md') -and $file.Name -ne 'LICENSE') { throw "Unexpected notice format: $($file.Name)" }
    Copy-PayloadFile $file.FullName ('third-party/notices/' + $file.Name)
}

# A native asInvoker GUI avoids depending on another installed .NET runtime.
$appManifest = Join-Path $stageRoot 'wizard.manifest'
Write-Utf8 $appManifest @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity version="1.0.0.0" name="DigitalRCS.FrankySetup" />
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false" /></requestedPrivileges></security></trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1"><application><supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}" /></application></compatibility>
</assembly>
'@
& $CSharpCompiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$(Join-Path $payload 'FrankySetup.exe')" "/win32manifest:$appManifest" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:System.Net.Http.dll (Join-Path $repoRoot 'installer\FrankySetup.cs')
Test-Exit 'Wizard compilation'

# Retain dependency licenses in place and ship provenance plus a file inventory.
$reportPath = Join-Path $stageRoot 'pip-install-report.json'
Require-File $reportPath 'Wheel installation report'
$pipReport = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$wheels = @($pipReport.install | ForEach-Object {
    $uri = [Uri]$_.download_info.url
    if ($uri.UserInfo) { throw 'Credential-bearing package URL cannot be shipped.' }
    [ordered]@{ name=$_.metadata.name; version=$_.metadata.version; url=$uri.GetLeftPart([UriPartial]::Path); sha256=$_.download_info.archive_info.hashes.sha256 }
})
$manifest = [ordered]@{
    version=$sourceData.version
    python=[ordered]@{ version=$runtimeVersion; build=$runtimeBuild; source=$runtimeUrl; sha256=$runtimeHash; license='.runtime/LICENSE.txt'; distribution='Astral python-build-standalone, Windows x64 install_only_stripped' }
    external_assets=$externalAssets
    wheel_assets=$wheels
    requirements_sha256=(Hash-File (Join-Path $repoRoot 'bridge\requirements-lock.txt'))
}
Write-Utf8 (Join-Path $payload 'installer\assets-manifest.json') ($manifest | ConvertTo-Json -Depth 16)
Write-Utf8 (Join-Path $payload 'installer\PACKAGED-ASSETS.md') @'
# Bundled software

The isolated Python distribution is maintained by Astral and contains CPython and its bundled dependencies. Its license texts remain under `.runtime`, including `LICENSE.txt` and package `licenses` directories. This is not a python.org Windows installer and does not modify system Python.

Python-package copyright notices and licenses remain in `.runtime/Lib/site-packages`, including each distribution's `.dist-info` directory. Source URLs, versions and hashes are recorded in `assets-manifest.json`. Model/tool notices and corresponding-source archives are under `third-party`. Consult the application's `THIRD_PARTY_NOTICES.md` and `firmware/PROVENANCE.md` for further attribution.

Uninstall preserves speech models and user-created settings/credentials. The installer does not erase robot storage or flash a robot automatically.
'@
$inventory = @()
Write-Host 'Checking and hashing the complete installer payload...'
foreach ($file in (Get-ChildItem -LiteralPath $payload -File -Recurse -Force | Sort-Object FullName)) {
    $relative = $file.FullName.Substring($payload.Length + 1).Replace('\', '/')
    if ($relative -match '(^|/)(\.git|\.venv|\.secrets|private-backups|logs|\.cache)(/|$)' -or $relative -match '^bridge/(config\.json|voice_settings\.json)(\.|$)' -or $relative -match '\.part$') {
        throw "Private or incomplete file found in payload: $relative"
    }
    if (-not $relative.StartsWith('.runtime/') -and -not $payloadFiles.Contains($relative)) {
        throw "Unlisted stale file found in payload: $relative. Rebuild without -SkipPayloadBuild."
    }
    if ($relative -eq 'installer/payload-files.json') { continue }
    $inventory += [ordered]@{ path=$relative; bytes=$file.Length; sha256=(Hash-File $file.FullName) }
}
Write-Utf8 (Join-Path $payload 'installer\payload-files.json') ($inventory | ConvertTo-Json -Depth 4)
$vcVersion = (Get-Item -LiteralPath $VCRedist).VersionInfo.ProductVersion
if ($vcVersion -notmatch '^\d+\.\d+\.\d+\.\d+') { throw 'Could not determine the bundled VC++ runtime version.' }
$vcVersion = $Matches[0]
Write-Host 'Compiling the all-in-one Windows installer...'
& $InnoCompiler /Q "/DPayloadDir=$payload" "/DInstallerOutput=$([IO.Path]::GetFullPath($OutputDirectory))" "/DFrankyVersion=$($sourceData.version)" "/DVCRuntimeVersion=$vcVersion" "/DVCRedistSHA256=$(Hash-File $VCRedist)" (Join-Path $repoRoot 'installer\FrankySetup.iss')
Test-Exit 'Installer compilation'
$installer = Join-Path $OutputDirectory ("DigitalRCS-Franky-" + $sourceData.version + '-Setup.exe')
Require-File $installer 'Compiled installer'
Write-Utf8 ($installer + '.sha256') ((Hash-File $installer) + '  ' + [IO.Path]::GetFileName($installer) + "`n")
Write-Host "Installer ready: $installer" -ForegroundColor Green
