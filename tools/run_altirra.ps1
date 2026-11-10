# Launch Altirra as an Atari 800 (NTSC) with the owner-supplied Rev B OS and the Pac-Man cartridge.
# Usage: powershell -File tools\run_altirra.ps1 [-Cart <path>]   (extra Altirra switches may follow)
param([string]$Cart = (Join-Path $PSScriptRoot '..\original\Pac-Man.rom'), [Parameter(ValueFromRemainingArguments)]$Extra)
$alt = 'F:\Ports\Pac-Man-tools\Altirra\Altirra64.exe'
$os  = (Resolve-Path (Join-Path $PSScriptRoot '..\original\Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom')).Path
$cart = (Resolve-Path $Cart).Path
& $alt /portable /hardware:800 /kernel:$os /ntsc /cart:$cart @Extra
