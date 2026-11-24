# OV-68: the collision registers of the real game IN PLAY, against the model of tools/gtia_collisions.py: at the entry of the deferred vertical-blank handler ($A5FD) of every frame the scene that was on the screen
# in the frame before (the debugger's dump of the GTIA positions, the player-missile pages $2300-$27FF, the maze screen $0C00-$0F97) and the collision registers the game is about to read ($D000-$D00F) are logged, in
# session harnesses that have contacts (death, catch, frightened_cases).  Nothing is written to the emulated machine.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_collide_play_audit.ps1 [-Only death] [-Seconds 24]     then   python -I tools/analyze_collide.py --play analysis/raw-logs/collideplay-*.txt
param([string]$Only = '', [int]$Seconds = 28, [string[]]$Runs = @('death', 'catch', 'frightened_cases'))
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$extra = @(
  'bt a5fd "FR f=%d vp=%d" @frame vpos',
  'bp -n a5fd ".gtia; db $d000 L10; db $2300 L$500; db $0c00 L$398; db $85 L5; db $8a L5; db $ed L1"',
  'bt a60d "HE f=%d vp=%d" @frame vpos',
  'bt a98c "HC site=A98C f=%d vp=%d" @frame vpos',
  'bt aded "HC site=ADED f=%d vp=%d" @frame vpos',
  'bt b0ad "HC site=B0AD f=%d vp=%d" @frame vpos'
)
foreach ($n in $Runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("cp_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + $extra) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\collideplay-" + $n + ".txt") -Seconds $Seconds -Cmd ("cp_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
