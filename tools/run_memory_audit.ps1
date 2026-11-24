# Stage 55 (runtime memory inspection): snapshots of the RAM ($0000-$9FFF) at events of the real game (Altirra), to find every byte that changes and to check the variable catalogue (docs/25) against it.
# For each harness a temporary copy is made (the harness lines, then) one self-clearing breakpoint per event:
#     bp -n <addr> ".echo SNAP <NAME>; db 0 LA000; bc <number>"
# The first execution of the instruction prints the marker and the hex dump of $0000-$9FFF (the hardware registers at $D000 are never read) and removes the breakpoint.  The events: the clear after a restart ($A481), the end of InitBoard
# ($ADF0), the first score addition ($B423), a power pellet ($B3DE), a ghost eaten ($A886), the first frame of the death ($AE3D), the end of the frightened time ($AFA5), the bonus item appearing ($B677) and eaten ($A95A),
# the level-complete routine ($AC75), the turn handling ($AA2D), the game-over countdown ($AB26 CompareHighScore).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_memory_audit.ps1 [-Only levels] [-Seconds 70]     then   python -I tools/analyze_memory.py analysis/raw-logs/memory-*.txt
param([string]$Only = '', [int]$Seconds = 70)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame2', 'levels', 'p2win', 'itemshots', 'gameover')
$events = @(@('RESTART', 'a481'), @('BOARD', 'adf0'), @('DOT', 'b423'), @('PELLET', 'b3de'), @('EATEN', 'a886'), @('DEATH', 'ae3d'), @('FRIGHT_END', 'afa5'),
            @('BONUS_ON', 'b677'), @('BONUS_EATEN', 'a95a'), @('LEVEL_COMPLETE', 'ac75'), @('TURN', 'aa2d'), @('GAME_OVER', 'ab26'))
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("memory_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  $count = ($body | Where-Object { $_ -match '^\s*(bp|bt|bta|ba)\s' }).Count
  $lines = @('bt a386 "SENT f=%d pc=$%04X" @frame pc')
  $count += 1
  foreach ($e in $events) {
    $lines += ('bp -n ' + $e[1] + ' ".echo SNAP ' + $e[0] + '; db 0 LA000; bc ' + $count + '"')
    $count += 1
  }
  Set-Content -Path $tmp -Value (@($body) + @($lines)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\memory-" + $n + ".txt") -Seconds $Seconds -Cmd ("memory_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
