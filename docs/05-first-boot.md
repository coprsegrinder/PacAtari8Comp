# 05 – First Boot in the Emulator

Written in Step A5 (2026-11-10). Covers checklist stages 51 and 52 (first emulator run, baseline).

## Configuration used (Altirra 4.40, portable mode, settings in `Altirra.ini`)
- Machine: Atari 800, NTSC, 48K RAM.
- OS: owner-supplied Atari OS Rev B (NTSC) ROM, registered as firmware type `kernel800_osb`.
- Cartridge: `original/Pac-Man.rom`, mapper "8K (recommended)" (Altirra asks, because the raw image has no header).
- Launcher: `tools/run_altirra.ps1`.

## Result
The game boots to its title/attract screen: "1UP 00", "HIGH SCORE", PAC-MAN logo, "1 PLAYER GAME",
"PRESS SELECT FOR 2 PLAYER GAME", "PRESS OPTION TO CHANGE DIFFICULTY", "PRESS START TO PLAY GAME".
Evidence: owner screenshot `analysis/screenshot 4.jpg` (local only, not committed).
This confirms the ROM is a working Pac-Man cartridge image on the Rev B OS (it does not prove it is an
unaltered retail dump; see A1/A3).

## Known baseline caveats
- Altirra setting "Kernel: Fast boot enabled" is ON (patches OS boot). Turn it off before cycle-accurate traces (stage E17).
- The mapper dialog still appears on each launch; not yet automated.
- Gameplay, sound and controls have not been tested yet.
