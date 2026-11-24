# Stage 46 (pointers): measures the values of the six zero-page pointers in the real game, with Altirra, under the existing session harnesses (full games, death, ghosts eaten, extra life, two-player win).
# For each harness a temporary copy is made with extra TRACE lines after the harness lines (the harness clears its own breakpoint by number, so its lines keep numbers 0.. ) (nothing is written to emulated RAM, the ROM is untouched).  At each probe address every pointer is logged:
#   PTR s=<probe address> src=<$3C> dst=<$3E> mz=<$80> clip=<$47> pm=<$38> pp=<$3A> x y f
# The probes are the instruction before each loop that reads / writes through a pointer (once per call, not once per byte) and the single indirect accesses; see tools/analyze_pointers.py (PROBES).
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_pointer_audit.ps1 [-Only fullgame]     then   python -I tools/analyze_pointer_log.py analysis/raw-logs/pointers-*.txt
param([string]$Only = '')
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @(
  @{ n = 'fullgame';          s = 150 },
  @{ n = 'frightened_cases';  s = 150 },
  @{ n = 'death';             s = 120 },
  @{ n = 'extra_life';        s = 120 },
  @{ n = 'p2win';             s = 150 }
)
$probes = @('a3b8','a668','a8de','abbd','acc6','acf9','af29','af33','af41','af4c','b301','b330','b358','b363','b384','b4d0','b840','b96a','b98f')
# SENTINEL (OV-56): Altirra 4.40 prints the FIRST tracepoint hit of a session late - with the registers, memory and frame of the NEXT tracepoint hit.  A tracepoint on the entry of Start ($A386, the first game code to run)
# absorbs that error; its line (SENT) carries no data.  Without it the first real line of a log can show state from a later moment.
$extra = @('bt a386 "SENT f=%d pc=$%04X" @frame pc')
foreach ($p in $probes) {
  $extra += ('bt ' + $p + ' "PTR s=$' + $p.ToUpper() + ' src=$%04X dst=$%04X mz=$%04X clip=$%04X pm=$%04X pp=$%04X x=%d y=%d f=%d py=%d px=%d" dw($3c) dw($3e) dw($80) dw($47) dw($38) dw($3a) x y @frame db($89) db($8e)')
}
foreach ($r in $runs) {
  if ($Only -and $r.n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $r.n + ".cmd")
  $tmp = Join-Path $here ("pointers_tmp_" + $r.n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' }
  Set-Content -Path $tmp -Value (@($body) + @($extra)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\pointers-" + $r.n + ".txt") -Seconds $r.s -Cmd ("pointers_tmp_" + $r.n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
