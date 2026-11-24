# Stage 58 (state transitions): a write watch on every state variable of the game (docs/34-state-transitions.md: GameState $19, TwoPlayers $1A, IntroRequest $1C, CountdownActive $20, PlayStarted $21, StartTuneActive $22,
# TurnSwitchState $23, WaitState $24, LevelComplete $26, LevelEndStep $27, CurrentPlayer $2B, Paused $9B, BonusVisible $9F, BonusScoreShown $A1, PacFrozen $AA, EatPause $E5, DeathAnimActive $EA, DeathState $ED,
# FrightenPhase $FC and GhostState $CE-$D1), added to session harnesses of the real game (Altirra).  Every write prints   SW <address> v=<value written> pc=<writing instruction> f=<frame>   (a store of the same
# value is printed too: the analyzer tells a change from a rewrite).  Nothing is written to the emulated machine by the tracing; the harnesses keep their own test aids (docs/04).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_state_audit.ps1 [-Only fullgame] [-Seconds 60]     then   python -I tools/analyze_states.py analysis/raw-logs/states-*.txt --write analysis/evidence-states-summary.txt
param([string]$Only = '', [int]$Seconds = 60)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'fullgame2', 'pregame', 'gameover', 'p2win', 'levels', 'pause', 'death', 'extra_life', 'frightened_cases', 'house_frightened', 'catch', 'itemshots', 'inputs', 'inputs1', 'player1_survives', 'player2_lives', 'door_up', 'copyright_key', 'forcechase')
$extra = & python -I (Join-Path $here 'analyze_states.py') --probes
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("states_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + @('bt a386 "SENT f=%d pc=$%04X" @frame pc') + @($extra)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\states-" + $n + ".txt") -Seconds $Seconds -Cmd ("states_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
