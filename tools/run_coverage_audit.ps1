# Stages 53 / 54 (execution trace collection, breakpoints): which instructions of the ROM does the real game execute?  Altirra, the session harnesses of the project, one self-clearing breakpoint on EVERY instruction of the ROM.
# For each harness a temporary copy is made: the harness lines, then one line per instruction (`python -I tools/analyze_coverage.py --instructions` lists the addresses):
#     bp -n <addr> ".echo C <ADDR>; bc <number of this breakpoint>"
# The breakpoint prints its address the first time the instruction executes and removes itself, so the run slows down only at first and the log has one line per instruction reached ("first-hit coverage").
# The number of a breakpoint is the order of its definition (the harness's own bp / bt / bta lines come first and are counted).  Nothing is written to emulated RAM by these lines; the harness's own test aids apply as in its own header.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_coverage_audit.ps1 [-Only fullgame] [-Seconds 90]     then   python -I tools/analyze_coverage.py analysis/raw-logs/coverage-*.txt
param([string]$Only = '', [int]$Seconds = 90)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'fullgame2', 'frightened_cases', 'death', 'extra_life', 'p2win', 'levels', 'itemshots', 'catch', 'house_frightened', 'eaten_dir', 'door_up',
          'gameover', 'pregame', 'player2', 'humanplay', 'sound_bot', 'tunnel_bot', 'patrol', 'start_state_test', 'speed', 'sight',
          'tunnel_clip', 'steering', 'transitions', 'reversedir', 'afterdeath', 'extra_life2', 'player2_lives', 'titleicons', 'sight_states', 'pause', 'player1_survives', 'two_keys', 'ov59_row6', 'ov59_tunnel')
$addrs = & python -I (Join-Path $here 'analyze_coverage.py') --instructions
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("coverage_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  $count = ($body | Where-Object { $_ -match '^\s*(bp|bt|bta|ba)\s' }).Count
  $lines = @('bt a386 "SENT f=%d pc=$%04X" @frame pc')
  $count += 1
  foreach ($a in $addrs) {
    $lines += ('bp -n ' + $a + ' ".echo C ' + $a.ToUpper() + '; bc ' + $count + '"')
    $count += 1
  }
  Set-Content -Path $tmp -Value (@($body) + @($lines)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\coverage-" + $n + ".txt") -Seconds $Seconds -Cmd ("coverage_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
