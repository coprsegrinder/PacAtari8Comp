# 71 - The Controls page, and the DualShock 4 / DualSense pads (an addition to stage J)

Asked for by the owner on 2026-11-25: **(1)** a Controls page in the pause menu that lists the controls of the device in use (keyboard or XInput pad) with icons; **(2)** support for the DualShock 4 and the DualSense pads, with icons, vibration and the light bar. Nothing of the game changes: the menu is still a pause (docs/68), and the rumble and the light bar are read from the World after each frame and never written into it (the game's digests are the same: `check_front_end.py`).

Source: portable and tested (`src/c/shell/controls.[ch]`, `icons.[ch]`, `haptics.[ch]`, `padhid.[ch]`, `menu.[ch]`; `ctest controls_check`, `menu_check`), and the Windows part (`src/c/platform/win32/win_pad.[ch]`, `win_main.c`).

## 1. The Controls page

Pause menu: **Resume Game, Graphics Options, Controls, Quit Game** (Controls is the third item; Quit Game moved from the third to the fourth). The page shows the name of the device and one row per action: the action's text on the left, the keys or buttons that do it as icons on the right. Under the list are two items, **Vibration** and **Light Bar**, each OFF, LIGHT or HEAVY (default HEAVY; section 7): Up / Down move between them, Left / Right / Enter / Space switch the one the cursor is on. Vibration OFF keeps every motor at rest (PlayStation and XInput pads); Light Bar OFF sends no light (black). Esc (or a pad's B / Circle) goes back to the main menu, on "Controls". F1 (the help) works from it and returns to it. The settings are not saved.

**Which device.** The one the player touched last: a key press makes it the keyboard; a button pressed or the stick pushed on a pad makes it that pad (XInput pad, DualShock 4, DualSense). With no pad connected it is the keyboard. The page changes while it is open when the player touches another device.

| Action | Keyboard | Xbox / XInput pad | DualShock 4 | DualSense |
|---|---|---|---|---|
| Move | arrow keys, WASD | D-pad, left stick | D-pad, left stick | D-pad, left stick |
| Fire | Ctrl, Z, X, Enter | A, B | Cross, Circle | Cross, Circle |
| Start game | F2, Enter | Menu (Start) | Options | Options |
| 1 or 2 players | F3 | View (Back) | Share | Create |
| Starting level | F4 | X, Y | Square, Triangle | Square, Triangle |
| Pause | Space, P | | | |
| Pause menu | Esc | Menu + View together | Options + Share together | Options + Create together |
| Help | F1 | | | |
| Full screen | F11, Alt+Enter | | | |
| In menus: select / back | Enter, Space / Esc | A / B | Cross / Circle | Cross / Circle |
| Second pad | | player 2 | player 2 | player 2 |

The table is `src/c/shell/controls.c` and is what the front end really maps (`keys_now`, `pad_menu_poll`, `wnd_proc`). The pad has no pause button of its own (the original's pause key is the keyboard's); the pad opens the menu, which pauses.

**Icons.** Made by the program (`icons.c`, no image files): keycaps with their text in the game's own font, the arrow keys, the D-pad cross, the stick, the Xbox buttons (green A, red B, blue X, yellow Y, the Menu and View buttons), the PlayStation buttons (blue Cross, red Circle, pink Square, green Triangle, Options, Share, Create). They are drawn into the 384 x 240 picture like the rest of the menu, so they scale with it and the CRT shaders draw them too. The pictures of the page are made by the menu test (`logs/menu_controls.ppm`).

## 2. The PlayStation pads

**Why a driver of its own.** Windows' XInput does not see a DualShock 4 or a DualSense. They are found as HID devices (USB vendor 054C; DualShock 4: products 05C4, 09CC, dongle 0BA0; DualSense: 0CE6, DualSense Edge 0DF2), opened for reading and writing, read with overlapped reads (the program never waits for a pad) and written to with output reports. `win_pad.c` does the finding and the moving of bytes (it links `hid` and `setupapi`, both part of Windows); `padhid.c` is the portable part: how to read an input report and how to build an output report.

| | DualShock 4 | DualSense |
|---|---|---|
| Input, USB | report 1, 64 bytes | report 1, 64 bytes |
| Input, Bluetooth | report 0x11 (the pad starts with the short report 1; asking for its calibration, feature report 5, switches it to the full one: `bt_switch`) | report 0x31 (same switch) |
| Output, USB | report 5, 32 bytes | report 2, 63 bytes |
| Output, Bluetooth | report 0x11, 78 bytes, CRC-32 | report 0x31, 78 bytes, counter, CRC-32 |
| Light bar | colour bytes of the report | colour bytes; the pad's start-up light is put out once |
| Rumble | two motors: big (low), small (high) | the same two, as "compatible vibration" |

The layouts are the ones the public drivers use (Linux `hid-sony` and `hid-playstation`, DS4Windows), written out by hand in `ctest controls_check` as reports and checked both ways: all nine positions of the hat, the stick scaling and direction, every button, the three framings, the CRC-32 (the standard check value, and the 74-byte CRC of every Bluetooth report recomputed). **They have not been checked against a real pad: OV-81.**

**Ports.** A pad takes the first port that has no XInput pad (port 1 is player 1, port 2 is player 2), in the order Windows lists them; XInput pads keep their ports. Mapping to the game: Cross = A (fire), Circle = B (fire), Square and Triangle = X and Y (option), Options = Start, Share / Create = Back (select); the cross or the left stick move. The same `FrontKeys` the keyboard and XInput feed, so the game cannot tell them apart.

## 3. Rumble and the light bar

`haptics.c` is a small state machine fed with a snapshot of the game after each frame (lives, the death counter, how many ghosts are frightened, how many are eyes, board complete) and answering with the strength of the two motors and a colour. Effects are counted in game frames, so a pause stops them.

| Event (found as a change in the snapshot) | Rumble (big / small, 0..255) | Light bar |
|---|---|---|
| Power pellet (a ghost becomes frightened) | 140 / 230, 22 frames, held then falling | blue while any ghost is frightened |
| Ghost eaten (a ghost becomes eyes) | 230 / 255, 28 frames, held then falling | white for 12 frames |
| Pac-Man caught (the death counter starts) | 255 / 255, 80 frames, held then falling | red, fading back to yellow over 80 frames |
| Extra life | 180 / 230, 36 frames, held then falling | |
| Board cleared | 220 / 220, 44 frames, held then falling | |
| Nothing | at rest | Pac-Man yellow |
| A menu is open | at rest, effects dropped | dim yellow |

The lives counter falls when a life *starts*, not when Pac-Man dies (`start_tune_step`), so it is not the death signal; the death counter is. A change of player's turn is not an event. At exit the motors are put at rest and the light bar goes to a dim blue. **XInput pads rumble too** (`XInputSetState`, the same two strengths; no light bar). The vibration is sent only when it changes (a motor that is on is refreshed every 100 ms on a PlayStation pad), at most every 16 ms, and a write that is still on its way is not stacked on.

## 4. How it was checked

| Check | Where | Result |
|---|---|---|
| The table: every row has text and glyphs that exist, a key glyph has a label and only a key glyph does, each row fits the picture; the keyboard rows name F1 to F4, F11, Esc, Ctrl, Z, X, Space, WASD; a pad shows no key; each pad shows its own buttons and no other pad's | `ctest controls_check` | pass |
| Icons: each is drawn inside its own box (not one pixel outside), is not blank, and is a different picture from every other; a keycap is as wide as its label | `controls_check` | pass |
| Haptics: first snapshot no event; quiet game quiet pad; power pellet, ghost eaten, death, extra life, board cleared each give their effect and colour, effects only die away, a life starting is no event, a change of player is no event, a pause puts everything at rest | `controls_check` | pass |
| Reports: all kinds of input report of both pads (USB, Bluetooth full, Bluetooth short) parsed to the expected buttons, hat, sticks; wrong ids and short reports refused without touching the result; the four output layouts byte by byte; the CRCs | `controls_check` | pass |
| The menu: the fourth item, the page's text for each device, back and the help from it | `ctest menu_check` | pass |
| **The real program** (`pacman_a8_play --menutest`): the Controls page opened by real key messages in the running game, the picture it really draws holds icons (a colour only they use, 4,527 pixels), the game frozen (frame count and state hash unchanged over 500 ms), Esc back to the main menu on Controls, and Quit Game still last; the rest of the menu test as before | `--menutest` | 106 passed, 0 failed |
| The game is unchanged: the game recorded through the front end replays headless to the same digests | `tools/check_front_end.py` | see `analysis/evidence-front-end-summary.txt` |
| The page's pictures for the keyboard (taken from the real window) and for the three pads (drawn by the same icon code in a scratch program) looked at | `logs/menu_controls.ppm` | looked at |

## 5. Limits (OV-81)

- **No pad was available: the PlayStation code was not run against a device.** What is checked is the byte layouts against the public drivers' (written from them, tested by hand-made reports), the build, and that with no pad connected the program behaves as before. Not seen: a DualShock 4 or a DualSense found, opened, read; a button reaching the game; the motors turning; the light bar changing colour; Bluetooth at all (the switch to the full reports, the CRC); the second pad's port; a pad leaving and coming back. The most likely places for a fault: the Bluetooth switch (a pad that stays on its short report would still work, minus the DualSense triggers, which are not used), the DualShock 4 Bluetooth byte offsets, the DualSense light-bar flags.
- **A pad that is also seen through XInput** (Steam Input, DS4Windows without hiding the real pad) shows up twice: as an XInput pad and as a raw PlayStation pad, so one controller can occupy both ports. Turn off that emulation or hide the device from the game; the program does not try to tell the two apart.
- **Another program holding the pad exclusively** keeps this one from opening it (it tries again every two seconds).
- **The strengths and the colours are choices, not measurements** (a table in section 3, constants at the top of `haptics.c`); how they feel is the owner's to judge. No setting turns the vibration or the light bar off (not asked for); the settings are not saved (as for the rest of the menu).
- **The page was looked at by a person only through pictures.** The icons of the three pads were drawn by a scratch program, not by the running game (no pad to select them).
- The Controls page is not told that a second pad exists beyond the line "2ND PAD: PLAYER 2"; pad 2's own device type is not shown.
- **A timing flake seen once in the checks**: in two of four runs of `check_front_end.py` for gcc (right after the from-scratch build) the 1,200-frame self test had 1 sound underrun and 1 to 3 picture gaps over 40 ms; four direct runs of the same program, the final full run (52 steps, gcc and clang) and the first run had 0 and 0. The pad scan costs 0.3 to 3 ms with no pad, so it is not the cause; the cause was not found (machine load after the build is the likely one).

## 6. After the owner's first test with real pads (2026-11-25)

Reported: the vibration was too light everywhere; no way to turn vibration or the light bar off; neither pad was found over Bluetooth. **Done:** (1) the strengths of section 3 were raised (the old values were 50 to 150 of 255 and fell away linearly: now 140 to 255 and held for three quarters of the effect); how strong they are is still a choice, not a measurement. (2) The two items of section 1. (3) and (4) **Found by reading the code against how Windows names Bluetooth devices, not yet by a pad:** the scan only opened HID paths containing `vid_054c`, which is how a USB device is named; a Bluetooth HID path has `vid&0002054c` (the number before the vendor is the vendor-id source), so every Bluetooth pad was skipped before it was even asked what it was. The filter is now just `054c`, and `HidD_GetAttributes` still decides. Because that is a guess at the cause, **the program now writes what it finds to `logs/shell.log`**: `pad found: <path> (kind, input length, output length)` (kind 4 = DualShock 4, 5 = DualSense; output length +1000 when it is Bluetooth), or why a Sony path was not used (`cannot be opened (error)`, `is not a known pad (vendor, product)`, `first read failed`). If a pad is still not found over Bluetooth, that file says where it stops.

## 7. After the owner's second test (2026-11-25): Bluetooth works; two corrections

Reported: Bluetooth detection and the pads work; (1) choosing Resume Game (or backing out) with A / Cross or B / Circle on the first screen of the pause menu also started the game; (2) Vibration and Light Bar should have three levels and be grayed out when they cannot work.

1. **A button held from the menu no longer reaches the game.** The menu is a pause, and the button that closed it was still down on the first frame after it: the game saw FIRE (or START) and left the attract mode. Now, while any menu is open, the front end sets a hold-off; after the menu closes, every action input (fire on both ports, Start, Select, Option, from the keyboard or a pad) is ignored until all of them have been let go once. Movement is not held back. The same covers Enter on the keyboard.
2. **Vibration and Light Bar are `OFF / LIGHT / HEAVY`** (Right / Enter / Space go Off, Light, Heavy, Off...; Left goes the other way; both start at HEAVY). HEAVY is the strength of section 3; LIGHT is 40 % of the rumble and 35 % of the light bar's brightness (choices, not measurements). **Vibration is grayed out when no pad is connected** (keyboard only); **Light Bar is grayed out and shows OFF (nothing is sent) unless a DualShock 4 or a DualSense is connected** (an XInput pad can rumble but has no light). A grayed-out item cannot be selected or changed (the cursor skips it); the choice made earlier is kept and comes back when a pad is connected.

Checked: `ctest menu_check` (cycle both ways, grayed-out items inert and skipped, text), the real program's `--menutest` (no pad is not the case on the owner's machine: see below). **Not checked with a real pad:** the hold-off with a real button press (the test machine has no way to press one; it is exercised by reading the code and by the keyboard path of `--menutest`) (OV-81).
