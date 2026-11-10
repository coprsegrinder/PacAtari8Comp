# Unattended test harness (patrol routes by default; -Cmd altirra_levels.cmd for the level sweep): starts Altirra with tools\altirra_patrol.cmd, presses Start (F2) by itself, runs for -Seconds, then stops it.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_patrol_trace.ps1 -Log <logfile> [-Seconds 300]
# -Ini: a private settings copy (same folder as Altirra.ini) whose 'Speed: Frame rate modifier' is 800 (about 7.5x real time), so the user's own settings stay untouched.
# The log flushes in 4 KB chunks, so the last few lines may be missing after the process is stopped.
param([Parameter(Mandatory)][string]$Log, [int]$Seconds = 300, [string]$Ini = 'F:\Ports\Pac-Man-tools\Altirra\Altirra_fast.ini', [switch]$Complete, [string]$Cmd = 'altirra_patrol.cmd', [bool]$PressStart = $false)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$alt  = 'F:\Ports\Pac-Man-tools\Altirra\Altirra64.exe'
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_patrol.batch'
$lines = @(".logopen $Log") + (Get-Content (Join-Path $root $Cmd) | ForEach-Object { if ($Complete -and $_ -match '^#COMPLETE (.*)$') { $Matches[1] } else { $_ } } | Where-Object { $_ -notmatch '^\s*(#|$)' }) + @('.restart', 'g')
Set-Content -Path $batch -Value $lines -Encoding ascii
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Kb { [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
                  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
                  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
                  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l); }
"@
$line = '/portablealt:' + $Ini + ' /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
$p = Start-Process -FilePath $alt -ArgumentList $line -PassThru
Start-Sleep 10                                     # boot, copyright screen, menu
# Start the game by posting F2 (Start) straight to Altirra's own window: no focus needed, and no other program can receive it.
# (A debugger-side start via a breakpoint on the main loop's CONSOL poll was tried and rejected: that loop runs thousands of times per frame.)
# Off by default: the command files start the game themselves (self-clearing breakpoint at $A504). -PressStart $true tries the window message.
if ($PressStart) {
  [void][Kb]::PostMessage($p.MainWindowHandle, 0x0100, [IntPtr]0x71, [IntPtr]::new(0x003C0001L))   # WM_KEYDOWN, VK_F2
  Start-Sleep -Milliseconds 300
  [void][Kb]::PostMessage($p.MainWindowHandle, 0x0101, [IntPtr]0x71, [IntPtr]::new(0xC03C0001L))   # WM_KEYUP
}
Start-Sleep $Seconds
if (-not $p.HasExited) { $p.Kill() }
