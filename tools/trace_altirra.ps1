# Launch Altirra (Rev B OS, Pac-Man cartridge) with the tracepoints in tools\altirra_trace.cmd, logging to a file.
# Usage: powershell -ExecutionPolicy Bypass -File tools\trace_altirra.ps1 -Log <logfile> [-TestFlush]
# The log is written when Altirra exits cleanly (close the window and answer Yes), or when -TestFlush is used
# (closes the log at the first vertical blank, for a hands-off check of the mechanism).
# -InfinitePowerPill: test aid. A debugger breakpoint at $AF5F refills the frightened-mode countdown (zp_FD) with $FF every frame,
# so a power pellet never wears off and all four ghosts can be eaten in one go. Only emulated RAM is written; the ROM is untouched.
# Read-only tracing otherwise: nothing here changes the ROM or the project.
param([Parameter(Mandatory)][string]$Log, [switch]$TestFlush, [switch]$InfinitePowerPill)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$alt  = (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra64.exe')
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_trace.batch'
$lines = @(".logopen $Log") + (Get-Content (Join-Path $root 'altirra_trace.cmd') | Where-Object { $_ -notmatch '^\s*(#|$)' })
if ($InfinitePowerPill) { $lines += @('.echo INFINITE_POWER_PILL_ACTIVE', 'bp -n af5f "eb $fd $ff"') }
if ($TestFlush) { $lines += 'bp -n a5fd ".logclose"' }
$lines += @('.restart', 'g')
Set-Content -Path $batch -Value $lines -Encoding ascii
# Altirra treats a quoted token as a FILE name: keep switches unquoted; quote only values/paths with spaces.
$line = '/portable /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
Start-Process -FilePath $alt -ArgumentList $line | Out-Null
