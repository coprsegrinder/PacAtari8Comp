# Boot a ROM image in Altirra (Rev B OS, 48K) and log CRCs of the RAM the game builds at start-up, taken at the first
# vertical-blank interrupt. Used to show that bytes of the ROM are irrelevant (same CRCs with different contents).
# Usage: powershell -ExecutionPolicy Bypass -File tools\boot_crc_check.ps1 -Rom <image> -Log <logfile>
param([Parameter(Mandatory)][string]$Rom, [Parameter(Mandatory)][string]$Log)
$alt   = (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra64.exe')
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_crc.batch'
Set-Content -Path $batch -Encoding ascii -Value @(
  ".logopen $Log",
  'bp -n a5fd ".echo RAM_0600_0FFF; .crc 0600 L0A00; .echo RAM_1000_18C7; .crc 1000 L08C8; .echo RAM_3000_3327; .crc 3000 L0328; .logclose"',
  '.restart', 'g')
$line = '/portable /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + (Resolve-Path $Rom).Path + '"'
$p = Start-Process -FilePath $alt -ArgumentList $line -PassThru
Start-Sleep 10
if (-not $p.HasExited) { $p.Kill() }
Get-Content $Log
