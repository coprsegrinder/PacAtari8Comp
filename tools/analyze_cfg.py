"""Stage 33: the control flow graph of every routine of the Pac-Man ROM, as basic blocks.

Method.  The routines and their bodies are those of tools/analyze_functions.py (the same trace as src/asm/pacman.s).  Inside a body:
  leader  = the entry, every branch / JMP target, the instruction after a branch, and every instruction with more than one predecessor in the body (a join).
  block   = a leader and the instructions up to the next leader or up to an instruction without a fall-through (RTS, RTI, JMP).  A JSR is a call, not a block end: control comes back to the next instruction.
  edge    = taken / not taken (a conditional branch), jump (JMP), fall (into the next leader).  A branch that `Rom.decided` proves always or never taken (`lda #imm / bne`, `clc / bcc`, `bne x / beq y`)
            has only the edge that can happen, so the graph is the one the code can really run.
Per routine: blocks, edges, exit blocks, cyclomatic complexity (E - N + 2), the back edges (an edge whose target dominates its source: a natural loop), and whether the graph is reducible (every retreating edge of a
depth-first search is a back edge).  A JMP into another routine is a tail call: its code is part of the body, so a shared tail appears as blocks of each routine that jumps to it.
Usage: python -I tools/analyze_cfg.py [--write docs/26-control-flow-graphs.md]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_functions as AF  # noqa: E402
import disasm6502 as D  # noqa: E402

ROOT = AF.ROOT


class Graph:
    pass


def build(rom, f):
    """The basic-block graph of one routine: blocks {start: [addresses]}, edges [(from block, to block, kind)]."""
    body = f.body
    succ = {a: [s for s in rom.succ(a) if s in body] for a in body}
    preds = collections.defaultdict(set)
    for a in body:
        for s in succ[a]:
            preds[s].add(a)
    leaders = {f.entry}
    for a in body:
        n, m, mode, op = rom.ins[a]
        if m in D.BRANCHES or m == "jmp":
            leaders.update(succ[a])
            if a + n in body:
                leaders.add(a + n)
        if len(preds[a]) > 1:
            leaders.add(a)
        # an instruction reached only by a jump or branch (no fall-through predecessor) starts a block too
        if a != f.entry and not any(p + rom.ins[p][0] == a and a in succ[p] for p in preds[a]):
            leaders.add(a)
    blocks = {}
    for l in sorted(leaders):
        seq, a = [], l
        while True:
            seq.append(a)
            n, m, mode, op = rom.ins[a]
            nxt = succ[a]
            if len(nxt) != 1 or nxt[0] != a + n or nxt[0] in leaders:
                break
            a = nxt[0]
        blocks[l] = seq
    edges = []
    for l, seq in blocks.items():
        last = seq[-1]
        n, m, mode, op = rom.ins[last]
        for s in succ[last]:
            if m in D.BRANCHES:
                d = rom.decided(last)
                kind = "taken" if s == op and (s != last + n or d is True) else "not taken"
                if d is not None:
                    kind += " (always)" if d is True else " (never)"
                if s == op == last + n:
                    kind = "taken = next"
            elif m == "jmp":
                kind = "jump"
            else:
                kind = "fall"
            edges.append((l, s, kind))
    g = Graph()
    g.blocks, g.edges, g.entry = blocks, edges, f.entry
    g.out = collections.defaultdict(list)
    g.inn = collections.defaultdict(list)
    for a, b, k in edges:
        g.out[a].append(b)
        g.inn[b].append(a)
    g.exits = [l for l, seq in blocks.items() if not g.out[l]]
    g.dom = dominators(g)
    g.back = sorted((a, b) for a, b, k in edges if b in g.dom[a])
    g.bad = retreating_not_back(g)
    g.reducible = not g.bad
    g.cc = len(edges) - len(blocks) + 2
    return g


def dominators(g):
    nodes = list(g.blocks)
    dom = {n: set(nodes) for n in nodes}
    dom[g.entry] = {g.entry}
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n == g.entry:
                continue
            ps = [dom[p] for p in g.inn[n]]
            new = {n} | (set.intersection(*ps) if ps else set())
            if new != dom[n]:
                dom[n], changed = new, True
    return dom


def retreating_not_back(g):
    """Retreating edges of a depth-first search whose target does not dominate the source: they make the graph irreducible (a loop with a second entry)."""
    state, bad = {g.entry: 1}, []
    stack = [(g.entry, iter(g.out[g.entry]))]
    while stack:
        n, it = stack[-1]
        for s in it:
            if state.get(s) == 1:
                if s not in g.dom[n]:
                    bad.append((n, s))
            elif s not in state:
                state[s] = 1
                stack.append((s, iter(g.out[s])))
                break
        else:
            state[n] = 2
            stack.pop()
    return bad


def natural_loop(g, tail, head):
    loop, work = {head, tail}, [tail]
    while work:
        n = work.pop()
        for p in g.inn[n]:
            if p not in loop:
                loop.add(p)
                work.append(p)
    return loop


def block_label(rom, g, l):
    seq = g.blocks[l]
    last = seq[-1]
    n, m, mode, op = rom.ins[last]
    return "$%04X-$%04X" % (l, last)


def analyse():
    rom, F = AF.analyse()
    G = {e: build(rom, f) for e, f in F.items()}
    return rom, F, G


def report(rom, F, G):
    L = []
    P = L.append
    nb = sum(len(g.blocks) for g in G.values())
    ne = sum(len(g.edges) for g in G.values())
    nloops = sum(len(g.back) for g in G.values())
    irr = [F[e].name for e, g in G.items() if not g.reducible]
    P("# 26 - The Control Flow Graphs (stage 33)")
    P("")
    P("GENERATED by `python -I tools/analyze_cfg.py --write docs/26-control-flow-graphs.md` from the same trace as `src/asm/pacman.s` and the routines of `23-function-table.md`; do not edit by hand. Tests: `tests/test_cfg.py`.")
    P("")
    P("## Method")
    P("")
    P("Each of the %d routines is cut into **basic blocks**: a block starts at the routine entry, at every branch or `JMP` target, after every branch, and at every join (an instruction with two or more predecessors); it ends at the next block start or at an `RTS`, `RTI` or `JMP`. A `JSR` is a call and does not end a block. Edges: **taken** / **not taken** for a conditional branch, **jump** for `JMP`, **fall** into the next block. A branch that the code itself decides (`lda #imm` / `bne`, `clc` / `bcc`, a branch after its complement) keeps only the edge that can happen. A `JMP` into another routine is a tail call: its code is part of the body, so a shared tail appears in each routine that jumps to it." % len(G))
    P("")
    P("A **back edge** is an edge whose target dominates its source; each is one natural loop. **Cyclomatic complexity** = edges - blocks + 2. A graph is **reducible** when every retreating edge of a depth-first search is a back edge (the loops are properly nested single-entry loops).")
    P("")
    P("## Totals")
    P("")
    P("- %d routines, **%d basic blocks**, **%d edges**, %d instructions in the bodies (shared tails counted once per routine)." % (len(G), nb, ne, sum(len(b) for g in G.values() for b in g.blocks.values())))
    P("- %d back edges (natural loops); the loop count of `23-function-table.md` counts every backward branch, so it agrees on routines without a decided branch." % nloops)
    P("- %s." % ("all %d graphs are reducible" % len(G) if not irr else "%d graphs are reducible and **%d are not** (%s): each has a loop that can be entered at two places, through an always-taken `lda #imm / bne` used as a jump; the block pairs are listed under each routine. A port must keep these as a `goto` or duplicate a block; they cannot be written as nested `while` loops as they stand." % (len(G) - len(irr), len(irr), ", ".join(irr))))
    P("- Exit blocks: %d (an RTS or RTI, or a `JMP` out of the routine); routines with no exit block: %s." % (sum(len(g.exits) for g in G.values()), ", ".join(F[e].name for e, g in sorted(G.items()) if not g.exits) or "none"))
    top = sorted(G, key=lambda e: -G[e].cc)[:10]
    P("- Most complex routines (cyclomatic complexity): " + ", ".join("%s %d" % (F[e].name, G[e].cc) for e in top) + ".")
    P("")
    P("## Summary table")
    P("")
    P("| Routine | Entry | Blocks | Edges | Exits | Back edges | Complexity | Reducible |")
    P("|---|---|---|---|---|---|---|---|")
    for e in sorted(G):
        g = G[e]
        P("| %s | `$%04X` | %d | %d | %d | %d | %d | %s |" % (F[e].name, e, len(g.blocks), len(g.edges), len(g.exits), len(g.back), g.cc, "yes" if g.reducible else "NO"))
    P("")
    P("## The graphs")
    P("")
    P("Each routine: a table of its blocks (`first-last` address, instruction count, last instruction, calls made inside the block, successors) and the graph as a Mermaid flowchart. Solid arrows: taken / jump / fall; dotted: not taken; thick: back edge.")
    P("")
    for e in sorted(G):
        g, f = G[e], F[e]
        P("### %s  `$%04X`" % (f.name, e))
        P("")
        P("%d blocks, %d edges, %d exits, %d back edges, complexity %d%s." % (len(g.blocks), len(g.edges), len(g.exits), len(g.back), g.cc, "" if g.reducible else ", IRREDUCIBLE"))
        if g.bad:
            P("")
            P("**Irreducible**: the retreating edge%s %s enter%s a loop at a block that does not dominate the edge's source (a second entry into the loop)." % ("s" if len(g.bad) > 1 else "", ", ".join("`$%04X` -> `$%04X`" % x for x in g.bad), "" if len(g.bad) > 1 else "s"))
        P("")
        P("| Block | Instr | Last | Calls | Successors |")
        P("|---|---|---|---|---|")
        for l in sorted(g.blocks):
            seq = g.blocks[l]
            last = rom.ins[seq[-1]]
            calls = [rom.names.get(rom.ins[a][3], "$%04X" % rom.ins[a][3]) for a in seq if rom.ins[a][1] == "jsr"]
            outs = ["%s `$%04X`" % (k, b) for a, b, k in g.edges if a == l]
            P("| `%s`%s | %d | %s | %s | %s |" % (block_label(rom, g, l), " (entry)" if l == e else "", len(seq), last[1].upper(), ", ".join(calls) or "-", "; ".join(outs) or (("**exit** (%s)" % last[1].upper()) if last[1] in ("rts", "rti", "jmp") else "none (does not return)")))
        P("")
        P("```mermaid")
        P("flowchart TD")
        for l in sorted(g.blocks):
            seq = g.blocks[l]
            last = rom.ins[seq[-1]][1].upper()
            P("  B%04X[\"$%04X<br/>%d instr, %s\"]" % (l, l, len(seq), last))
        for a, b, k in g.edges:
            back = (a, b) in g.back
            if back:
                P("  B%04X ==> B%04X" % (a, b))
            elif k.startswith("not taken"):
                P("  B%04X -.-> B%04X" % (a, b))
            else:
                P("  B%04X --> B%04X" % (a, b))
        P("```")
        P("")
    return L


def main():
    rom, F, G = analyse()
    AF.solve(rom, F)
    txt = "\n".join(report(rom, F, G)) + "\n"
    if "--write" in sys.argv:
        path = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", path, len(G), "routines,", sum(len(g.blocks) for g in G.values()), "blocks,", len(txt), "bytes")
    else:
        print(txt)


if __name__ == "__main__":
    main()
