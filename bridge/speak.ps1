param([Parameter(Mandatory=$true)][string]$InputPath,
      [Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$stream = $null
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
    if (-not $voice) { throw 'No English Windows speech voice is installed.' }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $stream = [System.IO.File]::Create($OutputPath)
    $speaker.SetOutputToAudioStream($stream, $format)
    $speaker.Speak([System.IO.File]::ReadAllText($InputPath))
} finally {
    $speaker.Dispose()
    if ($stream) { $stream.Dispose() }
}
