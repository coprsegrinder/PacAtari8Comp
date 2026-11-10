# Unattended patrol-route test: starts Altirra with tools\altirra_patrol.cmd, presses Start (F2) by itself, runs for -Seconds, then stops it.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_patrol_trace.ps1 -Log <logfile> [-Seconds 300]
# -Ini: a private settings copy (same folder as Altirra.ini) whose 'Speed: Frame rate modifier' is 800 (about 7.5x real time), so the user's own settings stay untouched.
# The log flushes in 4 KB chunks, so the last few lines may be missing after the process is stopped.
param([Parameter(Mandatory)][string]$Log, [int]$Seconds = 300, [string]$Ini = 'F:\Ports\Pac-Man-tools\Altirra\Altirra_fast.ini', [switch]$Complete)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$alt  = 'F:\Ports\Pac-Man-tools\Altirra\Altirra64.exe'
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_patrol.batch'
$lines = @(".logopen $Log") + (Get-Content (Join-Path $root 'altirra_patrol.cmd') | ForEach-Object { if ($Complete -and $_ -match '^#COMPLETE (.*)$') { $Matches[1] } else { $_ } } | Where-Object { $_ -notmatch '^\s*(#|$)' }) + @('.restart', 'g')
Set-Content -Path $batch -Value $lines -Encoding ascii
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Kb { [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
                  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }
"@
$line = '/portablealt:' + $Ini + ' /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
$p = Start-Process -FilePath $alt -ArgumentList $line -PassThru
Start-Sleep 10                                     # boot, copyright screen, menu
[void][Kb]::SetForegroundWindow($p.MainWindowHandle); Start-Sleep 1
[Kb]::keybd_event(0x71, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 300   # F2 = Start (down, hold, up)
[Kb]::keybd_event(0x71, 0, 2, [UIntPtr]::Zero)
Start-Sleep $Seconds
if (-not $p.HasExited) { $p.Kill() }
