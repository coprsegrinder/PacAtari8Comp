"""Stage 40: the relationships between the routines - which subsystem each belongs to, which subsystem calls which, and in what ORDER things run (start-up, the interrupts, one frame of play).

The subsystem and role of each routine is written down here (SUBSYSTEM, ROLE: from the chapters 13-22 and the reads / writes of docs/23-function-table.md); the dependency matrix and the orders are derived
from the code by tools/analyze_functions.py.  tests/test_relationships.py checks that every routine has exactly one subsystem and that the document is up to date.
Usage: python -I tools/analyze_relationships.py [--write docs/24-function-relationships.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402

ROOT = os.path.dirname(HERE)

SUBSYSTEMS = collections.OrderedDict([
    ("BOOT", ("Start-up and the main loop", "cartridge entry, the one-time set-up, the key loop (`$A4BA-$A559`)", "21")),
    ("DECOMP", ("Data decompression", "the helpers that expand the packed maze and charset streams at start-up", "12")),
    ("INT", ("Interrupts and display", "the vertical-blank and display-list interrupt handlers, display lists, the tunnel-edge clip", "06, 15, 16")),
    ("FRAME", ("The per-frame dispatcher", "`Sub_A6CC`: the deferred VBI routine that is the whole game in one: title states 1-4 and the game frame", "21")),
    ("TITLE", ("Title, status line, labels, high score", "the score row, the 1UP / 2UP labels, the title score clearing, the high-score compare", "19, 21")),
    ("BOARD", ("Game, board and level set-up", "new game, new board, level advance, the lives and level indicators, two-player turn switching, the maze copies", "14, 19, 20, 21")),
    ("PAC", ("Pac-Man and the dots", "Pac-Man's step, the dot and power-pellet pick-up, his animation phase", "20")),
    ("MAZE", ("Maze items", "power-pellet blink, the bonus item", "14, 15")),
    ("DEATH", ("Death", "the death sequence and animation", "20")),
    ("GHOST", ("Ghost AI", "state machine, steering, junction lookup, move delays, timers, drawing", "13, 17, 18")),
    ("HOUSE", ("Ghost house and the eyes' return", "waiting, leaving, the eaten ghost's way home", "18")),
    ("FRIGHT", ("Frightened and eaten ghosts", "power-pellet effects, the frightened clock, a ghost eaten and the pop-up pause", "18")),
    ("SCORE", ("Score", "BCD score addition, the extra life", "12, 22")),
    ("SOUND", ("Sound", "POKEY writes that are not inline (the dot, bonus and frightened sounds, clearing the registers)", "22")),
])

# address -> (subsystem, role).  The 39 routines that were called Sub_XXXX got their names from this table's roles on 2026-11-14 (tools/labels.py, ROM_NAMES).
ROLE = {
    0xA386: ("BOOT", "cartridge RUN entry: sets up the machine, decompresses the data, starts a game ($A537) and loops on the keys"),
    0xA6B4: ("BOOT", "cartridge INIT entry: just RTS"),
    0xA668: ("DECOMP", "expand a packed stream through SrcPtr / DstPtr"),
    0xA69C: ("DECOMP", "read one source byte"),
    0xA69E: ("DECOMP", "advance the source pointer"),
    0xA6A5: ("DECOMP", "write one destination byte and advance"),
    0xA6AE: ("DECOMP", "read a byte, high nibble"),
    0xA573: ("INT", "display-list interrupt of the maze screen (colour bands, CHBASE)"),
    0xA5CE: ("INT", "display-list interrupt of the title screen"),
    0xA5FD: ("INT", "deferred vertical-blank handler: calls the dispatcher and the tunnel clip"),
    0xA610: ("INT", "title display: clears HPOS / audio registers, installs DisplayList2 and DliHandler2, loads the title colours"),
    0xA6B5: ("INT", "install a display list (X, Y = address) and its DLI vector"),
    0xAB48: ("INT", "for each entity on y = $74 call the clip"),
    0xAB57: ("INT", "mask the picture at the tunnel edges and wrap X (docs/16, OV-31)"),
    0xA6CC: ("FRAME", "the deferred VBI routine - title states 1-4 (draw), and in state 0 the whole game frame"),
    0xA632: ("TITLE", "clear the scores to '00' in title state 3 (one player)"),
    0xA64E: ("TITLE", "the same for two players (also draws both labels)"),
    0xAB26: ("TITLE", "copy the player's score to the high score when it is larger (game over)"),
    0xAD69: ("TITLE", "blink the label of the player on turn every 16th jiffy"),
    0xAD87: ("TITLE", "draw '2UP' at $2021"),
    0xAD9F: ("TITLE", "draw '1UP' at $2004"),
    0xADAF: ("BOARD", "InitBoard: draw the board, clear sprites, load colours and the release timers"),
    0xADF1: ("BOARD", "lives 3, Level := StartLevel, first board of a game"),
    0xAE02: ("BOARD", "copy the original maze, reset the counters and release timers for the player's level"),
    0xAE1E: ("BOARD", "dots eaten, pellets, bonus counter of player X"),
    0xAE2B: ("BOARD", "SetReleaseTimers: the ghost-house release timers for the level"),
    0xB113: ("BOARD", "LoadShadowColors: the eight colour shadows"),
    0xB11F: ("BOARD", "Copy0800To0C00: restore the maze from the stored original"),
    0xB13D: ("BOARD", "Copy0C00To1000: save the maze of player 1"),
    0xB15B: ("BOARD", "Copy0C00To1400: save the maze of player 2"),
    0xB0F1: ("BOARD", "clear the player / missile pages"),
    0xB100: ("BOARD", "fill the five pages $2300-$27FF with A"),
    0xAC75: ("BOARD", "AdvanceLevel: level complete - next board"),
    0xAC93: ("BOARD", "DrawLevelIndicator: the fruit row in the bottom line"),
    0xAA2D: ("BOARD", "after a death or at the READY wait - switch players, load / save mazes, game over"),
    0xAD0E: ("BOARD", "Pac-Man and ghosts in place, lives drawn"),
    0xAD15: ("BOARD", "the lives icons of the player on turn"),
    0xAD42: ("BOARD", "store X into the second lives cell(s)"),
    0xAD45: ("BOARD", "store X into the first lives cell"),
    0xAD49: ("BOARD", "draw the four ghosts and Pac-Man without moving them (DrawOnly = 1)"),
    0xAD5E: ("BOARD", "clear the READY! row ($0DED)"),
    0xB179: ("PAC", "MovePacMan: read the joystick, steer and step Pac-Man"),
    0xB33A: ("PAC", "the dot or pellet in Pac-Man's cell: clear, count, score, sound"),
    0xB39F: ("PAC", "is Pac-Man on one of the four power-pellet squares whose flag is set (then `PowerPelletEaten`)"),
    0xAC05: ("PAC", "ToggleLegPhase: the animation phase of ghosts' feet every 16th jiffy"),
    0xB54F: ("MAZE", "show / hide the four power-pellet cells"),
    0xB55A: ("MAZE", "set the four cells from the player's pellet flags"),
    0xB62E: ("MAZE", "BonusItemUpdate: the bonus item appears at 80 and 160 dots and vanishes"),
    0xAE3D: ("DEATH", "DeathSequence: the freeze, the death sound and the ghosts hidden"),
    0xAEF7: ("DEATH", "DeathAnimation: the 16 frames of Pac-Man's death"),
    0xB7F5: ("GHOST", "GhostBehaviour: one step of a ghost by its state"),
    0xB827: ("GHOST", "GhostStartRoute: walk the start route"),
    0xB851: ("GHOST", "GhostSelectPatrol: pick a patrol route"),
    0xB878: ("GHOST", "GhostPatrolTravel: walk to the patrol start"),
    0xB89A: ("GHOST", "GhostPatrol: walk the patrol route"),
    0xB8C5: ("GHOST", "GhostGoToCorner: go to the corner"),
    0xB8EF: ("GHOST", "GhostChase: chase Pac-Man (flee when frightened)"),
    0xB999: ("GHOST", "SteerToTarget: choose the direction at a junction"),
    0xBA19: ("GHOST", "GhostSeesPacMan: the sight test"),
    0xB48E: ("GHOST", "JunctionLookup: the exits of the junction under an entity (C = at a junction)"),
    0xB902: ("GHOST", "StepAndDrawEntity: move one step and draw the picture"),
    0xB590: ("GHOST", "MoveDelayTick: the speed pacing of an entity"),
    0xB5C7: ("GHOST", "three per-frame jobs: ChaseTimer falls every 8th jiffy; the siren step 2..5 and, late in the board (dots eaten >= $E0 / $F0), `ForceChase`; the sight test of every ghost in state $08 / $10"),
    0xB616: ("GHOST", "late board - ghosts into chase, ChaseTimer = $FF"),
    0xB69E: ("HOUSE", "every frame: each eaten ghost (bit 6, not yet at the door, not the one in the pop-up) steers to the door square (124,100) and steps, state $44 at the door; `EyesReturningSound` while any are returning; then the ghosts in house states walk: $44 entering every frame (`HouseEnterStep`), $04 leaving every 4th jiffy"),
    0xB738: ("HOUSE", "up the door column, state $01 at the door row"),
    0xB76D: ("HOUSE", "ghost 2 leaving the house (it starts left of the door): if X = $7C then `HouseLeaveStep` (up), else one step right; chosen by `HouseWaitingTick` and `EyesAndHousePerFrame` by the ghost number"),
    0xB777: ("HOUSE", "ghost 3 leaving the house (it starts right of the door): if X = $7C then `HouseLeaveStep` (up), else one step left"),
    0xB781: ("HOUSE", "an eaten ghost ($44) inside the house, every frame: down the door column to y = $74, then sideways to its own x (ghost 2: $70, ghost 3: $88; ghosts 0 and 1 stay at $7C), then state $04 and its colour back ($B760)"),
    0xB7A5: ("HOUSE", "ghosts 1-3 waiting in the house (state $00 / $80), every 4th jiffy: the release timer falls and the ghost bobs (`HouseBobStep`); at 0 it leaves: ghost 3 `HouseLeaveGhost3`, ghost 2 `HouseLeaveGhost2`, ghost 1 `HouseLeaveStep`"),
    0xB7D6: ("HOUSE", "the bobbing step"),
    0xB3DE: ("FRIGHT", "PowerPelletEaten: bit 7 for every ghost, reversal, the frightened clock, 50 points"),
    0xA886: ("FRIGHT", "GhostEaten: state $42, the pop-up, the score, the freeze"),
    0xAF54: ("FRIGHT", "the frightened clock, flashing and the end of the time"),
    0xB02C: ("SOUND", "the sound of the eaten ghosts on their way home: AUDF2 steps 13..23 (`EyesSoundStep`), AUDC2 $A4; played by `EyesAndHousePerFrame` while any eyes are returning (`EyesReturning`)"),
    0xB049: ("FRIGHT", "the pause after a ghost is eaten: `EatPauseTick` / `EatPausePitch` count down with the sound; at the end ($B085) it restores COLOR3, GPRIOR = $11 and the eaten ghost's colour ($DC -> $0C), moves Pac-Man once and goes on at `EatDotAtPacMan`; reached by a jump from `FrameDispatch` ($A840, `EatPause` <> 0), not by a call"),
    0xB423: ("SCORE", "AddToScore: add the BCD digits to the score, the extra life"),
    0xAFD7: ("SOUND", "the sound of the frightened phase"),
    0xB0BC: ("SOUND", "the dot-eaten sweep"),
    0xABC9: ("SOUND", "the bonus-eaten sound"),
    0xB0E6: ("SOUND", "ClearPokeyRegisters: silence the eight audio registers"),
}

# one frame of play: the call order of the dispatcher in the code, annotated with its guard (read from src/asm/pacman.s)
FRAME_NOTES = {
    0xA79C: "sound switched off (`Paused`): silence the audio and stop",
    0xA7B5: "(tail) the other label",
    0xA79F: "every frame of state 0 (after the countdown byte `CountdownTimer` is stepped every 8th jiffy; sound off -> `ClearPokeyRegisters` and stop)",
    0xA7B2: "READY / game-over countdown (`CountdownActive` = 1): redraw the labels",
    0xA7BC: "level complete (`LevelComplete` set): the level-end sequence at $AC18 (see below)",
    0xA7D0: "start of a board (`IntroRequest` = 2): the level indicator",
    0xA7FB: "the start tune finished (step $28): lives and ghosts in place",
    0xA802: "start of play (`PlayStarted` set, $A800: first move)",
    0xA80D: "after a death (`WaitState` = 1): the turn control",
    0xA82C: "normal frame (`WaitState` = 0): power-pellet blink",
    0xA833: "Pac-Man is dying (`DeathState` <> 0)",
    0xA836: "(tail) the death animation, then the frame ends",
    0xA839: "not dying: eaten ghosts home and the house",
    0xA840: "ghost-eaten pause (`EatPause` <> 0): jump to `GhostEatenPause` and end the frame",
    0xA843: "the bonus item",
    0xA846: "the power-pellet test (Pac-Man on one of the four pellet squares)",
    0xA883: "contact loop ($A851): a ghost touches Pac-Man -> eaten ($A886) or death ($A923)",
    0xA920: "(tail) the ghost-eaten score, ends the frame",
    0xA929: "death ($A923): silence the audio",
    0xA989: "bonus item eaten ($A936): its score",
    0xA994: "after the contacts (`DeathState` = 0): the frightened clock",
    0xA99B: "unless the pause is on: the dot sound sweep",
    0xA99E: "the bonus sound",
    0xA9A1: "the feet phase",
    0xA9B2: "Pac-Man's speed pacing (X = 4), unless the pause flags `PacCornering` / `DotDelay`",
    0xA9BB: "Pac-Man steps",
    0xA9C2: "the dot at his cell",
    0xA9CB: "every 4th jiffy: the waiting ghosts in the house",
    0xA9CE: "ChaseTimer, the siren, the sight tests",
    0xAA08: "the ghost loop X = 3..0 (ghosts at state $00 / $80, waiting in the house, are skipped; GhostTimer falls every 8th jiffy): frightened ghosts and ghosts on the tunnel row act on every second run-out of the pacing",
    0xAA1F: "the other ghosts: the speed pacing",
    0xAA26: "the ghost's behaviour step",
}


RENAMED = {0xA632, 0xA64E, 0xA6CC, 0xAA2D, 0xAB26, 0xAB48, 0xAB57, 0xABC9, 0xAD0E, 0xAD15, 0xAD42, 0xAD45, 0xAD49, 0xAD5E, 0xAD69, 0xAD87, 0xAD9F, 0xADF1, 0xAE02, 0xAE1E,
           0xAF54, 0xAFD7, 0xB02C, 0xB0BC, 0xB0F1, 0xB100, 0xB33A, 0xB39F, 0xB54F, 0xB55A, 0xB5C7, 0xB616, 0xB69E, 0xB738, 0xB76D, 0xB777, 0xB781, 0xB7A5, 0xB7D6}      # the routines that were Sub_XXXX


def label(F, e):
    """the routine's name (all routines are named since 2026-11-14; the old Sub_XXXX labels are in tools/labels.py)"""
    return F[e].name


def build():
    rom, F = AF.analyse()
    AF.solve(rom, F)
    missing = [F[e].name for e in F if e not in ROLE]
    extra = [hex(a) for a in ROLE if a not in F]
    return rom, F, missing, extra


def report(rom, F):
    L = []
    P = L.append
    sub_of = {e: ROLE[e][0] for e in F}
    P("# 24 - The Relationships between the Routines (stage 40)")
    P("")
    P("GENERATED by `python -I tools/analyze_relationships.py --write docs/24-function-relationships.md`; the subsystem and the role of each routine are written in the tool (from chapters 13-22 and the reads / writes of `23-function-table.md`), everything else is derived from the code. Tests: `tests/test_relationships.py`. The 39 routines that were `Sub_XXXX` were named from these roles on 2026-11-14 (`tools/labels.py`; the old label is in the comment of each name, and in section 2 below).")
    P("")
    P("## 1. The subsystems")
    P("")
    P("| Subsystem | What it does | Routines | Bytes | Chapters |")
    P("|---|---|---|---|---|")
    size = collections.Counter()
    cnt = collections.Counter()
    for e, f in F.items():
        cnt[sub_of[e]] += 1
    for a in rom.ins:                       # an instruction belongs to the routine with the smallest body that contains it (a tail-called routine owns its own code, not the caller)
        owner = min((e for e in F if a in F[e].body), key=lambda e: (len(F[e].body), e))
        size[sub_of[owner]] += rom.ins[a][0]
    for k, (title, what, ch) in SUBSYSTEMS.items():
        P("| **%s** (%s) | %s | %d | %d | %s |" % (title, k, what, cnt[k], size[k], ch))
    P("")
    P("(Bytes: each instruction is counted once, for the routine with the smallest body that contains it, so that a routine reached by a tail jump owns its own code; %d of %d code bytes in all.)" % (sum(size.values()), sum(v[0] for v in rom.ins.values())))
    P("")
    P("## 2. Every routine, its subsystem and its role")
    P("")
    P("| Address | Name | Was | Subsystem | Role |")
    P("|---|---|---|---|---|")
    for e in sorted(F):
        was = "Sub_%04X" % e if e in RENAMED else ""
        P("| `$%04X` | %s | %s | %s | %s |" % (e, F[e].name, was, sub_of[e], ROLE[e][1]))
    P("")
    P("## 3. Which subsystem calls which")
    P("")
    P("Calls and tail jumps between routines, counted per call site, rows = caller, columns = callee (a routine calling itself or its own subsystem is shown on the diagonal).")
    P("")
    mat = collections.defaultdict(collections.Counter)
    for e, f in F.items():
        for site, c in f.calls.items():
            if c in F:
                mat[sub_of[e]][sub_of[c]] += 1
        for c in f.tail:
            if c in F:
                mat[sub_of[e]][sub_of[c]] += 1
    keys = list(SUBSYSTEMS)
    P("| caller \\ callee | " + " | ".join(keys) + " |")
    P("|---|" + "---|" * len(keys))
    for k in keys:
        P("| **%s** | " % k + " | ".join(str(mat[k][c]) if mat[k][c] else "" for c in keys) + " |")
    P("")
    leaf = [k for k in keys if not any(mat[k][c] for c in keys if c != k)]
    P("Subsystems that call nothing outside themselves: %s." % ", ".join(leaf))
    P("")
    P("| Subsystem | calls into |")
    P("|---|---|")
    for k in keys:
        into = ["%s (%d)" % (c, mat[k][c]) for c in keys if c != k and mat[k][c]]
        P("| %s | %s |" % (k, ", ".join(into) or "-"))
    P("")
    P("## 4. In what order things run")
    P("")
    P("### 4.1 Start-up (the code of `Start` in address order)")
    P("")
    P("```")
    seen = []
    for a in sorted(F[0xA386].body):
        n, m, mode, op = rom.ins[a]
        if m == "jsr" and a >= 0xA43E:
            P("$%04X  jsr %s" % (a, rom.names.get(op, "$%04X" % op)))
    P("```")
    P("")
    P("Before these: the two `ExpandData` calls at `$A42B` / `$A43E` unpack the maze and charset (with `ReadSrcByte` / `ReadSrcHighNibble` / `WriteDstByte` / `AdvanceSrcPtr`), `SETVBV` installs the VBI at `$A460`. `$A477` is the **new-game entry** (`$A537` jumps here): clear the audio, restore and save both mazes, install the maze display list, `InitBoard`, `Sub_ADF1`, the title score clearing; then the key loop `$A4BA` runs for ever, and the whole game happens in the interrupt-time routines below (`docs/21`).")
    P("")
    P("### 4.2 At interrupt time")
    P("")
    P("1. **Display-list interrupts** (`DliHandler1`: the maze bands, `DliHandler2`: the title) change colours and `CHBASE` at scanlines (docs/15).")
    P("2. **Vertical blank** (`VbiHandler`, deferred): `FrameDispatch` (`Sub_A6CC`), then `Sub_AB48` (the tunnel clip) unless the pause flag `EatPause` is set.")
    P("3. `FrameDispatch` by the state `GameState`: 0 = the game frame (4.3), 1 = the copyright screen, 2 = wait, 3 = the title, 4 = the title after a game (docs/21).")
    P("")
    P("### 4.3 One frame of play (state 0), in the order of the code")
    P("")
    P("Every call of `FrameDispatch` at or after `$A78C`, in address order, with the condition that leads to it (read from `src/asm/pacman.s`). Calls inside a routine reached by a tail jump belong to that routine.")
    P("")
    P("| Address | Call | When |")
    P("|---|---|---|")
    f = F[0xA6CC]
    for a in sorted(f.body):
        if a < 0xA78C or a > 0xAA2C:
            continue
        n, m, mode, op = rom.ins[a]
        if m in ("jsr", "jmp") and op in F:
            P("| `$%04X` | %s %s | %s |" % (a, m, label(F, op), FRAME_NOTES.get(a, "")))
    P("")
    P("What the order means: the **death and the pause** are tested before anything moves; the **contacts** (ghost eaten or Pac-Man caught, then the bonus item) come before the sounds and the movement; **Pac-Man moves first, then the dot at his cell, then the house and the ghost timers, then the ghosts one by one from ghost 3 to ghost 0**. So a ghost always sees Pac-Man's new position, and a contact found in a frame concerns the positions drawn at the end of the frame before.")
    P("")
    P("### 4.4 The sequences that cross frames")
    P("")
    P("- **New game**: `$A537` -> `$A477` (clear, copy mazes, `InitBoard`, `NewGameInit`) -> READY! with the start tune (`IntroRequest` = 2 steps, `DrawReadyScreen` at step $28) -> `$A800` first move (docs/21).")
    P("- **Ghost eaten**: contact -> `GhostEaten` ($A886: state $42, score, `EatPause` pause) -> `GhostEatenPause` ($B049, a block reached by a jump from the dispatcher) counts the pause down 32-33 frames -> colours restored; the eyes then walk home in `EyesAndHousePerFrame` (docs/18).")
    P("- **Death**: contact -> `$A923` -> `DeathSequence` (97 frames of freeze, ghosts hidden) -> `DeathAnimation` (16 frames) -> `TurnControl` (switch players or game over) -> the READY! wait (docs/20, 19).")
    P("- **Level complete**: `LevelComplete` (the last dot) -> `$AC18`: `ClearPokeyRegisters`, `DrawAllInPlace` (the entities drawn in place), ..., `InitBoard` (`$AC6F`), then `AdvanceLevel` (`$AC75`: `NewBoardInit`, `DrawLevelIndicator`, `DrawReadyScreen`) (docs/14, 20).")
    P("")
    return L


def main():
    rom, F, missing, extra = build()
    if missing or extra:
        sys.exit("routines without a role: %s; roles for no routine: %s" % (missing, extra))
    txt = "\n".join(report(rom, F)) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
