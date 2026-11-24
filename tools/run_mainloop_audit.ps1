# Stage 62 (main loop): the frame by frame record of the game, in session harnesses of the real game (Altirra): at the entry of the deferred vertical-blank handler ($A5FD) the state variables that FrameDispatch tests, at the return of FrameDispatch ($A606) and at the exit of the handler ($A60D) the scan line.
#   VB f=<frame> vp=<scan line> gs=.. v1c=.. v20=.. v21=.. v22=.. v23=.. v24=.. v26=.. v27=.. e5=.. ed=.. p9b=.. a3=.. cnt=..   entry (the state the dispatcher decides on)
#   VF f vp   FrameDispatch returned;   VX f vp   the handler leaves through XITVBV
# Nothing is written to the emulated machine by the tracing; the harnesses keep their own test aids (docs/04).  The sentinel absorbs Altirra's late first tracepoint (docs/32).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_mainloop_audit.ps1 [-Only fullgame] [-Seconds 60] [-Video pal] [-Cycles]  (PAL logs: palmainloop-*.txt, analysed with PACMAN_VIDEO=pal, OV-62)     then   python -I tools/analyze_mainloop.py analysis/raw-logs/mainloop-*.txt --write analysis/evidence-mainloop-summary.txt
param([string]$Only = '', [int]$Seconds = 60, [string]$Video = 'ntsc', [switch]$Cycles, [switch]$Loops, [switch]$Clip)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'fullgame2', 'p2win', 'levels', 'death', 'frightened_cases', 'pause')
if ($Only -eq 'rare') { $runs = @('rare') }
if ($Only -eq 'fuzz') { $runs = @('fuzz') }   # OV-64: adversarial play frames (altirra_fuzz.cmd), log fuzzmainloop-fuzz.txt, tools/analyze_fuzz.py
if (($Loops -or $Clip) -and -not $Only) { $runs += 'rare' }   # OV-64: the rare paths (altirra_rare.cmd), log raremainloop-rare.txt
$hp = if ($Cycles) { ' hp=%d' } else { '' }; $hpa = if ($Cycles) { ' hpos' } else { '' }   # -Cycles (OV-63): the cycle in the line too, logs cycmainloop-*.txt
$extra = @(
  'bt a386 "SENT f=%d pc=$%04X" @frame pc',
  ('bt a5fd "VB f=%d vp=%d gs=%d v1c=%d v20=%d v21=%d v22=%d v23=%d v24=%d v26=%d v27=%d e5=%d ed=%d p9b=%d a3=%d cnt=%d' + $hp + '" @frame vpos db($19) db($1c) db($20) db($21) db($22) db($23) db($24) db($26) db($27) db($e5) db($ed) db($9b) db($a3) db($1e)' + $hpa),
  "bt a606 `"VF f=%d vp=%d$hp`" @frame vpos$hpa",
  "bt a60d `"VX f=%d vp=%d$hp`" @frame vpos$hpa"
)
if ($Loops) {   # OV-64: the executions of the loop pcs bounded by hand in tools/static_wcet.py (ANNOT) between two entries of the routine they are bounded per call of: logs loopmainloop-*.txt, tools/analyze_loopbounds.py
  $extra = @('bt a386 "SENT f=%d pc=$%04X" @frame pc')
  foreach ($e in 'b7f5', 'ac93', 'afd7', 'af54', 'b999') { $extra += ('bt ' + $e + ' "EN pc=' + $e + ' f=%d" @frame') }
  foreach ($l in 'b8e8', 'acdf', 'b018', 'aff3', 'b53d', 'b9f2') { $extra += ('bt ' + $l + ' "LP pc=' + $l + ' f=%d" @frame') }
}
if ($Clip) {    # OV-64: the heavy calls of ClipEntityAtTunnel per frame (right zone $AB71, left zone $AB99) with the frame class state, logs clipmainloop-*.txt, tools/analyze_clip.py
  $extra[1] = $extra[1]
  $extra += 'bt ab57 "CE f=%d" @frame'
  $extra += 'bt ab71 "CR f=%d" @frame'
  $extra += 'bt ab99 "CLL f=%d" @frame'
}
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("ml_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + $extra) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\" + $(if ($Video -eq 'pal') { 'palmainloop-' } elseif ($Clip) { 'clipmainloop-' } elseif ($Loops) { 'loopmainloop-' } elseif ($Cycles) { 'cycmainloop-' } elseif ($Only -eq 'rare') { 'raremainloop-' } elseif ($Only -eq 'fuzz') { 'fuzzmainloop-' } else { 'mainloop-' }) + $n + ".txt") -Video $Video -Seconds $Seconds -Cmd ("ml_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
