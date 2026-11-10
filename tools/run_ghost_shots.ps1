# Step C11 (ghost frames, screenshot check): for each ghost picture, run the game in Altirra (private 800 % settings copy) until that picture is on screen,
# freeze the emulated machine there (tools\altirra_ghostshots.cmd), save screenshots of ALTIRRA'S OWN WINDOW ONLY (PrintWindow: never reads other windows)
# and the debugger log (GTIA registers, the ghost's player memory), then stop Altirra.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_ghost_shots.ps1 -OutDir F:\Ports\ghost-shots [-Only name1,name2] [-TimeoutSec 240]
# Output per picture: <name>.log, <name>_0.png .. _2.png. The pictures are local evidence only (game images are not committed).
param([Parameter(Mandatory)][string]$OutDir, [string[]]$Only, [int]$TimeoutSec = 240, [string]$CondOverride, [switch]$Diag, [string]$Ini = 'F:\Ports\Pac-Man-tools\Altirra\Altirra_fast.ini')
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$alt  = 'F:\Ports\Pac-Man-tools\Altirra\Altirra64.exe'
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f); }
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
# name, shape address, feet byte, optional colour register value
$S = @{ Up = 0xBAC0; Down = 0xBACA; Left = 0xBAD4; Right = 0xBADE; Frightened = 0xBAE8; Eyes = 0xBAF2 }
$targets = @()
foreach ($d in 'Up', 'Down', 'Left', 'Right') { foreach ($f in 0x54, 0xAA) { $targets += ,@(('{0}_{1:X2}' -f $d, $f), $S[$d], $f, $null) } }
foreach ($f in 0x54, 0xAA) { foreach ($c in 0x84, 0x0C) { $targets += ,@(('Frightened_{0:X2}_c{1:X2}' -f $f, $c), $S.Frightened, $f, $c) } }
$targets += ,@('Eyes', $S.Eyes, 0, $null)
$targets += ,@('Eyes_c0C', $S.Eyes, 0, 0x0C)      # the eaten ghost's eyes while its colour register is $0C (the name 'Eyes' may be caught after the colour was restored)
if ($Only) { $targets = @($targets | Where-Object { $Only -contains $_[0] }) }
$base = Get-Content (Join-Path $root 'altirra_ghostframes.cmd') | Where-Object { $_ -notmatch '^\s*(#|$|bt )' }
$tpl  = Get-Content (Join-Path $root 'altirra_ghostshots.cmd') | Where-Object { $_ -notmatch '^\s*(#|$)' }
foreach ($t in @($targets)) {
  $name = $t[0]; $log = Join-Path $OutDir "$name.log"
  Remove-Item $log -ErrorAction SilentlyContinue
  $cond = '(dw($3c)=${0})&(db($41c)=${1})' -f ('{0:X4}' -f $t[1]), ('{0:X2}' -f $t[2])
  if ($null -ne $t[3]) { $cond += '&(db($2c0+x)=${0})' -f ('{0:X2}' -f $t[3]) }
  $cond = '(' + $cond + ')'
  if ($CondOverride) { $cond = $CondOverride }
  $lines = @(".logopen $log") + $base + ($tpl | ForEach-Object { $_.Replace('@COND@', $cond) }) + @('.restart', 'g')
  $batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_ghostshot.batch'
  Set-Content -Path $batch -Value $lines -Encoding ascii
  $line = '/portablealt:' + $Ini + ' /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
  $p = Start-Process -FilePath $alt -ArgumentList $line -PassThru
  $t0 = Get-Date; $done = $false
  while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Seconds 2
    try { if ((Test-Path $log) -and (Select-String -Path $log -Pattern '^\s*SHOT ' -Quiet -ErrorAction Stop)) { $done = $true; break } } catch { }
  }
  if (-not $done) { Write-Warning "$name : picture not reached"; if (-not $Diag) { if (-not $p.HasExited) { $p.Kill() }; continue } }
  Start-Sleep -Seconds 2
  $p.Refresh()
  # Only Altirra's own window is read (PrintWindow renders that window's content, never other windows on the screen).
  for ($i = 0; $i -lt 3; $i++) {
    $r = New-Object Win+RECT; [void][Win]::GetClientRect($p.MainWindowHandle, [ref]$r)
    $bmp = New-Object System.Drawing.Bitmap $r.R, $r.B
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
    [void][Win]::PrintWindow($p.MainWindowHandle, $dc, 3)   # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save((Join-Path $OutDir ('{0}_{1}.png' -f $name, $i)), [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Start-Sleep -Milliseconds 400
  }
  if (-not $p.HasExited) { $p.Kill() }
  Write-Host "$name : captured"
}
