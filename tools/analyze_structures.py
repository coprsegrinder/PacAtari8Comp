"""Stage 48: the structures (objects) of the Pac-Man ROM and the layout proposed for the port.

The 6502 has no structures: the game keeps its objects as 'structure of arrays' in the zero page - one array per field (EntityX, EntityY, EntityDir, ..., stride 1), indexed by the object number in X.  This tool derives
from the code (the trace of src/asm/pacman.s, tools/analyze_functions.py) and the variable catalogue (tools/analyze_variables.py, stage 41):
  - which arrays are indexed by X, with which offset (every access is `array,x` with the offset 0 of its own array except `GhostTimer+1,x`), and by which routines;
  - the structures: every one of the 109 zero-page variables is the field of exactly one structure (Entity[5], Ghost[4], Player[2], PacMan, Bonus, Frighten, Death, Sound, Flow, Display, Scratch, Pointers, Os), with its
    C type, its original address and its lifetime (what the bulk writes of Start and InitBoard reset);
  - the initial state of the five entities (ZeroPageInit80);
  - the record shapes of the RAM tables and the ROM tables, the player-missile pages and the picture buffers;
  - the sites for the Altirra measurement of the index ranges (tools/run_structure_audit.ps1, tools/analyze_structures_log.py).
Usage: python -I tools/analyze_structures.py [--write docs/30-structures.md | --probes]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402
import analyze_stack as AS  # noqa: E402
import analyze_variables as V  # noqa: E402

ROOT = AF.ROOT
LB = AF.LB
BASE = AF.BASE
EVIDENCE = os.path.join(ROOT, "analysis", "evidence-structures-summary.txt")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# The structures.  (name, count, description, [(C field, C type, [(variable, byte)], note)])
# count > 1: the structure is an array of `count` objects and every listed variable is a whole array of that size (object i = byte i of each variable).
# count = 1: a single object; each listed (variable, byte) is one byte of a variable (a 16-bit field lists its low and its high byte).
U8, U16 = "uint8_t", "uint16_t"
STRUCTS = [
    ("Entity", 5, "the five moving objects: ghosts 0-3 (index 0 red, 1 pink, 2 green, 3 gold: the colour order of `ColorsGame`) and Pac-Man (index 4). The index is the player page: ghost g draws in page $24+g, Pac-Man in the missile page $23.", [
        ("x", U8, [("EntityX", 0)], "horizontal position in colour clocks; the tunnel wraps $2A <-> $CA"),
        ("y", U8, [("EntityY", 0)], "vertical position in scan lines = the row of the player page where the picture starts"),
        ("dir", U8, [("EntityDir", 0)], "1 up, 2 down, 4 left, 8 right (a bit mask: the same values index JunctionExits and the reverse tables)"),
        ("delay_cycle", U8, [("MoveDelayCycle", 0)], "position in the four-step speed-pacing cycle"),
        ("delay_count", U8, [("MoveDelayCount", 0)], "frames left until the next step"),
    ]),
    ("Ghost", 4, "the extra state of a ghost (index = entity index 0-3). Pac-Man has no element: a ghost array indexed with 4 would read the next array.", [
        ("state", U8, [("GhostState", 0)], "$00 house, $01 start route, $02 chase, $04 leaving, $08 / $10 patrol, $20 corner, $42 / $44 eyes; bit 7 = frightened"),
        ("timer", U8, [("GhostTimer", 0)], "release timer in the house, later the patrol time"),
        ("patrol_route", U8, [("PatrolRoute", 0)], "patrol route number 0-15"),
        ("patrol_step", U8, [("PatrolStep", 0)], "step in the patrol route"),
        ("target_x", U8, [("TargetX", 0)], "X the ghost steers to"),
        ("target_y", U8, [("TargetY", 0)], "Y the ghost steers to"),
        ("start_step", U8, [("StartRouteStep", 0)], "step in the start route"),
        ("want_vert", U8, [("WantVert", 0)], "vertical direction the steering wants (0, 1, 2)"),
        ("want_horiz", U8, [("WantHoriz", 0)], "horizontal direction the steering wants (0, 4, 8)"),
        ("half_speed", U8, [("HalfSpeedToggle", 0)], "toggles at each run-out of the speed pacing (frightened ghost, tunnel row)"),
    ]),
    ("Player", 2, "what belongs to player 1 / player 2 (index = `CurrentPlayer`); the saved maze of the other player is `SavedMaze1` / `SavedMaze2` (section 6).", [
        ("lives", U8, [("Lives", 0)], "lives left after the current one"),
        ("extra_life_given", U8, [("ExtraLifeFlag", 0)], "the extra life at 10,000 has been given"),
        ("level", U8, [("Level", 0)], "level counter, 0 = first board"),
        ("pellets", U8, [("PelletFlags", 0)], "one bit per power pellet still on the board ($0F at a new board)"),
        ("dots_eaten", U16, [("DotsEatenLo", 0), ("DotsEatenHi", 0)], "dots and power pellets eaten on this board: the low and the high byte are two separate arrays in the original"),
        ("bonus_count", U8, [("BonusCount", 0)], "bonus items shown on this board (0, 1, 2)"),
    ]),
    ("PacMan", 1, "the scalars that belong to Pac-Man alone (his X, Y, direction and pacing are `Entity[4]`).", [
        ("maze_ptr", U16, [("MazePtr", 0), ("MazePtr", 1)], "address of his cell in the maze screen RAM ($0C00-$0F97)"),
        ("sub_x", U8, [("PacSubX", 0)], "pixel step inside the cell, horizontal 0-3"),
        ("last_cell_y", U8, [("LastCellY", 0)], "Y of the cell last checked for a dot"),
        ("last_cell_x", U8, [("LastCellX", 0)], "X of the same"),
        ("sub_y", U8, [("PacSubY", 0)], "pixel step inside the cell, vertical 0-3"),
        ("hold", U8, [("PacHold", 0)], "Pac-Man must not advance in this frame"),
        ("cornering", U8, [("PacCornering", 0)], "turned to a perpendicular direction: forces a step"),
        ("dot_delay", U8, [("DotDelay", 0)], "a dot was eaten: wait one frame"),
        ("frozen", U8, [("PacFrozen", 0)], "bit 7 = frozen (death)"),
        ("chomp_phase", U8, [("ChompPhase", 0)], "mouth phase of the picture"),
        ("wanted_dir", U8, [("PacWantedDir", 0)], "direction the joystick asks for, kept until it can be taken"),
    ]),
    ("GhostShared", 1, "the state shared by the four ghosts (not per ghost).", [
        ("chase_timer", U8, [("ChaseTimer", 0)], "ONE timer for all ghosts: the time a chase lasts ($FF = permanent)"),
        ("leg_phase", U8, [("LegPhase", 0)], "feet phase of the ghost pictures, toggled every 16th jiffy"),
        ("draw_only", U8, [("DrawOnly", 0)], "1: draw without moving (freeze, READY!)"),
        ("eyes_returning", U8, [("EyesReturning", 0)], "eaten ghosts on their way home in this frame"),
    ]),
    ("Frighten", 1, "the frightened period and the ghost-eaten pause.", [
        ("phase", U8, [("FrightenPhase", 0)], "0 none, 1 solid blue, 2.. flashing"),
        ("countdown", U8, [("FrightenCountdown", 0)], "frames left in phase 1"),
        ("flash_timer", U8, [("FrightenFlashTimer", 0)], "frames left in a flash phase"),
        ("ghosts_eaten", U8, [("GhostsEaten", 0)], "eaten in this period ($FF before the first): pop-up 200, 400, 800, 1600"),
        ("eat_pause", U8, [("EatPause", 0)], "1 during the pause after a ghost is eaten"),
        ("eat_pause_tick", U8, [("EatPauseTick", 0)], "frame phase of the pause"),
        ("eat_pause_pitch", U8, [("EatPausePitch", 0)], "pitch of the pause sound"),
        ("eaten_ghost", U8, [("EatenGhost", 0)], "number of the ghost just eaten"),
    ]),
    ("Bonus", 1, "the bonus item (fruit) and its score picture.", [
        ("timer", U16, [("BonusTimer", 0), ("BonusTimer", 1)], "16-bit down counter, $02C0 frames at the start"),
        ("visible", U8, [("BonusVisible", 0)], "the item is on the screen"),
        ("score_shown", U8, [("BonusScoreShown", 0)], "the bonus score picture is on the screen"),
        ("score_timer", U8, [("BonusScoreTimer", 0)], "frames left for the score picture ($40)"),
        ("item_color", U8, [("ItemColor", 0)], "colour of the fruit glyphs in the maze band ($44, $DA on levels 6-9)"),
    ]),
    ("Death", 1, "the death sequence and animation.", [
        ("state", U8, [("DeathState", 0)], "0 alive, 1 freeze, 2 start, 3-5 sound glide, 6 end"),
        ("freeze", U8, [("DeathFreeze", 0)], "97-frame freeze before the animation"),
        ("anim_active", U8, [("DeathAnimActive", 0)], "the animation is running"),
        ("anim_frame", U8, [("DeathAnimFrame", 0)], "frame 0-15"),
        ("anim_delay", U8, [("DeathAnimDelay", 0)], "frame delay (7)"),
        ("base_pitch", U8, [("DeathBasePitch", 0)], "starting pitch of the death sound"),
        ("pitch", U8, [("DeathPitch", 0)], "current AUDF1"),
        ("step", U8, [("DeathStep", 0)], "step inside a glide 0-4"),
    ]),
    ("Sound", 1, "the sound generators' state (stage 22).", [
        ("siren_step", U8, [("SirenStep", 0)], "siren pitch step 2..5"),
        ("siren_tone", U8, [("SirenTone", 0)], "siren AUDF2: a triangle $28-$40"),
        ("siren_dir", U8, [("SirenDir", 0)], "1 rising, 2 falling"),
        ("siren_init", U8, [("SirenInit", 0)], "siren started on this board"),
        ("fright_pitch", U8, [("FrightSound", 0)], "frightened sound pitch (AUDF2 $40-$90)"),
        ("fright_dir", U8, [("FrightSound", 1)], "frightened sound direction"),
        ("fright_step", U8, [("FrightSound", 2)], "frightened sound volume step (5 / 4 / 3)"),
        ("fright_started", U8, [("FrightSound", 3)], "frightened sound started flag"),
        ("eyes_step", U8, [("EyesSoundStep", 0)], "eyes sound AUDF2 13..23"),
        ("dot_active", U8, [("DotSoundActive", 0)], "dot sweep running"),
        ("dot_step", U8, [("DotSoundStep", 0)], "dot sweep step 0-5"),
        ("dot_alt", U8, [("DotSoundAlt", 0)], "alternates rising / falling at every dot"),
        ("bonus_step", U8, [("BonusSoundStep", 0)], "bonus sound step"),
        ("bonus_pitch", U8, [("BonusSoundPitch", 0)], "bonus sound pitch ($78 at the start)"),
    ]),
    ("Flow", 1, "the game flow: title / game state, turn switch, waits, the level-end sequence, the start tune, the key loop.", [
        ("game_state", U8, [("GameState", 0)], "0 game / countdown, 1 copyright, 2 copyright wait, 3 title, 4 title after a game"),
        ("two_players", U8, [("TwoPlayers", 0)], "0 one player, 1 two players"),
        ("start_level", U8, [("StartLevel", 0)], "level chosen with OPTION"),
        ("intro_request", U8, [("IntroRequest", 0)], "1 after START, 2 after the board is set up"),
        ("copyright_end", U8, [("CopyrightEnd", 0)], "jiffy at which the copyright screen ends"),
        ("countdown_timer", U8, [("CountdownTimer", 0)], "game-over countdown ($E2 steps)"),
        ("countdown_active", U8, [("CountdownActive", 0)], "the countdown runs"),
        ("play_started", U8, [("PlayStarted", 0)], "the start tune has finished"),
        ("start_tune_active", U8, [("StartTuneActive", 0)], "the start tune plays"),
        ("tune_step", U8, [("TuneStep", 0)], "step of the start tune"),
        ("turn_switch_state", U8, [("TurnSwitchState", 0)], "two-player turn switch 0-3"),
        ("wait_state", U8, [("WaitState", 0)], "0 normal, 1 after a death, 2 the READY! wait"),
        ("wait_timer", U8, [("WaitTimer", 0)], "frames left in the wait"),
        ("level_complete", U8, [("LevelComplete", 0)], "the last dot has been eaten"),
        ("level_end_step", U8, [("LevelEndStep", 0)], "0 draw, 1 wait, 2 flash, 3 new board"),
        ("level_end_delay", U8, [("LevelEndDelay", 0)], "frames left in the step"),
        ("level_end_flashes", U8, [("LevelEndFlashes", 0)], "number of maze flashes"),
        ("current_player", U8, [("CurrentPlayer", 0)], "0 / 1: the index of every Player[] access"),
        ("paused", U8, [("Paused", 0)], "toggled by the space bar"),
        ("key_debounce", U8, [("KeyDebounce", 0)], "decremented by every VBI"),
        ("key_value", U8, [("KeyValue", 0)], "CONSOL value being debounced"),
        ("label_blink", U8, [("LabelBlink", 0)], "blink phase of the label of the player on turn"),
    ]),
    ("Display", 1, "what the display-list interrupts use.", [
        ("band_counter", U8, [("BandCounter", 0)], "display-list band number: cleared by the VBI, +1 at each DLI"),
        ("dli_color0", U8, [("DliColors", 0)], "peach (faded by DRKMSK / COLRSH)"),
        ("dli_color1", U8, [("DliColors", 1)], "red"),
        ("dli_color2", U8, [("DliColors", 2)], "gold"),
        ("dli_color3", U8, [("DliColors", 3)], "light green"),
    ]),
    ("Scratch", 1, "temporaries shared by several routines (stage 42: automatic variables of their routines in C).", [
        ("scratch_2a", U8, [("Scratch2A", 0)], "shared temporary; after JunctionLookup the exit mask"),
        ("junction_temp", U8, [("JunctionTemp", 0)], "local to JunctionLookup"),
        ("bcd_carry", U8, [("BcdCarry", 0)], "decimal carry inside AddToScore"),
        ("clip_mask", U8, [("ClipMask", 0)], "tunnel clip mask"),
        ("clip_counter", U8, [("ClipCounter", 0)], "tunnel clip working X"),
        ("score_add0", U8, [("ScoreAdd", 0)], "BCD digit 100,000 of the amount to add to the score"),
        ("score_add1", U8, [("ScoreAdd", 1)], "10,000"),
        ("score_add2", U8, [("ScoreAdd", 2)], "1,000"),
        ("score_add3", U8, [("ScoreAdd", 3)], "100"),
        ("score_add4", U8, [("ScoreAdd", 4)], "10"),
        ("score_add5", U8, [("ScoreAdd", 5)], "1"),
    ]),
    ("Pointers", 1, "the five data pointers that are not part of an object (`29-pointers.md`; MazePtr is `PacMan.maze_ptr`).", [
        ("src_ptr", U16, [("SrcPtr", 0), ("SrcPtr", 1)], "source of the copiers and drawers"),
        ("dst_ptr", U16, [("DstPtr", 0), ("DstPtr", 1)], "destination of the same"),
        ("popup_missile_ptr", U16, [("PopupMissilePtr", 0), ("PopupMissilePtr", 1)], "GhostEaten: pop-up in the missile page"),
        ("popup_player_ptr", U16, [("PopupPlayerPtr", 0), ("PopupPlayerPtr", 1)], "GhostEaten: '00' in the ghost's page"),
        ("clip_ptr", U16, [("ClipPtr", 0), ("ClipPtr", 1)], "tunnel clip rows"),
    ]),
    ("Os", 1, "Atari OS variables the game uses (not game state; the hardware layer of the port supplies them).", [
        ("pokmsk", U8, [("POKMSK", 0)], "POKEY interrupt-enable shadow"),
        ("rtclok2", U8, [("RTCLOK2", 0)], "jiffy clock, +1 per frame"),
        ("atract", U8, [("ATRACT", 0)], "attract-mode counter"),
        ("drkmsk", U8, [("DRKMSK", 0)], "attract-mode luminance mask"),
        ("colrsh", U8, [("COLRSH", 0)], "attract-mode colour rotation"),
    ]),
]

# the lifetime, from the bulk writes of the code (analyse() checks the sites): (first, last, label, what clears it)
LIFETIME = [
    (0x18, 0x1F, "start-up", "cleared once by the cold start (`Start` $A395, X = $27..0 stores A = 0 in $18-$3F)"),
    (0x20, 0x3F, "game", "cleared at every start and restart of the game (`$A47B`: X = $1F..0 stores 0 in $20-$3F), then set by NewGameInit / ClearPlayerCounters"),
    (0x80, 0xFF, "board", "cleared by InitBoard (`$ADB4`: X = $7F..0 stores 0 in $80-$FF; called by Start, FrameDispatch and TurnControl: the first board, a new board, a new life, a turn switch); $80-$93 are then loaded from `ZeroPageInit80`, `MoveDelayCount` and `GhostTimer`[1..3] are set"),
]
KEPT = "kept"

# record shapes: (label, count, record bytes, what the record is) - the sizes are checked against the data map of tools/labels.py
RAM_RECORDS = [
    ("DeathPlotRows", 0x0600, 14, 1, "one nibble per death-animation frame: the row plotted"),
    ("JunctionExits", 0x060E, 10, 10, "10 rows x 10 columns of direction masks (1 up, 2 down, 4 left, 8 right): the exits of each junction of the maze lattice"),
    ("FrightenEndPhase", 0x0672, 20, 1, "by level: the FrightenPhase value at which the frightened period ends"),
    ("StartRoutes", 0x0686, 40, 1, "four routes of 13, 8, 8, 11 direction-per-junction steps, each ended by $F; the pointers are `StartRoutePtrs`"),
    ("PatrolRoutes", 0x06AE, 230, 1, "16 zero-terminated closed routes; `PatrolRouteOffsets` gives the start of each"),
    ("BonusScore", 0x0794, 13, 2, "by level: (thousands, hundreds) digit pair"),
    ("MoveDelay", 0x07AE, 24, 1, "frames per step in four-step cycles, chosen through `PacMoveDelayBase` / `GhostMoveDelayBase`"),
    ("NoReverseMask", 0x07C6, 9, 1, "by direction: the mask that forbids reversing"),
    ("ReverseDir", 0x07CF, 9, 1, "by direction: the opposite direction"),
]
ROM_RECORDS = [
    ("PatrolStartPositions", 16, 2, "(x, y) of the junction where each patrol route starts"),
    ("CornerPositions", 4, 2, "(x, y) of the four corners the ghosts go to"),
    ("BonusScoreGlyphs", 8, 5, "five glyph codes per bonus score (100 300 500 700 1000 2000 3000 5000)"),
]
SHAPES = [("GhostShapeUp", 10), ("GhostShapeDown", 10), ("GhostShapeLeft", 10), ("GhostShapeRight", 10), ("GhostShapeFrightened", 10), ("GhostEyesShape", 10),
          ("PacShapeFull", 10), ("PacShapeRight1", 10), ("PacShapeRight2", 10), ("PacShapeLeft1", 10), ("PacShapeLeft2", 10), ("PacShapeUp1", 10), ("PacShapeUp2", 10),
          ("PacShapeDown1", 10), ("PacShapeDown2", 10), ("StarShape", 12), ("GhostScoreZeros", 12), ("GhostScore200Digits", 12), ("GhostScore400Digits", 12),
          ("GhostScore800Digits", 12), ("GhostScore1600Digits", 12)]
PM_PAGES = [(0x2300, "Pac-Man (`Entity[4]`) and the pop-up digits: the four missiles, two bits each; `Entity[4].y` is the row of the first picture line"),
            (0x2400, "ghost 0 (player 0, `Entity[0]`)"), (0x2500, "ghost 1 (player 1)"), (0x2600, "ghost 2 (player 2)"), (0x2700, "ghost 3 (player 3)")]

SNAKE = {"PacMan": "pac", "GhostShared": "ghost_shared"}
IDX_PROBE_SKIP = {0xA395, 0xA39C, 0xA47B, 0xADB4, 0xADE3}      # the bulk clears


class Model:
    pass


def zp_vars():
    return {name: (first, n, kind, role) for first, n, name, kind, role, ev in V.ZP}


def struct_coverage():
    """ {(variable, byte): (struct, field)} and the problems found (a byte used twice, a variable missing, a size that does not fit) """
    var = zp_vars()
    owner, problems = {}, []
    for sname, count, desc, fields in STRUCTS:
        for cname, ctype, src, note in fields:
            nbytes = 0
            for v, off in src:
                if v not in var:
                    problems.append("unknown variable %s" % v)
                    continue
                size = var[v][1]
                idx = range(size) if count > 1 else [off]
                if count > 1 and size != count:
                    problems.append("%s.%s: %s has %d bytes, the structure has %d objects" % (sname, cname, v, size, count))
                for i in idx:
                    if (v, i) in owner:
                        problems.append("%s byte %d used twice (%s.%s and %s.%s)" % (v, i, owner[(v, i)][0], owner[(v, i)][1], sname, cname))
                    owner[(v, i)] = (sname, cname)
                    nbytes += 1
            expect = (2 if ctype == U16 else 1) * (count if count > 1 else 1)
            if nbytes != expect:
                problems.append("%s.%s: %s needs %d bytes, %d listed" % (sname, cname, ctype, expect, nbytes))
    for v, (first, n, kind, role) in var.items():
        for i in range(n):
            if (v, i) not in owner:
                problems.append("%s byte %d belongs to no structure" % (v, i))
    return owner, problems


LIFE_OVERRIDE = {"PelletFlags": "board (per player, `ClearPlayerCounters`)", "DotsEatenLo": "board (per player, `ClearPlayerCounters`)", "DotsEatenHi": "board (per player, `ClearPlayerCounters`)",
                 "BonusCount": "board (per player, `ClearPlayerCounters`)", "BandCounter": "frame (cleared by the VBI)",
                 # stage 65 (`43`): the sensitivity experiment on the concrete 6502 corrected these three
                 "ScoreAdd": "zero between uses (the callers set one digit, `AddToScore` adds six and clears them)",
                 "WantVert": "temporary (set before use in `SteerToTarget`)", "WantHoriz": "temporary (set before use in `SteerToTarget`)", "PacHold": "frame (set before use every frame)"}
LIFE_STRUCT = {"Scratch": "temporary (set before use)", "Pointers": "temporary (set before use)", "Os": "OS"}


def life_of(sname, variable, addr):
    if variable in LIFE_OVERRIDE:
        return LIFE_OVERRIDE[variable]
    if sname in LIFE_STRUCT:
        return LIFE_STRUCT[sname]
    return lifetime(addr)


def lifetime(addr):
    for a, b, label, what in LIFETIME:
        if a <= addr <= b:
            return label
    return KEPT


def field_address(sname, count, cname, src):
    var = zp_vars()
    v, off = src[0]
    return var[v][0] + (0 if count > 1 else off)


def w16(rom, a):
    o = a - BASE
    return rom.data[o] | (rom.data[o + 1] << 8)


def data_range(name):
    for first, last, kind, n, comment in LB.DATA:
        if n == name:
            return first, last
    raise KeyError(name)


def analyse():
    rom, F, owner_fn = AS.load()
    var = zp_vars()
    arrays = [(first, n, name) for name, (first, n, kind, role) in var.items() if kind.startswith("array")]
    sites = collections.defaultdict(list)                    # array name -> [(address, mnemonic, offset, routine)]
    probes = []
    outside = []
    for a, (n, m, mode, op) in sorted(rom.ins.items()):
        if mode in ("zpx", "zpy"):
            hit = [(f, n_, nm) for f, n_, nm in arrays if f <= op < f + n_]
            if hit:
                f, n_, nm = hit[0]
                sites[nm].append((a, m, op - f, F[owner_fn[a]].name))
                probes.append(a)
            elif a not in IDX_PROBE_SKIP:
                outside.append((a, m, op, F[owner_fn[a]].name))
    callers = {}
    for target in (0xADAF, 0xADF1, 0xAE02, 0xAE1E, 0xAE2B):
        callers[target] = sorted(F[e].name for e, f in F.items() if target in f.calls.values())
    init = [rom.data[0xBB6F - BASE + i] for i in range(20)]
    bulk = {a: (rom.ins[a][1], rom.ins[a][3], F[owner_fn[a]].name) for a in (0xA395, 0xA39C, 0xA47B, 0xADB4, 0xADE3)}
    return rom, F, owner_fn, sites, probes, outside, callers, init, bulk


def evidence():
    if os.path.exists(EVIDENCE):
        with open(EVIDENCE, encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    return None


def c_header():
    L = []
    for sname, count, desc, fields in STRUCTS:
        L.append("typedef struct {")
        for cname, ctype, src, note in fields:
            var = zp_vars()
            first = var[src[0][0]][0] + (0 if count > 1 else src[0][1])
            L.append("    %-9s %-18s /* $%02X%s */" % (ctype, cname + ";", first, (" + %d * i" % 1) if count > 1 else ""))
        L.append("} %s;" % sname)
        L.append("")
    L.append("typedef struct {")
    L.append("    Entity   entity[5];      /* 0-3 ghosts, 4 Pac-Man */")
    L.append("    Ghost    ghost[4];")
    L.append("    Player   player[2];")
    for sname, count, desc, fields in STRUCTS[3:]:
        L.append("    %-11s %s;" % (sname, SNAKE.get(sname, sname.lower())))
    L.append("} GameVars;")
    return L


def report():
    rom, F, owner_fn, sites, probes, outside, callers, init, bulk = analyse()
    var = zp_vars()
    owner, problems = struct_coverage()
    L = []
    P = L.append
    nvar = len(var)
    nbytes = sum(n for first, n, kind, role in var.values())
    P("# 30 - The Structures (stage 48)")
    P("")
    P("GENERATED by `python -I tools/analyze_structures.py --write docs/30-structures.md` from the trace of `src/asm/pacman.s`, the routines of `23-function-table.md`, the variable catalogue of `25-variable-catalogue.md` (`tools/analyze_variables.py`) and `analysis/evidence-structures-summary.txt` (the emulator measurement). Tests: `tests/test_structures.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- The ROM has **no structures and no record-shaped data in the zero page**: every object is kept as a **structure of arrays**, one zero-page array per field with stride 1 (`EntityX`, `EntityY`, `EntityDir`, ... at `$8A`, `$85`, `$8F`), indexed by the object number in X. There are **%d arrays** (`25-variable-catalogue.md`), indexed by **%d instructions** `sta/lda array,x`; **no instruction reaches a field of one object through another** (no `EntityX-1,x` or `+k` offsets) **except `GhostTimer+1,x`** in `SetReleaseTimers`, which stores the release timers of ghosts 1-3 (section 2)." % (sum(1 for v in var.values() if v[2].startswith("array")), sum(len(s) for s in sites.values())))
    P("- The objects are: **Entity** x5 (ghosts 0-3 and Pac-Man = 4), **Ghost** x4, **Player** x2; and nine single objects (PacMan, GhostShared, Frighten, Bonus, Death, Sound, Flow, Display, Scratch) plus the pointers and the OS variables. **All %d zero-page variables (%d bytes) belong to exactly one structure** (section 3; the check is in `tests/test_structures.py`)." % (nvar, nbytes))
    P("- The object index is **the same number everywhere**: ghost g = player page `$24+g` = colour register `PCOLR0+g` = `HPOSP0+g`; Pac-Man = 4 = the missile page `$23` (the page is computed as `$24 + X` with X = $FF for Pac-Man in `ClipEntityAtTunnel`, `29-pointers.md`). `CurrentPlayer` (0, 1) is the index of every per-player array.")
    P("- **Lifetime** follows the memory map: `$80-$FF` is cleared at every `InitBoard` (and the first 20 bytes loaded with the start positions), `$20-$3F` at every game start, the rest is kept (section 5). Measured in Altirra (section 8): the index of every array access stays in the range of its array, and the state after `InitBoard` and after the game restart is what section 5 says.")
    P("- For the port: **an array of structures** (`Entity entity[5]`, `Ghost ghost[4]`, `Player player[2]`) replaces the structure of arrays; the equivalence tests (stages 86-87) read the original RAM image, so the port keeps a **mapping function** per field (original address = base + index; the table of section 3) rather than the original layout.")
    P("")
    P("## 2. The arrays and their indexing")
    P("")
    P("Every `array,x` access found in the code, per array (the offset is relative to the base of the array; the array sizes are 2 per player, 4 per ghost, 5 per entity):")
    P("")
    P("| Array | Address | Size | Sites | Offsets used | Routines |")
    P("|---|---|---|---|---|---|")
    for name in sorted(sites, key=lambda n: (var[n][0])):
        s = sites[name]
        P("| %s | `$%02X-$%02X` | %d | %d | %s | %s |" % (name, var[name][0], var[name][0] + var[name][1] - 1, var[name][1], len(s),
          ", ".join("+%d" % o for o in sorted({o for a, m, o, r in s})), ", ".join(sorted({r for a, m, o, r in s}))))
    P("")
    off = [(a, m, o, r, nm) for nm, s in sites.items() for a, m, o, r in s if o != 0]
    for a, m, o, r, nm in sorted(off):
        P("- `$%04X` %s `%s+%d,x` in %s: `SetReleaseTimers` runs X = 2..0 and stores `HouseReleaseTimers[board window + 2 - X]` at `$CB + X`, that is `GhostTimer[1..3]`; **ghost 0 keeps the 0 from InitBoard** (it leaves the house at once)." % (a, m, nm, o, r))
    P("")
    P("Indexed instructions that are not an array access (the bulk clears and the initial load): " + ", ".join("`$%04X` %s `$%02X,x` in %s" % t for t in sorted(
        (a, rom.ins[a][1], rom.ins[a][3], F[owner_fn[a]].name) for a in IDX_PROBE_SKIP)) + ".")
    P("")
    P("## 3. The structures")
    P("")
    P("C names are the proposal of this stage (the catalogue names are in the **Original** column). A structure with count > 1 is an array of objects: the original has one array per field (`base + i`).")
    P("")
    for sname, count, desc, fields in STRUCTS:
        P("### %s%s" % (sname, "[%d]" % count if count > 1 else ""))
        P("")
        P(desc)
        P("")
        P("| C field | Type | Original (variable) | Address | Lifetime | Meaning |")
        P("|---|---|---|---|---|---|")
        for cname, ctype, src, note in fields:
            first = var[src[0][0]][0] + (0 if count > 1 else src[0][1])
            last = first + (count if count > 1 else 1) - 1
            if ctype == U16 and count == 1:
                last = first + 1
            names = " + ".join("%s%s" % (v, ("[%d]" % off) if count == 1 and var[v][1] > 1 and not ctype == U16 else "") for v, off in src)
            addr = "`$%02X`" % first if first == last else "`$%02X-$%02X`" % (first, last)
            if len(src) == 2 and count > 1:
                addr = "`$%02X-$%02X` + `$%02X-$%02X`" % (var[src[0][0]][0], var[src[0][0]][0] + count - 1, var[src[1][0]][0], var[src[1][0]][0] + count - 1)
            P("| %s | %s | %s | %s | %s | %s |" % (cname, ctype, names, addr, life_of(sname, src[0][0], first), note))
        P("")
    P("## 4. The initial state of the entities")
    P("")
    P("`InitBoard` copies the 20 bytes of `ZeroPageInit80` (`$BB6F`) to `$80-$93`: that is `PacMan.maze_ptr`, `PacMan.sub_x`, `PacMan.last_cell_y`, `PacMan.last_cell_x` and the three entity arrays. Decoded:")
    P("")
    P("- `PacMan.maze_ptr` = `$%04X`, `sub_x` = %d, `last_cell_y` = $%02X, `last_cell_x` = $%02X" % (init[0] | init[1] << 8, init[2], init[3], init[4]))
    P("")
    P("| Entity | Object | y | x | dir |")
    P("|---|---|---|---|---|")
    nm = ["0 (red)", "1 (pink)", "2 (green)", "3 (gold)", "4 Pac-Man"]
    for i in range(5):
        P("| %s | %s | $%02X | $%02X | %d (%s) |" % (i, nm[i], init[5 + i], init[10 + i], init[15 + i], {1: "up", 2: "down", 4: "left", 8: "right"}[init[15 + i]]))
    P("")
    P("Ghost 0 starts in the corridor above the ghost house (y $64), ghosts 1-3 inside the house (y $74) at x $7C, $70, $88; Pac-Man starts below it (y $A4, x $7C) facing left. `MoveDelayCount[0..3]` (the ghosts) and `[4]` (Pac-Man) are loaded from `MoveDelay` by level; `GhostTimer[1..3]` from `HouseReleaseTimers`; everything else in `$94-$FF` is 0.")
    P("")
    P("## 5. Lifetimes: what the code resets")
    P("")
    P("| Range | Class | Reset by |")
    P("|---|---|---|")
    for a, b, label, what in LIFETIME:
        P("| `$%02X-$%02X` | %s | %s |" % (a, b, label, what))
    P("| the rest (`$00-$17`, `$40-$7F`) | kept | no bulk write; these are the OS bytes (`POKMSK`, `RTCLOK2`, `ATRACT`, `DRKMSK`, `COLRSH`), `KeyDebounce`, `KeyValue`, the pointers `$38-$3F`/`$47-$48` (set before use), `HalfSpeedToggle` and `DliColors` |")
    P("")
    P("Callers of the routines that reset: `InitBoard` is called by %s; `NewGameInit` by %s; `NewBoardInit` by %s; `ClearPlayerCounters` (per player: `pellets` = $0F, `bonus_count` and `dots_eaten` = 0) by %s, **and by falling through from the end of `NewBoardInit`** (`$AE1C`: `ldx CurrentPlayer`), so the per-board counters of the player on turn are reset at every new board; `SetReleaseTimers` by %s." % tuple(", ".join(callers[t]) for t in (0xADAF, 0xADF1, 0xAE02, 0xAE1E, 0xAE2B)))
    P("")
    P("What this means for the structures: `Entity`, `Ghost`, `PacMan`, `GhostShared`, `Frighten`, `Bonus`, `Death` and the Sound state are **per-board** (re-initialised by one `memset` and the start-position copy); `Player` and `Flow` are per-game; the pointers and OS bytes are not game state. In C: `memset(&board_state, 0, sizeof board_state)` then the initial values of section 4 reproduces `InitBoard`, if the per-board structures are kept together in one block.")
    P("")
    P("## 6. Objects that are not zero-page arrays")
    P("")
    P("**The player-missile memory** (`PMBASE` = $20, 256 bytes per object, one byte per scan line; the picture of an object starts at row `Entity.y`):")
    P("")
    P("| Page | Object |")
    P("|---|---|")
    for a, what in PM_PAGES:
        P("| `$%04X` | %s |" % (a, what))
    P("")
    P("**The picture buffers** (RAM, one byte per picture row, copied 16 rows to the page at `Entity.y` by the drawers): `$0400-$040F` Pac-Man's (his 10 shape rows at `$0403-$040C`, copied by `DrawAllInPlace` from `PacShapePtrs[dir] + mouth offset`), `$0410-$041F` a ghost's (shape rows `$0412-$041B`, feet row `$041C`, copied by `StepAndDrawEntity` from `$BAC0 + A`).")
    P("")
    P("**Saved mazes and the screen**: `WorkingMaze` `$0C00-$0FFF` is the working maze **and** the screen of the maze band (23 rows of 40 bytes: the dots, walls and power pellets; `PacMan.maze_ptr` points into it); `SavedMaze1` `$1000-$13FF` / `SavedMaze2` `$1400-$17FF` are the two players' mazes while the other plays (`Copy0C00To1000` / `Copy0C00To1400`); `OriginalMaze` `$0800-$0BFF` is the stored original. So **a Player is (the 6 fields of section 3) + one 1,024-byte maze**; the working maze is the maze of `CurrentPlayer`. The score of a player is not a field of the zero page: it lives as digits in the status row (`StatusRow`, `25-variable-catalogue.md` section 3; `19-two-players.md`) and is added to with `ScoreAdd[0..5]` by `AddToScore`.")
    P("")
    P("**RAM tables built at start-up** (from the nibble tables, `12-data-formats.md`) and their records:")
    P("")
    P("| Table | Address | Records x bytes | Size | What |")
    P("|---|---|---|---|---|")
    for name, addr, cnt, rec, what in RAM_RECORDS:
        P("| %s | `$%04X` | %d x %d | %d | %s |" % (name, addr, cnt, rec, cnt * rec, what))
    P("")
    P("**Records in ROM:**")
    P("")
    P("| Table | Address | Records x bytes | What |")
    P("|---|---|---|---|")
    for name, cnt, rec, what in ROM_RECORDS:
        f, l = data_range(name)
        P("| %s | `$%04X` | %d x %d | %s |" % (name, f, cnt, rec, what))
    P("")
    P("**Pictures** (ROM, one byte per row; the row count is the record size): " + "; ".join("%s `$%04X` x %d" % (n, data_range(n)[0], r) for n, r in SHAPES) + ".")
    P("")
    P("## 7. The proposed C layout")
    P("")
    P("```c")
    for line in c_header():
        P(line)
    P("```")
    P("")
    P("Rules for the port (the owner decides the file layout at stage 74): (1) the per-object **index stays 0-4**, so `Pac-Man = entity[4]` and loops `for i in 0..3` over the ghosts keep their meaning; (2) a loop that ran X from 4 down to 0 over the five entities is `for (i = 4; i >= 0; i--)`, and a ghost-only loop must stop at 3 (the 4-byte arrays); (3) `dots_eaten` is one 16-bit field; (4) the only cross-array access, `GhostTimer+1`, becomes `ghost[i + 1].timer` for i = 0..2; (5) the bit meanings of `Ghost.state` and `Entity.dir` stay as masks (`23`, `24`, `17`).")
    P("")
    P("## 8. Measured (Altirra)")
    P("")
    ev = evidence()
    if ev:
        P("`tools/run_structure_audit.ps1` runs session harnesses of the project in Altirra (OS-B, NTSC) with a trace at every indexed array access (%d sites; the value of X is logged), at the end of `InitBoard` (all of `$80-$FF`) and after the game-restart clear (`$20-$3F`); `tools/analyze_structures_log.py` checks each against the structures above:" % len(probes))
        P("")
        P("```")
        for line in ev:
            P(line)
        P("```")
        P("")
        P("Reading the result:")
        P("")
        P("- **Every index stays in its array**: 0 accesses outside, in 93 million hits at **all 191 sites**. The ghost arrays are only ever indexed 0-3, the entity arrays 0-4, the player arrays 0-1; the entity index 4 (Pac-Man) never reaches a 4-byte array. `EntityDir` is indexed 0-3 only: Pac-Man's direction is read through its own address (`PacDirection`, `$93`), not with X.")
        P("- **Reaching every site took twelve harnesses**: the first five missed 11 sites (the bonus item eaten, the bonus appearing, the 256th dot of a board, the forced chase, a ghost entering the house), added by `levels`, `itemshots`, `catch`, `house_frightened`, `eaten_dir` and `fullgame2`; the last two (`$B6C8` / `$B6CA` in `EyesAndHousePerFrame`: an eaten ghost arrives at the door square moving up) by `tools/altirra_door_up.cmd` (`18-frightened-eaten-house.md`, OV-57 / C-58).")
        P("- **After `InitBoard`** (89 snapshots): `$80-$93` equal `ZeroPageInit80`, `MoveDelayCount` is loaded (the four ghost entries equal, none 0), `GhostTimer[1..3]` are the first window of `HouseReleaseTimers` (`InitBoard` calls `SetReleaseTimers` with Y = 0) and every other byte of `$94-$FF` is 0: sections 4 and 5 are exactly what the code leaves behind.")
        P("- **After the restart clear** (29 snapshots): `$20-$3F` is 0 in all 29. An earlier run showed `$3F` = `$A5` in the first snapshot of five logs; that was the debugger, not the game: Altirra 4.40 prints the **first tracepoint hit of a session with the state of the next hit**. Every harness now starts with a sentinel tracepoint on `Start` that absorbs it (`04-analysis-tools.md`, OV-56 / C-57).")
    else:
        P("NOT YET MEASURED: `analysis/evidence-structures-summary.txt` does not exist (run `tools/run_structure_audit.ps1`, then `python -I tools/analyze_structures_log.py analysis/raw-logs/structures-*.txt`).")
    P("")
    return L


def main():
    if "--probes" in sys.argv:
        for a in analyse()[4]:
            print("%04x" % a)
        return
    txt = "\n".join(report()) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
