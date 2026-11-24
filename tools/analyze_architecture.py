"""Checklist stage 4 (stages 61-68): the architecture document docs/48-architecture.md - how the game is built and how one frame runs, and what a port is made of - generated from the routines of the ROM (tools/absint6502.py, `23`,
`24`), the port-form modules (tools/core_*.py, tools/platform_iface.py, tools/asset_pack.py) and the curated text of this file.  Every routine of the ROM is classified against the port (ROUTINE_PORT), every port function named
there must exist, and the order of the calls of the running-game frame in the ROM must be the order of `core_play.play_frame` (checked by tests/test_architecture.py).
Usage: python -I tools/analyze_architecture.py [--doc docs/48-architecture.md]"""
import ast
import importlib
import os
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import analyze_relationships as AR  # noqa: E402
import output_map as O  # noqa: E402
import platform_iface as PI  # noqa: E402,F401
import core_world as W  # noqa: E402

F = O.PROG.F
PORT, PART, NOT, LAYER, ASSET = "port form", "partly", "not in port form", "platform / renderer", "asset pack"

# every routine of the ROM against the port: name -> (status, port reference or None, what it becomes)
ROUTINE_PORT = OrderedDict([
    # boot
    ("Start", (NOT, None, "the start-up expansion is the asset pack (`47`); the key loop and the new-game sequence are the application glue over the `Platform` (`45`, `46`)")),
    ("Init", (LAYER, None, "a bare `RTS`: nothing")),
    # interrupts and display
    ("VbiHandler", (LAYER, "platform_iface.run_frame", "the once-per-frame call")),
    ("DliHandler1", (LAYER, None, "five colour / character-set changes per game frame at fixed lines (`35`): the renderer's band table")),
    ("DliHandler2", (LAYER, None, "the same on the title screen")),
    ("InitDisplay2", (LAYER, None, "the title screen's display set-up")),
    ("SetDisplayList", (LAYER, None, "display-list and interrupt vector set-up")),
    ("ClipEntitiesOnTunnelRow", (PORT, "core_draw.clip_entities_on_tunnel_row", "the pictures cut at the tunnel mouths, and an entity that has gone round wraps (state: `EntityX`, Pac-Man's `MazePtr`); runs after the frame unless the eaten-ghost pause is on (`core_play.vbi_play_frame`)")),
    ("ClipEntityAtTunnel", (PORT, "core_draw.clip_entity_at_tunnel", "the same, one entity")),
    # decompression
    ("ExpandData", (ASSET, None, "done once, at build time: the pack's pictures and tables equal the RAM `Start` builds (`47`, check 4)")),
    ("ReadSrcByte", (ASSET, None, "part of the decompression")),
    ("AdvanceSrcPtr", (ASSET, None, "part of the decompression")),
    ("WriteDstByte", (ASSET, None, "part of the decompression")),
    ("ReadSrcHighNibble", (ASSET, None, "part of the decompression")),
    # frame
    ("FrameDispatch", (PART, "core_play.play_frame", "the running-game frame (class 15, with death and the eaten pause: classes 13, 14) is `play_frame`; the title, copyright, intro, countdown, level-end and turn-control classes are not in port form (`44`, section 7)")),
    # title and status row
    ("TitleClearScores1P", (NOT, None, "status-row drawing")),
    ("TitleClearScores2P", (NOT, None, "status-row drawing")),
    ("CompareHighScore", (NOT, None, "the high-score rule (a status-row compare)")),
    ("BlinkPlayerLabel", (NOT, None, "status-row drawing: the 1UP / 2UP blink")),
    ("DrawLabel1UP", (NOT, None, "status-row drawing")),
    ("DrawLabel2UP", (NOT, None, "status-row drawing")),
    # board
    ("TurnControl", (NOT, None, "the two-player turn switch: effects measured in `43` (resets / keeps / computes)")),
    ("AdvanceLevel", (NOT, None, "the level-end step to the next board: effects measured in `43`")),
    ("DrawLevelIndicator", (NOT, None, "drawing the fruit row; its content is `core_ref.bonus_glyph`")),
    ("DrawReadyScreen", (NOT, None, "drawing READY!")),
    ("DrawLives", (PORT, "core_score.draw_lives", "the lives icons of the status row")),
    ("LifeIcon1", (PORT, "core_score.draw_lives", "inside `DrawLives`")),
    ("LifeIcon2", (PORT, "core_score.draw_lives", "inside `DrawLives`")),
    ("DrawAllInPlace", (PORT, "core_draw.draw_all_in_place", "the four ghosts drawn where they stand, then Pac-Man's full disc")),
    ("ClearReadyText", (NOT, None, "drawing")),
    ("InitBoard", (NOT, None, "state initialisation: `InitBoard` writes 114 constants (`43`, section 4)")),
    ("NewGameInit", (NOT, None, "state initialisation (`43`)")),
    ("NewBoardInit", (NOT, None, "state initialisation (`43`)")),
    ("ClearPlayerCounters", (NOT, None, "state initialisation (`43`)")),
    ("SetReleaseTimers", (PORT, "core_ref.release_timers", "the ghost-house release timers by level")),
    ("ClearPlayerMemory", (PORT, "core_draw.clear_player_memory", "the five pages to 0, rows $F0-$FF to $FE")),
    ("FillPlayerPages", (PORT, "core_draw.fill_player_pages", "the byte A into rows X-$FF of the five pages")),
    ("LoadShadowColors", (LAYER, None, "colour set-up")),
    ("Copy0800To0C00", (NOT, None, "new board: the maze of the asset pack into the working maze")),
    ("Copy0C00To1000", (NOT, None, "two-player turn switch: save player 1's maze")),
    ("Copy0C00To1400", (NOT, None, "two-player turn switch: save player 2's maze")),
    # death
    ("DeathSequence", (PORT, "core_sound.death_sequence", "the death state machine with its sound")),
    ("DeathAnimation", (PORT, "core_sound.death_animation", "the death animation's counters and pictures")),
    # frightened
    ("GhostEaten", (PORT, "core_frame.ghost_eaten", "a ghost is eaten: score, pause, eyes, the pop-up picture")),
    ("FrightenedTick", (PORT, "core_frame.frightened_tick", "the frightened countdown and its phases")),
    ("GhostEatenPause", (PORT, "core_sound.ghost_eaten_pause", "the pause after a ghost is eaten, with its sound")),
    ("PowerPelletEaten", (PORT, "core_score.power_pellet_check", "50 points, the frightened period, the ghosts turn")),
    # sound
    ("BonusSound", (PORT, "core_sound.bonus_sound", "the bonus sweep")),
    ("FrightenedSound", (PORT, "core_sound.frightened_sound", "the frightened-mode sound")),
    ("EyesReturningSound", (PORT, "core_sound.eyes_returning_sound", "the returning-eyes sound")),
    ("DotSoundSweep", (PORT, "core_sound.dot_sound_sweep", "the dot sound")),
    ("ClearPokeyRegisters", (PORT, "core_sound.clear_pokey", "silence")),
    # Pac-Man
    ("ToggleLegPhase", (PORT, "core_sound.toggle_leg_phase", "the ghosts' feet row phase")),
    ("MovePacMan", (PORT, "core_pacman.move_pacman", "joystick, buffered turn, step, tunnel wrap, the mouth picture and the four missiles")),
    ("EatDotAtPacMan", (PORT, "core_score.eat_dot", "dot: 10 points, count, sound")),
    ("PowerPelletCheck", (PORT, "core_score.power_pellet_check", "Pac-Man on a pellet square")),
    # score
    ("AddToScore", (PORT, "core_score.add_to_score", "BCD score, the extra life")),
    # maze
    ("BlinkPowerPellets", (PORT, "core_play.blink_power_pellets", "the pellets blink every 16 jiffies")),
    ("ShowPowerPellets", (PORT, "core_play.show_power_pellets", "draw the pellets still on the board")),
    ("BonusItemUpdate", (PORT, "core_play.bonus_item_update", "the bonus item appears at 80 and 160 dots")),
    # ghosts
    ("JunctionLookup", (PORT, "core_ghost.junction_lookup", "the lattice: exits at a junction")),
    ("MoveDelayTick", (PORT, "core_play.move_delay_tick", "speed pacing")),
    ("ChaseTimerSirenSight", (PORT, "core_ghost.chase_timer_siren_sight", "the shared chase timer, the siren, the sight test")),
    ("ForceChase", (PORT, "core_ghost.force_chase", "all ghosts chase")),
    ("GhostBehaviour", (PORT, "core_ghost.ghost_behaviour", "the ghost state machine")),
    ("GhostStartRoute", (PORT, "core_ghost.ghost_start_route", "leaving the house")),
    ("GhostSelectPatrol", (PORT, "core_ghost.ghost_select_patrol", "choosing a patrol route")),
    ("GhostPatrolTravel", (PORT, "core_ghost.ghost_patrol_travel", "travelling to the route start")),
    ("GhostPatrol", (PORT, "core_ghost.ghost_patrol", "patrolling")),
    ("GhostGoToCorner", (PORT, "core_ghost.ghost_go_to_corner", "going to a corner")),
    ("GhostChase", (PORT, "core_ghost.ghost_chase", "chasing")),
    ("StepAndDrawEntity", (PORT, "core_ghost.step_entity", "the movement step and the ghost's picture (`core_draw`)")),
    ("SteerToTarget", (PORT, "core_ghost.steer_to_target", "the choice of direction")),
    ("GhostSeesPacMan", (PORT, "core_ghost.ghost_sees_pacman", "the sight test")),
    # house
    ("EyesAndHousePerFrame", (PORT, "core_frame.eyes_and_house_per_frame", "eyes returning, the house, the whistle")),
    ("HouseLeaveStep", (PORT, "core_ghost.house_leave_step", "leaving the house")),
    ("HouseLeaveGhost2", (PORT, "core_ghost.house_leave_ghost2", "leaving the house, ghost 2")),
    ("HouseLeaveGhost3", (PORT, "core_ghost.house_leave_ghost3", "leaving the house, ghost 3")),
    ("HouseEnterStep", (PORT, "core_ghost.house_enter_step", "eyes entering the house")),
    ("HouseWaitingTick", (PORT, "core_ghost.house_waiting_tick", "the waiting ghosts' release")),
    ("HouseBobStep", (PORT, "core_ghost.house_bob_step", "the ghosts bobbing in the house")),
])

# the Platform of `45` and the pieces the application glue is made of (not routines of the ROM)
LAYERS = [
    ("Platform", "`tools/platform_iface.py`", "the 14 declared inputs in, the frame's outputs out (`45`)", "`tests/test_iface.py`; closure over 3,000 states (`45`)"),
    ("Core", "`tools/core_*.py`", "`play_frame`, `vbi_play_frame` and the functions they compose: 18 pure functions, the World-form routines and the drawing (`44`)", "243,000 calls + 8,000 frames + 500 runs of 20 frames against the ROM, the drawing included: 0 differences (`44`)"),
    ("State", "`tools/core_world.py`", "the `World`: 181 fields (the zero-page variables by name, the maze, the status rows, the shadows, the player-missile pages and positions, the inputs, the sound-chip writes) (`43`, `44`)", "round trip with the memory image; a misspelt name is an error (`tests/test_core_world.py`)"),
    ("Resources", "`tools/asset_pack.py`", "pictures, maze, text, tunes, tables, font in one schema (`47`)", "equal to the RAM `Start` builds; all 2,246 non-code bytes (`47`)"),
    ("Application", "(to be written)", "the key loop, the title / intro / level-end / turn-control / countdown states, the new-game sequence, the drawing", "the oracles of `34`, `38`, `43` (measured sessions)"),
]

PLAY_ORDER_FIRST = 0xA82C
PLAY_ORDER_LAST = 0xAA26


def rom_frame_order():
    """the calls of the running-game frame in the ROM, in address order: [(call site, routine name)]"""
    fd = F[0xA6CC]
    return [(site, F[t].name) for site, t in sorted(fd.calls.items()) if PLAY_ORDER_FIRST <= site <= PLAY_ORDER_LAST]


def port_frame_order():
    """the calls of `core_play.play_frame` in source order, the two local helpers `_contact_and_bonus` and `_pick_up_bonus` expanded: [function name]"""
    path = os.path.join(HERE, "core_play.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    out = []

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Call):
                for a in child.args:
                    visit(a)
                f = child.func
                name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
                if name in ("_contact_and_bonus", "_pick_up_bonus"):
                    visit(funcs[name])
                elif name:
                    out.append(name)
                visit(f)
            else:
                visit(child)
    visit(funcs["play_frame"])
    return out


def port_function_of(routine):
    ref = ROUTINE_PORT[routine][1]
    return ref.split(".")[-1] if ref else None


def check_refs():
    """-> list of problems: every routine classified, every port reference importable"""
    bad = []
    names = {f.name for f in F.values()}
    for n in names:
        if n not in ROUTINE_PORT:
            bad.append("routine %s is not classified" % n)
    for n, (status, ref, note) in ROUTINE_PORT.items():
        if n not in names:
            bad.append("%s is not a routine of the ROM" % n)
        if status in (PORT, PART) and not ref:
            bad.append("%s: %s without a port function" % (n, status))
        if ref:
            mod, fn = ref.split(".")
            try:
                if not callable(getattr(importlib.import_module(mod), fn)):
                    bad.append("%s is not callable" % ref)
            except (ImportError, AttributeError):
                bad.append("%s does not exist" % ref)
    return bad


def frame_table():
    rows = []
    seen = set()
    for site, name in rom_frame_order():
        status, ref, note = ROUTINE_PORT[name]
        rows.append((site, name, ref or "-", status, name in seen))
        seen.add(name)
    return rows


def stats():
    sub = {f.name: AR.ROLE[e][0] for e, f in F.items()}
    by = {}
    for n, (st, ref, note) in ROUTINE_PORT.items():
        by.setdefault(sub[n], []).append((n, st))
    return sub, by


def chapter():
    sub, by = stats()
    c = Counter(st for st, ref, note in ROUTINE_PORT.values())
    nport, npart = c[PORT], c[PART]
    refs = {ref for st, ref, note in ROUTINE_PORT.values() if ref and st == PORT}
    P = []
    w = P.append
    w("# 48 - Architecture (checklist stage 4: stages 61-68)")
    w("")
    w("GENERATED by `python -I tools/analyze_architecture.py --doc docs/48-architecture.md` from the routines of the ROM (`23`, `24`), the port-form modules and the curated text of `tools/analyze_architecture.py`; tests: `tests/test_architecture.py`. This chapter **puts together** what stages 61-70 measured (`37`, `38`, `41`-`47`): how the original is built, how one frame runs, which part of it exists in port form and checked, and what a port is made of. The owner decisions of stages 71-74 (taken 2026-11-18, `49`) are section 9; sections 5-7 are written to them.")
    w("")
    w("## 1. The result")
    w("")
    w("- **The game is one frame function and a poll.** Everything the game does runs in **one deferred interrupt per video frame** (`FrameDispatch`, 15 frame classes, a play frame 37 scan lines of 262 at the median); the main program is a **key loop** that never returns and does no game logic; five display-list interrupts per frame only change colours and character-set pages (`38`, `46`).")
    w("- **The boundary is closed and small**: 14 inputs in, the chips out, two OS calls, nothing else (`45`); the inside shares a listed set of variables between its five contexts (`46`).")
    w("- **The core is already a port**: of the %d routines of the ROM, **%d are in port form** (%d port functions, checked against the ROM: 0 differences) and **%d more partly**; the rest are the renderer, the platform layer, the asset pack and the application glue (section 4)." % (len(ROUTINE_PORT), nport, len(refs), npart))
    w("- **What is missing is specified, not just absent**: the title, intro, level-end, turn-control and countdown frame logic, the key loop and the drawing are the application layer (section 5); their effects on the state are measured (`43`), their timing is measured (`38`), their frames are the oracles.")
    w("- **A layered architecture follows from the evidence** (section 2): *Platform* (inputs, outputs, clock) - *Core* (`play_frame` over the World) - *State* (the World) - *Resources* (the asset pack) - *Application* (states and drawing). Section 6 proposes how `src/c` mirrors it; section 7 says how it is tested.")
    w("")
    w("## 2. The program in one picture")
    w("")
    w("```mermaid")
    w("flowchart TB")
    w("    subgraph HW[Hardware and OS]")
    w("        OSVBI[OS vertical blank: clock, stick and trigger shadows, shadow to chip copy]")
    w("        KB[keyboard interrupt: CH]")
    w("        CHIPS[ANTIC / GTIA / POKEY]")
    w("    end")
    w("    subgraph GAME[The cartridge: five contexts on one CPU]")
    w("        KEY[main program: key loop A4BA]")
    w("        NEW[new-game sequence A477]")
    w("        VBI[deferred VBI A5FD: FrameDispatch, 15 classes]")
    w("        DLI[display-list interrupts A573 / A5CE]")
    w("    end")
    w("    OSVBI -->|once a frame| VBI")
    w("    KB --> KEY")
    w("    KEY <-->|12 hand-over variables| VBI")
    w("    KEY --> NEW")
    w("    NEW -->|initialises the state| VBI")
    w("    VBI -->|writes| CHIPS")
    w("    DLI -->|colours, CHBASE| CHIPS")
    w("    VBI -.->|DliColors, ItemColor| DLI")
    w("```")
    w("")
    w("The same program as a port is made of five layers (section 5). The thin line between them is the `Platform` of `45`:")
    w("")
    w("```mermaid")
    w("flowchart LR")
    w("    P[Platform: 14 inputs, clock, RANDOM, collisions] --> C[Core: play_frame and its routines]")
    w("    C --> S[State: the World, 181 fields]")
    w("    R[Resources: asset pack, font] --> C")
    w("    C --> O[Outputs: sound-chip writes, maze and status cells, colours, sprite state]")
    w("    A[Application: key loop, title, intro, level end, turn control, drawing] --> P")
    w("    A --> C")
    w("    O --> A")
    w("```")
    w("")
    w("## 3. How one frame runs")
    w("")
    w("**Timeline of one NTSC frame** (262 scan lines; `35`, `38`):")
    w("")
    w("1. **Vertical blank (line 248 on)**: the OS reads the joystick, triggers and clock into the shadows, copies the colour, DMA and display-list shadows to the chips, counts the attract mode, then jumps through `VVBLKD` to the game's handler. The handler is entered at line 256 in every frame (`38`).")
    w("2. **The handler** `VbiHandler` `$A5FD`: clears the band counter, steps the key-debounce counter, calls `FrameDispatch`, then (unless a ghost-eaten pause is on) the tunnel clip, then returns through `XITVBV`. A **play frame takes a median of 37 lines (maximum 103)**; the heaviest frame of all, a level end, 234 lines, which leaves 28 lines to the next vertical blank (PAL: 122 of 312 lines, OV-62).")
    w("3. **Five display-list interrupts** (game screen: lines 39, 47, 207, 215, 231; title: 47, 87, 127, 143, 215): each changes colours or `CHBASE` for the band that follows (`35`). They only read the four band colours, `ItemColor` and the attract values (`46`).")
    w("4. **The rest of the frame** belongs to the key loop: the colour refresh, the keys, the console, the pause, the game-over countdown (`38`).")
    w("")
    w("**`FrameDispatch` decides in this order** and the first class that applies is the frame (`38`, section 4; frames seen in the 7 measured sessions):")
    w("")
    w("| # | Frame class | Frames seen | In the port |")
    w("|---|---|---|---|")
    for n, cls, seen, st in (
            (1, "copyright setup", 7, NOT), (2, "copyright wait", 745, NOT), (3, "title menu", 13650, NOT), (4, "title after game", 9232, NOT), (5, "paused", 300, "trivial: `clear_pokey`"),
            (6, "board start", 17, NOT), (7, "game-over countdown", 13444, NOT), (8, "level end", 7480, NOT), (9, "start idle", 59, "trivial"), (10, "start tune", 4411, "partly: `core_sound.start_tune_step`"),
            (11, "turn control", 822, NOT), (12, "ready wait", 6630, NOT), (13, "death", 25488, "**port form**: `death_sequence`, `death_animation`"), (14, "eaten pause", 1023, "**port form**: `ghost_eaten_pause`"),
            (15, "play", 136679, "**port form**: `play_frame`")):
        w("| %d | %s | %s | %s |" % (n, cls, "{:,}".format(seen), st))
    w("")
    w("Classes 13-15 (death, eaten pause, play) are **163,190 of the 219,987 measured frames (74%)**: the frames in which the game is played; the rest is the title, the countdown, the intro and the level end. They are the ones `play_frame` covers and `44` checks.")
    w("")
    w("**The play frame, in the order of the code** (from the call sites of `FrameDispatch` between `$A82C` and `$AA26`; the port function is what `core_play.play_frame` calls, in the same order: `tests/test_architecture.py` compares the two):")
    w("")
    w("| Call site | ROM routine | Port function | Status |")
    w("|---|---|---|---|")
    for site, name, ref, st, again in frame_table():
        w("| `$%04X` | %s%s | %s | %s |" % (site, name, " (again)" if again else "", "`%s`" % ref if ref != "-" else "-", st))
    w("")
    w("The branches between the calls (death, the eaten pause, the contact with a ghost, the bonus pick-up, Pac-Man's pacing and the corner that freezes the ghosts, each ghost's move) are in `play_frame` and are described in `44` (section 3) and `24` (section 4.3). A ghost-eaten pause and a death leave the frame early (`$A833`, `$A840`).")
    w("")
    w("## 4. Subsystems and what is in port form")
    w("")
    w("Each of the %d routines is classified in `tools/analyze_architecture.py`; **%d in port form, %d partly, %d not** (%s):" % (len(ROUTINE_PORT), nport, npart, c[NOT], ", ".join("%d %s" % (v, k) for k, v in c.items() if k not in (PORT, PART, NOT))))
    w("")
    w("| Subsystem | Routines | In port form | Partly | Not in port form | Platform / asset |")
    w("|---|---|---|---|---|---|")
    order = ["BOOT", "INT", "DECOMP", "FRAME", "TITLE", "BOARD", "DEATH", "FRIGHT", "SOUND", "PAC", "SCORE", "MAZE", "GHOST", "HOUSE"]
    for s in order:
        items = by.get(s, [])
        cc = Counter(st for n, st in items)
        w("| %s | %d | %d | %d | %d | %d |" % (s, len(items), cc[PORT], cc[PART], cc[NOT], cc[LAYER] + cc[ASSET]))
    w("")
    w("What the routines **not** in port form are, and where each one goes:")
    w("")
    w("| Routine | Status | What it becomes |")
    w("|---|---|---|")
    for n, (st, ref, note) in ROUTINE_PORT.items():
        if st != PORT:
            w("| %s | %s | %s |" % (n, st, note))
    w("")
    w("## 5. The layers of a port")
    w("")
    w("| Layer | Where | What | Verified by |")
    w("|---|---|---|---|")
    for a, b, c_, d in LAYERS:
        w("| %s | %s | %s | %s |" % (a, b, c_, d))
    w("")
    w("- **Platform**: `Platform.stick / trigger / console / key / key_delay / clock / attract / random / collisions` and `run_frame(w, platform)`. The collision registers are the one input the port must *compute*: the geometry is built and checked against the hardware (OV-68 closed, `50`); it takes the scene the drawing leaves, which is in port form (OV-69 closed, `44`).")
    w("- **Core**: functions of the World, no I/O, no globals; a RANDOM iterator is the only source of randomness; the sound chip is a list of `(register, value)` writes. A function is a unit of test: `core_play.play_frame` is the whole frame.")
    w("- **State**: the 144 state bytes of the 256 (`43`), the maze (920 cells), the status rows, the colour shadows (**one byte of state lives there**: `PCOLR0-3` = `$DC` marks the eaten ghost, `45`). The per-player variables are the `Player[2]` structure (`30`, `43`).")
    w("- **Resources**: the asset pack (`47`): pictures, maze, text, tunes, tables, the font; schema 2.")
    w("- **Application**: what turns inputs and states into frames outside the running game. Its inputs and variables are specified (`46`: the 12 hand-over variables; `43`: what each event resets, keeps and computes); its drawing is the renderer's (`42`); its timing is measured (`38`).")
    w("")
    w("## 6. The layout of `src/c` (decided, stage 74)")
    w("")
    w("*Decided by the owner on 2026-11-18 (`49`): this layout, C99, clang and gcc, CMake.* One C module per Python module of the core, named alike, so that a C function and its Python twin can be compared one to one; the skeleton with its `CMakeLists.txt` and `tests/toolchain_check.c` is in `src/c`:")
    w("")
    w("```")
    w("src/c/")
    w("  platform/   hal.h, hal_*.c         Platform: inputs, clock, RANDOM, collisions; audio and video sinks")
    w("  core/       world.h                the World: 181 fields generated from docs/25 (tools/make_core_world.py writes the Python one)")
    w("              tables.h / .c          the layout of the constant tables (tools/make_c_tables.py); the bytes are installed at start-up from the owner's ROM")
    w("              ref.c                  the 18 pure functions (core_ref.py)")
    w("              ghost.c  house.c  pacman.c  score.c  sound.c  frame.c  play.c")
    w("  assets/     pack loader (schema 2) and the pack builder")
    w("  app/        key loop, title, intro, level end, turn control, countdown, new game (to be written)")
    w("  render/     sprites, bands, colours, mode 4 / 6 drawing (to be written)")
    w("  tests/      differential tests against vectors written by the Python core and by the ROM")
    w("```")
    w("")
    w("## 7. How a port is tested (the oracle chain)")
    w("")
    w("```")
    w("ROM  --(concrete 6502 interpreter)-->  Python core  --(vectors)-->  C core")
    w("  \\                                         |                          |")
    w("   \\--(Altirra sessions: 34, 38, 43)-->      +-- frame-level traces ----+")
    w("```")
    w("")
    w("1. **Unit level**: the 18 pure functions and each World routine, from random states: the Python core against the ROM is already 0 differences (`44`); the C core is compared with the Python core on the **same** state vectors (written by `tools/check_*.py`'s generators), which is exact and fast.")
    w("2. **Frame level**: `play_frame` over 8,000 random frames and 500 runs of 20 frames (`44`); the C core is compared on whole frames (zero page, maze, status rows, shadows, ordered sound-chip writes, RANDOM count).")
    w("3. **Session level**: the traces of the real game (`34`, `38`) - 20 sessions, 15 frame classes, the frame by frame story of a game (`38`, section 6) - are the oracle for the application layer.")
    w("4. **Platform level**: `ScriptedPlatform` (`45`): determinism, inputs through the platform only.")
    w("")
    w("## 8. Not yet specified or checked (the gaps)")
    w("")
    w("- **The application layer** is specified by measurement, not written: frame classes 1-4, 6-9, 11, 12 (`38`), the key loop (`40`), the new game (`43`), drawing (`42`).")
    w("- **The drawing of the maze, the status rows and the text** is not in port form (the cells the game writes are in the World; their pictures are the renderer's). **OV-69 is closed**: the sprite drawing (the player-missile pages, positions and picture buffers) and the tunnel clip are in port form and equal the ROM's (`44`), and the collision geometry turns that scene into the registers (`50`).")
    w("- **OV-02: no C code exists**, so no equivalence claim has been tested against a port; the oracle chain of section 7 is what the port will be tested against.")
    w("- **No race-freedom proof** for the key loop against the frame (`46`): a port that runs them in turn needs none.")
    w("- **PAL**: the data is the same, the frame is 312 lines; the colour hues differ and were not checked (`47`).")
    w("- **The font's provenance** (its glyphs equal the Atari OS font bit for bit) was **accepted as it is by the owner on 2026-11-18** (`49`, `47` section 6); the risk is known and recorded, not removed.")
    w("")
    w("## 9. The owner decisions of stages 71-74 (taken 2026-11-18)")
    w("")
    w("| Stage | Decision | Chosen | What follows |")
    w("|---|---|---|---|")
    w("| 71 | Faithful port or redesign | **faithful frame-by-frame port with a thin hardware layer** | one `play_frame` over the same state; the Python core and the measured sessions stay the oracle (`44`, `38`); the application layer is written to the measured behaviour of `38`, `40`, `43`, `46` |")
    w("| 72 | Equivalence level | **the whole state each frame** | zero page, maze, status rows, colour shadows, the ordered sound-chip writes and the RANDOM count equal the original's every frame: exactly what `44` compares |")
    w("| 73 | Language and toolchain | **C99, clang and gcc, CMake (Ninja)** | `-std=c99`, extensions off, `-Wall -Wextra -Wpedantic -Wconversion -Werror`; MSVC is not installed and not a target now; `tests/toolchain_check.c` builds and passes with clang 19.1 and gcc 14.2 |")
    w("| 74 | Layout of `src/c` | **the layout of section 6** | `platform/ core/ assets/ app/ render/ tests/`, core files named like the Python modules |")
    w("")
    return "\n".join(P) + "\n"


def main():
    bad = check_refs()
    if bad:
        print("problems:", bad)
        return 1
    if "--doc" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--doc") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(chapter())
    else:
        print(chapter())
    return 0


if __name__ == "__main__":
    sys.exit(main())
