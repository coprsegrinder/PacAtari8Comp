"""Stage 66 (core algorithms): the chapter docs/44-core-algorithms.md, from the port-form reference (tools/core_ref.py and the World modules), its data (tools/core_tables.py), the evidence of the checkers (tools/check_*.py)
and the algorithms of docs/31.
Usage: python -I tools/analyze_core.py [--doc docs/44-core-algorithms.md]"""
import inspect
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import core_ref as R  # noqa: E402
import core_tables as T  # noqa: E402


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# area -> (algorithms of docs/31, [(function of core_ref, ROM routine, check row of the evidence)], what is left out of the port form)
AREAS = [
    ("Levels", "A08, A13 (the release timers), A14 (the durations), A20, A19",
     [("pacing_delay / move_delay_tick", "MoveDelayTick `$B590`", "pacing"), ("release_timers", "SetReleaseTimers `$AE2B`", "release_timers"),
      ("fright_frames / fright_end_phase / fright_total_frames", "PowerPelletCheck `$B39F`, FrightenedTick `$AF54`", "frightened"),
      ("bonus_glyph / bonus_points / bonus_popup_glyphs", "BonusItemUpdate `$B62E`, `$A93D`, `$A972`", "bonus")],
     "the level-end sequence, the board set-up and the turn control are state management (`43`), not computation"),
    ("Scoring", "A07, A15, A06 (the values)",
     [("score_add", "AddToScore `$B423`", "score"), ("ghost_points", "GhostEaten `$A886`", "ghost_points"), ("count_dot", "EatDotAtPacMan `$B33A`", "count_dot")],
     "the pictures of the digits"),
    ("Ghost AI", "A09 - A14, A16",
     [("junction_exits", "JunctionLookup `$B48E`", "junction"), ("steer", "SteerToTarget `$B999`", "steer"), ("force_chase", "ForceChase `$B616`", "force_chase"),
      ("power_pellet_ghosts", "PowerPelletCheck `$B39F`", "power_pellet"), ("frightened_end", "FrightenedTick `$AF54`", "frightened_end")],
     "the pictures of the ghosts (core_draw)"),
    ("Pac-Man", "A05, A06, A17", [], "the mouth and the pictures of the death (core_draw)"),
    ("Sound", "A22", [], "nothing"),
]

# the World form: module, what it holds, the checker, the evidence file
MODULES = [
    ("core_ghost", "the ghost state machine: `ghost_behaviour` (start route, patrol travel, patrol, corner, chase, frightened), the sight test, `chase_timer_siren_sight`, `force_chase`, the movement step, the ghost house (`house_waiting_tick`, bob, leave, enter)", "check_ghost", "evidence-ghost-summary.txt"),
    ("core_pacman", "Pac-Man's movement: the joystick, the remembered turn, the cornering flag, one step with the sub-cells, the maze pointer, the tunnel wrap, the chomp phase", "check_pacman", "evidence-pacman-summary.txt"),
    ("core_score", "the score cells and the extra life, the lives icons, eating a dot, the dot count, the power pellet", "check_score", "evidence-score-summary.txt"),
    ("core_sound", "every sound (dot, bonus, frightened, eyes, siren, eaten-ghost pause, start tune) and the death (`death_sequence`, `death_animation`) with their register writes", "check_sound", "evidence-sound-summary.txt"),
    ("core_frame", "`frightened_tick`, `ghost_eaten`, `eyes_and_house_per_frame`", "check_frame", "evidence-frame-summary.txt"),
    ("core_draw", "**the drawing (OV-69)**: what the drawing routines leave in the player-missile pages, the eight position registers and the picture buffers - the ghosts (`step_and_draw_entity`), Pac-Man (`draw_pacman`, `draw_all_in_place`), the pop-up of an eaten ghost, the death animation, the tunnel clip (`clip_entities_on_tunnel_row`, which also wraps an entity round the tunnel), `clear_player_memory` - the scene of `50`", "check_draw", "evidence-draw-summary.txt"),
    ("core_play", "**one frame of play**: `play_frame` = the frame body of FrameDispatch from `$A82C` (death, eyes, pause, bonus, pellet, contact, frightened tick, sounds, Pac-Man, dot, house, every ghost) and `vbi_play_frame` = the whole deferred handler `$A5FD` for it (the frame body, then the tunnel clip unless the eaten-ghost pause is on), with the drawing", "check_play", "evidence-play-summary.txt"),
]

FINDINGS = [
    ("The extra life is not 'score >= 10,000'", "The check is on the 10,000s **screen cell**, which is blank only while every digit to its left is 0, and the loop tests the **old** cell to its left. So the life is given when the new score is 10,000 or more **or when the old score was 100,000 or more** (a wrap from 999,992 to 1,992 gives a life if none was given). The first version of the port function used `score >= 10000` and the check against the ROM found 605 of 6,000 cases wrong; in a real game the second case cannot happen (the life is given long before 100,000), but a port that tests the number instead of the cell would differ from the ROM on a game that wraps the score."),
    ("The ghost-eaten count is an 8-bit counter, not 0-3", "`GhostsEaten` (`$E9`) starts at `$FF` for a frightened period and is incremented before use: 0 gives 200, 1 gives 400, 2 gives 800 and **every other value gives 1,600** (the fourth ghost, and any value the counter could wrap to). A port that clamps at 3 is right for the game, wrong for a state the ROM does not leave."),
    ("The frightened tables are not clamped", "`fright_frames` and `fright_end_phase` index with the whole 8-bit level counter; past their 15 and 20 entries the lookup reads the ROM and RAM bytes that follow (`14`). The port keeps the full 256-entry images (`tools/core_tables.py`), so boards 16-256 behave as in the ROM: 29 of the 256 levels have no frightened time at all and 14 have an end phase of 0 (practically endless)."),
    ("A frightened ghost that leaves the house loads the chase timer with its own state", "`HouseLeaveStep` at the door row: a ghost whose state has bit 7 set gets state `$82` **and `ChaseTimer` = `$82`** (the code stores the state value into the timer before it sets the direction); a normal ghost does not touch the timer. The port keeps it (`house_leave_step`)."),
    ("`ForceChase`, `BonusSound` and `FrightenedSound` have quirks the port keeps", "`ForceChase` ends with `stx ChaseTimer` with X = `$FF` from its loop; `BonusSound` ends its rising sweep when the pitch is `$B4` **or when adding 5 wraps it to 0** (the same code runs with the wrapped pitch: the first version of the port missed it, 96 of 2,000 calls differed); `FrightenedSound` falls from the rising branch into the falling one when the pitch sum is 0."),
    ("The eaten-ghost pause ends with a step of Pac-Man", "`GhostEatenPause` at its last step clears the sound chip, restores the colours and, when it finds the ghost shown in the pop-up colour (`$DC`), runs `MovePacMan` and `EatDotAtPacMan` once more and sets the cornering flag; the port's `ghost_eaten_pause` does the same."),
    ("The collision registers are not the position registers", "The ROM writes the ghosts' horizontal positions to `HPOSP0-3` (`$D000-$D003`) and reads the collision latches at the same addresses (`M0PF` ..). In the flat memory of the concrete 6502 the second reads back the first, which made the first version of the frame check fail on the bonus pick-up (`M2PF` is `$D002`, the position of ghost 2); the checker now reads `$D000-$D00F` as inputs, as the hardware does, and the port takes them as `w.collide`."),
]


def evidence(rel="analysis/evidence-core-summary.txt"):
    """name -> (what, calls, differences) from an evidence file: lines `name: what: N calls: M differences` (also `N random frames`, `N runs of 20 frames`)"""
    out = {}
    for ln in read(rel).splitlines():
        m = re.match(r"^(\w+(?: x20)?): (.*?): ([\d,]+) (?:calls|random frames|runs of 20 frames)[^:]*: (\d+) differences", ln)
        if m:
            out[m.group(1)] = (m.group(2), int(m.group(3).replace(",", "")), int(m.group(4)))
    return out


def count_functions(mod):
    t = read("tools/%s.py" % mod)
    return len(re.findall(r"^def [a-z]\w*\(", t, re.M))


def chapter():
    ev = evidence()
    funcs = [n for n, f in inspect.getmembers(R, inspect.isfunction) if f.__module__ == "core_ref"]
    pure_calls = sum(v[1] for v in ev.values())
    pure_bad = sum(v[2] for v in ev.values())
    mods = []
    for mod, what, chk, evf in MODULES:
        e = evidence("analysis/" + evf)
        calls = sum(v[1] * (20 if k.endswith("x20") else 1) for k, v in e.items())
        mods.append((mod, what, chk, evf, e, count_functions(mod), calls, sum(v[2] for v in e.values())))
    wcalls = sum(m[6] for m in mods)
    wbad = sum(m[7] for m in mods)
    P = []
    w = P.append
    w("# 44 - Core algorithms (stage 66)")
    w("")
    w("GENERATED by `python -I tools/analyze_core.py --doc docs/44-core-algorithms.md` from the port-form reference (`tools/core_ref.py` and the World modules of section 3), its data (`tools/core_tables.py`, written by `tools/make_core_tables.py`; the World by `tools/make_core_world.py`), the evidence of the checkers (`tools/check_*.py`, run by `tools/run_core_checks.sh`) and the algorithms of `31`; tests: `tests/test_core.py`, `tests/test_core_world.py`. The behaviours and their live evidence are `36`; the state the algorithms work on is `43`; the numbers inside the code are `31`.")
    w("")
    w("## 1. The result")
    w("")
    w("- **The core of the game is written in port form and checked against the ROM.** Two layers: **%d pure functions** on plain values (levels, scoring, the lattice and the steering: section 2) and **%d functions on a named World** (the ghost state machine, Pac-Man, the sound, the death, and `play_frame`, one whole frame of play: section 3). The World has every zero-page variable of the catalogue (`25`) by name, the maze screen and the score cells; there is no memory image and no 6502 address in the logic." % (len(funcs), sum(m[5] for m in mods)))
    w("- **Every function was run against the ROM routine it stands for** on the concrete 6502: **%s calls of the pure functions and %s calls of the World functions, %d differences** (sections 2 and 3). The World checks compare the **whole zero page**, the maze, the status rows, the OS shadows and the **ordered writes to the sound chip** after every call; a misspelt field name is an error, not a silently dropped write." % (format(pure_calls, ","), format(wcalls, ","), pure_bad + wbad))
    w("- `play_frame` also runs 20 frames in a row against the ROM with the state carried by the port itself: the port reproduces the original's game logic frame by frame.")
    w("- **The drawing is in port form too** (OV-69, section 3): the pictures and positions the game leaves in the player-missile pages, the eight position registers and the picture buffers equal the ROM's after every function and after every frame, and so does the tunnel clip that follows the frame (which also moves an entity round the tunnel). That scene is what `50` turns into the collision registers.")
    w("- **What is not in port form** (section 8): the parts of FrameDispatch that are state management rather than game logic - the title and copyright screens, the READY! intro, the level-end sequence, the turn control and the game-over countdown (`43`) - and the drawing of the maze, the status rows and the text.")
    w("")
    w("## 2. The pure functions (`tools/core_ref.py`)")
    w("")
    w("| Area | Function | ROM routine | Calls | Differences |")
    w("|---|---|---|---|---|")
    for area, algs, rows, _ in AREAS:
        for fn, rom, key in rows:
            what, n, bad = ev[key]
            w("| %s | `%s` | %s | %s | %d |" % (area, fn, rom, format(n, ","), bad))
    w("")
    w("The checks vary what the ROM reads: **every level 0-255** for the pacing, the release timers, the frightened tables and the bonus; every phase 1-255 against every level's end phase; the whole length of 242 frightened periods counted frame by frame; every x on the ten lattice rows for the exits; random positions, targets, states and masks with the same `RANDOM` values for the steering (the number of values used must be equal too).")
    w("")
    w("## 3. The World form")
    w("")
    w("| Module | What it holds | Checker | Functions | Calls | Differences |")
    w("|---|---|---|---|---|---|")
    for mod, what, chk, evf, e, nfun, calls, bad in mods:
        w("| `%s` | %s | `%s` | %d | %s | %d |" % (mod, what, chk, nfun, format(calls, ","), bad))
    w("")
    w("What each checker compares after every call: the whole zero page except the declared temporaries (`Scratch2A`, `SrcPtr`, `DstPtr`, `zp_A5`: the mask between the lattice lookup and the steering, the pointers of the drawing), the maze, the status rows (the score), the OS shadows (colours, `GPRIOR`), **the player-missile pages `$2300-$27FF`, the eight positions `$D000-$D007` and the picture buffers `$0400-$041F`**, the ordered writes to the sound chip and `HITCLR`, and the number of `RANDOM` values read. The collision registers `$D000-$D00F` are **inputs** of `play_frame` (`w.collide`), the joystick shadows `STICK0-3` are inputs of `move_pacman` (`w.stick`).")
    w("")
    w("The rows of each checker:")
    w("")
    w("| Checker | Row | What | Calls | Differences |")
    w("|---|---|---|---|---|")
    for mod, what, chk, evf, e, nfun, calls, bad in mods:
        for k, (txt, n, b) in e.items():
            w("| `%s` | `%s` | %s | %s | %d |" % (chk, k, txt[:150].replace("|", "/"), format(n, ","), b))
    w("")
    w("## 4. What the comparison found")
    w("")
    for h, t in FINDINGS:
        w("- **%s.** %s" % (h, t))
    w("")
    w("## 5. The five areas of the checklist")
    w("")
    w("| Area | Algorithms (`31`) | Pure functions | World form | Left out |")
    w("|---|---|---|---|---|")
    world = {"Levels": "`move_delay_tick`, `bonus_item_update`, `frightened_tick` (core_play, core_frame)", "Scoring": "`add_to_score`, `eat_dot`, `count_dot`, `power_pellet_check`, `ghost_eaten` (core_score, core_frame)",
             "Ghost AI": "`ghost_behaviour` and the five state routines, `ghost_sees_pacman`, `chase_timer_siren_sight`, the house, `eyes_and_house_per_frame`, `ghost_eaten` (core_ghost, core_frame)",
             "Pac-Man": "`move_pacman`, the contact test and the bonus pick-up in `play_frame`, `death_sequence`, `death_animation` (core_pacman, core_play, core_sound)",
             "Sound": "`dot_sound_sweep`, `bonus_sound`, `frightened_sound`, `eyes_returning_sound`, `siren`, `ghost_eaten_pause`, `start_tune_step`, `death_sequence` (core_sound)"}
    for area, algs, rows, rest in AREAS:
        w("| %s | %s | %s | %s | %s |" % (area, algs, ", ".join("`%s`" % r[0].split(" ")[0] for r in rows) or "-", world[area], rest))
    w("")
    w("## 6. The numbers, as the port reference gives them")
    w("")
    w("Per level (0 = board 1; the pacing is clamped at 6, the bonus at 12, the release timers at 3, the frightened tables are not clamped):")
    w("")
    w("| Level | Pac-Man frames per step (cycle) | Ghost frames per step (cycle) | Release timers (ghosts 1-3, x4 frames) | Frightened: solid frames / end phase / total | Bonus: glyph / points |")
    w("|---|---|---|---|---|---|")
    for lv in list(range(0, 8)) + [12, 15, 20]:
        pc = [R.pacing_delay(4, lv, c) for c in range(4)]
        gc = [R.pacing_delay(0, lv, c) for c in range(4)]
        tot = R.fright_total_frames(lv)
        w("| %d | %s | %s | %s | %d / %d / %s | `$%02X` / %d |" % (lv, ",".join(map(str, pc)), ",".join(map(str, gc)), ", ".join("$%02X" % x for x in R.release_timers(lv)), R.fright_frames(lv), R.fright_end_phase(lv), tot if tot is not None else "endless", R.bonus_glyph(lv), R.bonus_points(lv)))
    w("")
    w("Constants: a dot is 10 points, a power pellet 50, the ghosts of one frightened period 200, 400, 800, 1,600; a board is complete at 260 dots and pellets (`DOTS_PER_BOARD`); the four power pellets stand at (y, x) = %s." % ", ".join("(`$%02X`, `$%02X`)" % p for p in R.PELLET_SQUARES))
    w("")
    w("## 7. For the port")
    w("")
    w("- Translate `tools/core_ref.py` and the World modules function by function: the names of the World are the catalogue's (`25`), the structures of `30` group them; the tables are `tools/core_tables.py` (generated). Keep the **unclamped** frightened lookups and the quirks of section 4.")
    w("- `play_frame(w, rnd)` is the frame loop of the game proper. A port's frame function takes the same inputs (the state, the joystick, the collision registers, the `RANDOM` source) and must leave the same state and make the same sound-chip writes; the checkers' random states and the 20-frame runs are its tests, and the same `tools/check_*.py` run with the ROM replaced by the port decide equivalence (OV-02).")
    w("- The collision registers need a rule: the original reads the hardware's player-missile collision latches; a port without that hardware computes the same two tests (missile 1 and 2 of a ghost against Pac-Man's player: both set, and the vertical distance under 5) from the positions, and the bonus pick-up (missile 2 on playfield 1) from the maze cell.")
    w("")
    w("## 8. Limits")
    w("")
    w("- Concrete 6502 (`tools/cpu6502.py`), not the live game: the live evidence of each area is in `36`; the functions inherit it through the routines they reproduce.")
    w("- Random samples, not proofs, where the input space is large (the ghost behaviour, the frame, the sounds: 1,500 to 40,000 random states a row); exhaustive for the level tables, the pacing, the junction rows and the frightened phases.")
    w("- The random states are those of the project's frame set-ups (entities on lattice cells, ghosts in every documented state, every counter around its thresholds). States the game cannot reach are out of scope: a siren step of 0 loops for ever in the ROM, and a maze pointer outside the maze is a fault of the state (the checker skips such runs and counts them).")
    w("- Left out of the port form: the drawing of the maze, the status rows and the text (the cells the game writes are in the World; their pictures are the renderer's), and the frame logic that is state management: the title and copyright screens, the READY! intro, the level-end sequence, the turn control and the game-over countdown (`43` describes their effect on the state by experiment, `34` their rules).")
    w("- The hardware's collision registers share their addresses with the horizontal-position registers the code writes; the checkers read them as inputs, as the hardware does.")
    w("- OV-67 (the port form of the ghost state machine, Pac-Man and the sound) is closed by this chapter; OV-02, the equivalence of a real port, stays open.")
    return chr(10).join(P) + chr(10)


def main():
    if "--doc" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--doc") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(chapter())
    print(chapter()[:3000])


if __name__ == "__main__":
    main()
