# Bottom-row items, bonus items and the ghost-eaten pop-up, screenshot check (OPEN-VERIFICATION.md OV-32): for each target run the game in Altirra (private 800 % settings copy) until the state is on screen, freeze the emulated machine
# (tools\altirra_itemshots.cmd), save screenshots of ALTIRRA'S OWN WINDOW ONLY (PrintWindow) and the debugger log (RAM dump), then stop Altirra.  Same method as run_pacman_shots.ps1.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_item_shots.ps1 -OutDir analysis\shots\item-shots [-Only name1,name2] [-TimeoutSec 200]
# Targets: Item_L<n> (bonus item and level indicator of level n: StartLevel $1B is set at the new game, so the game itself starts at level n, the dot counter to $50 so that the item appears), Lives_<k> (after k deaths, no aids except the bot's pseudo-random STICK0),
# Popup_<k> (the k-th ghost eaten in a row: pellet, all ghosts put on Pac-Man; shown 4 frames after the eating),
# Title_<1P|2P> and Game2P_<cp0|cp1>_<shown|blank> (OV-53: the title screen before / after SELECT and the two-player game with the 1UP / 2UP label shown or blank; input only through CONSOL, the bot's STICK0 pattern),
# Overlap_<A|B> (OV-52: the four ghosts put side by side in the ghost house, 4 pixels apart and overlapping: A = ghost 0 leftmost, B = ghost 3 leftmost).
param([Parameter(Mandatory)][string]$OutDir, [string[]]$Only, [int]$TimeoutSec = 200, [string]$Ini = '', [string]$Cmd = 'altirra_itemshots.cmd', [string]$FreezeAt = '')
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Ini) { $Ini = Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra_fast.ini' }
$alt  = (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra64.exe')
$cart = (Resolve-Path (Join-Path $root '..\original\Pac-Man.rom')).Path
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f); }
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
$bot = 'bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"'
$frz = 'eb 440 $4c; eb 441 $43; eb 442 $04; eb 443 $4c; eb 444 $43; eb 445 $04; r pc ($a82f*(1-@t6))+($440*@t6)'
# -FreezeAt a5fd (stage 80b): freeze at the entry of the NEXT frame handler instead of inside the frame of the state: then the window shows the frame whose RAM and chip writes are logged
# the frozen machine keeps running its video frames: at every entry of the frame handler the program counter goes to a stub that clears BandCounter ($18) and spins (440: LDA #0; STA $18; 444: JMP 444), the stack
# pointer is reset, and after 90 such frames (at 800 % speed the window presents only some of the emulated frames: the last presented one must be one of the frozen frames) the pc goes to the halt loop at $450 (the cmd file has its final breakpoint there): the window then shows the frame of the logged RAM and chip writes, three times over
if ($FreezeAt) { $frz = 'eb 440 $a9; eb 441 0; eb 442 $85; eb 443 $18; eb 444 $4c; eb 445 $44; eb 446 4; eb 450 $4c; eb 451 $50; eb 452 4; eb 510 0' }
$targets = @()
foreach ($n in (0..20 + 25 + 30)) { $targets += ,@("Item_L$n", 'item', $n) }
foreach ($k in 0..2) { $targets += ,@("Lives_$k", 'lives', $k) }
foreach ($k in 0..3) { $targets += ,@("Popup_$k", 'popup', $k) }
foreach ($k in '1P','2P') { $targets += ,@("Title_$k", 'title', $k) }
foreach ($c in 'cp0','cp1') { foreach ($l in 'shown','blank') { $targets += ,@("Game2P_${c}_$l", 'game2p', "$c,$l") } }
foreach ($k in 'A','B') { $targets += ,@("Overlap_$k", 'overlap', $k) }
if ($Only) { $Only = @($Only | ForEach-Object { $_ -split ',' }); $targets = @($targets | Where-Object { $Only -contains $_[0] }) }
$tpl = Get-Content (Join-Path $root $Cmd) | Where-Object { $_ -notmatch '^\s*(#|$)' }
foreach ($t in @($targets)) {
  $name = $t[0]; $mode = $t[1]; $arg = $t[2]; $log = Join-Path $OutDir "$name.log"
  Remove-Item $log -ErrorAction SilentlyContinue
  if ($mode -eq 'item') {
    $hx = '$' + ('{0:X2}' -f $arg)          # the debugger reads a bare number as hexadecimal: always pass a $-prefixed hex value
    $cond = '(db($9f)=1)&(db($df3)>0)&(db($30)=' + $hx + ')'
    $ml = @(('bp -n a504 "eb $1b ' + $hx + '; r pc $a537; bc 3"'), 'bp -n a923 "r pc $a936"', $bot,
            'bp -n a800 "r @t0 @frame"',
            'bp -n a82f "r @t4 (@frame-@t0); eb $34 (((@t4>=40)&(@t4<48))*$50)+(1-((@t4>=40)&(@t4<48)))*db($34); eb $35 (((@t4>=40)&(@t4<48))*$50)+(1-((@t4>=40)&(@t4<48)))*db($35)"',
            ('bp -n a82f "r @t1 (' + $cond + '); r @t2 (@t2|@t1)"'),
            ('bp -n a82f "r @t3 (@t3+@t2); r @t6 (@t3>=4); ' + $frz + '"'))
  } elseif ($mode -eq 'lives') {
    $cond = '(db($24)=0)&(db($ce)=1)&(db($ed)=0)&(db($21)=1)&(@t4=' + $arg + ')'
    $ml = @('bp -n a504 "r pc $a537; bc 3"', 'bp -n a923 "r @t4 (@t4+1)"', $bot,
            ('bp -n a78c "r @t1 (' + $cond + '); r @t2 (@t2|@t1)"'),
            ('bp -n a78c "r @t3 (@t3+@t2); r @t6 (@t3>=8); ' + $frz.Replace('$a82f', '$a78c') + '"'))
  } elseif ($mode -eq 'title' -or $mode -eq 'game2p') {
    # the real title: nothing is skipped; SELECT at title frame 150 (two players), START at 300 for the game
    $two = if ($mode -eq 'game2p' -or $arg -eq '2P') { 1 } else { 0 }
    $key = 'bp -n a5fd "r @t5 ((' + $two + '=1)&(@t4>=150)&(@t4<=158))*2+(' + $(if ($mode -eq 'game2p') { '1' } else { '0' }) + '=1)*((@t4>=300)&(@t4<=350))*1"'
    $common = @('r @t4 0', 'r @t5 0', 'bp -n a5fd "r @t4 (db($19)>=3)*(@t4+1)"', $key, 'bp -n a507 "r a 7-@t5"', 'bp -n a514 "r a 7-@t5"', 'bp -n a51c "r a 6+(@t5>0)"', 'bp -n a4fa "eb $284 1"', 'bp -n a4ff "eb $285 1"')
    if ($mode -eq 'title') {
      $cond = '(db($19)=3)&(db($1a)=' + $two + ')&(@t4>=' + $(if ($two) { 260 } else { 120 }) + ')'
      $ml = $common + @(('bp -n a78b "r @t1 (' + $cond + '); r @t2 (@t2|@t1)"'), ('bp -n a78b "r @t3 (@t3+@t2); r @t6 (@t3>=4); ' + $frz.Replace('$a82f', '$a78b') + '"'))
    } else {
      $parts = $arg -split ','; $cp = if ($parts[0] -eq 'cp1') { 1 } else { 0 }
      $addr = if ($cp -eq 0) { '$2004' } else { '$2021' }
      $lab = '0'; if ($parts[1] -eq 'shown') { if ($cp -eq 0) { $lab = '$11' } else { $lab = '$12' } }
      $cond = '(db($19)=0)&(db($1a)=1)&(db($2b)=' + $cp + ')&(db(' + $addr + ')=' + $lab + ')'
      $stick = 'bp -n a82f "r @t8 ((@frame/$30)%4); eb $278 ($0E*(@t8=0))+($07*(@t8=1))+($0D*(@t8=2))+($0B*(@t8=3))"'
      $ml = $common + @($stick, ('bp -n a82f "r @t1 (' + $cond + '); r @t2 (@t2|@t1)"'), ('bp -n a82f "r @t3 (@t3+@t2); r @t6 (@t3>=4); ' + $frz + '"'))
    }
  } elseif ($mode -eq 'overlap') {
    $xs = if ($arg -eq 'A') { @(112, 116, 120, 124) } else { @(124, 120, 116, 112) }
    $pk = @()
    for ($g = 0; $g -lt 4; $g++) { $pk += ('eb ${0:X2} ${1:X2}; eb ${2:X2} $76' -f (0x8A + $g), $xs[$g], (0x85 + $g)) }
    $ml = @('bp -n a504 "r pc $a537; bc 3"', 'bp -n a923 "r pc $a936"', $bot, 'bp -n a800 "r @t0 @frame"',
            ('bp -n a82f "r @t4 (@frame-@t0); r @t7 (@t4>=100); ' + ($pk -join '; ') + '"'),
            'bp -n a82f "r @t1 (@t7); r @t2 (@t2|@t1)"',
            ('bp -n a82f "r @t3 (@t3+@t2); r @t6 (@t3>=6); ' + $frz + '"'))
  } else {
    $cond = '(db($e5)>0)&(db($e9)=' + $arg + ')'
    $ml = @('bp -n a504 "r pc $a537; bc 3"', 'bp -n a923 "r pc $a936"', $bot,
            'bp -n a800 "r @t0 @frame"',
            'bp -n a82f "r @t4 (@frame-@t0); r @t7 ((@t4>=60)&(@t4<76)); eb $32 (@t7*$0F)+(1-@t7)*db($32); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89))"',
            'bp -n a82f "r @t8 ((@t4>=120)&(@t4<500))"',
            'bp -n a82f "r @t9 (@t8*(1-((db($ce)&$40)>0))); eb $85 (@t9*db($89))+(1-@t9)*db($85); eb $8a (@t9*db($8e))+(1-@t9)*db($8a)"',
            'bp -n a82f "r @t9 (@t8*(1-((db($cf)&$40)>0))); eb $86 (@t9*db($89))+(1-@t9)*db($86); eb $8b (@t9*db($8e))+(1-@t9)*db($8b)"',
            'bp -n a82f "r @t9 (@t8*(1-((db($d0)&$40)>0))); eb $87 (@t9*db($89))+(1-@t9)*db($87); eb $8c (@t9*db($8e))+(1-@t9)*db($8c)"',
            'bp -n a82f "r @t9 (@t8*(1-((db($d1)&$40)>0))); eb $88 (@t9*db($89))+(1-@t9)*db($88); eb $8d (@t9*db($8e))+(1-@t9)*db($8d)"',
            ('bp -n a82f "r @t1 (' + $cond + '); r @t2 (@t2|@t1)"'),
            ('bp -n a82f "r @t3 (@t3+@t2); r @t6 (@t3>=4); ' + $frz + '"'))
  }
  $extra = @(); if ($FreezeAt) { $extra = @(('bp -n ' + $FreezeAt + ' "eb 510 db(510)+@t6; r s (s*(1-@t6))+($ff*@t6); r pc ($' + $FreezeAt + '*(1-@t6))+($440*@t6)"'), 'bp -n 444 "r pc ($444*(db(510)<90))+($450*(db(510)>=90))"') }
  $lines = @(".logopen $log") + ($tpl | ForEach-Object { if ($_ -eq '@MODELINES@') { $ml + $extra } else { $_.Replace('@MODE@', $mode) } }) + @('.restart', 'g')
  $batch = Join-Path ([IO.Path]::GetTempPath()) 'pacman_itemshot.batch'
  Set-Content -Path $batch -Value $lines -Encoding ascii
  $line = '/portablealt:"' + $Ini + '" /hardware:800 /ntsc /nofastboot /cartmapper:1 /debug /debugcmd:".batch ' + $batch + '" "' + $cart + '"'
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
