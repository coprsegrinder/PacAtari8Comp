# Records Altirra's real audio output of the game start tune to a WAV file, unattended and without taking the keyboard focus (docs/21).
# Altirra has no command line or debugger command for recording, so this script sends the menu commands "Record > Record Audio..." (ID 40200) and "Stop Recording" (ID 40204)
# straight to Altirra's own window with PostMessage, and fills in the file dialog through Windows UI Automation (works on a window that does not have the focus).
# The game is started by the debugger script tools\altirra_tune_record.cmd (ONE START press injected at the CONSOL read, title frame 1500, i.e. after the recording has begun).
# Then:  python -I tools\analyze_tune_wav.py analysis\start-tune-recorded.wav
# -Video ntsc|pal and -Kernel <name or path of a ROM file> (e.g. hle) select the video standard and the OS for OV-42 (default: NTSC and the OS-B ROM of Altirra.ini).
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File tools\record_tune.ps1 [-Out analysis\start-tune-recorded.wav] [-Seconds 50] [-Cmd altirra_tune_record.cmd] [-Trace analysis\raw-logs\tune-record.txt]
param([string]$Out = 'analysis\start-tune-recorded.wav', [int]$Seconds = 50, [string]$Ini = '', [string]$Cmd = 'altirra_tune_record.cmd', [string]$Trace = 'analysis\raw-logs\tune-record.txt', [string]$Video = 'ntsc', [string]$Kernel = '')
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Rec { [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll", EntryPoint="SendMessageW", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageS(IntPtr h, uint msg, IntPtr w, string l);
  [DllImport("user32.dll", EntryPoint="SendMessageW", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageB(IntPtr h, uint msg, IntPtr w, System.Text.StringBuilder l); }
"@
$proj = Split-Path -Parent $PSScriptRoot
# Altirra pauses the emulation whenever its window is not the active one ("Pause when inactive" = 1 in Altirra.ini), which silently truncates a recording as soon as another window
# (a terminal, the user's other programs) takes the focus.  Recordings therefore use a private copy of the settings with that option off; it is created on first use.
$recIni = Join-Path $proj 'external-tools\Altirra\Altirra_record.ini'
if (-not (Test-Path $recIni)) {
  (Get-Content (Join-Path $proj 'external-tools\Altirra\Altirra.ini')) -replace '("Pause when inactive" = )1', '${1}0' | Set-Content -Path $recIni -Encoding ascii
}
if (-not $Ini) { $Ini = $recIni }
$Out = if ([IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $proj $Out }
$log = if ([IO.Path]::IsPathRooted($Trace)) { $Trace } else { Join-Path $proj $Trace }
[void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log))
if (Test-Path $Out) { Remove-Item $Out -Force }
$cmdLines = Get-Content (Join-Path $PSScriptRoot $Cmd) | Where-Object { $_ -notmatch '^\s*(#|$)' }
$batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_tune_record.batch'
Set-Content -Path $batch -Value (@(".logopen `"$log`"") + $cmdLines + @('.restart', 'g')) -Encoding ascii
$cart = Join-Path $proj 'original\Pac-Man.rom'
$args1 = '/portablealt:"' + $Ini + '" /hardware:800 /' + $Video + ' ' + $(if ($Kernel) { if ($Kernel -match '[\\/]') { '/kernel:"' + $Kernel + '" ' } else { '/kernel:' + $Kernel + ' ' } } else { '' }) + '/nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
$p = Start-Process -FilePath (Join-Path $proj 'external-tools\Altirra\Altirra64.exe') -ArgumentList $args1 -PassThru
Start-Sleep 6
$p.Refresh(); $h = $p.MainWindowHandle
[void][Rec]::PostMessage($h, 0x111, [IntPtr]40200, [IntPtr]::Zero)       # WM_COMMAND: Record Audio...
$dlg = $null
for ($i = 0; $i -lt 40 -and -not $dlg; $i++) {
  Start-Sleep -Milliseconds 250
  # an owned dialog is listed under its owner window, not under the desktop
  $dlg = [Windows.Automation.AutomationElement]::FromHandle($h).FindAll('Children', [Windows.Automation.Condition]::TrueCondition) |
         Where-Object { $_.Current.ClassName -eq '#32770' } | Select-Object -First 1
}
if (-not $dlg) { $p.Kill(); throw 'the file dialog of Record Audio did not appear' }
# The common dialog's "File name:" box and Save button are plain Win32 controls without UI Automation patterns: find them by their control ids (1001, 1) and use window messages.
$all = $dlg.FindAll('Descendants', [Windows.Automation.Condition]::TrueCondition)
$edit = $all | Where-Object { $_.Current.ClassName -eq 'Edit' -and $_.Current.AutomationId -eq '1001' -and $_.Current.NativeWindowHandle -ne 0 } | Select-Object -First 1
$save = $all | Where-Object { $_.Current.ClassName -eq 'Button' -and $_.Current.AutomationId -eq '1' -and $_.Current.NativeWindowHandle -ne 0 } | Select-Object -First 1
if (-not $edit -or -not $save) { $p.Kill(); throw 'the File name box or the Save button of the dialog was not found' }
$eh = [IntPtr]$edit.Current.NativeWindowHandle
[void][Rec]::SendMessageS($eh, 0x0C, [IntPtr]::Zero, $Out)                # WM_SETTEXT
$sb = New-Object System.Text.StringBuilder 520
[void][Rec]::SendMessageB($eh, 0x0D, [IntPtr]520, $sb)                    # WM_GETTEXT: read it back
if ($sb.ToString() -ne $Out) { $p.Kill(); throw "the file name box holds '$($sb.ToString())' instead of '$Out'" }
[void][Rec]::PostMessage([IntPtr]$save.Current.NativeWindowHandle, 0xF5, [IntPtr]::Zero, [IntPtr]::Zero)   # BM_CLICK on Save
Start-Sleep 2
Write-Host "recording started at $(Get-Date -Format T); waiting $Seconds s for the game start and the tune"
Start-Sleep $Seconds
[void][Rec]::PostMessage($h, 0x111, [IntPtr]40204, [IntPtr]::Zero)       # WM_COMMAND: Stop Recording
Start-Sleep 2
[void]$p.CloseMainWindow(); Start-Sleep 2
if (-not $p.HasExited) { $p.Kill() }
if (Test-Path $Out) { "{0}: {1:N0} bytes" -f $Out, (Get-Item $Out).Length } else { throw 'no recording file was written' }
