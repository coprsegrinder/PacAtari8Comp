# docs/images

The pictures of the root README. They are the program's own output, made by `python -I tools/make_screenshots.py` (a scratch main folder with only a ROM, the real program, the real screen); the script only enlarges them (the game's 384 x 240 picture three times, nearest pixel, no smoothing; the CRT shaders' result halved).

- `gameplay-*.png`: the title screen and two moments of the game, played by the scripted keys of the self test.
- `crt-*.png`: the three CRT shaders on a frame of play (2304 x 1440 on the test machine's screen).
- `menu-*.png`: the pause menu and its pages, from the real window's pictures; the Controls page for an Xbox pad and a DualSense is shown with `--device`.
- `menu-achievements.png`: the Achievements page **with a prepared save file** (some achievements earned) so that the page has something to show: an illustration of the page, not a record of one game. `achievement-toast.png` is a real first dot, with a CRT shader on.

They contain the game's graphics, as any picture of the game does; the ROM itself is not here.
