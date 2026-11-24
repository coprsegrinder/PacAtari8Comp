# Stage 63 (input processing): the CONTACT TEST of the real game: at the entry of the ghost loop of the frame ($A84D) the two collision registers, the four ghost states and the vertical positions are logged (CT), and the outcome ($A886 a ghost is eaten: CE, $A923 Pac-Man dies: CD, $A87C no contact: CN),
# in session harnesses that have contacts: death, frightened_cases, fullgame, house_frightened, catch, and the two-player stick harness.  Nothing is written to the emulated machine.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_input_audit.ps1 [-Only death] [-Seconds 60]     then   python -I tools/analyze_input.py --contacts analysis/raw-logs/contact-*.txt
param([string]$Only = '', [int]$Seconds = 60, [string[]]$Runs = @('death', 'frightened_cases', 'fullgame', 'house_frightened', 'catch', 'stick2'))
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$extra = @(
  'bt a84d "CT f=%d m1=%d m2=%d s=%d,%d,%d,%d y=%d,%d,%d,%d py=%d" @frame db($d009) db($d00a) db($ce) db($cf) db($d0) db($d1) db($85) db($86) db($87) db($88) db($89)',
  'bt a886 "CE f=%d x=%d" @frame @x',
  'bt a923 "CD f=%d x=%d" @frame @x',
  'bt a87c "CN f=%d" @frame'
)
foreach ($n in $Runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("ia_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + $extra) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\contact-" + $n + ".txt") -Seconds $Seconds -Cmd ("ia_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
