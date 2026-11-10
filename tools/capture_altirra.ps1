# Capture screenshots of the Altirra window (display area) to PNG files, for visual evidence.
# Usage: powershell -ExecutionPolicy Bypass -File tools\capture_altirra.ps1 -OutDir <dir> [-Prefix shot] [-Count 1] [-IntervalMs 500]
# Needs the Altirra window to be visible and not covered by other windows. Reads only the screen; changes nothing.
param([Parameter(Mandatory)][string]$OutDir, [string]$Prefix = 'shot', [int]$Count = 1, [int]$IntervalMs = 500)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class WinRect { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; } }
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
for ($i = 0; $i -lt $Count; $i++) {
  $p = Get-Process Altirra64 -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $p -or $p.MainWindowHandle -eq 0) { Write-Warning 'Altirra window not found'; break }
  $r = New-Object WinRect+RECT; [void][WinRect]::GetClientRect($p.MainWindowHandle, [ref]$r)
  $pt = New-Object WinRect+POINT; [void][WinRect]::ClientToScreen($p.MainWindowHandle, [ref]$pt)
  $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($pt.X, $pt.Y, 0, 0, $bmp.Size)
  $bmp.Save((Join-Path $OutDir ('{0}_{1:D2}.png' -f $Prefix, $i)), [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  if ($i -lt $Count - 1) { Start-Sleep -Milliseconds $IntervalMs }
}
