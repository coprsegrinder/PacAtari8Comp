"""Stage 95 (behavioural documentation): ONE chapter that records what the ORIGINAL software does - its functionality (the 24 behaviours of `36`), its execution behaviour (the 15 frame classes, the 20 state variables and their 68 rules, the
rules by level), its interfaces (the 14 inputs and the outputs of `45` and `42`) and the known behavioural differences (the original's quirks that the port keeps, the differences between the original and the port, the differences between the machines
the original was run on).  GENERATED from the behaviour table of tools/analyze_correlation.py, the state rules of tools/analyze_states.py, the input list of tools/iface_map.py, the output regions of tools/output_map.py, the level tables through
tools/core_ref.py (the ROM's own tables) and the discrepancy ledger `56`; the curated parts are the tables at the top.
Usage: python -I tools/analyze_behaviour_docs.py [--doc docs/61-behaviour.md]
Tests: tests/test_behaviour_docs.py (the chapter is current; every behaviour, frame class and input is covered; the by-level table is the ROM's)."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import analyze_correlation as AC  # noqa: E402
import analyze_states as S  # noqa: E402
import core_app as APP  # noqa: E402
import core_ref as R  # noqa: E402
import iface_map as I  # noqa: E402
import output_map as O  # noqa: E402

# what the game does, as rules of play (each fact is verified in the chapter named)
RULES_OF_PLAY = [
    ("Board", "A maze of 23 rows of 40 cells with 256 dots and 4 power pellets (260 to eat); the ghost house in the middle, a tunnel on the row at `y = 116` that wraps from `x = 42` to `x = 202`; four ghosts (red, pink, green, gold) and Pac-Man.", "`12`, `14`, `18`, `20`"),
    ("Pac-Man", "Moves in small steps (1 pixel across, 2 down) through the maze cells; turns happen at the lattice of junctions (10 rows by 10 columns); the stick sets the wanted direction, which is buffered until the maze allows it, and can reverse at once; a corner gives a free step; the mouth opens and closes every move.", "`20`, `41`"),
    ("Dots and pellets", "10 points a dot, 50 a power pellet; every dot slows Pac-Man for a frame; the board is complete at 260; an extra life the first time the ten-thousands cell of the score is not blank (at 10,000, or after a wrap).", "`20`, `31`, `44`"),
    ("Ghosts", "Each ghost leaves the house on its own timer (by level), walks a start route, then chases, patrols and goes to its corner by its own timers; at a junction it steers towards its target (away when frightened), breaking ties with RANDOM; it cannot reverse; it sees Pac-Man along its row or column and chases for 160 timer steps.", "`13`, `17`, `31`"),
    ("Frightened ghosts", "A power pellet turns every ghost that is not eaten frightened for a time that depends on the level (and may be none); they turn round, slow down, flash in the last phase, and can be eaten for 200, 400, 800, 1,600 points in a row; an eaten ghost returns to the house as eyes.", "`18`, `14`"),
    ("Bonus item", "A bonus item appears at 80 and again at 160 dots, stays about 704 frames, and is worth 100 to 5,000 points by level; its score picture stays for 64 frames.", "`14`, `15`"),
    ("Lives and death", "Three lives; a ghost that touches Pac-Man while not frightened starts the death: a freeze of 96 frames, a glide of sound, a death animation, then the turn is handled; the game ends when nobody has a life, with a 30-second countdown back to the title.", "`20`, `19`, `21`"),
    ("Two players", "The players alternate by life (each keeps their own maze, score, level and lives); the other player's maze is stored while one plays.", "`19`"),
    ("Levels", "The board counter advances at each completed board; speeds are clamped at level 6, the bonus tables at 12, the frightened tables are read past their end above level 15; ghost speeds and release timers follow the level.", "`14`, `44`"),
    ("Title and menu", "A copyright screen (about 4 seconds), then the title menu: SELECT toggles one or two players, OPTION steps through the start levels (0, 1, 2, 4, 6, 8, 10, 12), START or a trigger begins; a game that ends returns to the title; the space bar pauses.", "`21`, `38`"),
    ("Sound", "A siren that rises with the dots eaten, a dot sound, the frightened and returning-eyes sounds, a bonus sweep, the start tune, the death glide and the ghost-eaten sweep, all on four POKEY channels.", "`22`"),
    ("Attract mode", "After a time without input the OS dims and shifts the colours (`DRKMSK`, `COLRSH`); any stick input or key resets it. The game has no demonstration mode: a long idle at the title only dims the colours (`55`).", "`33`, `45`"),
]

# the frame classes: what the game does in each, from docs/38 section 4
FRAME_CLASSES = [
    ("copyright setup", "the copyright screen is drawn once (`GameState` 1, then 2)"),
    ("copyright wait", "waits for its time (255 frames), or a console key"),
    ("title menu", "the menu: SELECT, OPTION, START, trigger"),
    ("title after game", "the menu after a game (the high score is shown)"),
    ("paused", "the space bar has paused: the chip is silenced and nothing moves"),
    ("board start", "the READY! intro begins"),
    ("game-over countdown", "the 30-second countdown: labels blink, a key or trigger starts a game"),
    ("level end", "the five steps: the frozen board, a wait, the maze flashes, the new board is set up, the next level"),
    ("start tune", "the start tune plays while READY! is on the screen (260 frames)"),
    ("start idle", "the board is set up and the start tune has not begun: the frame before it (one frame)"),
    ("turn control", "after a death or a level: lives, the other player's maze, the wait"),
    ("ready wait", "the READY! wait before play (130 frames)"),
    ("death", "the death freeze, sound glide and animation (`DeathState` 1 to 6)"),
    ("eaten pause", "the pause after a ghost is eaten: the pop-up score, the sweep sound"),
    ("play", "one frame of the game: blink, sound, ghosts, Pac-Man, dots, collisions, drawing"),
]

# the quirks of the original that the port keeps
QUIRKS = [
    ("The extra life is decided by the screen cell of the ten-thousands digit, not by the number", "it is also given at a score wrap from 999,992 to 1,992", "`44`"),
    ("The ghost count of a frightened period is an 8-bit counter that starts at `$FF`", "the points of the n-th ghost are 200, 400, 800, 1,600 and 1,600 for every one after", "`31`, `44`"),
    ("The level-dependent tables are indexed past their ends above level 15", "the frightened time and end phase on boards 16 to 255 are whatever bytes follow the table", "`14`, `44`"),
    ("`NewBoardInit` sets the release timers from `level + 1` but skips them at level 255", "the `iny` wraps to 0", "`C-104`"),
    ("`PCOLR0-3` = `$DC` carries which ghost was eaten across the pause", "a colour shadow used as a variable", "`45`"),
    ("`InitDisplay2` writes 16 bytes into the ROM and a black band-1 colour writes `$D111`", "ignored by the machine", "`42`"),
    ("A race at `$A800` (ghost 0 incremented twice)", "a path of the search that no game can take", "`34`"),
    ("A console key that changes within a frame of its first being seen is read or not, by which instruction the interrupt lands on", "the original's behaviour depends on the timing of the change", "`55`"),
]

# the environments the original was run in and what differed
ENVIRONMENTS = [
    ("NTSC, Atari 800, OS Rev B (Altirra 4.40)", "the reference of every measurement", "`05`, `22`, `38`"),
    ("PAL timing (312 lines, 50 Hz)", "the same game at 50 frames a second: the handler takes 122 of 312 lines; timers in frames, so the game runs 1/6 slower in real time; the sound pitches differ", "`38`, C-24 to C-27"),
    ("The PAL OS and Altirra's built-in OS (historical: the project now uses only the NTSC OS ROM)", "the same behaviour: the game takes only the clock, the shadow registers and two OS calls from the OS", "`37`, `45`, C-25, C-26"),
    ("Real hardware", "not tested: a documented limit", "OV-01, C-27"),
]


def level_rows():
    rows = []
    for lv in list(range(0, 14)) + [16, 20, 255]:
        tot = R.fright_total_frames(lv)
        rt = R.release_timers(lv)
        rows.append((lv, R.fright_frames(lv), R.fright_end_phase(lv), "" if tot is None else tot, R.bonus_points(lv), "%d / %d / %d" % rt))
    return rows


def section3_of_ledger():
    path = os.path.join(ROOT, "docs", "56-discrepancy-analysis.md")
    with open(path, encoding="utf-8") as fh:
        t = fh.read().splitlines()
    out = []
    on = False
    for l in t:
        if l.startswith("## 3."):
            on = True
            continue
        if on and l.startswith("## "):
            break
        if on and l.startswith("|"):
            out.append(l)
    return out


def doc():
    L = []
    P = L.append
    P("# 61 - Behaviour of the Original (checklist stage 95)")
    P("")
    P("GENERATED by `python -I tools/analyze_behaviour_docs.py --doc docs/61-behaviour.md` from the behaviour table of `36`, the state rules of `34`, the input list of `45`, the output regions of `42`, the ROM's own level tables (through `tools/core_ref.py`) and the ledger `56`; the rules of play, the frame-class table, the quirks and the environments are tables in the tool. Tests: `tests/test_behaviour_docs.py`.")
    P("")
    P("Checklist stage 95: \"Record the original software's functionality, execution behaviour, interfaces, and known behavioural differences.\" This chapter says **what the original does**, in terms a player or a porter can read; every sentence names the chapter that proves it. The structure of the program is `58`, the binary `59`, the data `60`.")
    P("")
    P("## 1. Functionality: the rules of play")
    P("")
    P("| Part | What the game does | Proved in |")
    P("|---|---|---|")
    for a, b, c in RULES_OF_PLAY:
        P("| %s | %s | %s |" % (a, b, c))
    P("")
    P("Points: a dot %d, a power pellet %d, the ghosts of one frightened period %s; the bonus item %s by level (section 3.3)." % (10, 50, ", ".join("{:,}".format(R.ghost_points(i)) for i in range(4)), "100 to {:,}".format(max(R.bonus_points(l) for l in range(0, 13)))))
    P("")
    P("## 2. The behaviours, one by one")
    P("")
    P("The game is cut into **%d behaviours**; each has its rule (the chapter), its live evidence (register entries C-nn: sessions of the real game in Altirra), and its executable check (tests). `36` ties every one to the routines and algorithms that carry it." % len(AC.BEHAVIOURS))
    P("")
    P("| # | Behaviour | Algorithms | Rule in | Live evidence | Tests |")
    P("|---|---|---|---|---|---|")
    for b in AC.BEHAVIOURS:
        bid, text, algs, chs, evid, sess, tests = b
        P("| %s | %s | %s | %s | %s | %d |" % (bid, text.replace("|", "/"), ", ".join(algs), ", ".join("`%s`" % c for c in chs), ", ".join(evid[:3]) + (" ..." if len(evid) > 3 else ""), len(tests)))
    P("")
    P("## 3. Execution behaviour")
    P("")
    P("### 3.1 The frame")
    P("")
    P("Everything the game does happens in one of **15 frame classes**, chosen every frame by the dispatcher from the state (`38`):")
    P("")
    P("| Class | What the frame does |")
    P("|---|---|")
    for n, t in FRAME_CLASSES:
        P("| %s | %s |" % (n, t))
    P("")
    P("A frame is 1/60 s on NTSC (262 lines; the handler gets 16,100 cycles on the game screen, 19,750 on the title; a play frame costs at most 14,278 in the heaviest case found, `39`). The handler never ran late in any measured session (219,987 frames, `38`).")
    P("")
    P("### 3.2 The state")
    P("")
    P("**%d state variables** carry the game from frame to frame; **%d rules** say how each may change (`34`); every rule was seen in the real game and no change was seen that a rule does not allow." % (len(S.STATES), len(S.RULES)))
    P("")
    P("| Variable | Values | Rules |")
    P("|---|---|---|")
    for a, name, size, meaning in S.STATES:
        n = sum(1 for r in S.RULES if r[0] == name)
        P("| `%s`%s | %s | %d |" % (name, " x %d" % size if size > 1 else "", "; ".join("%s = %s" % (("$%02X" % k), v[:42]) for k, v in list(meaning.items())[:4]) + (" ..." if len(meaning) > 4 else ""), n))
    P("")
    P("### 3.3 By level")
    P("")
    P("From the ROM's own tables (`14`). Levels are counted from 0 (the first board). The frightened time is the solid-colour frames plus the flashing phases; **0 frames of solid colour with an end phase of 11 or 7 still frightens the ghosts for the flashing phases**; from level 16 the tables are read past their ends (the real game's behaviour, kept). Release timers are for ghosts 1, 2, 3 in units of 4 frames.")
    P("")
    P("| Level | Frightened: solid frames | End phase | Frightened in all (frames) | Bonus points | Release timers |")
    P("|---|---|---|---|---|---|")
    for lv, fr, ep, tot, bp, rt in level_rows():
        P("| %d | %d | %d | %s | %d | %s |" % (lv, fr, ep, tot, bp, rt))
    P("")
    P("Speeds: the move-delay tables are indexed by the level clamped at 6, for Pac-Man and for the ghosts separately; a ghost is slower in the tunnel and while frightened (`13`, `14`).")
    P("")
    P("## 4. Interfaces")
    P("")
    P("The game's whole boundary is a closed list (`45`): **%d inputs** and the outputs below; no file, serial, network or PIA access." % len(I.INPUTS))
    P("")
    P("| Input | Address | What it is |")
    P("|---|---|---|")
    for name, lo, hi, dev, who, what in I.INPUTS:
        P("| `%s` | `$%04X` | %s |" % (name, lo, what.replace("|", "/")))
    P("")
    outs = [r for r in O.REGIONS if r[0] in O.OUTPUT]
    P("**Outputs** (`42`): the screen (the maze band, the status rows, the title: %s), the player-missile pages (Pac-Man, the four ghosts, the pop-up score), the character sets, the colour and position registers, and the sound. The regions the game writes: %s. **Timing contract**: one handler run per frame, display-list interrupts on fixed lines (game screen 39, 47, 207, 215, 231; title 47, 87, 127, 143, 215), the collision registers latched since the last `HITCLR`." % (
        ", ".join("`$%04X-$%04X`" % (lo, hi) for n, lo, hi, k in outs if n in ("MazeScreen", "TitleScreen", "StatusRows")), ", ".join(n for n, lo, hi, k in outs)))
    P("")
    P("## 5. Known behavioural differences")
    P("")
    P("### 5.1 Quirks of the original (the port keeps them)")
    P("")
    P("| Quirk | Effect | Chapter |")
    P("|---|---|---|")
    for a, b, c in QUIRKS:
        P("| %s | %s | %s |" % (a, b, c))
    P("")
    P("### 5.2 Differences between the original and the port")
    P("")
    P("From the ledger of `56` (section 3 there; the port equals the original in the whole state after every frame on 709,116 compared frames):")
    P("")
    for l in section3_of_ledger():
        P(l)
    P("")
    P("### 5.3 Differences between the environments the original ran in")
    P("")
    P("| Environment | What differs | Evidence |")
    P("|---|---|---|")
    for a, b, c in ENVIRONMENTS:
        P("| %s | %s | %s |" % (a, b, c))
    P("")
    P("## 6. How this was checked")
    P("")
    P("- The rules of play, the behaviours and the state rules were measured on the real game in the emulator (sessions of 4 to 220,000 frames, `32`-`40`), proved by abstract interpretation where a claim is about every state (`34`), and compared with models run against the ROM (`31`, `44`).")
    P("- The port reproduces them: **709,116 frames** compared with the ROM in the whole state, and the frame classes, the state changes and the outputs on 171,300 frames (`52`-`56`).")
    P("- This chapter is regenerated from the tables it cites: `tests/test_behaviour_docs.py` fails if a behaviour, a frame class or an input is not covered or if the by-level table is not the ROM's.")
    return "\n".join(L) + "\n"


def main():
    text = doc()
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o) if not os.path.isabs(o) else o, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote", o)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
