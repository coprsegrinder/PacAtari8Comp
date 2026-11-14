# Human-played high-level test: starts Altirra at NORMAL speed with the invulnerable, logging command file tools\altirra_humanplay.cmd, and leaves it running for you to play.
# Usage: powershell -ExecutionPolicy Bypass -File tools\play_level_test.ps1 -StartLevel 15 [-Log analysis\raw-logs\play-level.txt]
# -StartLevel: the game's zero-based level counter (board shown = counter + 1; 15 = the 16th board). Your own Altirra.ini is used (speed 100 %); nothing of yours is changed.
# When you are done just close the Altirra window; the log is flushed every few seconds (heartbeat line), so at most the last second is missing.
param([int]$StartLevel = 15, [string]$Log = 'analysis\raw-logs\play-level.txt')
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# Logs live in analysis\raw-logs (gitignored); relative paths resolve against the project root, and the folder is created if missing.
$Log = if ([IO.Path]::IsPathRooted($Log)) { $Log } else { Join-Path (Split-Path -Parent $root) $Log }
[void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log))
$alt  = (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra64.exe')
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
$hex  = '$' + $StartLevel.ToString('X2')
$text = (Get-Content (Join-Path $root 'altirra_humanplay.cmd') -Raw).Replace('@@LEVEL@@', "$StartLevel").Replace('@@HEX@@', $hex)
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_humanplay.batch'
$lines = @(".logopen `"$Log`"") + ($text -split "`r?`n" | Where-Object { $_ -notmatch '^\s*(#|$)' }) + @('.restart', 'g')
Set-Content -Path $batch -Value $lines -Encoding ascii
$line = '/portablealt:"' + (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra.ini') + '" /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
Start-Process -FilePath $alt -ArgumentList $line
