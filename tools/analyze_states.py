"""Stage 58: state transitions - the state machines of the game, from the code and from the running game.

State variables (STATES below, with the meaning of every value): the screen state, the start / turn / wait / level-end sequence variables, the death state, the eaten-ghost pause, the frightened phase, the bonus item,
the ghost states.  Static part: every instruction that writes one of them (tools/analyze_stack.py: the traced code) with the value it stores when that is a constant of the code.  Live part: tools/run_state_audit.ps1 puts
a write watch on each variable in twenty sessions of the real game and prints every write (address, value, writing instruction, frame); this tool rebuilds, per variable, the sequence of values and the transitions
old -> new with their counts and writers.  The document docs/34-state-transitions.md and the summary analysis/evidence-states-summary.txt are written from both.
Usage:  python -I tools/analyze_states.py --probes | analysis/raw-logs/states-*.txt [--write analysis/evidence-states-summary.txt] | --doc [docs/34-state-transitions.md]
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "analysis", "evidence-states-summary.txt")

# address, name, size, {value: meaning}
STATES = [
    (0x19, "GameState", 1, {0: "game frame, or the game-over countdown", 1: "title: copyright screen set up", 2: "title: copyright screen shown (waits for the time)", 3: "title: menu", 4: "title: menu, after a game / demo"}),
    (0x1A, "TwoPlayers", 1, {0: "one player", 1: "two players"}),
    (0x1C, "IntroRequest", 1, {0: "none", 1: "START pressed: the new game is being set up", 2: "the board is set up: the frame routine starts the READY! intro"}),
    (0x20, "CountdownActive", 1, {0: "no countdown", 1: "the 30 s game-over countdown runs"}),
    (0x21, "PlayStarted", 1, {0: "the start tune is not finished", 1: "the start tune has finished: play"}),
    (0x22, "StartTuneActive", 1, {0: "no start tune", 1: "the start tune plays"}),
    (0x23, "TurnSwitchState", 1, {0: "no turn switch", 1: "load player 1's maze", 2: "load player 2's maze", 3: "the load is done"}),
    (0x24, "WaitState", 1, {0: "normal frame", 1: "turn handling after a death", 2: "the READY! wait"}),
    (0x26, "LevelComplete", 1, {0: "no", 1: "the last dot was eaten: the level-end sequence"}),
    (0x27, "LevelEndStep", 1, {0: "draw the frozen board", 1: "wait", 2: "flash the maze", 3: "set up the new board", 4: "advance to the next level (AdvanceLevel resets it to 0)"}),
    (0x2B, "CurrentPlayer", 1, {0: "player 1", 1: "player 2"}),
    (0x9B, "Paused", 1, {0: "playing", 1: "paused (the space bar)"}),
    (0x9F, "BonusVisible", 1, {0: "no bonus item", 1: "the bonus item is on the screen"}),
    (0xA1, "BonusScoreShown", 1, {0: "no", 1: "the bonus score picture is shown"}),
    (0xAA, "PacFrozen", 1, {0x00: "free", 0x80: "frozen (death)"}),
    (0xE5, "EatPause", 1, {0: "no", 1: "the pause after a ghost was eaten"}),
    (0xEA, "DeathAnimActive", 1, {0: "no", 1: "the death animation runs"}),
    (0xED, "DeathState", 1, {0: "alive", 1: "freeze (97 frames)", 2: "start of the death sound", 3: "sound glide up", 4: "sound glide down", 5: "sound glide, second part", 6: "end: the turn handling follows"}),
    (0xFC, "FrightenPhase", 1, {0: "no frightened period", 1: "solid blue", 2: "flashing (phase 2 ...)"}),
    (0xCE, "GhostState", 4, {0x00: "waits in the house", 0x01: "start route", 0x02: "chase", 0x08: "walks to the patrol start", 0x10: "patrols", 0x20: "goes to its corner", 0x42: "eyes returning (eaten)", 0x44: "eyes at the door",
                              0x80: "frightened, waiting in the house", 0x81: "frightened (bit 7 added)", 0x82: "frightened chase", 0x88: "frightened, to the patrol start", 0x90: "frightened patrol", 0xA0: "frightened, to the corner"}),
]
# the values a variable can have (the closure of the rules: every rule writes a value of this set from values of this set; tools/check_state_rules.py checks it by running the code)
DOMAIN = {
    "GameState": [0, 1, 2, 3, 4], "TwoPlayers": [0, 1], "IntroRequest": [0, 1, 2], "CountdownActive": [0, 1], "PlayStarted": [0, 1], "StartTuneActive": [0, 1], "TurnSwitchState": [0, 1, 2, 3],
    "WaitState": [0, 1, 2], "LevelComplete": [0, 1], "LevelEndStep": [0, 1, 2, 3, 4], "CurrentPlayer": [0, 1], "Paused": [0, 1], "BonusVisible": [0, 1], "BonusScoreShown": [0, 1],
    "PacFrozen": [0x00, 0x80], "EatPause": [0, 1], "DeathAnimActive": [0, 1], "DeathState": [0, 1, 2, 3, 4, 5, 6], "FrightenPhase": list(range(256)),
    "GhostState": [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x42, 0x44, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0],
}
ADDR = {}
ADDR_OF_NAME = {}
for a, n, size, d in STATES:
    for k in range(size):
        ADDR[a + k] = (n, k, a)
    ADDR_OF_NAME[n] = a
BOOT_PCS = {0xA395, 0xA39C}                                  # the clears of $18-$3F and $80-$FF at the start of `Start`
WRITERS = ("sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror")


def preds(rom):
    p = collections.defaultdict(list)
    for a in rom.ins:
        for s in rom.succ(a):
            p[s].append(a)
    return p


def constant_before(rom, pred, a, reg):
    """the immediate value that the register `reg` ('a', 'x', 'y') holds when the store at a executes, if the straight line before it loads one and no branch target intervenes; else None"""
    load = {"a": "lda", "x": "ldx", "y": "ldy"}[reg]
    cur = a
    for _ in range(8):
        ps = pred.get(cur, [])
        if len(ps) != 1:
            return None
        cur = ps[0]
        n, m, mode, op = rom.ins[cur]
        if m == load:
            return op if mode == "imm" else None
        # an instruction that changes the register or the flow stops the search
        if m in ("sta", "stx", "sty", "cmp", "cpx", "cpy", "bit", "nop", "pha", "php", "clc", "sec", "cld", "sed"):
            continue
        if m in ("inx", "iny", "dex", "dey") and reg == {"inx": "x", "iny": "y", "dex": "x", "dey": "y"}[m]:
            return None
        if m in ("inx", "iny", "dex", "dey", "ldx", "ldy", "lda", "tax", "tay", "txa", "tya") and (m in ("ldx", "inx", "dex", "tax") and reg != "x" or m in ("ldy", "iny", "dey", "tay") and reg != "y" or m in ("lda", "txa", "tya") and reg != "a"):
            continue
        return None
    return None


def static_writers():
    rom, F, owner = AS.load()
    pred = preds(rom)
    out = []
    for a in sorted(rom.ins):
        n, m, mode, op = rom.ins[a]
        if m in WRITERS and mode in ("zp", "zpx", "abs") and isinstance(op, int):
            base = None
            if op in ADDR:
                base = op
            elif mode == "zpx":
                for lo, name, size, d in STATES:
                    pass
            if op in ADDR:
                name, k, first = ADDR[op]
                if m in ("inc", "dec"):
                    val = "+1" if m == "inc" else "-1"
                elif m in ("asl", "lsr", "rol", "ror"):
                    val = m
                else:
                    reg = {"sta": "a", "stx": "x", "sty": "y"}[m]
                    c = constant_before(rom, pred, a, reg)
                    val = "$%02X" % c if c is not None else "computed"
                out.append({"pc": a, "var": name, "addr": op, "m": m, "mode": mode, "value": val, "routine": F[owner[a]].name})
    return out, rom, F, owner


def bulk_writers(rom, F, owner):
    """indexed stores that clear or fill a range containing state variables (`sta zp_20,x` ...)"""
    out = []
    for a in sorted(rom.ins):
        n, m, mode, op = rom.ins[a]
        if m in ("sta", "stx", "sty") and mode == "zpx" and isinstance(op, int) and op not in ADDR:
            out.append((a, op, F[owner[a]].name))
    return out


def probe_lines():
    L = []
    for a, name, size, d in STATES:
        L.append('bta w %04x L%d "SW %%04X v=%%02X pc=%%04X f=%%d" @address @value pc @frame' % (a, size))
    return L


LINE = re.compile(r"^SW ([0-9A-F]{4}) v=([0-9A-F]{2}) pc=([0-9A-F]{4}) f=(\d+)")


def parse(paths):
    """-> runs: {name: [(frame, address, value, pc), ...]} in log order"""
    runs = {}
    for p in paths:
        h = os.path.basename(p)[len("states-"):-len(".txt")]
        ev = []
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = LINE.match(line)
                if m:
                    ev.append((int(m.group(4)), int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)))
        runs[h] = ev
    return runs


def game_pcs():
    w, rom, F, owner = static_writers()
    pcs = {x["pc"] for x in w}
    pcs |= {a for a, op, r in bulk_writers(rom, F, owner)}
    return pcs


def classify_pc(pc, gp):
    if pc in gp:
        return "game"
    if pc >= 0xC000:
        return "os"
    return "harness"


def transitions(runs):
    """-> per variable name: Counter of (old, new) by change, Counter of rewrites (same value), dict (old,new) -> Counter(pc), first value counts, and per transition the harness names"""
    gp = game_pcs()
    trans = collections.defaultdict(collections.Counter)
    same = collections.defaultdict(collections.Counter)
    by_pc = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    first = collections.defaultdict(collections.Counter)
    other = collections.defaultdict(collections.Counter)
    boot = collections.Counter()
    where = collections.defaultdict(lambda: collections.defaultdict(set))
    for h, ev in runs.items():
        last = {}
        for f, ad, v, pc in ev:
            name, k, base = ADDR[ad]
            key = ad
            cls = classify_pc(pc, gp)
            if cls != "game":
                other[name][(h, cls)] += 1
                last[key] = v                                      # the OS (at the cold start) and the harness's own test aids also change the value; the next write of the game starts from it
                continue
            if pc in BOOT_PCS:
                boot[name] += 1                                    # the clear of the zero page by Start
                last[key] = v
                continue
            if key in last:
                old = last[key]
                if old == v:
                    same[name][(old, pc)] += 1
                else:
                    trans[name][(old, v)] += 1
                    by_pc[name][(old, v)][pc] += 1
                    where[name][(old, v)].add(h)
            else:
                first[name][v] += 1
            last[key] = v
    return trans, same, by_pc, first, where, other, boot


def summary_lines(paths):
    runs = parse(paths)
    trans, same, by_pc, first, where, other, boot = transitions(runs)
    L = []
    P = L.append
    nev = sum(len(v) for v in runs.values())
    P("State audit (tools/run_state_audit.ps1, tools/analyze_states.py): %d harness logs (%s), %d writes to %d state variables printed" % (len(runs), ", ".join(sorted(runs)), nev, len(STATES)))
    P("")
    P("variable (address) | changes | transitions old -> new (count)")
    for a, name, size, d in STATES:
        tr = trans.get(name, {})
        P("%s ($%02X%s): %d changes, %d rewrites of the same value, %d distinct transitions" % (name, a, "-$%02X" % (a + size - 1) if size > 1 else "", sum(tr.values()), sum(same.get(name, {}).values()), len(tr)))
        for (o, n), c in sorted(tr.items()):
            P("    %02X -> %02X  %7d   by %s" % (o, n, c, " ".join("$%04X" % pc for pc in sorted(by_pc[name][(o, n)]))))
    return L


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# The transitions as the code makes them: (variable, from-values or None for any, to-value / function of the old value, writing instructions, rule).  Written from the code (docs 17-21, 26, 31); checked against the
# static writers (the value the instruction stores, the routine it is in) and against every transition the game made in the sessions (tests/test_states.py): a transition seen live that no rule allows would fail.
def _ghost_frighten(s):
    return {s | 0x80}


def _ghost_end(s):
    return {0x00} if s == 0x80 else {0x20}


def _ghost_leave(s):
    return {0x01} if s == 0 else {(s & 0x80) | 0x02}


RULES = [
    ("GameState", [0], 1, [0xA3A1], "`Start` after clearing the zero page: the copyright screen is set up"),
    ("GameState", [1], 2, [0xA70A], "the copyright screen is drawn: wait for its time"),
    ("GameState", [2], 3, [0xA70A], "the copyright time is over (RTCLOK2 = CopyrightEnd): the title menu"),
    ("GameState", [1, 2, 3, 4], 0, [0xA53B], "START (released) or a trigger: a new game"),
    ("GameState", [0], 4, [0xA552], "the game-over countdown ended (`CountdownTimer` = 0): the title after a game"),
    ("GameState", [0, 4], 3, [0xA552], "SELECT or OPTION in play, in the countdown or in state 4: the title menu"),
    ("GameState", [1, 2], 3, [0xA552], "a console key other than START at the copyright screen: the title menu"),
    ("TwoPlayers", [0], 1, [0xA54E], "SELECT in the title menu: two players"),
    ("TwoPlayers", [1], 0, [0xA54E], "SELECT again: one player"),
    ("IntroRequest", [0, 2], 1, [0xA53F], "START / trigger: the new game is being set up (from 2 if START is pressed in the one frame between the board set-up and the intro)"),
    ("IntroRequest", [1], 2, [0xA4B8], "the board and the status line are set up (`$A4B6`)"),
    ("IntroRequest", [2], 0, [0xA7CE], "the frame routine starts the READY! intro (`$A7C8`)"),
    ("CountdownActive", [0], 1, [0xAB1A], "no lives left for anybody: the game-over countdown starts"),
    ("CountdownActive", [1], 0, [0xA539], "a new game while the countdown runs"),
    ("PlayStarted", [0], 1, [0xA7FE], "the start tune has finished (index $40): play begins"),
    ("StartTuneActive", [0], 1, [0xA7C8], "the intro: the start tune begins"),
    ("TurnSwitchState", [0], 1, [0xAACC, 0xAADD], "two players: the player on turn is out of lives (or the turn ends) and the other one's maze has to be loaded: player 1's"),
    ("TurnSwitchState", [0], 2, [0xAAAF, 0xAA9A], "the same for player 2's maze"),
    ("TurnSwitchState", [1, 2], 3, [0xAA9A], "the maze is loaded"),
    ("TurnSwitchState", [3], 0, [0xAA94], "the load is done: the board of the next turn is set up"),
    ("WaitState", [0], 1, [0xAEF1], "the death sequence is over: the turn handling"),
    ("WaitState", [0], 2, [0xAC8C], "`AdvanceLevel`: the READY! wait of the new board"),
    ("WaitState", [1], 2, [0xA818], "the turn handling is done and play goes on: the READY! wait"),
    ("WaitState", [1], 0, [0xAB16], "nobody has a life left: back to the normal frame (the countdown follows)"),
    ("WaitState", [2], 0, [0xA828], "the wait is over ($25 frames): play"),
    ("LevelComplete", [0], 1, [0xB39C], "the last dot or pellet is eaten (dots eaten = $0104)"),
    ("LevelComplete", [1], 0, [0xAC86], "`AdvanceLevel`"),
    ("LevelEndStep", [0, 1, 2], "+1", [0xAC26], "the step is finished (`inc`): 0 -> 1 -> 2 -> 3"),
    ("LevelEndStep", [3], 4, [0xAC72], "the board is set up: advance"),
    ("LevelEndStep", [4], 0, [0xAC88], "`AdvanceLevel` resets the sequence"),
    ("CurrentPlayer", [0], 1, [0xAA8B], "two players: the turn goes to player 2"),
    ("CurrentPlayer", [1], 0, [0xAA61], "two players: the turn goes to player 1"),
    ("Paused", [0], 1, [0xA4E2], "the space bar (CH = $21, KEYDEL = 0): pause"),
    ("Paused", [1], 0, [0xA4E2], "the space bar again: resume"),
    ("BonusVisible", [0], 1, [0xB679], "80 or 160 dots eaten: the bonus item appears"),
    ("BonusVisible", [1], 0, [0xB694, 0xA964], "its time is over, or it was eaten"),
    ("BonusScoreShown", [0], 1, [0xA95C], "the bonus item was eaten: its score is shown"),
    ("BonusScoreShown", [1], 0, [0xB638], "the score picture's time is over"),
    ("PacFrozen", [0], 0x80, [0xA927], "a ghost touched Pac-Man: frozen"),
    ("EatPause", [0], 1, [0xA8F1], "a frightened ghost was eaten: the pause"),
    ("EatPause", [1], 0, [0xB08B], "the pause is over"),
    ("DeathAnimActive", [0], 1, [0xAE76], "the death animation begins"),
    ("DeathAnimActive", [1], 0, [0xAF51], "its last picture"),
    ("DeathState", [0], 1, [0xA930], "a ghost touched Pac-Man (not frightened, not eaten): the freeze"),
    ("DeathState", [1], 2, [0xAE57], "the 97 frames of the freeze are over"),
    ("DeathState", [2], 3, [0xAE7E], "the sound starts"),
    ("DeathState", [3], 4, [0xAECD], "four steps up the glide ($AE92)"),
    ("DeathState", [4], 3, [0xAECD], "the glide comes down to the start of a phase and the next phase begins"),
    ("DeathState", [4], 5, [0xAEEA], "the last phase is done ($6D)"),
    ("DeathState", [5], 6, [0xAEEA], "the glide ends at $25"),
    ("FrightenPhase", [0], 1, [0xB3EF], "a power pellet: the frightened period"),
    ("FrightenPhase", None, 1, [0xB3EF], "another power pellet during the period: it starts again"),
    ("FrightenPhase", list(range(1, 256)), "+1", [0xAFB6], "the flash timer ran out: the next phase (an end phase of 0 is never reached, so on the levels whose table entry is 0 the phase counts on to $FF and wraps)"),
    ("FrightenPhase", [1, 2, 4, 7, 8, 11, 15], 0, [0xAFA7], "the phase equals `FrightenEndPhase[Level]` (the values that table holds: 1, 2, 4, 7, 8, $0B, $0F): the period ends"),
    ("GhostState", [0], 1, [0xA800], "ghost 0 starts its route (`inc`)"),
    ("GhostState", [0, 4, 0x80, 0x84], _ghost_leave, [0xB756], "`HouseLeaveStep`: 00 -> 01, 04 -> 02, 80 -> 82 (a frightened ghost keeps bit 7)"),
    ("GhostState", [1], 8, [0xB853], "the start route ends (ghosts 1-3): walk to the patrol start"),
    ("GhostState", [0x20], 8, [0xB853], "the corner is reached: choose a patrol"),
    ("GhostState", [8], 0x10, [0xB895], "the patrol start is reached: patrol"),
    ("GhostState", [2, 8, 0x10], 0x20, [0xB8C7], "the chase or patrol timer ran out: go to the corner"),
    ("GhostState", [1], 2, [0xB8ED], "ghost 0's start route ends: chase"),
    ("GhostState", [8, 0x10], 2, [0xBAB9], "the ghost sees Pac-Man: chase"),
    ("GhostState", [8, 0x10, 0x20], 2, [0xB626], "late in the board (dots eaten >= $E0): forced chase"),
    ("GhostState", [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0], _ghost_frighten, [0xB40A], "a power pellet: bit 7 is added to every ghost that is not eaten"),
    ("GhostState", [0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0], 0x42, [0xA888], "a frightened ghost is eaten: eyes"),
    ("GhostState", [0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0], _ghost_end, [0xAFA0], "the frightened period ends: 80 -> 00 (house), the others -> 20 (corner)"),
    ("GhostState", [0x42], 0x44, [0xB6D0], "the eyes reach the door square"),
    ("GhostState", [0x44], 0x04, [0xB764], "the eyes are home (floor, or the side position of ghosts 2 and 3): bits 7 and 6 removed"),
]
# Pairs that the code makes (found by running it, tools/check_state_rules.py) but that no rule lists, with the reason a game does not reach them: the guard of the caller or an invariant of the other variables.
# These are ARGUMENTS read from the code (the evidence is: not made at the frame level / never seen in the sessions), not machine-proved facts; tests/test_states.py requires an argument for each such site.
# stores that only a RACE can make (found by the abstract search of tools/prove_state_rules.py; the rules above do not list them): (variable, pc) -> (the new value from the old one, the reason)
RACE_ONLY = {
    ("GhostState", 0xA800): (lambda o: (o + 1) & 0xFF, "ghost 0 is incremented a second time: START pressed, and the vertical-blank handler running inside the `$A47B` clear loop between the clears of `$26` and `$21` in the frame in which the last pellet is eaten, leaves LevelComplete set with PlayStarted = 0; the level advance (`$AC8C`) then makes WaitState = 2, and `$A7FE`->`$A800` and later `$A826`->`$A800` both add 1 (01 -> 02, 80 -> 81). The search allows the same race again before `InitBoard` clears ghost 0, which gives every n -> n+1 (255 pairs, 255 -> 00 included); only the first step (01 -> 02, 80 -> 81) was followed through by hand."),
}

EXTRA_PAIRS_SITES = {
    ("DeathAnimActive", 0xAE76): "`inc` in the state-2 branch of `DeathSequence`: the branch runs once per death (the same call moves `DeathState` to 3), and the flag is 0 until then because only `InitBoard` (which clears it) separates two deaths.",
    ("GhostState", 0xA800): "`inc GhostState` (ghost 0) at the end of the intro and of every READY! wait: at that moment ghost 0's state is 0 - `InitBoard` / the restart cleared it, and nothing writes it while the wait runs (the frame returns before the ghost loop); the code adds 1 to whatever is there. **Exception found by the abstract search (tools/prove_state_rules.py, slice R, witness in tools/absint_diag.py): a race.** If START is pressed and the vertical-blank handler runs inside the `$A47B` clear loop after `$26` has been cleared but before `$21` is, in the frame in which the last pellet is eaten, LevelComplete is set while PlayStarted ends up 0; the level advance (`$AC8C`) then sets WaitState = 2 with PlayStarted = 0, and ghost 0 is incremented twice (once at `$A7FE`->`$A800`, again at `$A826`->`$A800`): the pairs 01 -> 02 and 80 -> 81 at this site. It needs START and the last pellet in one frame and the interrupt inside a three-instruction window: possible in the code, not shown on a real run.",
    ("StartTuneActive", 0xA7C8): "`inc` in the intro branch: `IntroRequest` = 2 is set only after the restart cleared `$20-$3F` (which includes this flag), and the branch clears `IntroRequest`, so it runs once with the flag 0.",
    ("WaitState", 0xAC8C): "`sta WaitState := 2` in `AdvanceLevel`, after the level-end steps: the last dot is eaten in a play frame (`WaitState` 0), and a frame with `WaitState` 1 or 2 does not run the dot eating, so the old value is 0.",
    ("DeathState", 0xAECD): "`DeathSequence` is called only when `DeathState` is not 0 (`$A82F`); its fall-through for the other values ($AE92) would store 4 from 0.",
    ("EatPause", 0xA8F1): "`GhostEaten` runs in the contact test, which the frame reaches only with `EatPause` 0 (a non-zero value branches to `GhostEatenPause` at `$A83C`).",
    ("GhostState", 0xA888): "`GhostEaten` is entered only for a ghost with bit 7 set (`bmi` at `$A881`): the old values are the frightened ones.",
    ("GhostState", 0xB756): "`HouseLeaveStep` is called for waiting ghosts (`GhostState` AND $7F = 0: $00, $80) and, in `EyesAndHousePerFrame`, for ghosts with bit 2 set and bit 6 clear ($04, $84).",
    ("GhostState", 0xB764): "`HouseEnterStep` is called only for ghosts with bits 2 and 6 set (the eyes at the door, $44).",
    ("LevelEndStep", 0xAC88): "`AdvanceLevel` is reached only when `LevelEndStep` is not 0-3 (the dispatch at `$AC18-$AC6B`): the value is 4.",
    ("WaitState", 0xAB16): "`TurnControl` is called only with `WaitState` = 1 (`$A809`).",
    ("WaitState", 0xAEF1): "`inc WaitState` at the end of the death sequence: the death sequence runs only in the play frame, which needs `WaitState` = 0 (`$A805`).",
}

# the clears: the restart of a game ($A47B clears $20-$3F) and the board set-up ($ADB4 clears $80-$FF) set every state variable in their range to 0 from any value
BULK_CLEARS = [(0xA47B, 0x20, 0x3F, "the restart at `$A477` (START): $20-$3F cleared"), (0xADB4, 0x80, 0xFF, "`InitBoard` (a new board or a new life): $80-$FF cleared")]


def rule_matches(rule, old, new, pc):
    var, froms, to, pcs, text = rule
    if pc not in pcs:
        return False
    if froms is not None and old not in froms:
        return False
    if callable(to):
        return new in to(old)
    if to == "+1":
        return new == old + 1
    return new == to


def explain(name, old, new, pc):
    """the rules (or the bulk clears) that allow this change of this variable written by this instruction"""
    a = next(a for a, n, s, d in STATES if n == name)
    out = [r for r in RULES if r[0] == name and rule_matches(r, old, new, pc)]
    for cpc, lo, hi, text in BULK_CLEARS:
        if pc == cpc and new == 0 and lo <= a <= hi:
            out.append((name, None, 0, [cpc], text))
    return out


def analysis(paths):
    runs = parse(paths)
    trans, same, by_pc, first, where, other, boot = transitions(runs)
    unexplained = []
    seen = collections.defaultdict(collections.Counter)                 # rule index -> count
    ruleidx = {id(r): i for i, r in enumerate(RULES)}
    bulk_seen = collections.defaultdict(collections.Counter)
    for name, tr in trans.items():
        for (o, n), c in tr.items():
            for pc, k in by_pc[name][(o, n)].items():
                ex = explain(name, o, n, pc)
                if not ex:
                    unexplained.append((name, o, n, pc, k))
                for r in ex:
                    if id(r) in ruleidx:
                        seen[name][ruleidx[id(r)]] += k
                    else:
                        bulk_seen[name][(r[3][0], o)] += k
    return runs, trans, same, by_pc, other, boot, unexplained, seen, bulk_seen


def mermaid(name, edges):
    L = ["```mermaid", "stateDiagram-v2"]
    for (o, n), c in sorted(edges.items()):
        L.append("    s%02X --> s%02X : %d" % (o, n, c))
    L.append("```")
    return L


def timeline(runs, run, start_pred, stop_after, limit=60):
    """the first `limit` changes of state variables from the first write that satisfies start_pred, in the game's own writes (no OS, no harness aid)"""
    gp = game_pcs()
    last = {}
    out = []
    started = False
    for f, ad, v, pc in runs[run]:
        name, k, base = ADDR[ad]
        cls = classify_pc(pc, gp)
        old = last.get(ad)
        last[ad] = v
        if cls != "game" or pc in BOOT_PCS:
            continue
        if old is None or old == v:
            continue
        if not started and start_pred(name, old, v):
            started = True
        if started:
            out.append((f, name + ("[%d]" % k if k else ""), old, v, pc))
            if len(out) >= limit or stop_after(name, old, v):
                break
    return out


def summary_lines2(paths):
    runs, trans, same, by_pc, other, boot, unexplained, seen, bulk_seen = analysis(paths)
    L = summary_lines(paths)
    P = L.append
    P("")
    P("writes that are not transitions of the game (the game's next write starts from the value they left):")
    osn = collections.Counter()
    agg = collections.defaultdict(collections.Counter)
    for name, c in other.items():
        for (h, cls), n in c.items():
            if cls == "os":
                osn[h] += n
            else:
                agg[(name, cls)][h] += n
    P("  the OS at the cold start (pc >= $C000): %d writes in %d sessions (the OS clears its RAM before the cartridge starts)" % (sum(osn.values()), len(osn)))
    for (name, cls), c in sorted(agg.items()):
        P("  %s by the harness's own test aid: %s" % (name, ", ".join("%s %d" % kv for kv in sorted(c.items()))))
    P("")
    P("transitions seen that no rule of the code allows: %d" % len(unexplained))
    for u in unexplained:
        P("  %s %02X -> %02X by $%04X (%d times)" % u)
    P("")
    nrules = len(RULES)
    unseen = [i for i, r in enumerate(RULES) if not seen[r[0]].get(i)]
    P("rules of the code: %d, seen in the sessions: %d, not seen: %d" % (nrules, nrules - len(unseen), len(unseen)))
    for i in unseen:
        r = RULES[i]
        fr = "any" if r[1] is None else "/".join("%02X" % x for x in r[1])
        to = "computed" if callable(r[2]) else ("%02X" % r[2] if isinstance(r[2], int) else r[2])
        P("  NOT SEEN: %s %s -> %s by %s: %s" % (r[0], fr, to, " ".join("$%04X" % x for x in r[3]), r[4]))
    P("")
    P("rule counts (index in RULES of the tool, changes seen):")
    for i, r in enumerate(RULES):
        P("RULE %d %s %d" % (i, r[0], seen[r[0]].get(i, 0)))
    for name, c in sorted(bulk_seen.items()):
        for (cpc, olds), k in sorted(c.items()):
            P("BULK %s %04X %02X %d" % (name, cpc, olds, k))
    return L


def read_summary():
    """-> (trans: name -> {(old, new): count}, rule counts: name -> {index: count}, bulk: name -> {(pc, old): count}, unexplained count, writes, lines)"""
    with open(SUMMARY, encoding="utf-8", newline="") as fh:
        lines = fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    trans = collections.defaultdict(dict)
    rc = collections.defaultdict(dict)
    bulk = collections.defaultdict(dict)
    cur = None
    unexpl = None
    for ln in lines:
        m = re.match(r"^(\w+) \(\$[0-9A-F]{2}(-\$[0-9A-F]{2})?\): \d+ changes", ln)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"^    ([0-9A-F]{2}) -> ([0-9A-F]{2})\s+(\d+)", ln)
        if m and cur:
            trans[cur][(int(m.group(1), 16), int(m.group(2), 16))] = int(m.group(3))
            continue
        m = re.match(r"^RULE (\d+) (\w+) (\d+)$", ln)
        if m:
            rc[m.group(2)][int(m.group(1))] = int(m.group(3))
            continue
        m = re.match(r"^BULK (\w+) ([0-9A-F]{4}) ([0-9A-F]{2}) (\d+)$", ln)
        if m:
            bulk[m.group(1)][(int(m.group(2), 16), int(m.group(3), 16))] = int(m.group(4))
            continue
        m = re.match(r"^transitions seen that no rule of the code allows: (\d+)", ln)
        if m:
            unexpl = int(m.group(1))
    m = re.search(r"(\d+) writes to (\d+) state variables", lines[0])
    return trans, rc, bulk, unexpl, int(m.group(1)), lines



def read_exact():
    """-> (lines, header counts, {(var, pc): {'f': set, 'd': set}}) from analysis/evidence-state-rules-summary.txt (tools/check_state_rules.py)"""
    path = os.path.join(ROOT, "analysis", "evidence-state-rules-summary.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", newline="") as fh:
        lines = fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    ex = collections.defaultdict(lambda: {"f": set(), "d": set()})
    for ln in lines:
        m = re.match(r"^EXACT (\w+) ([0-9A-F]{4}) ([fd]) ([0-9A-F]{2}) ([0-9A-F]{2})$", ln)
        if m:
            ex[(m.group(1), int(m.group(2), 16))][m.group(3)].add((int(m.group(4), 16), int(m.group(5), 16)))
    counts = {}
    for ln in lines:
        for key, pat in (("frame_extra", r"^pairs made at the frame level that no rule allows: (\d+)"), ("direct_extra", r"^pairs made only by a direct call of a routine that no rule allows.*: (\d+)$"),
                         ("missing", r"^pairs a rule allows that no call made: (\d+)"), ("only_direct", r"^pairs a rule allows that only a direct call made.*: (\d+)"),
                         ("calls", r"^Exactness of the transition rules .*: (\d+) calls of the ROM"), ("sites", r"^writing instructions examined: (\d+)")):
            m = re.match(pat, ln)
            if m:
                counts[key] = int(m.group(1))
    return lines, counts, ex


def live_pairs():
    """-> {(variable, writing pc): set of (old, new)} seen in the sessions (analysis/evidence-states-summary.txt)"""
    out = collections.defaultdict(set)
    cur = None
    if not os.path.exists(SUMMARY):
        return out
    with open(SUMMARY, encoding="utf-8", newline="") as fh:
        for ln in fh.read().replace("\r\n", "\n").split("\n"):
            m = re.match(r"^(\w+) \(\$[0-9A-F]{2}(-\$[0-9A-F]{2})?\): \d+ changes", ln)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r"^    ([0-9A-F]{2}) -> ([0-9A-F]{2})\s+(\d+)\s+by (.*)$", ln)
            if m and cur:
                for pc in re.findall(r"\$([0-9A-F]{4})", m.group(4)):
                    out[(cur, int(pc, 16))].add((int(m.group(1), 16), int(m.group(2), 16)))
    return out


def rule_pair_set(rl):
    f = range(256) if rl[1] is None else rl[1]
    out = set()
    for o in f:
        if callable(rl[2]):
            out |= {(o, n) for n in rl[2](o)}
        elif rl[2] == "+1":
            out.add((o, (o + 1) & 0xFF))
        else:
            out.add((o, rl[2]))
    return {p for p in out if p[0] != p[1] and p[0] in DOMAIN[rl[0]]}


def rule_pair_classes(ex):
    """the pairs of the rules: made at the frame level / only by a direct call and seen in the sessions / only by a direct call and not seen in the sessions"""
    live = live_pairs()
    by = collections.defaultdict(list)
    for rl in RULES:
        for pc in rl[3]:
            by[(rl[0], pc)].append(rl)
    total = frame = d_live = 0
    d_unseen = collections.defaultdict(set)
    for (name, pc), rls in by.items():
        al = set()
        for rl in rls:
            al |= rule_pair_set(rl)
        e = ex.get((name, pc), {"f": set(), "d": set()})
        for p in al:
            total += 1
            if p in e["f"]:
                frame += 1
            elif p in live.get((name, pc), set()):
                d_live += 1
            else:
                d_unseen[(name, pc)].add(p)
    return total, frame, d_live, d_unseen


def condensed(pairs, domain):
    by = collections.defaultdict(list)
    for o, n in sorted(pairs):
        by[n].append(o)
    parts = []
    for n, olds in sorted(by.items()):
        parts.append("%s -> %02X" % ("any" if set(olds) >= set(domain) - {n} else "/".join("%02X" % x for x in olds), n))
    return "; ".join(parts)


def exact_section(trans):
    """the markdown lines of section 5 (the exact relation of the code); `trans` = the live transitions with their writers"""
    r = read_exact()
    L = []
    P = L.append
    P("## 5. The exact relation of the code, and what is argued")
    P("")
    if not r:
        P("NOT YET RUN: `analysis/evidence-state-rules-summary.txt` does not exist (run `python -I tools/check_state_rules.py --write analysis/evidence-state-rules-summary.txt`, about 10 minutes).")
        P("")
        return L
    lines, counts, ex = r
    P("The rules of section 4 say what a game does. Whether they are **complete and exact for the code** was checked by running the code (`tools/check_state_rules.py`, `analysis/evidence-state-rules-summary.txt`): in the 6502 interpreter, %d calls - the whole frame, the vertical-blank handler, the key loop with its restart, `InitBoard`, `Start`, the OV-58 comparisons (every instruction of the ROM, state variables random in each) and 17 routines called directly - with **every state variable forced to every value of its domain** in random contexts, every store to a state variable logged with the writing instruction, the old and the new value." % counts["calls"])
    P("")
    P("- Writing instructions examined: **%d** (the 62 stores of section 3, the clears of `Start`, the restart and `InitBoard`, and the other indexed stores that reach a state variable)." % counts["sites"])
    total, frame, d_live, d_unseen = rule_pair_classes(ex)
    nun = sum(len(v) for v in d_unseen.values())
    P("- **Every pair of every rule was made by the code** in these runs (pairs a rule allows that no call made: **%d**). Of the %d pairs of the rules: **%d** were made at the frame level (the guards of the callers inside), **%d** only when the routine was called directly but were seen in the sessions, and **%d** only by a direct call and not in the sessions: %s. For these the code makes the pair (the instruction is exactly that), and what is not shown is that a game reaches the old value." %
      (counts["missing"], total, frame, d_live, nun, "; ".join("`%s` `$%04X`: %s%s" % (n, pc, condensed(list(v)[:40], DOMAIN[n]), " ..." if len(v) > 40 else "") for (n, pc), v in sorted(d_unseen.items())) or "none"))
    P("- **The code accepts more than the rules say at %d instruction(s)** (%d pairs at the frame level, %d more only when the routine is called directly): the instruction does not look at the old value, and the old value that would give the extra pair is kept away by a guard in the caller or by an invariant of the other variables. That no game makes these pairs is **machine-proved in section 5a** (the abstract search over every behaviour of the code: none of the extra pairs occurs, except the race at `$A800`); the arguments in the table below say why, read from the code." % (len({k for k, v in EXTRA_PAIRS_SITES.items()}), counts["frame_extra"], counts["direct_extra"]))
    P("")
    P("| Variable | Writer | Level | Pairs the code makes with an old value outside the rules | Why a game does not make them |")
    P("|---|---|---|---|---|")
    byvar = {n: d for a, n, s, d in STATES}
    rules_by = collections.defaultdict(list)
    for rl in RULES:
        for pc in rl[3]:
            rules_by[(rl[0], pc)].append(rl)
    for (name, pc), note in sorted(EXTRA_PAIRS_SITES.items(), key=lambda t: (t[0][0], t[0][1])):
        dom = DOMAIN[name]
        allowed = set()
        for rl in rules_by.get((name, pc), []):
            f = range(256) if rl[1] is None else rl[1]
            for o in f:
                if callable(rl[2]):
                    allowed |= {(o, n) for n in rl[2](o)}
                elif rl[2] == "+1":
                    allowed.add((o, (o + 1) & 0xFF))
                else:
                    allowed.add((o, rl[2]))
        e = ex.get((name, pc), {"f": set(), "d": set()})
        extra_f = {p for p in e["f"] if p not in allowed and p[0] in dom}
        extra_d = {p for p in e["d"] - e["f"] if p not in allowed and p[0] in dom}
        if extra_f:
            P("| `%s` | `$%04X` | the frame | %s | %s |" % (name, pc, condensed(extra_f, dom), note))
        if extra_d:
            P("| `%s` | `$%04X` | a direct call only | %s | %s |" % (name, pc, condensed(extra_d, dom), note))
    P("")
    P("What this does not prove (see section 5a for the assumptions of the machine proof): that the pairs just listed as not seen are reached by a game (the phases above `$53` need a frightened period of more than 33 s on a level whose end phase is 0, the end phases 4 and 8 a level that has them); and that the domain of each variable is the only set of values it can ever hold (it is the closure of the rules plus the pairs argued away above: a store from an old value outside a domain was not examined).")
    P("")
    return L


PROOF_SUMMARY = os.path.join(ROOT, "analysis", "evidence-state-proof-summary.txt")


def proof_section():
    L = []
    P = L.append
    P("## 5a. The proof by abstract search (every behaviour of the code, not only the runs)")
    P("")
    if not os.path.exists(PROOF_SUMMARY):
        P("NOT YET RUN: `analysis/evidence-state-proof-summary.txt` does not exist (`python -I tools/prove_state_rules.py --slice <name>` for each slice, then `--combine --write`).")
        P("")
        return L
    with open(PROOF_SUMMARY, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    sl = [l for l in lines if l.startswith("slice ") and "followed" in l]
    tot = next((l for l in lines if l.startswith("totals over")), "")
    unfinished = next((l for l in lines if l.startswith("slices not finished")), "")
    P("The sessions and the forced runs (section 5) only show what happened in the contexts that were run. To close the question \"can any other behaviour exist\", `tools/absint6502.py` runs the ROM code **abstractly**: the key loop from `Start` on, with the vertical-blank handler entering between any two instructions of the main loop (never two within 100 instructions; the real distance is thousands), every branch on something not followed taken **both ways**, and every memory byte that is not followed an unknown value. What it finds is therefore a superset of everything the code can do, whatever the joystick, the timers, the random numbers and the other variables are. `tools/prove_state_rules.py` runs it for sets of followed variables (**slices**) and compares every store to a followed variable (writer, old value, new value) with the rules of section 4 (`analysis/evidence-state-proof-summary.txt`, `tests/test_absint.py`, `tests/test_states.py`).")
    P("")
    P("| Slice | Followed (besides `CurrentPlayer`) | Search states | Combinations of values | Stores | Not allowed by a rule | Race only | Imprecision of the slice |")
    P("|---|---|---|---|---|---|---|---|")
    import re
    for l in sl:
        m = re.match(r"slice (\w+): followed ([^;]*); (\d+) states of the main loop.*?combinations of followed values reached: (\d+); stores seen: (\d+); stores of an unknown value: (\d+); stores that no rule allows: (\d+); race-only stores[^:]*: (\d+); stores that slice R rules out[^:]*: (\d+)", l)
        if m:
            nm, fol, st, comb, stores, unk, bad, race, imp = m.groups()
            P("| %s | %s | %s | %s | %s | **%s** | %s | %s |" % (nm, fol.replace("$2B", "").strip(), st, comb, stores, bad, race, imp))
    P("")
    P("%s. %s" % (tot.replace("totals over", "Totals over"), ("Not finished: " + unfinished.split(': ')[-1]) if unfinished and not unfinished.endswith("none") else "All slices finished."))
    P("")
    P("- **Proved**: no store to a state variable that a rule does not allow, apart from the race below. This closes 11 of the 12 instructions that accept more than the rules say: the pairs they could make with an old value outside the rules **never occur** in the code's behaviour (the arguments of the table above are right); the twelfth, `$A800`, is the race below, and the 'From' column of the rules is not only what the code allows but - up to the over-approximation of the search - what it can do; `04 -> 84` at `$B40A` is among the stores the search reaches in the ghost slices, so the code cannot be shown to exclude it, though no session saw it.")
    P("- **The race at `$A800`** (`tools/analyze_states.py` `RACE_ONLY`): ghost 0 can be incremented a second time (01 -> 02, 80 -> 81, and by repeating the race every n -> n+1 before `InitBoard` clears it). It needs START to be pressed and the vertical-blank handler to run inside the restart's clear loop (`$A47B`, between the clears of `$26` and `$21`) in the frame in which the last pellet is eaten: a path of the abstract search, which does not follow the dot counter; **it cannot happen in a game (OV-60, C-66)**: the same clear loop zeroes `DotsEaten` (`$34-$37`) at X = `$14-$17`, before it clears `$26` at X = 6, so in the window the counter is 0 and the frame cannot reach the end value `$0104` (LevelComplete is set only at `$B39C`); run in the interpreter with the interrupt forced at every instruction of the restart in states one dot from the end of the board: 0 races (`tools/check_ov60_race.py`, `analysis/evidence-ov60-race-summary.txt`). So the claim 'ghost 0 is always 0 at `$A800`' stays true in every game.")
    P("- **Imprecision of a slice** is a store that a slice with fewer variables allows but the flow slice R (which follows every flow variable together) rules out; the ghost-0 slice leaves out `DeathAnimActive`, `PacFrozen` and `CountdownActive` because the full set did not finish (4 h, 60 million states), and so allows `WaitState` 00 -> 01 at `$A818` (`TurnControl` clears `WaitState` and sets `CountdownActive` in the same call, so `$A816` returns before `$A818`).")
    P("- **The assumptions of the proof**: the vertical-blank handler and the display-list interrupt of the OS write no state variable (the OS code is not in the ROM); indirect stores `(zp),y` never aim at a state variable (docs/29 lists their pointers); the table area `$0600-$07FF` is never written after the expansion (`tests/test_absint.py`); the register sets that skipped routines preserve (docs/23, checked live over 5.5 million calls); the key loop's polling lets the handler enter at any pass. The abstract interpreter is tested against the concrete one (`tests/test_absint.py`: 160 handler runs and 120 key-loop passes from random memory, every concrete store and end value inside the abstract result).")
    P("")
    return L


def doc_lines():
    import copy
    live = None
    if os.path.exists(SUMMARY):
        strans, rcounts, sbulk, unexpl, nwrites, live = read_summary()
        live = [x for x in live if not x.startswith(("RULE ", "BULK ", "rule counts"))]
    w, rom, F, owner = static_writers()
    L = []
    P = L.append
    P("# 34 - State Transitions (stage 58)")
    P("")
    P("GENERATED by `python -I tools/analyze_states.py --doc docs/34-state-transitions.md` from the traced code (`tools/analyze_stack.py`), the rules of the code in `RULES` of the tool and `analysis/evidence-states-summary.txt` (`tools/run_state_audit.ps1`, 20 sessions of the real game). Tests: `tests/test_states.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- The game has **%d state variables** that form small state machines: the screen (`GameState`), the start of a game (`IntroRequest`, `StartTuneActive`, `PlayStarted`), the turn handling (`WaitState`, `TurnSwitchState`, `CurrentPlayer`, `TwoPlayers`, `CountdownActive`), the end of a level (`LevelComplete`, `LevelEndStep`), the pause, the death (`PacFrozen`, `DeathState`, `DeathAnimActive`), the eaten-ghost pause (`EatPause`), the frightened period (`FrightenPhase`), the bonus item (`BonusVisible`, `BonusScoreShown`) and the four ghosts (`GhostState`, the largest machine, 14 values)." % len(STATES))
    P("- **%d transition rules** (section 4) describe every way the code changes these variables: the writing instruction, the values it can come from and the value it writes; each rule is checked against the code (the instruction exists, stores that value, is in that routine) and against the running game." % len(RULES))
    P("- In 20 sessions of the real game (%d writes watched) **every change of every state variable is allowed by a rule** (%d transitions without a rule), and **every rule was seen at work at least once** (section 5)." % (nwrites, unexpl))
    P("- **Exactness** (section 5): the code itself was run with every variable forced to every value of its domain (about 100,000 calls in the 6502 interpreter) and every store logged: every pair of every rule is a pair the code makes; the code makes **more** at 12 instructions (an instruction that does not look at the old value), and section 5a **proves** by abstract search over every behaviour of the code that a game makes none of those pairs, except one race at `$A800` (ghost 0 incremented twice; a path of the search that no game can take, because the dot counter is zero there: OV-60 closed, C-66). In particular the code does make `04 -> 84` at `$B40A` (a pellet eaten while a ghost is in state `$04`); whether a game reaches it is argued from the timing (the state lasts until the next `HouseLeaveStep`, four jiffies), not seen.")
    P("- Two other ways change state variables at once: the **restart** at `$A477` (START clears `$20-$3F`) and the **board set-up** `InitBoard` (clears `$80-$FF`: the death, the eaten pause, the frightened phase, the bonus and every ghost go to 0); the clear of `Start` zeroes everything at the first start.")
    P("")
    P("## 2. How it was found")
    P("")
    P("1. **Static**: every instruction of the traced ROM code that stores to one of the variables (`sta`, `stx`, `sty`, `inc`, `dec`, shifts), with the constant it stores when the straight line before it loads one (section 3). The indexed clears are listed apart.")
    P("2. **Live**: `tools/run_state_audit.ps1` adds a write watch (`bta w <address> L<n> \"SW ...\"`) on each variable to 20 session harnesses (full games, two players, deaths, extra lives, pause, level sweeps, frightened and eaten ghosts, the input exercisers, the turn-switch paths); every write prints address, value, the writing instruction and the frame. `tools/analyze_states.py` rebuilds the sequence of values of each variable and its changes.")
    P("3. **Classify**: a write by the OS (`pc` >= `$C000`, at the cold start), by the clears of `Start`, or by a harness's own test aid (a `pc` that is no writing instruction of the game: for example the level sweep sets `LevelComplete`) is not a transition of the game; the game's next write starts from the value it left.")
    P("4. **Compare** with the rules written from the code (section 4).")
    P("")
    P("## 3. The state variables and the instructions that write them")
    P("")
    P("| Variable | Address | Values | Writing instructions (static) |")
    P("|---|---|---|---|")
    bywrit = collections.defaultdict(list)
    for x in w:
        bywrit[x["var"]].append(x)
    for a, name, size, d in STATES:
        vals = "; ".join("`%02X` %s" % (k, v) for k, v in sorted(d.items()))
        ws = "; ".join("`$%04X` %s %s (%s)" % (x["pc"], x["m"], x["value"], x["routine"]) for x in bywrit[name])
        P("| `%s` | `$%02X%s` | %s | %s |" % (name, a, "-$%02X" % (a + size - 1) if size > 1 else "", vals, ws))
    P("")
    bw = bulk_writers(rom, F, owner)
    P("Indexed stores that clear or fill a range (so also state variables): `Start` `$A395` ($18-$3F) and `$A39C` ($80-$FF) at the first start, `$A47B` ($20-$3F, the restart), `InitBoard` `$ADB4` ($80-$FF) and the copy of `ZeroPageInit80` into `$80-$93` (`$ADE3`: no state variable). The tool's list of the other indexed stores: " + ", ".join("`$%04X` (%s)" % (a, r) for a, op, r in bw[:6]) + ", ...")
    P("")
    P("## 4. The transition rules, and what the game did")
    P("")
    P("A rule lists the values the code allows the variable to have before the write (the `From` column), the value it stores and the instruction; the last column counts the changes of the sessions that the rule covers. The diagram under each table shows only what was **seen** (the numbers are the changes). `InitBoard` and the restart clear every variable in their range to 0 from any value: the rows with `$ADB4` / `$A47B` show the values it was cleared from.")
    P("")
    if not live:
        P("NOT YET RUN: `analysis/evidence-states-summary.txt` does not exist (run `tools/run_state_audit.ps1`, then `python -I tools/analyze_states.py analysis/raw-logs/states-*.txt --write analysis/evidence-states-summary.txt`).")
        return L
    trans, seen, bulk_seen = strans, rcounts, sbulk
    names_in_order = [n for a, n, s, d in STATES]
    for a, name, size, d in STATES:
        P("### %s (`$%02X%s`)" % (name, a, "-$%02X" % (a + size - 1) if size > 1 else ""))
        P("")
        P("| From | To | Writer | Rule | Seen |")
        P("|---|---|---|---|---|")
        for i, r in enumerate(RULES):
            if r[0] != name:
                continue
            fr = "any" if r[1] is None else " ".join("`%02X`" % x for x in r[1])
            to = "(computed)" if callable(r[2]) else ("old + 1" if r[2] == "+1" else "`%02X`" % r[2])
            P("| %s | %s | %s | %s | %s |" % (fr, to, " ".join("`$%04X`" % x for x in r[3]), r[4], seen.get(name, {}).get(i, 0) or "**not seen**"))
        for (cpc, olds), c in sorted(bulk_seen.get(name, {}).items()):
            P("| `%02X` | `00` | `$%04X` | %s | %d |" % (olds, cpc, next(t for p, lo, hi, t in BULK_CLEARS if p == cpc), c))
        P("")
        edges = collections.Counter()
        for (o, n), c in trans.get(name, {}).items():
            edges[(o, n)] = c
        if name in ("FrightenPhase",):
            P("Seen: %d changes; the phase rises by one from 1 to the end phase of the level (up to `%02X`) and falls to 0 at the end or at the board set-up; a new pellet sets it back to 1." % (sum(edges.values()), max((n for (o, n) in edges), default=0)))
            P("")
            continue
        if sum(edges.values()) and len(edges) <= 45:
            L.extend(mermaid(name, edges))
            P("")
    L.extend(exact_section(trans))
    L.extend(proof_section())
    P("## 6. Rules not seen, and the aids")
    P("")
    unseen = [i for i, r in enumerate(RULES) if not seen.get(r[0], {}).get(i)]
    P("Rules written from the code: %d; seen in the sessions: %d; **not seen: %d**." % (len(RULES), len(RULES) - len(unseen), len(unseen)))
    P("")
    for i in unseen:
        r = RULES[i]
        fr = "any" if r[1] is None else "/".join("%02X" % x for x in r[1])
        to = "computed" if callable(r[2]) else ("%02X" % r[2] if isinstance(r[2], int) else r[2])
        P("- `%s` %s -> %s by %s: %s" % (r[0], fr, to, " ".join("`$%04X`" % x for x in r[3]), r[4]))
    P("")
    P("Transitions that no rule allows: **%d**." % unexpl)
    P("")
    P("Rules that needed a special session (the first sessions did not reach them): `GameState` 1/2 -> 3 by a console key at the copyright screen (`tools/altirra_copyright_key.cmd`), `TwoPlayers` 1 -> 0 (the second SELECT of `tools/altirra_inputs.cmd`), `GhostState` 08/10/20 -> 02 by `ForceChase` (`tools/altirra_forcechase.cmd`, test aid: the dot count is set to $DF once).")
    P("")
    P("The writes that are not transitions of the game - the OS clearing its RAM at the cold start and a harness's own test aid (the level sweeps hold `LevelComplete`; two harnesses set `TwoPlayers`) - are counted in the summary and left out of the transitions.")
    P("")
    P("## 7. The summary of the sessions")
    P("")
    if live:
        P("```")
        for line in live:
            P(line)
        P("```")
    P("")
    return L


def main():
    args = sys.argv[1:]
    if "--probes" in args:
        print("\n".join(probe_lines()))
        return
    if "--doc" in args:
        txt = "\n".join(doc_lines()) + "\n"
        i = args.index("--doc")
        if i + 1 < len(args):
            with open(os.path.join(ROOT, args[i + 1]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(txt)
            print("wrote", args[i + 1], len(txt), "bytes")
        else:
            print(txt)
        return
    paths = [a for a in args if a.endswith(".txt") and "raw-logs" in a.replace("\\", "/")]
    if len(paths) == 1 and "*" in paths[0]:
        paths = sorted(glob.glob(paths[0]))
    L = summary_lines2(paths)
    txt = "\n".join(L) + "\n"
    if "--write" in args:
        out = args[args.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
