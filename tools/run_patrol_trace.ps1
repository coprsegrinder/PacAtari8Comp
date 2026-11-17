# Unattended test harness (patrol routes by default; -Cmd altirra_levels.cmd for the level sweep): starts Altirra with tools\altirra_patrol.cmd, presses Start (F2) by itself, runs for -Seconds, then stops it.
# -Video ntsc|pal and -Kernel hle select the video standard and Altirra's built-in OS (OV-42).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_patrol_trace.ps1 -Log <logfile> [-Seconds 300]
# -Drop <regex>: command lines matching it are left out (used to drop an injected input and press the key for real with -PressStart $true).
# -Ini: a private settings copy (same folder as Altirra.ini) whose 'Speed: Frame rate modifier' is 800 (about 7.5x real time), so the user's own settings stay untouched.
# The log flushes in 4 KB chunks, so the last few lines may be missing after the process is stopped.
param([Parameter(Mandatory)][string]$Log, [int]$Seconds = 300, [string]$Ini = '', [switch]$Complete, [string]$Cmd = 'altirra_patrol.cmd', [bool]$PressStart = $false, [string]$Drop = '', [string]$Video = 'ntsc', [string]$Kernel = '', [string[]]$Keys = @())
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# Logs live in analysis\raw-logs (gitignored); relative paths resolve against the project root, and the folder is created if missing.
$Log = if ([IO.Path]::IsPathRooted($Log)) { $Log } else { Join-Path (Split-Path -Parent $root) $Log }
[void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log))
if (-not $Ini) { $Ini = Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra_fast.ini' }
$alt  = (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra64.exe')
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_patrol.batch'
$lines = @(".logopen `"$Log`"") + (Get-Content (Join-Path $root $Cmd) | ForEach-Object { if ($Complete -and $_ -match '^#COMPLETE (.*)$') { $Matches[1] } else { $_ } } | Where-Object { $_ -notmatch '^\s*(#|$)' -and ($Drop -eq '' -or $_ -notmatch $Drop) }) + @('.restart', 'g')
Set-Content -Path $batch -Value $lines -Encoding ascii
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Kb { [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
                  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
                  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
                  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
                  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
                  public delegate bool EnumProc(IntPtr h, IntPtr l);
                  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr l);
                  [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetClassName(IntPtr h, System.Text.StringBuilder s, int n);
                  public static System.Collections.Generic.List<IntPtr> Children(IntPtr parent) { var r = new System.Collections.Generic.List<IntPtr>(); EnumChildWindows(parent, (h, l) => { r.Add(h); return true; }, IntPtr.Zero); return r; }
                  public static string Cls(IntPtr h) { var sb = new System.Text.StringBuilder(128); GetClassName(h, sb, 128); return sb.ToString(); } }
"@
$line = '/portablealt:"' + $Ini + '" /hardware:800 /' + $Video + ' ' + $(if ($Kernel) { '/kernel:' + $Kernel + ' ' } else { '' }) + '/nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
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
# -Keys 'T:VK', ...  a REAL key press (WM_KEYDOWN / WM_KEYUP posted to Altirra's window, 60 ms apart (at 7.5 times real time that is about 0.5 s of game time, less than the OS key-repeat delay)) T seconds after the boot wait, VK the Windows virtual-key code in hex (20 = space bar); the keyboard then reaches the game through Altirra's POKEY (OV-61).
$t0 = Get-Date
$ev = @(($Keys -split ",") | ForEach-Object { $a = $_ -split ':'; [pscustomobject]@{ T = [double]$a[0]; VK = [Convert]::ToInt32($a[1], 16) } } | Sort-Object T)
foreach ($k in $ev) {
  $wait = $k.T - ((Get-Date) - $t0).TotalSeconds
  if ($wait -gt 0) { Start-Sleep -Milliseconds ([int]($wait * 1000)) }
  $sc = [int64]([Kb]::MapVirtualKey([uint32]$k.VK, 0))
  $targets = @($p.MainWindowHandle) + @([Kb]::Children($p.MainWindowHandle))      # the frame and its child windows (the display): all belong to the Altirra process
  if ($k -eq $ev[0]) { Write-Host ("key targets: " + (($targets | ForEach-Object { [Kb]::Cls($_) }) -join ', ')) }
  foreach ($h in $targets) { [void][Kb]::PostMessage($h, 0x0100, [IntPtr]$k.VK, [IntPtr]::new(1L + ($sc -shl 16))) }
  Start-Sleep -Milliseconds 60
  foreach ($h in $targets) { [void][Kb]::PostMessage($h, 0x0101, [IntPtr]$k.VK, [IntPtr]::new(0xC0000001L + ($sc -shl 16))) }
}
$rest = $Seconds - ((Get-Date) - $t0).TotalSeconds
if ($rest -gt 0) { Start-Sleep -Milliseconds ([int]($rest * 1000)) }
if (-not $p.HasExited) { $p.Kill() }
