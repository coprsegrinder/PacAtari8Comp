# Stage 59 (API / hardware tracing): the chip side of the game, in the real game (Altirra 4.40), added to session harnesses.
#   HWW a=<address> v=<value> pc=<writer> f=<frame> vp=<scan line>   every CPU write to GTIA ($D000-$D01F), POKEY ($D200-$D20F), ANTIC ($D400-$D40F), by the game ($A000+) and by the OS ($C000+)
#   HWR ...                                                          every read of those chips and of the PIA ($D300-$D303)
#   SETVBV a x y / SETVBV_DONE vvblkd vvblki                         the one OS call of the game and what it leaves in the OS vectors
#   VBI f rtclok sdmctl sdl gprior colors pcolr pokmsk atract drkmsk colrsh chbas chact   the shadows at the entry of the game's deferred vertical-blank handler, then the chips' own state (.antic .gtia .pokey)
#   DLI1 / DLI2 f vp                                                 entries of the two display-list interrupt handlers
# Nothing is written to the emulated machine by the tracing; the harnesses keep their own test aids (docs/04).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_hw_audit.ps1 [-Only fullgame] [-Seconds 40]     then   python -I tools/analyze_hw.py analysis/raw-logs/hw-*.txt --write analysis/evidence-hw-summary.txt
param([string]$Only = '', [int]$Seconds = 40)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'pregame', 'gameover', 'p2win', 'death', 'frightened_cases', 'inputs', 'levels')
$extra = @(
  'bt a386 "SENT f=%d pc=$%04X" @frame pc',
  'bt a460 "SETVBV a=$%02X x=$%02X y=$%02X f=%d" @a x y @frame',
  'bt a463 "SETVBV_DONE vvblkd=$%04X vvblki=$%04X f=%d" dw($0224) dw($0222) @frame',
  'bta w d000 L20 "HWW a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bta w d200 L10 "HWW a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bta w d400 L10 "HWW a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bta r d000 L20 "HWR a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bta r d200 L10 "HWR a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bta r d300 L4 "HWR a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bta r d400 L10 "HWR a=$%04X v=$%02X pc=$%04X f=%d vp=%d" @address @value pc @frame vpos',
  'bt a573 "DLI1 f=%d vp=%d" @frame vpos',
  'bt a5ce "DLI2 f=%d vp=%d" @frame vpos',
  'bt a5fd "VBI f=%d rtclok=%d sdmctl=$%02X sdl=$%04X gprior=$%02X col=%02X,%02X,%02X,%02X,%02X pcol=%02X,%02X,%02X,%02X pokmsk=$%02X atract=%02X drk=%02X colrsh=%02X chbas=%02X chact=%02X" @frame db($14) db($22f) dw($230) db($26f) db($2c4) db($2c5) db($2c6) db($2c7) db($2c8) db($2c0) db($2c1) db($2c2) db($2c3) db($10) db($4d) db($4e) db($4f) db($2f4) db($2f3)',
  'bp -n a5fd ".antic; .gtia; .pokey"'
)
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("hw_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + $extra) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\hw-" + $n + ".txt") -Seconds $Seconds -Cmd ("hw_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
