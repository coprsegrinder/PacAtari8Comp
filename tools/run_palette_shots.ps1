# Stage 80b: captures of Altirra's own window (PrintWindow, same method as run_item_shots.ps1) for the two palette programs of tools\measure_palette.py --build.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_palette_shots.ps1 -Dir analysis\shots\palette
param([Parameter(Mandatory)][string]$Dir, [int]$WaitSec = 8)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ini = Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra_fast.ini'
$alt = (Join-Path $PSScriptRoot '..\external-tools\Altirra\Altirra64.exe')
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f); }
"@
$Dir = (Resolve-Path $Dir).Path
foreach ($n in 'palette_a', 'palette_b', 'palette_c') {
  $x = Join-Path $Dir "$n.xex"
  $p = Start-Process -FilePath $alt -ArgumentList ('/portablealt:"' + $Ini + '" /hardware:800 /ntsc "' + $x + '"') -PassThru
  Start-Sleep -Seconds $WaitSec
  $p.Refresh()
  $r = New-Object Win+RECT; [void][Win]::GetClientRect($p.MainWindowHandle, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap $r.R, $r.B
  $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
  [void][Win]::PrintWindow($p.MainWindowHandle, $dc, 3)
  $g.ReleaseHdc($dc); $g.Dispose()
  $bmp.Save((Join-Path $Dir "${n}_0.png"), [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  if (-not $p.HasExited) { $p.Kill() }
  Write-Host "$n : captured"
}
