Pac-Man (Atari 8-bit) - C port, for Windows
===========================================

A faithful C port of the Atari 8-bit (400/800/XL/XE) cartridge game, made from a
study of the original program: the game runs frame for frame as the original
does (NTSC, 59.92 frames a second). This is the version listed in the file
VERSION of the project.

WHAT YOU NEED
  - Windows 10 (version 1903, May 2019, or later) or Windows 11, 64-bit.
  - Your own copy of the Pac-Man (Atari 8-bit) cartridge ROM: the NTSC version,
    a file of exactly 8,192 bytes. The ROM is NOT included and is not for sale
    here; the program recognises the right file by its size and SHA-256.

FIRST START
  Double-click pacman_a8_play.exe. The first time, it asks you to choose your
  ROM file. It reads it ONCE, to make the game's data files (the parts of the
  cartridge that are data, not code) in the folder called resources, and then
  it is not needed again: the ROM is not copied into this folder, and you can
  put it away. (If a ROM is already at original/Pac-Man.rom, it is used without
  asking.) If the data file is ever damaged, the program asks again.

PORTABLE
  Everything is kept in this folder: your settings, your achievements and your
  high score (the folder save), a log (the folder logs) and the data file made
  from your ROM (the folder resources). Move or copy the folder and they go
  with it. To start afresh, delete the folder save. Keep the folder somewhere
  you can write to (not Program Files).

CONTROLS
  Keyboard                          Pad (Xbox, DualShock 4, DualSense)
  Move        arrows, W A S D       D-pad, left stick
  Fire        Ctrl, Z, X, Enter     A / B (Cross / Circle)
  Start game  F2, Enter             Menu / Options
  1 or 2 players  F3                View / Share / Create
  Starting level  F4                X / Y (Square / Triangle)
  Pause       Space, P
  Pause menu  Esc                   Menu + View together
  Help        F1
  Full screen F11, Alt+Enter
  The pause menu has: Graphics Options (display mode, resolution, FPS up to
  uncapped, three CRT shaders), Controls (the controls of the device you are
  using, with its icons; vibration and light bar for PlayStation pads),
  Achievements (27, kept in the folder save), Sound (volume, mute, output
  filter). Your choices are remembered.

WINDOWS MAY WARN BEFORE THE FIRST START
  The program is not code-signed (a signing certificate is a purchase this
  project has not made), so Windows SmartScreen can say "Windows protected your
  PC" for a downloaded copy. Choose "More info", then "Run anyway". To be sure the
  file is the one that was published, compare its SHA-256 with the .sha256 file
  next to the download (PowerShell: Get-FileHash file.zip). Every file in this
  folder is listed with its SHA-256 in FILES.sha256. The program needs no
  installation, no administrator rights, and writes only inside its own folder.

IF SOMETHING GOES WRONG
  Look at logs\shell.log in this folder: it says what the program found and why
  it could not do something.

LICENCE
  The work of this project is under the MIT licence (LICENSE). What that does not
  cover - the original game, which belongs to its owners, and the third-party
  files in the folder third-party, each under its own licence - is in NOTICE.
