; SPDX-License-Identifier: MIT
; Compile through scripts/build-installer.ps1. Only its audited payload is read.
#ifndef PayloadDir
  #error PayloadDir must name the staged installer payload.
#endif
#ifndef InstallerOutput
  #define InstallerOutput "..\dist\installer\output"
#endif
#ifndef FrankyVersion
  #define FrankyVersion "0.5.0-preview.1"
#endif
#ifndef VCRuntimeVersion
  #define VCRuntimeVersion "14.40.0.0"
#endif
#ifndef VCRedistSHA256
  #error VCRedistSHA256 must identify the signed prerequisite.
#endif

[Setup]
AppId={{173D0F5D-863A-4795-9F47-7641CE62D067}
AppName=Franky by DigitalRCS
AppVersion={#FrankyVersion}
AppPublisher=DigitalRCS
AppPublisherURL=https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot
DefaultDirName={localappdata}\Programs\Franky
DefaultGroupName=Franky
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
WizardStyle=modern dynamic
LicenseFile={#PayloadDir}\LICENSE
OutputDir={#InstallerOutput}
OutputBaseFilename=DigitalRCS-Franky-{#FrankyVersion}-Setup
Compression=lzma2/fast
SolidCompression=yes
UninstallDisplayIcon={app}\FrankySetup.exe
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Dirs]
; User-created settings and downloaded models survive uninstall.
Name: "{app}\bridge\models"; Flags: uninsneveruninstall
Name: "{app}\bridge\.secrets"; Flags: uninsneveruninstall

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Excludes: "bridge\models\*,installer\tools\vc_redist.x64.exe,bridge\config.json,bridge\voice_settings.json,bridge\.secrets\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\bridge\models\*"; DestDir: "{app}\bridge\models"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist uninsneveruninstall
Source: "{#PayloadDir}\installer\tools\vc_redist.x64.exe"; DestDir: "{app}\installer\tools"; Flags: ignoreversion

[Icons]
Name: "{group}\Franky Setup"; Filename: "{app}\FrankySetup.exe"; WorkingDir: "{app}"
Name: "{group}\Start Franky"; Filename: "{app}\FrankySetup.exe"; Parameters: "--start"; WorkingDir: "{app}"
Name: "{autodesktop}\Start Franky"; Filename: "{app}\FrankySetup.exe"; Parameters: "--start"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Uninstall Franky"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\FrankySetup.exe"; Description: "Open Franky setup and control panel"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
function GetCurrentProcessId: Cardinal;
  external 'GetCurrentProcessId@kernel32.dll stdcall';

function RunCheck(const ScriptName, ScriptText, Parameters: String): Boolean;
var
  ScriptPath: String;
  ExitCode: Integer;
begin
  ScriptPath := ExpandConstant('{tmp}\') + ScriptName;
  Result := SaveStringToFile(ScriptPath, ScriptText, False);
  if Result then
    Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + ScriptPath + '" ' + Parameters,
      '', SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

function InstalledProgramsClosed: Boolean;
var
  UninstallerPath: String;
begin
  UninstallerPath := '';
  if IsUninstaller then UninstallerPath := ExpandConstant('{uninstallexe}');
  Result := RunCheck('franky-process-check.ps1',
    'param([string]$InstallRoot, [int]$IgnoreProcessId, [string]$UninstallerPath)' + #13#10 +
    '$ErrorActionPreference = ''Stop''' + #13#10 +
    '$env:PSModulePath = Join-Path $PSHOME ''Modules''' + #13#10 +
    'try {' + #13#10 +
    '  $prefix = [IO.Path]::GetFullPath($InstallRoot).TrimEnd(''\'') + ''\''' + #13#10 +
    '  $processes = @(Get-CimInstance Win32_Process)' + #13#10 +
    '  $launcherId = 0' + #13#10 +
    '  if ($UninstallerPath) {' + #13#10 +
    '    $current = $processes | Where-Object { $_.ProcessId -eq $IgnoreProcessId } | Select-Object -First 1' + #13#10 +
    '    $launcher = $processes | Where-Object { $_.ProcessId -eq $current.ParentProcessId -and $_.ExecutablePath -eq $UninstallerPath } | Select-Object -First 1' + #13#10 +
    '    if ($launcher) { $launcherId = $launcher.ProcessId }' + #13#10 +
    '  }' + #13#10 +
    '  foreach ($p in $processes) {' + #13#10 +
    '    if ($p.ProcessId -eq $IgnoreProcessId) { continue }' + #13#10 +
    '    if ($p.ProcessId -eq $launcherId) { continue }' + #13#10 +
    '    if (($p.ExecutablePath -and $p.ExecutablePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) -or' + #13#10 +
    '        ($p.CommandLine -and $p.CommandLine.IndexOf($prefix + ''installer\bridge_runner.py'', [StringComparison]::OrdinalIgnoreCase) -ge 0)) { exit 1 }' + #13#10 +
    '  }' + #13#10 +
    '  exit 0' + #13#10 +
    '} catch { exit 2 }', '"' + ExpandConstant('{app}') + '" ' + IntToStr(GetCurrentProcessId) + ' "' + UninstallerPath + '"');
end;

function ValidMicrosoftPrerequisite: Boolean;
var
  Prerequisite: String;
begin
  Prerequisite := ExpandConstant('{tmp}\vc_redist.x64.exe');
  Result := CompareText(GetSHA256OfFile(Prerequisite), '{#VCRedistSHA256}') = 0;
  if Result then
    Result := RunCheck('franky-signature-check.ps1',
      'param([string]$FilePath)' + #13#10 +
      '$ErrorActionPreference = ''Stop''' + #13#10 +
      '$env:PSModulePath = Join-Path $PSHOME ''Modules''' + #13#10 +
      'try {' + #13#10 +
      '  $s = Get-AuthenticodeSignature -LiteralPath $FilePath' + #13#10 +
      '  if ($s.Status -ne ''Valid'' -or $s.SignerCertificate.Subject -notmatch ''(^|,\s*)O=Microsoft Corporation(,|$)'') { exit 1 }' + #13#10 +
      '  exit 0' + #13#10 +
      '} catch { exit 2 }', '"' + Prerequisite + '"');
end;

function NeedsVCRuntime: Boolean;
var
  Installed: Cardinal;
  VersionText: String;
  InstalledVersion, RequiredVersion: Int64;
begin
  Result := True;
  if not RegQueryDWordValue(HKLM64,
      'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then Exit;
  if Installed <> 1 then Exit;
  if not RegQueryStringValue(HKLM64,
      'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', VersionText) then Exit;
  if (Length(VersionText) > 0) and (VersionText[1] = 'v') then Delete(VersionText, 1, 1);
  if not StrToVersion(VersionText, InstalledVersion) then Exit;
  if not StrToVersion('{#VCRuntimeVersion}', RequiredVersion) then Exit;
  Result := ComparePackedVersion(InstalledVersion, RequiredVersion) < 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if not InstalledProgramsClosed then
  begin
    Result := 'Close Franky before installing or updating. In Franky Setup, click Stop bridge, then close the setup panel and retry. If you started the bridge in a terminal, stop that window with Ctrl+C.';
    Exit;
  end;
  if not NeedsVCRuntime then Exit;
  ExtractTemporaryFile('vc_redist.x64.exe');
  if not ValidMicrosoftPrerequisite then
  begin
    Result := 'Windows could not verify the bundled Microsoft Visual C++ installer. Check your connection and Windows certificate updates, then retry. The prerequisite was not run.';
    Exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installing Microsoft speech-library support...';
  // Only this signed Microsoft prerequisite requests administrator access.
  if not ShellExec('runas', ExpandConstant('{tmp}\vc_redist.x64.exe'),
      '/install /passive /norestart', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ExitCode) then
  begin
    Result := 'Microsoft Visual C++ support was not installed. Allow its Windows prompt and retry. ' + SysErrorMessage(ExitCode);
    Exit;
  end;
  if (ExitCode = 3010) or (ExitCode = 1641) then
    NeedsRestart := True
  else if ExitCode <> 0 then
    Result := 'Microsoft Visual C++ support could not be installed (code ' + IntToStr(ExitCode) + '). Retry after resolving the prerequisite error.';
end;

function InitializeUninstall: Boolean;
begin
  Result := InstalledProgramsClosed;
  if not Result then
  begin
    Log('Uninstall blocked: close Franky and its setup panel before retrying.');
    if not UninstallSilent then
      MsgBox('Close Franky before uninstalling. In Franky Setup, click Stop bridge, then close the setup panel and retry. If you started the bridge in a terminal, stop that window with Ctrl+C.', mbError, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if not UninstallSilent then
      MsgBox('Franky was removed. Your saved settings, protected provider keys, and speech models remain in ' +
        ExpandConstant('{app}') + '. You can keep them for reinstalling Franky.', mbInformation, MB_OK);
end;
