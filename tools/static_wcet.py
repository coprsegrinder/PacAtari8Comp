"""OV-64: a static upper bound of the instruction cycles of the vertical-blank handler ($A5FD to the jump to XITVBV), over every path the code allows for any contents of memory.
The machine is tools/absint6502.py (no followed variable: every memory byte and hardware input unknown, both outcomes of every branch on something unknown), but the search keeps the states EXACT (no joins) so that a
path is a real path of the abstraction; the bound is the longest path of that graph.  A loop whose counter the search cannot follow (a cycle in the graph) is reported, not bounded.
Cycles per instruction: the NMOS 6502 table; +1 for a read with an indexed address (page crossing assumed), a taken branch +1, +1 more when the target is on another page.
Usage: python -I tools/static_wcet.py [--entry A5FD] [--limit 3000000]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import absint6502 as AB  # noqa: E402

BASE = {"imm": 2, "zp": 3, "zpx": 4, "zpy": 4, "abs": 4, "abx": 4, "aby": 4, "izx": 6, "izy": 5, "imp": 2, "acc": 2}
READ = {"lda", "ldx", "ldy", "adc", "sbc", "and", "ora", "eor", "cmp", "cpx", "cpy", "bit"}
RMW = {"asl", "lsr", "rol", "ror", "inc", "dec"}
STORE = {"sta", "stx", "sty"}
BRANCHES = {"bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq"}


def cost(ins, pc, nxt_pc, x=None, y=None):
    """cycles of the instruction at pc whose successor is at nxt_pc; x, y: the index register when it is known (the page crossing of an indexed read is then exact; unknown, it is assumed unless the table starts on a page)"""
    ln, m, mode, op = ins[pc]
    if m in BRANCHES:
        if nxt_pc == pc + ln:
            return 2
        return 3 + (1 if (pc + ln) >> 8 != nxt_pc >> 8 else 0)
    if m == "jsr":
        return 6
    if m == "rts":
        return 6
    if m == "rti":
        return 6
    if m == "jmp":
        return 3 if mode == "abs" else 5
    if m in ("pha", "php"):
        return 3
    if m in ("pla", "plp"):
        return 4
    if m == "brk":
        return 7
    if m in RMW and mode != "acc":
        return {"zp": 5, "zpx": 6, "abs": 6, "abx": 7}[mode]
    if m in STORE:
        return {"zp": 3, "zpx": 4, "zpy": 4, "abs": 4, "abx": 5, "aby": 5, "izx": 6, "izy": 6}[mode]
    c = BASE[mode]
    if m in READ and mode in ("abx", "aby"):
        idx = x if mode == "abx" else y
        if idx is None:
            c += 1 if (op & 0xFF) else 0                      # the index may be up to 255: a crossing is possible unless the table starts on a page
        elif (op & 0xFF) + idx > 0xFF:
            c += 1
    elif m in READ and mode == "izy":
        c += 1
    return c


TRACK = [0x19, 0x9B, 0x1C, 0x20, 0x26, 0x21, 0x22, 0x24, 0xED, 0xE5, 0xFE]  # the variables FrameDispatch tests (gs, Paused, IntroRequest, CountdownActive, LevelComplete, play started, start tune, WaitState, DeathState, EatPause);                 # zp_24 (the WaitState): the dispatcher's A826 -> A800 re-dispatch is a loop of the abstraction only when this byte is unknown

# LOOP BOUNDS the abstraction cannot find by itself (memory is unknown to it, so a loop on a memory counter or a path that needs two reads of one byte to agree looks endless).
# pc of the instruction -> (the most times it executes per call of the routine at `owner` (None: per handler run), why).  Each one is a claim about the game, argued in docs/39.
ANNOT = {
    0xACDF: (0xAC93, 6, "DrawLevelIndicator: X counts 0..zp_2A, and zp_2A < 6 (A = cmp #6 / bcs at $ACB8-$ACBA)"),
    0xB018: (0xAFD7, 1, "siren: from $B018 the path goes to $B007, where E1 + $10 (E1 = $40) is not 0, so it leaves at $B00C"),
    0xAFF3: (0xAFD7, 1, "siren: one test per call"),
    0xB53D: (0xAF54, 1, "siren 2: from $B53D the sum SirenStep + DE of $B52C-$B531 is not 0 (SirenStep is 2, 3 or 4; DE starts $28), so it leaves at $B531"),
    0xB8E8: (None, 1, "GhostGoToCorner -> GhostSelectPatrol: once per ghost update (SelectPatrol sets the timer to $96, so Travel does not go back to the corner)"),
    0xB9F2: (0xB999, 2, "SteerToTarget: the loop $B9EA -> $B9EE needs WantHoriz = 0 at $B9EA and (WantHoriz and zp_2A) <> 0 at $B9F0, which cannot both hold: at most 2 passes"),
}


# a class fixes the dispatcher's variables to the values that give it (None: unknown); the other variables stay unknown
CLASSES = {
    "any": {},
    "title menu": {0x19: 3}, "title after game": {0x19: 4}, "copyright setup": {0x19: 1}, "copyright wait": {0x19: 2},
    "paused": {0x19: 0, 0x9B: 1},
    "board start": {0x19: 0, 0x9B: 0, 0x1C: 2},
    "game-over countdown": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 1},
    "level end": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 1},
    # the level-end sequence (zp_27 = LevelEndStep 0..4, docs/34: 0 -> 1 -> 2 -> 3 at $AC26, 3 -> 4 at $AC72 right after InitBoard, 4 -> 0 at $AC88): the frame of stage 4 (AdvanceLevel, the maze copy) is entered with the entities at
    # their start positions, because stage 4 is reached only from the frame of stage 3, which calls InitBoard (check_level_end_chain below); the other stages have unknown positions
    "level end 0": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 1, 0x27: 0},
    "level end 1": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 1, 0x27: 1},
    "level end 2": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 1, 0x27: 2},
    "level end 3": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 1, 0x27: 3},
    "level end 4": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 1, 0x27: 4},
    "start idle": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 0, 0x22: 0},
    "start tune": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 0, 0x22: 1},
    "turn control": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 1, 0x24: 1},
    "ready wait": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 1, 0x24: 2},
    "death": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 1, 0x24: 0, 0xED: 1},
    "eaten pause": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 1, 0x24: 0, 0xED: 0, 0xE5: 1},
    "play": {0x19: 0, 0x9B: 0, 0x1C: 0, 0x20: 0, 0x26: 0, 0x21: 1, 0x24: 0, 0xED: 0, 0xE5: 0},
}


# edges of the abstract graph counted together: at most `limit` executions of any of them in a handler run (a fact about the game, argued in docs/39).  (pc, next pc) of the entry into the heavy path of ClipEntityAtTunnel: right zone $AB6F -> $AB71, left zone $AB97 -> $AB99
CLIP_HEAVY_EDGES = frozenset({(0xAB6F, 0xAB71), (0xAB97, 0xAB99)})


def bounded_graph(entry, limit, init=None, edge_limits=None):
    """nodes = (state, counters): one counter per annotated pc, (times executed, stack depth of the first one) or (0, 0); a counter is cleared when the stack falls below that depth (the routine returned)"""
    prog = AB.Program()
    mach = AB.Machine(prog, TRACK, skip=False)
    pcs = sorted(ANNOT)
    index = {pc: k for k, pc in enumerate(pcs)}
    edge_limits = edge_limits or []
    zero = tuple((0, 0) for _ in pcs) + tuple((0, 0) for _ in edge_limits)
    st0 = (entry, None, None, None, None, None, None, None, 0, (), tuple((init or {}).get(a) for a in TRACK), None)
    start = (st0, zero)
    succ = {}
    work = [start]
    while work:
        node = work.pop()
        if node in succ:
            continue
        st, cnt = node
        out = mach.step(st, set(), True)
        if out == "EXIT":
            succ[node] = [(3 if prog.ins[st[0]][1] == "jmp" else cost(prog.ins, st[0], 0xFFFF, st[2], st[3]), "EXIT")]
            continue
        c2 = cnt
        if st[0] in ANNOT:
            k = index[st[0]]
            n, d0 = cnt[k]
            n, d0 = (n + 1, d0) if n else (1, len(st[9]))
            if n > ANNOT[st[0]][1]:
                succ[node] = []                       # beyond the bound: not a path of the game
                continue
            c2 = cnt[:k] + ((n, d0),) + cnt[k + 1:]
        lst = []
        for s2 in out:
            c3 = tuple((0, 0) if (n and len(s2[9]) < d0) else (n, d0) for n, d0 in c2)
            if edge_limits:
                ok = True
                for e, (edges, lim) in enumerate(edge_limits):
                    if (st[0], s2[0]) in edges:
                        k = len(pcs) + e
                        n = c3[k][0] + 1
                        if n > lim:
                            ok = False
                            break
                        c3 = c3[:k] + ((n, 0),) + c3[k + 1:]
                if not ok:
                    continue
            lst.append((cost(prog.ins, st[0], s2[0], st[2], st[3]), (s2, c3)))
        succ[node] = lst
        for _, n2 in lst:
            if n2 not in succ:
                work.append(n2)
        if len(succ) > limit:
            raise RuntimeError("state limit %d" % limit)
    return start, succ, prog


def find_cycles(succ, start):
    color = {start: 1}
    heads = {}
    stack = [(start, iter(succ[start]))]
    while stack:
        node, it = stack[-1]
        for c, n2 in it:
            if n2 == "EXIT":
                continue
            if color.get(n2) == 1:
                heads[n2[0][0]] = heads.get(n2[0][0], 0) + 1
            elif n2 not in color:
                color[n2] = 1
                stack.append((n2, iter(succ[n2])))
                break
        else:
            color[node] = 2
            stack.pop()
    return heads


def longest_path(succ, start):
    best = {}
    order = []
    color = {start: 1}
    stack = [(start, iter(succ[start]))]
    while stack:
        node, it = stack[-1]
        for c, n2 in it:
            if n2 != "EXIT" and n2 not in color:
                color[n2] = 1
                stack.append((n2, iter(succ[n2])))
                break
        else:
            order.append(node)
            stack.pop()
    for node in order:                                    # children before parents
        b = -1
        for c, n2 in succ[node]:
            b = max(b, c + (0 if n2 == "EXIT" else best[n2]))
        best[node] = b if succ[node] else -1             # -1: pruned (beyond a loop bound)
    return best[start], best


# the classes that follow the entity positions ($85-$8E) and the current player ($2B, 0 or 1: the bound is the larger of the two runs); the play-type classes keep the shorter list (the search would be far larger)
STAGES = ["level end 0", "level end 1", "level end 2", "level end 3", "level end 4"]
START_POSITIONS = None


def start_positions():
    """the entity bytes $85-$8E that InitBoard leaves: ZeroPageInit80 ($BB6F) bytes 5 to 14"""
    global START_POSITIONS
    if START_POSITIONS is None:
        with open(os.path.join(os.path.dirname(HERE), "original", "Pac-Man.rom"), "rb") as fh:
            rom = fh.read()
        tab = rom[0xBB6F - 0xA000:0xBB6F - 0xA000 + 20]
        START_POSITIONS = {0x80 + i: tab[i] for i in range(5, 15)}
    return START_POSITIONS


POSITION_CLASSES = set(STAGES) | {"copyright setup", "copyright wait", "title menu", "title after game", "paused", "board start", "start idle", "game-over countdown", "level end", "turn control", "death", "eaten pause"}


def class_bound(cls, heavy=None):
    """-> (bound in instruction cycles, states); heavy: the most entities in a tunnel zone (the heavy path of ClipEntityAtTunnel) in one frame, None: any number"""
    global TRACK
    base = TRACK
    ext = cls in POSITION_CLASSES
    try:
        if ext:
            TRACK = list(base) + list(range(0x85, 0x8F)) + [0x2B] + ([0x27] if cls in STAGES else [])
        res = []
        states = 0
        for cp in ((0, 1) if ext else (None,)):
            init = dict(CLASSES[cls])
            if cp is not None:
                init[0x2B] = cp
            if cls == "level end 4":
                init.update(start_positions())
            el = [(CLIP_HEAVY_EDGES, heavy)] if heavy is not None else None
            start, succ, prog = bounded_graph(0xA5FD, 8_000_000, init, el)
            if find_cycles(succ, start):
                raise RuntimeError("a cycle remains in class " + cls)
            res.append(longest_path(succ, start)[0])
            states = max(states, len(succ))
        return max(res), states
    finally:
        TRACK = base


def level_end_bound():
    """-> (bound, {stage: bound}): the level end is the largest of its five stages"""
    per = {st: class_bound(st)[0] for st in STAGES}
    return max(per.values()), per


def check_level_end_chain():
    """the inductive step behind the entry state of stage 4: the frame of stage 3, run from UNKNOWN entity positions, leaves in every path with LevelEndStep = 4 and the entities at the start positions; -> True/False"""
    global TRACK
    base = TRACK
    try:
        TRACK = list(base) + list(range(0x85, 0x8F)) + [0x2B, 0x27]
        want = tuple(start_positions()[a] for a in range(0x85, 0x8F))
        want = (4,) + want
        ok = True
        for cp in (0, 1):
            init = dict(CLASSES["level end 3"])
            init[0x2B] = cp
            start, succ, prog = bounded_graph(0xA5FD, 8_000_000, init)
            if find_cycles(succ, start):
                return False
            idx = [TRACK.index(0x27)] + [TRACK.index(a) for a in range(0x85, 0x8F)]
            exits = [tuple(node[0][10][i] for i in idx) for node, lst in succ.items() if lst and all(n2 == "EXIT" for c, n2 in lst)]
            ok = ok and bool(exits) and all(e == want for e in exits)
        return ok
    finally:
        TRACK = base


def main():
    if "--table" in sys.argv:
        out = ["Static worst case of the vertical-blank handler in instruction cycles, per frame class (tools/static_wcet.py --table; docs/39):",
               "class | bound | states of the largest run"]
        for cls in CLASSES:
            if cls == "any" or cls in STAGES:
                continue
            b, n = class_bound(cls)
            line = "%-20s %6d  (%d states)" % (cls, b, n)
            if cls == "level end":
                b2, n2 = class_bound(cls, heavy=2)
                line += "   with at most 2 entities in a tunnel zone: %d" % b2
                lb, per = level_end_bound()
                line += "   by stage (the entry state of stage 4 proved): %d = max of %s" % (lb, " / ".join("%d" % per[st] for st in STAGES))
                line += "   chain check (stage 3 leaves LevelEndStep 4 at the start positions): %s" % ("passed" if check_level_end_chain() else "FAILED")
            out.append(line)
            print(line, flush=True)
        if "--write" in sys.argv:
            with open(os.path.join(os.path.dirname(HERE), sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(("\n").join(out) + "\n")
        return
    ent = int(sys.argv[sys.argv.index("--entry") + 1], 16) if "--entry" in sys.argv else 0xA5FD
    cname = sys.argv[sys.argv.index("--class") + 1] if "--class" in sys.argv else "any"
    start, succ, prog = bounded_graph(ent, 6_000_000, CLASSES[cname])
    print("class", cname)
    heads = find_cycles(succ, start)
    print("states", len(succ))
    if heads:
        print("cycles remain at:", ", ".join("$%04X" % h for h in sorted(heads)))
        return
    b, best = longest_path(succ, start)
    print("longest path (instruction cycles):", b)


if __name__ == "__main__":
    main()


def path_profile(start, succ, best, prog):
    """the longest path as cycles per function entry (the routine the instruction belongs to, by the pc ranges of prog.F; a tail-shared pc is counted for the smallest body)"""
    owner = {}
    for e, f in sorted(prog.F.items(), key=lambda kv: -len(kv[1].body)):
        for a in f.body:
            owner[a] = e
    prof = {}
    node = start
    while node != "EXIT":
        st = node[0]
        bestc, bestn = None, None
        for c, n2 in succ[node]:
            v = c + (0 if n2 == "EXIT" else best[n2])
            if bestc is None or v > bestc:
                bestc, bestn, cc = v, n2, c
        o = owner.get(st[0], 0)
        prof[o] = prof.get(o, 0) + cc
        node = bestn
    return prof
