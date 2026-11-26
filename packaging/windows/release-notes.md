The Windows build of the faithful C port of the Atari 8-bit Pac-Man cartridge game. The game runs frame for frame as the original does; everything under **Modernization** is added around it.

## What you need

- Windows 10 (version 1903 or later) or Windows 11, 64-bit.
- **Your own copy of the Atari 8-bit Pac-Man cartridge ROM** (the NTSC version, a file of exactly 8,192 bytes). **It is not included** in this release or in the repository. The program recognises the right file by its size and SHA-256.

## How to play

1. Download `pacman-a8-port-{version}-win64.zip`, unpack it anywhere you can write to, run `pacman_a8_play.exe`.
2. The first time, the program asks for your ROM file. It reads it **once** to make the game's data files (the parts of the cartridge that are data, not code) in the folder `resources`, and then it is not needed again. It is not copied into the game folder.
3. Everything - settings, achievements, high score, log - stays in that folder: the game is portable. Delete `save/` to start afresh.

Windows may say "Windows protected your PC" because the program is not code-signed: choose **More info**, then **Run anyway**. To check the download, compare its SHA-256 with `pacman-a8-port-{version}-win64.zip.sha256` (PowerShell: `Get-FileHash pacman-a8-port-{version}-win64.zip`).

```
{sha256}  pacman-a8-port-{version}-win64.zip
```

## Modernization

None of this changes the game's own state: its rules, speed and sounds are the original's.

**Picture**
- Windowed or **borderless fullscreen**; 20 resolutions in 4:3, 16:9, 16:10 and 21:9; the picture is always 1.6:1 and centred.
- **Frame rate from native (59.92) to uncapped**, or 75 to 180 a second paced to the monitor: the pictures between two game frames blend the places where they differ, so objects glide.
- **Three CRT shaders** (crt-guest-advanced-ntsc, zfast-crt-composite, crt-aperture) on OpenGL 4.5, chosen live, or none.

**Controls**
- Keyboard and **Xbox pads**; **DualShock 4 and DualSense over USB and Bluetooth** with no extra software; a second pad is player 2; pads drive the menu.
- **Rumble** on every pad and the **light bar** of PlayStation pads follow the game (power pellet, ghost eaten, caught, extra life, board cleared); Vibration and Light Bar each Off / Light / Heavy.
- A **Controls page** with the controls of the device you are using and its icons.

**Sound**
- The chip's sound is made at four times the rate and low-passed, so the start tune no longer whines.
- A **Sound page**: master volume, mute, output filter (Off / Soft / Warm).

**Around the game**
- A **pause menu** (Esc, or Menu + View on a pad) with Graphics Options, Controls, Achievements, Sound and Quit; F1 shows the function keys.
- **27 achievements** (three hidden) with a toast, a chime and a gold flash on the pad; score and level ones count only in games from level 1; kept in a sealed file.
- **Everything you set is remembered**, in the game folder.

**Installing and running**
- **Portable**; folders and ROM paths with any characters work.
- **Only your ROM is needed**, read once; a wrong, missing or damaged file is explained.
- This zip is reproducible and was checked as a player meets it (`tools/check_win_release.py`: the first start from a ROM, wrong and damaged files, the real dialogs, unusual paths, a write-protected folder).

Screenshots and the full description: the [README](https://github.com/coprsegrinder/PacAtari8Comp#readme).

## Known limits

Everything not fully verified is listed in [docs/OPEN-VERIFICATION.md](https://github.com/coprsegrinder/PacAtari8Comp/blob/main/docs/OPEN-VERIFICATION.md) (for example one frame-rate measurement, 120 on a 180 Hz monitor, is intermittent on the test machine). How it is made and how faithful it is: [docs/75](https://github.com/coprsegrinder/PacAtari8Comp/blob/main/docs/75-first-run-and-release.md).
