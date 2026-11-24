# Stage 48 (structures): measures in Altirra that every indexed access to a zero-page array stays inside its array, and what InitBoard / the game restart leave in the zero page.
# For each harness a temporary copy is made with extra TRACE lines after the harness lines (the harness clears its own breakpoint by number, so its lines keep numbers 0..); nothing is written to emulated RAM, the ROM is untouched:
#   IDX s=<site> x=<X>   at every `array,x` instruction found by `python -I tools/analyze_structures.py --probes` (before it executes, so X is the index it uses)
#   IB f=<frame> <128 bytes>   the zero page $80-$FF at the last instruction of InitBoard ($ADF0, the RTS)
#   RS f=<frame> <32 bytes>    the zero page $20-$3F after the clear of the game restart ($A481)
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_structure_audit.ps1 [-Only fullgame]     then   python -I tools/analyze_structures_log.py analysis/raw-logs/structures-*.txt
param([string]$Only = '')
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @(
  @{ n = 'fullgame';          s = 60 },
  @{ n = 'frightened_cases';  s = 60 },
  @{ n = 'death';             s = 50 },
  @{ n = 'extra_life';        s = 50 },
  @{ n = 'p2win';             s = 60 },
  @{ n = 'levels';            s = 60 },
  @{ n = 'itemshots';         s = 60 },
  @{ n = 'catch';             s = 60 },
  @{ n = 'house_frightened';  s = 60 },
  @{ n = 'eaten_dir';         s = 60 },
  @{ n = 'fullgame2';         s = 60 },
  @{ n = 'door_up';           s = 60 }
)
$probes = & python -I (Join-Path $here 'analyze_structures.py') --probes
# SENTINEL (OV-56): Altirra 4.40 prints the FIRST tracepoint hit of a session late - with the registers, memory and frame of the NEXT tracepoint hit.  A tracepoint on the entry of Start ($A386, the first game code to run)
# absorbs that error; its line (SENT) carries no data.  Without it the first real line of a log can show state from a later moment.
$extra = @('bt a386 "SENT f=%d pc=$%04X" @frame pc')
foreach ($p in $probes) {
  $extra += ('bt ' + $p + ' "IDX s=$' + $p.ToUpper() + ' x=%d" x')
}
$fmt = 'IB f=%d' + (' %02X' * 128)
$args1 = (0x80..0xFF | ForEach-Object { 'db($' + ('{0:x2}' -f $_) + ')' }) -join ' '
$extra += ('bt adf0 "' + $fmt + '" @frame ' + $args1)
$fmt2 = 'RS f=%d' + (' %02X' * 32)
$args2 = (0x20..0x3F | ForEach-Object { 'db($' + ('{0:x2}' -f $_) + ')' }) -join ' '
$extra += ('bt a481 "' + $fmt2 + '" @frame ' + $args2)
foreach ($r in $runs) {
  if ($Only -and $r.n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $r.n + ".cmd")
  $tmp = Join-Path $here ("structures_tmp_" + $r.n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' }
  Set-Content -Path $tmp -Value (@($body) + @($extra)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\structures-" + $r.n + ".txt") -Seconds $r.s -Cmd ("structures_tmp_" + $r.n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
