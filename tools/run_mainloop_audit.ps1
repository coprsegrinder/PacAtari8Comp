# Stage 62 (main loop): the frame by frame record of the game, in session harnesses of the real game (Altirra): at the entry of the deferred vertical-blank handler ($A5FD) the state variables that FrameDispatch tests, at the return of FrameDispatch ($A606) and at the exit of the handler ($A60D) the scan line.
#   VB f=<frame> vp=<scan line> gs=.. v1c=.. v20=.. v21=.. v22=.. v23=.. v24=.. v26=.. v27=.. e5=.. ed=.. p9b=.. a3=.. cnt=..   entry (the state the dispatcher decides on)
#   VF f vp   FrameDispatch returned;   VX f vp   the handler leaves through XITVBV
# Nothing is written to the emulated machine by the tracing; the harnesses keep their own test aids (docs/04).  The sentinel absorbs Altirra's late first tracepoint (docs/32).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_mainloop_audit.ps1 [-Only fullgame] [-Seconds 60]     then   python -I tools/analyze_mainloop.py analysis/raw-logs/mainloop-*.txt --write analysis/evidence-mainloop-summary.txt
param([string]$Only = '', [int]$Seconds = 60)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'fullgame2', 'p2win', 'levels', 'death', 'frightened_cases', 'pause')
$extra = @(
  'bt a386 "SENT f=%d pc=$%04X" @frame pc',
  'bt a5fd "VB f=%d vp=%d gs=%d v1c=%d v20=%d v21=%d v22=%d v23=%d v24=%d v26=%d v27=%d e5=%d ed=%d p9b=%d a3=%d cnt=%d" @frame vpos db($19) db($1c) db($20) db($21) db($22) db($23) db($24) db($26) db($27) db($e5) db($ed) db($9b) db($a3) db($1e)',
  'bt a606 "VF f=%d vp=%d" @frame vpos',
  'bt a60d "VX f=%d vp=%d" @frame vpos'
)
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("ml_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + $extra) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\mainloop-" + $n + ".txt") -Seconds $Seconds -Cmd ("ml_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
