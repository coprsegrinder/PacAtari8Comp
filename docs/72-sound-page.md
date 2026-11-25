# 72 - The Sound page of the pause menu (an addition to stage J)

Asked for by the owner on 2026-11-25 (from the list of sound options offered): a **Sound** page in the pause menu with **Master Volume**, **Mute** and an **Output Filter** of three choices. Nothing of the game changes: the settings act only on the sound handed to the speaker, after the game's own sound (and its digest) is made.

Source: `src/c/shell/sound.[ch]` (portable, tested: `ctest sound_check`), `menu.[ch]` (the page), `win_main.c` (the glue). The settings are not saved between runs (as with the rest of the menu).

## 1. The page

Main menu: **Resume Game, Graphics Options, Controls, Sound, Quit Game** (Sound is fourth; Quit Game moved to fifth). Esc on the page goes back to the main menu, on "Sound"; F1 (the help) works from it.

| Item | Choices | Keys |
|---|---|---|
| Master Volume | 0 % to 100 % in steps of 10 (default 100 %) | Left / Right; stops at both ends; Enter does nothing |
| Mute | Off (default) / On | Left / Right / Enter |
| Output Filter | Off / Soft (default) / Warm | Left / Right / Enter, round and round |

**The volume is the program's own gain**, not the Windows volume mixer's (which the program never changes). It is on an audio taper: the gain is the square of the fraction, so 50 % is a quarter of the amplitude (about 12 dB down) and each step is about as loud a step as the next. A change, and Mute, move the gain over one frame of sound, so there is no click.

**The filters.**
- **Off**: the chip's plain output (`audio_frame`): what the game's sound digest is made of. Tones above half the output rate fold down into the hearing range (the start tune's 31.96 kHz rest tone rings at about 12 kHz): this is the raw sound, for comparison.
- **Soft** (the default, and what the program always played): the same chip at four times the rate through a 20 kHz low-pass (`audio_hq`, docs/22), so nothing folds down.
- **Warm**: Soft, then a 5 kHz low-pass and a 140 Hz high-pass (two 2nd-order Butterworth filters, Q 0.707): the cut top and thin bottom of a small TV speaker. The numbers are my choices, not measurements; how it sounds is the owner's to judge.

The Warm filters run on the Soft sound all the time, so choosing Warm starts from settled filters. At the defaults (100 %, not muted, Soft) the sound is bit for bit what it was before the page (checked in `sound_check`, and by the self test's loopback comparison of the handed and the played sound).

## 2. How it was checked

| Check | Where | Result |
|---|---|---|
| The gain taper and its ends; mute; the defaults pass Soft unchanged; Off passes the plain output with its own length; a change of volume moves without a jump; mute gives silence and back; Soft is 0 dB at 1 kHz; Warm is within 1 dB at 1 kHz, over 15 dB down at 12 kHz, 10 dB at 10 kHz, 6 dB at 50 Hz, less than 3 dB down at 3 kHz | `ctest sound_check` | pass |
| The page: the items and their text, the volume stopping at both ends, Enter and the volume, Mute, the filter round and round both ways, the cursor wrapping, F1 from it, Esc back on Sound, Quit Game still last | `ctest menu_check` | pass |
| The real program (`--menutest`): the page opened by real keys in the running game, the settings changed by keys and read back, the game frozen on the page, Esc back on Sound | `--menutest` | see `analysis/evidence-front-end-summary.txt` |
| The game is unchanged: digests of the game recorded through the front end | `tools/check_front_end.py` | see the summary |

## 3. Limits

- **Not heard by a person** (and not to be asked of one: the sound is confirmed by measurement). The filter's response is measured on test tones in `sound_check`; the sound of Warm and the steps of the volume were not played to the real speaker.
- The measurements through the real device (the loopback self test) run at the defaults only.
- Settings are not saved; no Windows-mixer interplay (the mixer's own volume and mute still apply on top).
