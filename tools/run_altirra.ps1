# Launch Altirra as an Atari 800 (NTSC) (Rev B OS configured in Altirra's firmware settings) and the Pac-Man cartridge.
# Usage: powershell -File tools\run_altirra.ps1 [-Cart <path>]   (extra Altirra switches may follow)
param([string]$Cart = '', [Parameter(ValueFromRemainingArguments)]$Extra)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Cart) { $Cart = Join-Path $root '..\original\Pac-Man.rom' }
$alt = 'F:\Ports\Pac-Man-tools\Altirra\Altirra64.exe'
$cart = (Resolve-Path $Cart).Path
# The Rev B OS ROM and 48K memory are set in Altirra's own configuration (Altirra.ini, portable mode).
& $alt /portable /hardware:800 /ntsc $cart @Extra
