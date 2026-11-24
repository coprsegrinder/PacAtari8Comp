# Stage 57 (input / output observation): a tracepoint on every instruction of the ROM that reads or writes a hardware register, an OS page-2 shadow or vector, or an OS zero-page variable (133 instructions,
# tools/analyze_io.py --probes), added to nine session harnesses; each execution prints  IO <pc> a=<effective address> v=<value read or the register stored>.  Nothing is written to the emulated machine by the tracing
# (the harnesses keep their own test aids, docs/04).  The sentinel line absorbs Altirra's late first tracepoint (OV-56).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_io_audit.ps1 [-Only fullgame] [-Seconds 60]     then   python -I tools/analyze_io.py analysis/raw-logs/io-*.txt --write analysis/evidence-io-summary.txt
param([string]$Only = '', [int]$Seconds = 60)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'pregame', 'gameover', 'p2win', 'levels', 'pause', 'frightened_cases', 'house_frightened', 'catch', 'inputs', 'inputs1')
$extra = & python -I (Join-Path $here 'analyze_io.py') --probes
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("io_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + @('bt a386 "SENT f=%d pc=$%04X" @frame pc') + @($extra)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\io-" + $n + ".txt") -Seconds $Seconds -Cmd ("io_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
