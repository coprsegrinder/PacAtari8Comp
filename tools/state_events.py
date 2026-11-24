"""Stage 65 (state management): WHAT EACH STATE-MANAGEMENT EVENT RESETS, KEEPS AND COMPUTES.  For each event of the game (the restart of a game, a new board, a new level, a turn switch, a ghost eaten, a power pellet) the real routine is run on
the concrete 6502 (tools/cpu6502.py) from many random game states; for every byte of the zero page the values before and after are compared over all the trials: a byte that has ONE value after, whatever it was before, is RESET to that constant;
a byte that is the same after as before in every trial is KEPT; every other byte is COMPUTED (a function of the state or of the inputs).  The three lists are the event's effect on the state vector.
Usage: python -I tools/state_events.py [--trials 400] [--write analysis/evidence-events-summary.txt] (the chapter: tools/analyze_state.py)"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)


def _mods():
    import algorithm_models as A
    import algorithm_models6 as M6
    import algorithm_models7 as M7
    import output_map as O
    import cpu6502 as C
    return A, M6, M7, O, C


def base_state(base, rng, mods, play=True):
    A, M6, M7, O, C = mods
    ys, xs = O.load_junction_lists()
    m = M6.prepare(base, rng)
    M7.frame_setup(m, rng, "play" if play else "game")
    O.realistic(m, rng, ys, xs)
    m.mem[0x2B] = rng.randrange(2)                              # the player on turn
    m.mem[0x1A] = rng.randrange(2)                              # one or two players
    m.random = [rng.randrange(256) for _ in range(12)]
    return m


def restart(m, rng):
    """the restart of a game: `$A477` to the top of the key loop `$A4BA` (the wait for the OS clock at `$A493` gets a tick)"""
    m.pc = 0xA477
    m.s = 0xFF
    n = 0
    stack_marker = 0
    while m.pc != 0xA4BA:
        if m.pc == 0xA493:
            m.mem[0x14] = (m.mem[0x14] + 1) & 255
        if m.pc >= 0xC000:
            lo, hi = m.pull(), m.pull()
            m.pc = (((hi << 8) | lo) + 1) & 0xFFFF
            continue
        m.step()
        n += 1
        if n > 500000:
            raise RuntimeError("restart did not end")


def call(addr, **kw):
    def f(m, rng):
        for k, v in kw.items():
            if k == "x":
                m.x = v
            elif k == "a":
                m.a = v
        m.call(addr)
    return f


def turn_setup(m, rng):
    import algorithm_models7 as M7
    M7.turn_setup(m, rng)


EVENTS = [
    # name, what it is, the function, optional set-up
    ("restart", "the restart of a game (`$A477` to `$A4BA`: clear `$20-$3F`, the three maze copies, `InitBoard`, `NewGameInit`, the title scores)", restart, None),
    ("InitBoard", "`InitBoard` (`$ADAF`): the start of every turn and of every board: clear `$80-$FF`, the start positions, the colours, the move delays", call(0xADAF), None),
    ("NewGameInit", "`NewGameInit` (`$ADF1`): lives 3, the start level, `NewBoardInit`", call(0xADF1), None),
    ("NewBoardInit", "`NewBoardInit` (`$AE02`): a new maze for the player on turn, the release timers", call(0xAE02), None),
    ("AdvanceLevel", "`AdvanceLevel` (`$AC75`): the level counter, the new board, the READY! screen (the end of a level)", call(0xAC75), None),
    ("turn control", "`TurnControl` (`$AA2D`): the turn passes to the other player, or the next board, or the end of the game", call(0xAA2D), turn_setup),
    ("ghost eaten", "`GhostEaten` (`$A886`): a frightened ghost is eaten (ghost 0 to 3)", None, "ghost"),
    ("power pellet", "`PowerPelletEaten` (`$B3DE`): the frightened phase starts", call(0xB3DE), None),
    ("add to score", "`AddToScore` (`$B423`): a score is added (a dot, a pellet, a ghost, a bonus)", call(0xB423), None),
]


def label_player(pre, post):
    return "player %d on turn" % (pre[0x2B] + 1)


def label_turn(pre, post):
    st = pre[0x23]
    if st != 0:
        return "stage %d (the hand-over in progress)" % st if pre[0x25] == 0 else "stage %d, waiting" % st
    names = {(0, 2): "next board, same player", (1, 3): "game over (both players out)"}
    if post[0x20] == 1:
        return "game over: the countdown starts"
    if post[0x23] in (1, 2):
        return "hand over: player %d is next" % (post[0x23] if post[0x23] == 2 else 1)
    return "next board (same player, a life lost)"


def run(trials=400, seed=1, only=None, port=None):
    """`only`: the names of the events to run (default all); `port`: {event name: function(machine)} that performs the event with the PORT instead of the ROM (stage 78a: the same trials, the same classification)"""
    A, M6, M7, O, C = mods = _mods()
    base = A.started_machine()
    out = {}
    for name, desc, fn, setup in EVENTS:
        if only is not None and name not in only:
            continue
        rng = random.Random(seed * 7919 + len(name))
        label_fn = label_turn if name == "turn control" else label_player
        groups = {}
        for t in range(trials):
            m = base_state(base, rng, mods)
            if name == "restart":
                m.mem[0x19], m.mem[0x20], m.mem[0x1C] = 0, 0, 1             # what `$A537` leaves
            if setup == "ghost":
                g = rng.randrange(4)
                m.mem[0xCE + g] = rng.choice([0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0])
                m.x = g
                fn_ = call(0xA886, x=g)
            else:
                if setup:
                    setup(m, rng)
                fn_ = fn
            pre = list(m.mem[:0x100])
            try:
                if port and name in port:
                    port[name](m)
                else:
                    fn_(m, rng)
            except Exception:
                continue
            post = list(m.mem[:0x100])
            lab = label_fn(pre, post)
            g_ = groups.setdefault(lab, {"n": 0, "kept": [True] * 256, "val": [None] * 256, "const": [True] * 256})
            g_["n"] += 1
            for b in range(256):
                if post[b] != pre[b]:
                    g_["kept"][b] = False
                if g_["val"][b] is None:
                    g_["val"][b] = post[b]
                elif g_["val"][b] != post[b]:
                    g_["const"][b] = False
        res = {"desc": desc, "groups": {}}
        for lab, g_ in sorted(groups.items()):
            if g_["n"] < 8:
                continue
            reset, kept, computed = {}, [], []
            for b in range(256):
                if g_["kept"][b]:
                    kept.append(b)
                elif g_["const"][b]:
                    reset[b] = g_["val"][b]
                else:
                    computed.append(b)
            res["groups"][lab] = {"trials": g_["n"], "reset": reset, "kept": kept, "computed": computed}
        out[name] = res
    return out


if __name__ == "__main__":
    a = sys.argv
    trials = int(a[a.index("--trials") + 1]) if "--trials" in a else 400
    res = run(trials)
    path = os.path.join(ROOT, "analysis", "raw-logs", "state-events.json")
    with open(path, "w") as fh:
        json.dump({k: {"desc": v["desc"], "groups": {lab: {"trials": g["trials"], "reset": {str(b): c for b, c in g["reset"].items()}, "kept": g["kept"], "computed": g["computed"]} for lab, g in v["groups"].items()}} for k, v in res.items()}, fh)
    for k, v in res.items():
        for lab, g in v["groups"].items():
            print("%-14s %-42s %4d trials: %3d reset, %3d kept, %3d computed" % (k, lab, g["trials"], len(g["reset"]), len(g["kept"]), len(g["computed"])))
