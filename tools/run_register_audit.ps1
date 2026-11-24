# Stage 56 (runtime register inspection): the registers A, X, Y, S and P at the entry and at every RTS / RTI of every routine, in the real game (Altirra), to check the register claims of docs/23-function-table.md
# (which registers a routine preserves, which it never changes, which it gives back).  For each harness a temporary copy is made (the harness lines, then):
#     bt a386 "SENT ..."                                    sentinel: Altirra prints the first tracepoint hit late (OV-56, docs/04)
#     bt <entry>  "RE <entry> a=%02X x=%02X y=%02X s=%02X p=%02X f=%d" @a x y s p @frame      entry of each routine (before its first instruction)
#     bt <rts>    "RX <rts> a=... "                          before each RTS / RTI instruction
# `python -I tools/analyze_registers.py --probes` lists the lines.  Nothing is written to emulated RAM.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_register_audit.ps1 [-Only fullgame] [-Seconds 40]     then   python -I tools/analyze_registers.py analysis/raw-logs/registers-*.txt
param([string]$Only = '', [int]$Seconds = 40)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @('fullgame', 'frightened_cases', 'death', 'extra_life', 'p2win', 'levels', 'itemshots', 'catch', 'house_frightened', 'door_up', 'gameover', 'pregame')
$extra = & python -I (Join-Path $here 'analyze_registers.py') --probes
foreach ($n in $runs) {
  if ($Only -and $n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $n + ".cmd")
  if (-not (Test-Path $src)) { Write-Host "missing harness $n"; continue }
  $tmp = Join-Path $here ("registers_tmp_" + $n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' }
  Set-Content -Path $tmp -Value (@($body) + @($extra)) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\registers-" + $n + ".txt") -Seconds $Seconds -Cmd ("registers_tmp_" + $n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
