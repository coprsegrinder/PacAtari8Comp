# OV-65: the outcome counters of the key loop ($A4BA-$A572, tools/make_keyloop_cmd.py) in session harnesses of the real game (Altirra); log analysis\raw-logs\keyloop-<harness>.txt, then tools\analyze_keyloop.py.
# Nothing is written to the emulated machine except the counters in RAM at $4300-$44FF (unused by the game); the harnesses keep their own test aids (docs/04).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_keyloop_audit.ps1 [-Only inputs] [-Seconds 60]     then   python -I tools/analyze_keyloop.py analysis/raw-logs/keyloop-*.txt --write analysis/evidence-keyloop-summary.txt
param([string]$Only = '', [string]$Branches = '', [string]$Blocks = '', [int]$Seconds = 60, [string[]]$Runs = @('inputs', 'inputs1', 'rare', 'fullgame', 'gameover', 'pause', 'copyright_key', 'pregame', 'keyloop', 'realkey'))
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
# -Branches a4eb,a4ef: a targeted run (only those branches are counted; the full set makes the emulator slow while the key loop spins): logs keyloop-<harness>-targeted.txt
$gen = @('--out', (Join-Path $here 'keyloop_counters.cmd')); if ($Branches) { $gen += @('--only', $Branches, '--nopass') }
if ($Blocks) { $gen += @('--blocks', $Blocks) }                    # block counters of cold points (a4ed,a4f1: the game-over countdown), logged as KB lines
python -I (Join-Path $here 'make_keyloop_cmd.py') @gen | Out-Null
$extra = Get-Content (Join-Path $here 'keyloop_counters.cmd')
foreach ($n in $Runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("kl_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + @($extra | Where-Object { $_ -notmatch '^\s*#' })) -Encoding ascii
  try {
    $keys = if ($n -eq 'realkey') { @('22:20,32:20') } else { @() }   # the space bar pressed twice from outside the machine (OV-61): the OS sets KEYDEL ($02F1), which the key loop tests at $A4CC
    & (Join-Path $here 'run_patrol_trace.ps1') -Keys $keys -Log ("analysis\raw-logs\keyloop-" + $n + $(if ($Branches -or $Blocks) { '-targeted' } else { '' }) + ".txt") -Seconds $Seconds -Cmd ("kl_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
