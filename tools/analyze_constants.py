"""Stage 50: the constants and the algorithms of the Pac-Man ROM.

Part 1 - the constants census, derived from the code: every immediate operand of every routine, classified by what it does (compared with a variable, assigned to a variable, a mask, an addition, a loop count / index), with the
variable or hardware register it belongs to.  Part 2 - NAMED: the constants that carry a meaning of the game (door square, tunnel, states, timers, thresholds, scores) with a proposed C name and the routines in which the
code uses them; the test checks that each is really found there.  Part 3 - ALGORITHMS: every routine of the ROM belongs to an algorithm with its rule, the constants and tables it uses, and the evidence (chapter, test,
live session, executable model).  Part 4 - the executable models of tools/algorithm_models.py (the ROM run instruction by instruction in tools/cpu6502.py against a model) from analysis/evidence-algorithms-summary.txt.
Usage: python -I tools/analyze_constants.py [--write docs/31-constants-algorithms.md | --census]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402
import analyze_relationships as AR  # noqa: E402
import analyze_stack as AS  # noqa: E402

ROOT = AF.ROOT
LB = AF.LB
BASE = AF.BASE
EVIDENCE = os.path.join(ROOT, "analysis", "evidence-algorithms-summary.txt")

LOAD = {"lda": "A", "ldx": "X", "ldy": "Y"}
STORE = {"sta": "A", "stx": "X", "sty": "Y"}
CMP = {"cmp": "A", "cpx": "X", "cpy": "Y"}
LOGIC = {"and": "and", "ora": "or", "eor": "xor"}
ARITH = {"adc": "+", "sbc": "-"}


_ZPNAMES = None


def zp_catalogue_name(addr):
    """the name of a zero-page byte: tools/labels.py when it has one, else the proposal of the variable catalogue (docs/25), with +i inside a multi-byte variable"""
    global _ZPNAMES
    if _ZPNAMES is None:
        import analyze_variables as V
        _ZPNAMES = {}
        for first, n, name, kind, role, ev in V.ZP:
            for i in range(n):
                _ZPNAMES[first + i] = name if i == 0 else "%s+%d" % (name, i)
    nm = LB.zp_name(addr)
    if nm.startswith("zp_") and addr in _ZPNAMES:
        return _ZPNAMES[addr]
    return nm


def mem_name(m, mode, op):
    """the name of a memory operand: zero page, a hardware register, an OS variable, a table"""
    if mode in ("zp", "zpx", "zpy"):
        return zp_catalogue_name(op) + (",x" if mode == "zpx" else ",y" if mode == "zpy" else "")
    if mode in ("abs", "abx", "aby"):
        nm = LB.hw_name(op, m) if 0xD000 <= op < 0xD800 else None
        if not nm:
            nm = LB.OS_ABS.get(op)
        if not nm:
            below = [a for a in LB.RAM_TABLES if a <= op < 0x0700]
            if op >= 0xA000:
                for first, last, kind, n, comment in LB.DATA:
                    if first <= op <= last:
                        nm = n if op == first else "%s+%d" % (n, op - first)
                        break
            elif below and op < 0x0800:
                a = max(below)
                nm = LB.RAM_TABLES[a] + ("" if op == a else "+%d" % (op - a))
        nm = nm or "$%04X" % op
        return nm + (",x" if mode == "abx" else ",y" if mode == "aby" else "")
    return "?"


def prev_instr(rom, a):
    cand = [p for p in (a - 1, a - 2, a - 3) if p in rom.ins and p + rom.ins[p][0] == a]
    return cand[0] if cand else None


def census():
    """per routine: list of (address, kind, value, subject) ; kinds: cmp, assign, logic, arith, load"""
    rom, F, owner = AS.load()
    out = collections.defaultdict(list)
    for a, (n, m, mode, op) in sorted(rom.ins.items()):
        if mode != "imm":
            continue
        rn = F[owner[a]].name
        if m in CMP:
            p = prev_instr(rom, a)
            subj = "A"
            if p is not None:
                pn, pm, pmode, pop = rom.ins[p]
                reg = CMP[m]
                if pm in ("lda", "ldx", "ldy") and LOAD[pm] == reg and pmode != "imm":
                    subj = mem_name(pm, pmode, pop)
                elif pm in ("lda", "ldx", "ldy") and LOAD[pm] == reg:
                    subj = "(#$%02X)" % pop
                elif pm in ("inx", "dex", "iny", "dey", "tax", "tay", "txa", "tya", "pla", "asl", "lsr", "rol", "ror"):
                    subj = {"inx": "X", "dex": "X", "iny": "Y", "dey": "Y", "tax": "A", "tay": "A", "txa": "A", "tya": "A", "pla": "A (pulled)"}.get(pm, "A (after %s)" % pm)
                    if reg != "A":
                        subj = reg
                elif pm in ("adc", "sbc", "and", "ora", "eor"):
                    subj = "A (after %s)" % pm
            if subj == "A":
                subj = reg_name(m)
            out[rn].append((a, "cmp", op, subj))
        elif m in LOAD:
            q = a + n
            if q in rom.ins and rom.ins[q][1] in STORE and STORE[rom.ins[q][1]] == LOAD[m]:
                _, sm, smode, sop = rom.ins[q]
                out[rn].append((a, "assign", op, mem_name(sm, smode, sop)))
            else:
                out[rn].append((a, "load", op, LOAD[m]))
        elif m in LOGIC:
            p = prev_instr(rom, a)
            subj = "A"
            if p is not None and rom.ins[p][1] == "lda" and rom.ins[p][2] != "imm":
                subj = mem_name("lda", rom.ins[p][2], rom.ins[p][3])
            out[rn].append((a, "logic", op, "%s %s" % (subj, LOGIC[m])))
        elif m in ARITH:
            p = prev_instr(rom, a)
            subj = "A"
            if p is not None and rom.ins[p][1] == "lda" and rom.ins[p][2] != "imm":
                subj = mem_name("lda", rom.ins[p][2], rom.ins[p][3])
            out[rn].append((a, "arith", op, "%s %s" % (subj, ARITH[m])))
    return rom, F, owner, out


def reg_name(m):
    return {"cmp": "A", "cpx": "X", "cpy": "Y"}[m]


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# the constants that carry a meaning: (C name, value, meaning, [routines in which the code uses it as an immediate], chapter)
NAMED = [
    # the maze lattice and the door
    ("DOOR_X", 0x7C, "x of the door square (124): the eaten ghost's target, the door column", ["EyesAndHousePerFrame", "HouseLeaveGhost2", "HouseLeaveGhost3"], "18"),
    ("DOOR_Y", 0x64, "y of the door square (100) and of the corridor above the ghost house", ["EyesAndHousePerFrame", "JunctionLookup", "HouseLeaveStep"], "18"),
    ("DOOR_SIDE_X_LEFT", 0x76, "x of the square left of the door: a normal ghost loses its up exit there, a frightened one gets up as its only exit", ["JunctionLookup"], "18"),
    ("DOOR_SIDE_X_RIGHT", 0x82, "x of the square right of the door (same rule)", ["JunctionLookup"], "18"),
    ("HOUSE_FLOOR_Y", 0x74, "y of the ghost-house floor, 116: eaten ghosts stop here", ["HouseEnterStep"], "18"),
    ("TUNNEL_Y", 0x74, "y of the tunnel row (the clip and the half speed apply to it)", ["ClipEntitiesOnTunnelRow", "FrameDispatch"], "16, 18"),
    ("TUNNEL_X_LEFT", 0x2A, "x at which an entity leaving the left end of the tunnel wraps", ["MovePacMan", "ClipEntityAtTunnel"], "16, 20"),
    ("TUNNEL_X_RIGHT", 0xCA, "x at which an entity leaving the right end wraps", ["MovePacMan", "ClipEntityAtTunnel"], "16, 20"),
    ("MAZE_ROW_STRIDE", 0x28, "bytes per maze row (40): MazePtr moves by this for one row", ["MovePacMan"], "20"),
    ("MAZE_PTR_LEFT_EXIT_LO", 0xB7, "low byte of MazePtr when Pac-Man wraps through the left tunnel", ["MovePacMan", "ClipEntityAtTunnel"], "20"),
    ("MAZE_PTR_RIGHT_EXIT_LO", 0x8F, "low byte of MazePtr when Pac-Man wraps through the right tunnel", ["MovePacMan", "ClipEntityAtTunnel"], "20"),
    ("CLIP_PAGE_OFFSET", 0x24, "player pages start at $24: ghost g draws in page $24 + g, Pac-Man (X = $FF) in $23 (`InitDisplay2` here is the shared tail of `StepAndDrawEntity`, `29-pointers.md`)", ["ClipEntityAtTunnel", "InitDisplay2"], "16"),
    # ghost states and bits
    ("GS_FRIGHTENED_BIT", 0x80, "bit 7 of GhostState: frightened", ["PowerPelletEaten", "FrightenedTick"], "17"),
    ("GS_EYES", 0x42, "state of an eaten ghost on its way to the door", ["GhostEaten"], "18"),
    ("GS_EYES_AT_DOOR", 0x44, "state of an eaten ghost that reached the door square (it enters the house)", ["EyesAndHousePerFrame"], "18"),
    ("GS_CHASE", 0x02, "chase", ["ForceChase", "HouseLeaveStep"], "17"),
    ("GS_PATROL_TRAVEL", 0x08, "walking to the patrol start", ["ForceChase", "GhostSelectPatrol"], "13, 17"),
    ("GS_PATROL", 0x10, "walking the patrol route", ["ForceChase"], "13, 17"),
    ("GS_CORNER", 0x20, "going to the corner", ["ForceChase"], "13, 17"),
    ("GS_END_FRIGHT_MASK", 0xBB, "AND mask that ends frightened for every state but the plain house state", ["FrightenedTick"], "17, 18"),
    ("GS_LOW_NIBBLE", 0x0F, "AND mask: state of an eaten ghost that is home again, bit 7 and 6 removed", ["HouseEnterStep"], "18"),
    ("DIR_UP", 0x01, "direction bit up (also the vertical want up)", ["SteerToTarget", "JunctionLookup"], "13"),
    ("DIR_DOWN", 0x02, "direction bit down", ["SteerToTarget"], "13"),
    ("DIR_LEFT", 0x04, "direction bit left", ["SteerToTarget"], "13"),
    ("DIR_RIGHT", 0x08, "direction bit right", ["SteerToTarget"], "13"),
    # timers and thresholds
    ("PATROL_TIME", 0x96, "GhostTimer after a patrol is chosen: 150 x 8 jiffies = 20 s", ["GhostSelectPatrol"], "13"),
    ("CHASE_ON_SIGHT", 0xA0, "ChaseTimer when a ghost sees Pac-Man: 160 x 8 jiffies", ["GhostSeesPacMan"], "13, 15"),
    ("CHASE_AFTER_START_ROUTE", 0x50, "ChaseTimer of ghost 0 when its start route ends", ["GhostStartRoute"], "13"),
    ("LATE_BOARD_DOTS_1", 0xE0, "dots eaten (low byte) from which the siren speeds up and ghosts are forced into chase", ["ChaseTimerSirenSight"], "17, 22"),
    ("LATE_BOARD_DOTS_2", 0xF0, "the second threshold", ["ChaseTimerSirenSight"], "17, 22"),
    ("BONUS_FIRST_DOTS", 0x50, "dots eaten (80) at which the first bonus item appears", ["BonusItemUpdate"], "14"),
    ("BONUS_SECOND_DOTS", 0xA0, "dots eaten (160) at which the second bonus item appears", ["BonusItemUpdate"], "14"),
    ("BONUS_TIME_LO", 0xC0, "low byte of the bonus item's time on the screen ($02C0 = 704 frames)", ["BonusItemUpdate"], "14"),
    ("BONUS_TIME_HI", 0x02, "high byte of the same", ["BonusItemUpdate"], "14"),
    ("BONUS_SCORE_TIME", 0x40, "frames the bonus score picture stays (64)", ["FrameDispatch"], "14"),
    ("FRIGHT_FLASH_FRAMES", 0x18, "frames of one flash phase of a frightened ghost (24)", ["FrightenedTick"], "14, 18"),
    ("DEATH_FREEZE", 0x60, "death freeze counter: 96 frames, 97 with the first", ["FrameDispatch"], "20"),
    ("DEATH_ANIM_DELAY", 0x07, "frames each death picture is held (counted 7..0 = 8 frames)", ["DeathSequence"], "20"),
    ("WAIT_AFTER_DEATH", 0x30, "WaitTimer frames", ["TurnControl"], "19, 21"),
    ("COUNTDOWN_STEPS", 0xE2, "game-over countdown steps (226, one per 8th jiffy: 30 s)", ["TurnControl"], "21"),
    ("LEVEL_CLAMP_SPEED", 0x06, "Level is clamped to 6 for the speed tables", ["MoveDelayTick"], "14"),
    ("LEVEL_CLAMP_BONUS", 0x0C, "Level is clamped to 12 for the bonus tables", ["BonusItemUpdate"], "14"),
    ("LEVEL_COMPLETE_SET", 0x01, "the value stored in LevelComplete when the dot count reaches $xx04 with a non-zero high byte (260 = $0104): the board is complete (the test is DotsEatenHi != 0 and DotsEatenLo == 4, $B390-$B398)", ["PowerPelletEaten"], "14"),
    # score
    ("SCORE_DIGIT_MASK", 0x0F, "AND mask: the digit of a score cell", ["AddToScore"], "12"),
    ("SCORE_DIGIT_BASE", 0x10, "OR mask: the screen code of digit d is $10 + d; $00 is blank", ["AddToScore"], "12"),
    ("SCORE_CELLS_P1", 0x2F, "X for player 1's units cell ($202F; the six cells are $202A-$202F)", ["AddToScore"], "19"),
    ("SCORE_CELLS_P2", 0x4C, "X for player 2's units cell ($204C; $2047-$204C)", ["AddToScore"], "19"),
    # hardware
    ("PMBASE_PAGE", 0x20, "PMBASE: the player-missile area at $2000 (pages $23-$27 used)", ["Start"], "06, 16"),
    ("PRIORITY_NORMAL", 0x11, "GPRIOR during play", ["Start", "GhostEatenPause"], "15"),
    ("PRIORITY_POPUP", 0x14, "GPRIOR during the ghost-eaten pop-up", ["GhostEaten"], "15"),
    ("POKEY_FREQ_BASE", 0xA8, "AUDC value (distortion 5, volume 8) of the death and ghost-eaten sounds", ["GhostEatenPause", "DeathSequence"], "22"),
]

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# the algorithms: (id, name, [routines], rule, tables / constants, evidence, status)
# status: LIVE = verified against the running game (chapter / evidence file), MODEL = also run against an executable model here, CODE = read from the code only
ALGORITHMS = [
    ("A01", "Start-up and data expansion", ["Start", "Init", "ExpandData", "ReadSrcByte", "AdvanceSrcPtr", "WriteDstByte", "ReadSrcHighNibble"],
     "Clear zero page $18-$3F and $80-$FF; expand the type A stream (inline RLE: literal, repeat (c&$3F)+1, three bytes out) to the maze at $0800, the nibble tables to $0600 (high nibble then low nibble of each of 256 bytes), the type B streams (table-driven: `PixelPatternTable[c&$3F]` repeated (c>>6)+1 times) to the charset $3000 and the title charset $1808; start the key loop.",
     "streams in ROM `$A003`, `$A1E1`, `$BE13`, `$BE95`; `PixelPatternTable`", "12; `tools/decode_streams.py`, `tests/test_streams.py`, `tests/test_nibble_map.py`", "LIVE + MODEL (the ROM code run to `$A477` produces the same RAM images)"),
    ("A02", "Key loop, game start and game over", ["Start", "CompareHighScore", "TitleClearScores1P", "TitleClearScores2P", "DrawLabel1UP", "DrawLabel2UP", "BlinkPlayerLabel"],
     "Poll CONSOL and the keyboard with a debounce counter; START begins a game, SELECT toggles one / two players, OPTION steps `StartLevel` through 0,1,2,4,6,8,10,12; the space bar pauses; at game over a 30 s countdown (`$E2` steps of 8 jiffies) returns to the title; the high score is replaced when the player's score is larger.",
     "`StartLevel` steps, `CountdownTimer` $E2", "21, 19; `tests/test_start_gameover.py`, `tests/test_pregame.py`", "LIVE + MODEL (the key loop with START / SELECT / OPTION / space bar, the debounce and the restart: 5,000 passes; the title screens: 3,000 frames; `tools/algorithm_models6.py`, `tools/algorithm_models7.py`); the pause key is also modelled (`25`)"),
    ("A03", "The frame: dispatch and pacing by the jiffy clock", ["FrameDispatch", "VbiHandler", "ToggleLegPhase"],
     "The deferred VBI handler runs the whole game in one call: title states 1-4, and in state 0 the game frame in the order of the code (`24-function-relationships.md`, section 'one frame of play'). Everything slower than a frame is paced by `RTCLOK2` bits: every 4th jiffy the house, every 8th the chase and patrol timers, every 16th the ghost feet and the label blink.",
     "`RTCLOK2` masks $03, $07, $0F", "24 (one frame in the order of the code), 17, 18, 20; `tests/test_timer_budgets.py`", "LIVE + MODEL (`FrameDispatch` and `VbiHandler` run frame by frame against a model of the whole frame: the clocks, the intro, the death, the pause, the contacts, the pacing of every ghost; 30,000 frames, whole memory compared, `tools/algorithm_models7.py`)"),
    ("A04", "Display-list interrupts and colour bands", ["DliHandler1", "DliHandler2", "InitDisplay2", "SetDisplayList"],
     "At each display-list interrupt the handler writes the colours of the next band (from `DliColors`, faded in attract mode by `DRKMSK` / `COLRSH`) and its `CHBASE` (`DliChbaseTable` on the title screen); `BandCounter` counts the bands and is cleared by the VBI.",
     "`ColorsDli`, `DliChbaseTable`, `ColorsTitle`", "15, 06", "LIVE (colours: 482,764 pixels checked, C-50) + MODEL (`DliHandler1`, `DliHandler2`, `SetDisplayList`, `InitDisplay2` against the code run with an interrupt frame, `tools/algorithm_models6.py`)"),
    ("A05", "Pac-Man's step", ["MovePacMan"],
     "Read STICK0; keep the wanted direction until it can be taken; cornering (a perpendicular turn forces a step); one step is 1 pixel sideways or 2 vertically; the sub-cell counters (0-3) and MazePtr (+-1 per 4 pixels, +-$28 per row) follow; the tunnel wraps x between $2A and $CA; frozen (bit 7 of `PacFrozen`) returns at once.",
     "`MAZE_ROW_STRIDE`, `TUNNEL_X_*`, `NoReverseMask`", "20, 16; `tests/test_tunnel_clip.py`", "LIVE + MODEL (`MovePacMan` 15,000 calls: joystick, cornering, sub-cells, MazePtr, tunnel wrap, chomp picture, `tools/algorithm_models4.py`)"),
    ("A06", "Dots, power pellets and the dot count", ["EatDotAtPacMan", "PowerPelletCheck", "PowerPelletEaten", "BlinkPowerPellets", "ShowPowerPellets"],
     "At each new cell test the maze byte through `MazePtr`: 1 = a dot (cleared, +10 points, the dot sound, `DotDelay` = 1, counted per player); 2 = the cell is cleared and nothing else happens here; the four power-pellet squares are recognised by position (`PowerPelletCheck`, with `PelletFlags`) and call `PowerPelletEaten` (50 points, the frightened period); the board is complete at 260 dots and pellets ($0104); the four pellet cells blink with the jiffy clock and follow `PelletFlags`.",
     "`SCORE`: digits 1 / 5 in `ScoreAdd`", "20, 12", "LIVE + MODEL (eating a dot 12,000 calls, a power pellet 15,000 calls, `tools/algorithm_models2.py`)"),
    ("A07", "Score: BCD addition, leading zeros, extra life", ["AddToScore"],
     "Add the six BCD digits of `ScoreAdd` (100,000 first) to the six screen cells of the player on turn, from the units upwards with decimal carry; a cell holds `$10 + digit`; a zero digit is blank unless a digit to its left is non-blank or a carry is pending, and the top digit zero is always blank; the amount is cleared; when the cell of the 10,000s becomes non-blank for the first time (`ExtraLifeFlag` = 0) the player gets one more life (+1 flag, +1 `Lives`).",
     "`SCORE_DIGIT_MASK`, `SCORE_DIGIT_BASE`, cells `$202A-$202F` / `$2047-$204C`", "12, 19, C-23; `tools/algorithm_models.py`", "LIVE + MODEL (6,000 additions)"),
    ("A08", "Speed pacing", ["MoveDelayTick", "InitBoard"],
     "Each entity has `MoveDelayCount` (frames to the next step) and `MoveDelayCycle` (0-3). Every frame the count falls; at 0 the cycle advances (3 wraps to 0) and the count is reloaded from `MoveDelay[base[min(Level,6)] + cycle]` (Pac-Man: `PacMoveDelayBase`, ghosts: `GhostMoveDelayBase`); the routine returns A = 0 when the entity acts in this frame, $FF when it waits. A frightened ghost and a ghost in the tunnel row act only on every second run-out (`HalfSpeedToggle`).",
     "`MoveDelay` $07AE (24), `PacMoveDelayBase`, `GhostMoveDelayBase`, `LEVEL_CLAMP_SPEED`", "14, 18; `tests/test_levels.py`", "LIVE + MODEL (every level 0-255, 10,241 calls)"),
    ("A09", "Junction lookup", ["JunctionLookup"],
     "If the entity's y is one of the 10 lattice rows and x one of the 10 lattice columns it is at a lattice point: mask = `JunctionExits[row][col]`, carry set; on a lattice row between columns the mask is $0C (left / right), anywhere else $03 (up / down). A ghost's mask loses the reverse of its direction (`NoReverseMask[dir]`); on the squares beside the door (y $64, x $76 / $82) a frightened ghost gets up only, a normal ghost loses up (mask AND $0E, or up if nothing is left).",
     "`JunctionYList`, `JunctionXList`, `JunctionExits`, `NoReverseMask`, `DOOR_*`", "13, 15, 18", "LIVE + MODEL (29,184 calls)"),
    ("A10", "Steering at a lattice point", ["SteerToTarget"],
     "Wanted vertical direction: none if y equals the target's, else toward the target (away from it when the ghost is frightened); wanted horizontal the same on x. If the vertical want is open in the exit mask: when the horizontal want is open too pick one by bit 7 of a POKEY `RANDOM` read, else the vertical; else if the horizontal want is open take it; else take the lowest set bit of `RANDOM AND mask` (of the mask if that is 0; right if the mask is empty).",
     "`RANDOM` ($D20A) read at `$B9E1` and `$B9F4`", "13, 18; `tools/algorithm_models.py`", "LIVE + MODEL (30,000 calls)"),
    ("A11", "Ghost state machine", ["GhostBehaviour", "ForceChase", "ChaseTimerSirenSight", "GhostStartRoute", "GhostSelectPatrol", "GhostPatrolTravel", "GhostPatrol", "GhostGoToCorner", "GhostChase"],
     "By `GhostState`: $00 waits in the house; $01 follows its start route (`StartRoutes`, ends with $F: ghosts 1-3 go to patrol travel, ghost 0 chases with `ChaseTimer` = $50); $08 walks to the start junction of the chosen patrol route; $10 walks the route (one direction nibble per junction, wraps at 0); $20 goes to its corner; $02 chases (target = Pac-Man's position); timers fall every 8th jiffy and send the ghost to the corner when they reach 0; late in the board (dots eaten >= $E0 / $F0) `ForceChase` puts ghosts in patrol or corner state into chase and sets `ChaseTimer` to $FF (the value of X after its loop: `stx ChaseTimer`, no immediate); the eaten bit (bit 6) is tested by `asl a / bpl`, not by a mask.",
     "`StartRoutes`, `PatrolRoutes`, `PatrolStartPositions`, `CornerPositions`, `PATROL_TIME`, `CHASE_*`, `RANDOM` at `$B859` (route = RANDOM AND $0F)", "13, 17", "LIVE (75,452 route reads, 261 selections, 864 start-route reads) + MODEL (the forced chase, the siren step and the sight test of patrolling ghosts: 24,000 calls; the route routines are not modelled)"),
    ("A12", "Sight test", ["GhostSeesPacMan"],
     "A ghost on Pac-Man's row or column, facing him, with no blocking entry between (read through the offset tables `SightOffsetsX/Y` into `SightListsX/Y`), switches to chase with `ChaseTimer` = $A0; ghost 2 reacts only when `RTCLOK2` bit 7 is clear.",
     "`SightListsX/Y`, `SightOffsetsX/Y`", "15; `tools/sight_model.py`", "LIVE + model of the sight test + MODEL against the ROM code (20,000 calls, `tools/algorithm_models2.py`)"),
    ("A13", "The ghost house", ["HouseWaitingTick", "HouseBobStep", "HouseLeaveStep", "HouseLeaveGhost2", "HouseLeaveGhost3", "SetReleaseTimers", "ClearPlayerCounters"],
     "Waiting ghosts 1-3 (state $00 / $80): every 4th jiffy the release timer falls and the ghost bobs between y $70 and $78; at 0 it leaves (ghosts 2 and 3 first walk to x $7C, then all go up the door column one step per 4 frames); at the door row y $64 the state becomes $01 (or keeps bit 7 and becomes $02) and the direction left. `SetReleaseTimers` gives ghosts 1-3 `HouseReleaseTimers[min(Level,3) + 2 - i]`; ghost 0 starts outside.",
     "`HouseReleaseTimers`, `DOOR_*`", "18, 14", "LIVE + MODEL (release timers, every level; `HouseWaitingTick`, `HouseBobStep`, `HouseLeaveStep` / `Ghost2` / `Ghost3`: 9,000 calls each, `tools/algorithm_models3.py`)"),
    ("A14", "The frightened period", ["PowerPelletEaten", "FrightenedTick", "FrightenedSound"],
     "A power pellet sets bit 7 of every ghost that is not eaten and reverses it (`ReverseDir`) unless state bit 2 is set, loads `FrightenCountdown` = `FrightenFrames[Level]` and `FrightenPhase` = 1, resets `GhostsEaten`; the countdown falls, then the phase steps every 24 frames (flashing on alternate steps) until it equals `FrightenEndPhase[Level]`; at the end every frightened ghost goes to its corner ($20; `AND $BB`, 0 stays) except a plain waiting house ghost ($80), which becomes $00, then `FrightenPhase` = 0 and `ChaseTimer` = $A0.",
     "`FrightenFrames` (15), `FrightenEndPhase` (20), `ReverseDir`, `FRIGHT_FLASH_FRAMES`", "14, 18, 17; `tests/test_frightened_house.py`", "LIVE + MODEL (`FrightenedTick` 20,000 calls and `FrightenedSound` 12,400 calls against the ROM; the start of the period is in A06)"),
    ("A15", "A ghost is eaten", ["GhostEaten", "GhostEatenPause"],
     "Contact with a frightened ghost: state $42, `EatenGhost`, the pop-up (`GhostScorePtrs[2*GhostsEaten]`: 200, 400, 800, 1600) drawn next to Pac-Man in the missile page, score added, the game freezes for 34 frames with a falling sweep (`AUDF` -4 / -3 alternately from $84 until $14) then colours and priority are restored; two ghosts cannot be eaten in one frame.",
     "`GhostScorePtrs`, `GhostScore*Digits`", "12, 18, 22; `tests/test_ghost_score.py`", "LIVE + MODEL (`GhostEaten` 9,000 calls, `GhostEatenPause` 12,000 calls, `tools/algorithm_models4.py`)"),
    ("A16", "The eaten ghost's return", ["EyesAndHousePerFrame", "HouseEnterStep", "EyesReturningSound"],
     "Every frame each eyes ghost steers to the door square (`DOOR_X`, `DOOR_Y`) with the normal steering and moves every frame (no pacing); at the door square state $44 (an arrival moving up is turned left first); inside it walks down to the floor y $74, ghosts 2 and 3 sideways to x $70 / $88, then the state loses bits 7 and 6 and the ghost leaves again.",
     "`DOOR_*`, `HOUSE_FLOOR_Y`", "18; `tools/altirra_door_up.cmd` (the up-arrival)", "LIVE (55 + 44 eaten journeys, C-58) + MODEL (`EyesAndHousePerFrame` 6,000 calls with the real steering, `HouseEnterStep` 9,000 calls, `EyesReturningSound`, `tools/algorithm_models3.py`)"),
    ("A17", "Contact and death", ["DeathSequence", "DeathAnimation", "DrawAllInPlace"],
     "A non-frightened, non-eaten ghost touching Pac-Man freezes him (97 frames), then the ghosts disappear, the 16-picture animation runs (8 frames each: the open shape, 14 shapes losing their top rows from `DeathPlotBytes` / `DeathPlotRows`, the star) with the AUDF1 glide, and after 129 more frames the turn handling takes over.",
     "`DeathPlotBytes`, `DeathPlotRows`, `StarShape`, `DEATH_*`", "20, 22; `tests/test_death.py`", "LIVE + software model (15,532 steps, 44 deaths) + MODEL (`DeathSequence` 12,900 calls and `DeathAnimation` 12,160 calls including a whole death frame by frame; the contact test in the frame model, `tools/algorithm_models5.py`, `tools/algorithm_models7.py`)"),
    ("A18", "Turn handling, lives, two players", ["TurnControl", "NewGameInit", "NewBoardInit", "ClearPlayerMemory", "FillPlayerPages", "LoadShadowColors", "Copy0800To0C00", "Copy0C00To1000", "Copy0C00To1400", "DrawReadyScreen", "DrawLives", "LifeIcon1", "LifeIcon2", "ClearReadyText"],
     "After a death (`WaitState` 1) the turn handling decides: lives left -> the READY! screen (`DrawReadyScreen` spends one life per READY!) and `InitBoard`; in a two-player game the maze of the player on turn is saved ($1000 / $1400) and the other player's loaded; no lives -> the game over. A new game: 3 lives, `Level` = `StartLevel`, counters cleared per player, the maze copied from the original ($0800).",
     "`SavedMaze1/2`", "19; `tests/test_two_players.py`", "LIVE + MODEL (`TurnControl` 6,000 calls, `CompareHighScore`, the labels, `tools/algorithm_models7.py`, `tools/algorithm_models5.py`)"),
    ("A19", "Level complete and the next board", ["AdvanceLevel", "DrawLevelIndicator"],
     "At the 260th dot: the level-end sequence (draw, wait, flash the maze `COLOR0` between $0C and $86, new board), `Level` + 1 (8-bit, wraps at 255), one more life; the level indicator in the bottom row shows the last 7 bonus items (`BonusItemCodes`).",
     "`BonusItemCodes`", "14, 20; `tests/test_levels.py`", "LIVE (levels 0-249) + MODEL (`AdvanceLevel`, `InitBoard`, `NewGameInit`, `NewBoardInit`, the level-complete flashing, `DrawLevelIndicator`: 300-4,000 calls each, `tools/algorithm_models5.py`)"),
    ("A20", "The bonus item", ["BonusItemUpdate", "BonusSound"],
     "At 80 and 160 dots eaten the item for `Level` (clamped to 12) appears for `$02C0` frames; eating it adds `BonusScore[Level]` and shows its score picture for 64 frames.",
     "`BonusItemCodes`, `BonusScore`, `BonusScoreGlyphs`, `BONUS_*`", "14, 15; `tests/test_item_shots.py`", "LIVE (C-36, C-50) + MODEL (`BonusItemUpdate` 15,000 calls, the pick-up in the frame model, `BonusSound` 10,300 calls, `tools/algorithm_models4.py`, `tools/algorithm_models5.py`)"),
    ("A21", "Drawing and the tunnel clip", ["StepAndDrawEntity", "ClipEntitiesOnTunnelRow", "ClipEntityAtTunnel"],
     "An entity moves one step by its direction (2 pixels vertically, 1 horizontally; not when `DrawOnly`), then its 10-row picture (direction block + feet phase, frightened or eyes) is copied with a 16-row loop to the player page at row `y`; on the tunnel row the picture is masked at the screen edges and x wraps.",
     "`GhostShape*`, `PacShape*`, `TUNNEL_*`", "16, 20; `tests/test_ghost_frames.py`, `tests/test_tunnel_clip.py`", "LIVE (pixels equal the bitmaps) + MODEL (`StepAndDrawEntity` 8,000 calls, `ClipEntityAtTunnel` 6,000 calls, the lives, the labels, `DrawAllInPlace`, `tools/algorithm_models3.py`, `tools/algorithm_models5.py`)"),
    ("A22", "Sound", ["DotSoundSweep", "ClearPokeyRegisters", "EyesReturningSound"],
     "One routine or inline block per sound on channels 1-4: dot sweep (alternating rising / falling `AudfSweepUp/Down`), bonus, ghost eaten (high-pass sweep), frightened triangle, eyes, siren (triangle $28-$40 stepping by `SirenStep`), death glide, start tune (`TuneAudf1/2`, one step per 4 jiffies); `ClearPokeyRegisters` silences all eight.",
     "`TuneAudf1/2`, `AudfSweep*`", "22 (waveform-checked: C-04 ... C-24)", "LIVE + measured audio + MODEL (the frightened sweep, the eyes sweep, the dot sweep, the bonus sound, the eaten-ghost pause sweep, the siren, the death glissando and the intro tune, each against the register writes of the code: `tools/algorithm_models2.py` to `tools/algorithm_models7.py`)"),
]
# routines that no algorithm names explicitly: they belong to the algorithm of their caller
EXTRA_ROUTINES = {"InitDisplay2": "A04", "ToggleLegPhase": "A03", "DrawAllInPlace": "A17", "BlinkPlayerLabel": "A02"}


def routine_algorithm():
    """routine name -> algorithm ids"""
    out = collections.defaultdict(list)
    for aid, name, routines, rule, tables, evidence, status in ALGORITHMS:
        for r in routines:
            out[r].append(aid)
    return out


def evidence_text():
    if os.path.exists(EVIDENCE):
        with open(EVIDENCE, encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    return None


SETS = [(2, "the sight test (also against every position on four rows and four columns), the forced chase and the siren step, the frightened sound and tick, eating a dot and a power pellet"),
        (3, "the ghost house (bobbing, leaving, entering), the way of an eaten ghost, `StepAndDrawEntity`"),
        (4, "Pac-Man's step, the bonus item, eating a ghost and its pause, the dot sound"),
        (5, "the scores and the high score, the tunnel clip, the fruit sound, the drawing routines, the siren, the level change, the board set-up, the death sequence and its animation"),
        (6, "the display-list interrupts, the display list, the title clearing, the key loop of `Start` and the restart"),
        (7, "the ghost state machine, the turn handling, the title screens, the whole game frame and the vertical-blank handler")]


def coverage_text():
    path = os.path.join(os.path.dirname(EVIDENCE), "evidence-model-coverage-summary.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read().splitlines()[2:]
    return None


def evidence_set(k):
    path = os.path.join(os.path.dirname(EVIDENCE), "evidence-algorithms%d-summary.txt" % k)
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read().splitlines()[2:]
    return None


def evidence2_text():
    path = os.path.join(os.path.dirname(EVIDENCE), "evidence-algorithms2-summary.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read().splitlines()[2:]
    return None


def fmt_val(v, kind):
    return "$%02X" % v


def report():
    rom, F, owner, cen = census()
    L = []
    P = L.append
    names = {f.name for f in F.values()}
    total = sum(len(v) for v in cen.values())
    kinds = collections.Counter(k for v in cen.values() for a, k, val, s in v)
    P("# 31 - Constants and Algorithms (stage 50)")
    P("")
    P("GENERATED by `python -I tools/analyze_constants.py --write docs/31-constants-algorithms.md` from the trace of `src/asm/pacman.s`, the routines of `23-function-table.md`, `24-function-relationships.md`, the executable models of `tools/algorithm_models.py` .. `algorithm_models7.py` (`analysis/evidence-algorithms*-summary.txt`, `analysis/evidence-model-coverage-summary.txt`) and the chapters named in each row. Tests: `tests/test_constants.py`, `tests/test_algorithms.py`, `tests/test_algorithms2.py`, `tests/test_algorithms_more.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- **%d immediate constants** in the code of %d routines (compared %d, assigned to a variable or register %d, masks %d, added / subtracted %d, loaded as counters / indexes %d). Section 3 lists every one of them by routine, with the variable or register it belongs to." % (
        total, len(cen), kinds["cmp"], kinds["assign"], kinds["logic"], kinds["arith"], kinds["load"]))
    P("- **%d constants carry a meaning of the game** (the door square, the tunnel, the ghost states, the timers, the thresholds, the score digits, the hardware set-up): section 2, each with a proposed C name and the routines where the code uses it (checked by `tests/test_constants.py`). The rest are loop counts, indexes and the immediate halves of 16-bit addresses." % len(NAMED))
    P("- **%d algorithms** (section 4) cover **all %d routines**: each has its rule, its tables and constants, its evidence and a status. **All 22 are also run as models** against the ROM code (section 5): first the data expansion of `Start`, the BCD score addition, the speed pacing, the house release timers, the junction lookup and the steering; since OV-58 (C-60) the rest, up to the whole game frame and the vertical-blank handler (about 940,000 calls, the whole memory compared after each one; every instruction of the ROM is executed by them and every one-sided conditional branch is explained)." % (
        len(ALGORITHMS), len(F)))
    P("- The data of the algorithms (tables, level formulas, shapes) is in `12`, `14`, `15`, `16` and in the table census of stage 49; this chapter adds the **numbers inside the code** and **what each routine computes**.")
    P("- **Randomness**: the program reads POKEY `RANDOM` (`$D20A`) at exactly **3 places**: `$B859` (`GhostSelectPatrol`: the route is `RANDOM AND $0F`), `$B9E1` (`SteerToTarget`: vertical or horizontal choice by bit 7) and `$B9F4` (`SteerToTarget`: a random exit, `RANDOM AND mask`). Every use of `RANDOM` in the program is one of them; for equivalence tests (stages 86-87) the port needs a `RANDOM` source that can be fed the recorded values of the emulator, and for play a POKEY polynomial counter (`pokey_noise.py`).")
    P("")
    P("## 2. The named constants")
    P("")
    P("| C name | Value | Meaning | Used in (as an immediate) | Chapter |")
    P("|---|---|---|---|---|")
    imm = collections.defaultdict(set)
    for rn, lst in cen.items():
        for a, k, val, s in lst:
            imm[rn].add(val)
    for name, val, meaning, routines, chap in NAMED:
        found = [r for r in routines if val in imm.get(r, set())]
        P("| `%s` | `$%02X` (%d) | %s | %s | %s |" % (name, val, val, meaning, ", ".join(found) if found else "**NOT FOUND**", chap))
    P("")
    P("```c")
    for name, val, meaning, routines, chap in NAMED:
        P("#define %-26s 0x%02X   /* %s */" % (name, val, meaning[:70]))
    P("```")
    P("")
    P("## 3. Every immediate constant, by routine")
    P("")
    P("Per routine, in code order: `compare` = `cmp / cpx / cpy #n` with what is compared; `assign` = a constant stored to a variable or hardware register; `mask` = `and` / `or` / `xor`; `add` = `adc` / `sbc`; `load` = a constant kept in a register (loop counts and indexes).")
    P("")
    for rn in sorted(cen, key=lambda r: min(a for a, k, v, s in cen[r])):
        lst = sorted(cen[rn])
        P("### %s" % rn)
        P("")
        groups = collections.OrderedDict((("compare", "cmp"), ("assign", "assign"), ("mask", "logic"), ("add", "arith"), ("load", "load")))
        for title, kind in groups.items():
            items = [(a, val, s) for a, k, val, s in lst if k == kind]
            if not items:
                continue
            if kind == "cmp":
                txt = ", ".join("%s vs $%02X (`$%04X`)" % (s, val, a) for a, val, s in items)
            elif kind == "assign":
                txt = ", ".join("%s := $%02X (`$%04X`)" % (s, val, a) for a, val, s in items)
            elif kind == "load":
                txt = ", ".join("%s $%02X (`$%04X`)" % (s, val, a) for a, val, s in items)
            else:
                txt = ", ".join("%s $%02X (`$%04X`)" % (s, val, a) for a, val, s in items)
            P("- **%s**: %s" % (title, txt))
        P("")
    P("## 4. The algorithms")
    P("")
    P("Status: **LIVE** = checked against the running game (the chapter and the register `OPEN-VERIFICATION.md` name the sessions); **MODEL** = also executed here: the ROM routine run in `tools/cpu6502.py` against a model, section 5.")
    P("")
    rtn = routine_algorithm()
    for aid, name, routines, rule, tables, evidence, status in ALGORITHMS:
        P("### %s - %s" % (aid, name))
        P("")
        P("- **Routines**: %s" % ", ".join("`%s`" % r for r in routines))
        P("- **Rule**: %s" % rule)
        P("- **Tables and constants**: %s" % tables)
        P("- **Evidence**: %s" % evidence)
        P("- **Status**: %s" % status)
        P("")
    covered = set(rtn)
    P("### Routines and their algorithms")
    P("")
    P("| Routine | Algorithm |")
    P("|---|---|")
    for rn in sorted(names):
        ids = rtn.get(rn) or ([EXTRA_ROUTINES[rn]] if rn in EXTRA_ROUTINES else [])
        P("| %s | %s |" % (rn, ", ".join(ids) if ids else "**NONE**"))
    P("")
    P("## 5. The algorithms run as models")
    P("")
    ev = evidence_text()
    if ev:
        P("`tools/cpu6502.py` is a 6502 interpreter (151 official opcodes, NMOS decimal mode, no hardware); it is itself checked by the first line below: **the ROM's own `Start` expands the maze, the nibble tables and both charsets to exactly the images of the independent decoders** (which were verified against the emulator's RAM, `12`). `tools/algorithm_models.py` then runs five more routines against models, and `tools/algorithm_models2.py` (OV-58) seven more, comparing the whole memory after every call (see the end of this section) written from the rules of section 4:")
        P("")
        P("```")
        for line in ev:
            P(line)
        P("```")
        P("")
        P("**OV-58: the other algorithms.**  Sets 2 to 7 (`tools/algorithm_models2.py` .. `algorithm_models7.py`) compare **the whole memory** (the zero page, `$0200-$9FFF` and the POKEY / GTIA / ANTIC page) byte for byte after every call, not only the results; the stack page is left out (below S it holds dead return addresses). A routine that is already proved equal to its model is called as Python code by the model of its caller, except `JunctionLookup` and `SteerToTarget`, which run as real ROM code inside the models of the ghost routines so that the RANDOM values they take are counted and compared too. The last model (`FrameDispatch` / `VbiHandler`) is the whole frame of the game.")
        P("")
        for k, what in SETS:
            ev2 = evidence_set(k)
            if not ev2:
                P("NOT YET RUN: `analysis/evidence-algorithms%d-summary.txt`" % k)
                continue
            P("Set %d (`tools/algorithm_models%d.py`, `analysis/evidence-algorithms%d-summary.txt`): %s" % (k, k, k, what))
            P("")
            P("```")
            for line in ev2:
                P(line)
            P("```")
            P("")
        cov = coverage_text()
        if cov:
            P("**What the comparisons reach of the ROM** (`tools/analyze_model_coverage.py`, `analysis/evidence-model-coverage-summary.txt`; all seven sets run with the interpreter counting every instruction and the outcome of every conditional branch):")
            P("")
            P("```")
            for line in cov:
                P(line)
            P("```")
            P("")
        P("A model that disagrees with the ROM would be shown here with the first inputs; the tests also break each model on purpose and require the comparison to notice (`tests/test_algorithms.py`).")
    else:
        P("NOT YET RUN: `analysis/evidence-algorithms-summary.txt` does not exist (run `python -I tools/algorithm_models.py --write analysis/evidence-algorithms-summary.txt`).")
    P("")
    P("## 6. What the port does with this")
    P("")
    P("- The named constants of section 2 become the `#define` / `enum` block of the C code (`src/c`, stage 74); the census of section 3 is the checklist that no number of the original is lost or invented (the C re-implementation of stage 76-78 can be compared routine by routine).")
    P("- Each algorithm of section 4 is one C function or a small group (`AddToScore` -> `add_to_score`, `SteerToTarget` -> `steer_to_target`, ...); the models of section 5 (all 22 algorithms, the whole frame included) are **ready-made unit-test oracles**: the same inputs, run against the C function, must give the model's outputs, and the model has been shown equal to the ROM.")
    P("- `RANDOM`: three call sites, each a pure function of one POKEY byte; the port takes the byte from a function `pokey_random()` so that the tests can replay the emulator's values and the game can use a real polynomial counter.")
    P("- `cpu6502.py` can run any other pure routine of the ROM on demand (for example the contact test or `StepAndDrawEntity` with a stubbed hardware), which is the quickest way to answer a question about the original while the C code is written.")
    P("")
    return L


def main():
    if "--census" in sys.argv:
        rom, F, owner, cen = census()
        for rn in cen:
            for a, k, val, s in cen[rn]:
                print("%04X %-24s %-6s $%02X %s" % (a, rn, k, val, s))
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
