# Pac-Man pictures and the death sequence, screenshot check: for each target, run the game in Altirra (private 800 % settings copy) until the picture is on screen, freeze the emulated machine
# (tools\altirra_pacshots.cmd), save screenshots of ALTIRRA'S OWN WINDOW ONLY (PrintWindow: never reads other windows) and the debugger log (RAM dump), then stop Altirra.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_pacman_shots.ps1 -OutDir F:\Ports\pac-shots [-Only name1,name2] [-TimeoutSec 200]
# Output per target: <name>.log, <name>_0.png .. _2.png. The pictures are local evidence only (game images are not committed).
param([Parameter(Mandatory)][string]$OutDir, [string[]]$Only, [int]$TimeoutSec = 200, [string]$Ini = 'F:\Ports\Pac-Man-tools\Altirra\Altirra_fast.ini')
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$alt  = 'F:\Ports\Pac-Man-tools\Altirra\Altirra64.exe'
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f); }
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
# shapes: name, the four words at $0403,$0405,$0407,$0409 (little endian) that identify the staged picture
$shapes = [ordered]@{ Full='7C38,FEFE,FEFE,FEFE'; Right1='7C38,F8FE,E0E0,FEF8'; Right2='7C38,F0F8,E0E0,F8F0'; Left1='7C38,3EFE,0E0E,FE3E'; Left2='7C38,1E3E,0E0E,3E1E'
              Up1='4400,C6C6,EEEE,FEFE'; Up2='0000,C682,EEEE,FEFE'; Down1='7C38,FEFE,EEEE,C6C6'; Down2='7C38,FEFE,EEEE,82C6' }
$targets = @()
foreach ($k in $shapes.Keys) {
  $w = $shapes[$k] -split ','
  $cond = '(dw($403)=${0})&(dw($405)=${1})&(dw($407)=${2})&(dw($409)=${3})&(db($93)>0)' -f $w[0], $w[1], $w[2], $w[3]
  $targets += ,@("Shape_$k", 'shape', $cond)
}
$targets += ,@('Death_freeze', 'death', '(db($ed)=1)&(db($ee)=50)&((db($14)&$0F)=8)')
for ($k = 0; $k -le 15; $k++) { $targets += ,@(('Death_anim{0:D2}' -f $k), 'death', ('(db($ed)>=3)&(db($ea)=1)&(db($eb)={0})&(db($ec)=3)' -f $k)) }
$targets += ,@('Death_end', 'death', '(db($ed)=6)&(db($ea)=0)&(db($24)=0)&(db($f1)=64)')
# after the death (the per-frame routine at $A78C): the get-ready wait (zp_24 = 2, zp_25 counts 64 -> 0) and the first frame after it
$targets += ,@('Ready_wait', 'ready', '(db($24)=2)&(db($25)=30)')
$targets += ,@('Ready_wait_start', 'ready', '(db($24)=2)&(db($25)=50)')
$targets += ,@('Ready_play', 'readylatch', '(db($24)=0)&(db($ce)=1)&(db($ed)=0)&(db($0def)=0)&(db($21)=1)')
if ($Only) { $Only = @($Only | ForEach-Object { $_ -split ',' }); $targets = @($targets | Where-Object { $Only -contains $_[0] }) }
$tpl = Get-Content (Join-Path $root 'altirra_pacshots.cmd') | Where-Object { $_ -notmatch '^\s*(#|$)' }
$bot = 'bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"'
$frz = 'eb 440 $4c; eb 441 $43; eb 442 $04; eb 443 $4c; eb 444 $43; eb 445 $04; r pc ($a82f*(1-@t6))+($440*@t6)'
foreach ($t in @($targets)) {
  $name = $t[0]; $mode = $t[1]; $cond = $t[2]; $log = Join-Path $OutDir "$name.log"
  Remove-Item $log -ErrorAction SilentlyContinue
  if ($mode -eq 'shape') {
    $ml = @('bp -n a504 "r pc $a537; bc 0"', 'bp -n a923 "r pc $a936"', $bot,
            ('bp -n a82f "r @t1 (' + $cond + '); r @t2 (@t2|@t1); eb $aa db($aa)|(@t2*$80)"'),
            ('bp -n a82f "r @t3 (@t3+@t2); r @t6 (@t3>=4); ' + $frz + '"'))
  } elseif ($mode -eq 'readylatch') {
    $ml = @('bp -n a504 "r pc $a537; bc 0"', 'bp -n a923 "eb $2c 3; eb $2d 3"', $bot,
            ('bp -n a78c "r @t1 (' + $cond + '); r @t2 (@t2|@t1)"'),
            ('bp -n a78c "r @t3 (@t3+@t2); r @t6 (@t3>=8); ' + $frz.Replace('$a82f', '$a78c') + '"'))
  } elseif ($mode -eq 'ready') {
    $ml = @('bp -n a504 "r pc $a537; bc 0"', 'bp -n a923 "eb $2c 3; eb $2d 3"', $bot,
            ('bp -n a78c "r @t6 (' + $cond + '); ' + $frz.Replace('$a82f', '$a78c') + '"'))
  } else {
    $ml = @('bp -n a504 "r pc $a537; bc 0"', 'bp -n a923 "eb $2c 3; eb $2d 3"', $bot,
            ('bp -n a82f "r @t6 (' + $cond + '); ' + $frz + '"'))
  }
  $lines = @(".logopen $log") + ($tpl | ForEach-Object { if ($_ -eq '@MODELINES@') { $ml } else { $_.Replace('@MODE@', $mode) } }) + @('.restart', 'g')
  $batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_pacshot.batch'
  Set-Content -Path $batch -Value $lines -Encoding ascii
  $line = '/portablealt:' + $Ini + ' /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
  $p = Start-Process -FilePath $alt -ArgumentList $line -PassThru
  $t0 = Get-Date; $done = $false
  while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Seconds 2
    try { if ((Test-Path $log) -and (Select-String -Path $log -Pattern '^\s*SHOT ' -Quiet -ErrorAction Stop)) { $done = $true; break } } catch { }
  }
  if (-not $done) { Write-Warning "$name : not reached"; if (-not $p.HasExited) { $p.Kill() }; continue }
  Start-Sleep -Seconds 2
  $p.Refresh()
  for ($i = 0; $i -lt 3; $i++) {
    $r = New-Object Win+RECT; [void][Win]::GetClientRect($p.MainWindowHandle, [ref]$r)
    $bmp = New-Object System.Drawing.Bitmap $r.R, $r.B
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
    [void][Win]::PrintWindow($p.MainWindowHandle, $dc, 3)
    $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save((Join-Path $OutDir ('{0}_{1}.png' -f $name, $i)), [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Start-Sleep -Milliseconds 400
  }
  if (-not $p.HasExited) { $p.Kill() }
  Write-Host "$name : captured"
}
