# Stage 44 (OV-54): measures how deep the 6502 stack gets in the real game, with Altirra, under the existing session harnesses (full games, death, ghosts eaten, extra life, two-player win).
# For each harness a temporary copy is made with extra TRACE lines in front (nothing is written to emulated RAM, the ROM is untouched):
#   STK  every write to the stack page below $01F0 (depth over 16 bytes): address, pc, frame        (hardware pushes of an interrupt show the interrupted pc)
#   VBIE / DLI1E / DLI2E   the stack pointer S, the frame, the scan line and the interrupted pc at the first instruction of the deferred VBI handler ($A5FD) and of the two display-list interrupt handlers ($A573, $A5CE)
#   VBIX  the end of the VBI handler ($A60D);  INITB  entry of InitBoard ($ADAF);  FILL  entry of FillPlayerPages ($B100): S, frame, scan line  (where the deepest call chain is and how long it runs)
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_stack_audit.ps1 [-Only fullgame]     then   python -I tools/analyze_stack_log.py analysis/raw-logs/stack-*.txt
param([string]$Only = '')
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = @(
  @{ n = 'fullgame';          s = 400 },
  @{ n = 'frightened_cases';  s = 300 },
  @{ n = 'death';             s = 150 },
  @{ n = 'extra_life';        s = 170 },
  @{ n = 'p2win';             s = 300 }
)
$extra = @(
  'bta w 0100 L0F0 "STK a=$%04X pc=$%04X f=%d" @address pc @frame',
  'bt a5fd "VBIE s=$%02X f=%d vp=%d ipc=$%04X" s @frame vpos dw($100+s+5)',
  'bt a573 "DLI1E s=$%02X f=%d vp=%d ipc=$%04X" s @frame vpos dw($100+s+2)',
  'bt a5ce "DLI2E s=$%02X f=%d vp=%d ipc=$%04X" s @frame vpos dw($100+s+2)',
  'bt a60d "VBIX s=$%02X f=%d vp=%d" s @frame vpos',
  'bt adaf "INITB s=$%02X f=%d vp=%d" s @frame vpos',
  'bt b100 "FILL s=$%02X f=%d vp=%d" s @frame vpos'
)
foreach ($r in $runs) {
  if ($Only -and $r.n -ne $Only) { continue }
  $src = Join-Path $here ("altirra_" + $r.n + ".cmd")
  $tmp = Join-Path $here ("stack_tmp_" + $r.n + ".cmd")
  $body = (Get-Content $src) | Where-Object { $_ -notmatch '^\s*#' }
  Set-Content -Path $tmp -Value (@($extra) + $body) -Encoding ascii
  try {
    & (Join-Path $here 'run_patrol_trace.ps1') -Log ("analysis\raw-logs\stack-" + $r.n + ".txt") -Seconds $r.s -Cmd ("stack_tmp_" + $r.n + ".cmd") -Ini (Join-Path $here '..\external-tools\Altirra\Altirra_fast.ini')
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
