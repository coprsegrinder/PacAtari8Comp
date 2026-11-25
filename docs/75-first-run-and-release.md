# 75 - The first start from the player's ROM, and the Windows release (an addition to stage J)

Decided by the owner on 2026-11-25: **the release should only need the game ROM to be played; the ROM holds the data that is not code, and it is read from it once, on the first start.** Source: `src/c/assets/rom_install.[ch]` (the extraction, from stage 80a), `src/c/platform/win32/win_main.c` (`boot`, `first_run_assets`), `tools/make_win_release.py`, `tools/check_win_release.py`, `packaging/windows/`, the file `VERSION`.

## 1. How the first start works

The program needs the game's data file `resources/pack/assets.pmab` (about 9.4 KB: the 79 regions of the cartridge that are data, not code - the character sets, the maze, the tables - expanded the way the game's own start-up expands them). The code is the C port. If the file is there and good, the ROM is not touched. If it is not (the first start), is damaged, or is of another version of the program, it is made from the ROM, in this order:

1. **`--rom FILE`** on the command line (any path, any name);
2. **`original/Pac-Man.rom`** in the game folder (the older layout: still used, without asking);
3. else the player is **asked**: a short text (the NTSC cartridge, a file of 8,192 bytes, read once to make the data files in this folder, not copied and not needed again), then the Windows file chooser. A file that is refused (wrong size, wrong SHA-256, cannot be opened) is explained and the player may choose another.

The ROM is checked by exact size and SHA-256 (only the NTSC cartridge); **nothing is written unless everything succeeded**. A ROM chosen in the dialog is read from where it is and **never copied into the game folder**. If the folder cannot be written to (for example Program Files) the program says so and suggests moving it. With **`--no-dialogs`** (a test, a script) nothing is shown: the reason goes to `logs/shell.log` and the exit code is 2.

**The game folder.** The folder that holds `original/Pac-Man.rom` or `resources/pack/assets.pmab`, looked for from the current folder and from the program's folder upwards; if neither is found (a fresh copy of the release) it is **the program's own folder, whatever the current folder is** (a shortcut may start it elsewhere), so that settings, achievements, high score, log and data file are all in one place. This is what makes the release portable.

## 2. The release

`python -I tools/make_win_release.py` builds the program (clang, Release; it links only the Windows system libraries and the Universal C Runtime) and makes `build/release/pacman-a8-port-<version>-win64.zip` with its `.sha256`: a folder with `pacman_a8_play.exe`, `README.txt` (for the player), `LICENSE`, `NOTICE`, `VERSION`, `FILES.sha256`, the shader files the Graphics Options read (`src/shaders`, `third-party/crt-shaders` with the GPL text), the font's licence, and `original/README.txt`. **No ROM, no derived data, no saved data.** The zip is deterministic (sorted names, one time stamp, LF text): the same program gives the same bytes. The version is the one line of the file `VERSION` (0.2.0); the program writes it to `logs/shell.log` at every start; `tools/make_release.py` (the source archive) reads the same file.

## 3. How it was checked (`tools/check_win_release.py`, 20 steps)

The zip is unpacked into an empty folder, as a player would, and only a ROM is given:

| Check | Result |
|---|---|
| every file equals `FILES.sha256`; the files a player needs are there; `original/` holds only its README | pass |
| **no ROM file, nothing of the cartridge, and nothing of the OS ROM except the font's glyph bytes, in any file - the program included** (32-byte pieces sampled all along the ROMs) | pass: 0 pieces of the cartridge; 63 pieces are the first 64 glyphs of the OS character set, which the open font EightBit Atari-Regular (SIL OFL) copies bit for bit (`third-party/README.md`, stated since stage 80a) |
| made again from the same program: byte-identical zip | pass |
| first start, ROM given from outside the folder: runs, the data file is made, **the ROM is not copied into the folder** | pass |
| second start, no ROM anywhere: runs, the data file untouched (same bytes, same time stamp): **the ROM is read once** | pass |
| started from another current folder: same game folder, no new data file | pass |
| no ROM, no data file, no dialogs: exit 2, the reason in the log, nothing made | pass |
| not the cartridge (wrong size, one byte changed, all zeros, the Atari OS ROM): refused, nothing made; the reason in the log; a file that cannot be opened: said so | pass |
| a damaged data file with the ROM given: made again, equal to the first; without the ROM: exit 2 (it would ask), the file left | pass |
| a ROM left at `original/Pac-Man.rom`: used without asking | pass |
| a folder that cannot be written to: exit 2 with the write-protect text | pass |
| **the dialogs** (a real desktop): with no ROM the question appears (it names the ROM, 8,192 bytes, once), OK opens the file chooser, closing it leaves with exit 2 and makes nothing | pass |
| **the real file chooser, driven** (the file name typed into the system's chooser, Open pressed, on a real desktop): a wrong file is refused with the reason ("sha256 differs") and an offer of another file, **Retry brings the chooser back, and the right ROM then makes the data file and starts the game** (the ROM is not copied into the folder, the game window is closed and the exit is 0); **Cancel on the refusal leaves with exit 2** and nothing made; the right ROM chosen at once starts the game | pass |
| a damaged data file with dialogs allowed: the question says the data file is damaged and has to be made again; Cancel leaves with exit 2 and the file as it was | pass |
| `ctest rom_install_check`: the same logic below the front end (wrong sizes, one byte changed, zeros; written once; a damaged file replaced by identical bytes; a refused ROM leaves a good file alone; a blocked folder) | pass |

## 4. Limits (OV-84)

- The chooser itself is the system's; the check drives it by typing the file name and pressing Open (as a player would by typing a path), not by browsing folders with the mouse.
- Tried on Windows 11 only (not Windows 10); not run under a reduced-rights account or from Program Files; the executable is **not signed**, so Windows SmartScreen may warn on the first start of a downloaded copy.
- Only the clang build is packaged; gcc builds the same sources (the headless parts are tested with both) but its executable is not packaged or checked.
