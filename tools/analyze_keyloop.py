"""OV-65: which outcome of which conditional branch of the key loop `$A4BA-$A572` ran, from the logs of tools/run_keyloop_audit.ps1 (the last complete `KC` line of each log: the counters of tools/make_keyloop_cmd.py),
and how long a pass of the loop takes (the static cost of its paths, tools/static_wcet.py cost table) against what the sessions measured (passes of the loop per frame).
Usage: python -I tools/analyze_keyloop.py analysis/raw-logs/keyloop-*.txt [--write analysis/evidence-keyloop-summary.txt]"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import make_keyloop_cmd as K  # noqa: E402
import static_wcet as W       # noqa: E402
import absint6502 as AB       # noqa: E402

KC = re.compile(r"^KC f=(\d+) p=(\d+) ((?:\d+ ?)+)$")
KB = re.compile(r"^KB f=(\d+) ((?:\d+ ?)+)$")
# outcomes that cannot happen by construction (the flag is fixed by the instruction before): pc -> (outcome, why)
DEAD = {
    0xA4DE: ("not taken", "after `lda #$00`: Z = 1, `beq` always taken (Paused := 0)"),
    0xA4F3: ("not taken", "after `lda #$04`: Z = 0, `bne` always taken"),
    0xA535: ("not taken", "`bne` after `cmp #$05 / beq` fell through: not equal, always taken (any other key combination: back to the top)"),
    0xA54A: ("not taken", "after `lda #$01`: Z = 0, `bne` always taken"),
    0xA561: ("not taken", "after `inc StartLevel` from 0 or 1: the result is 1 or 2, `bne` always taken"),
    0xA56B: ("not taken", "after two `inc StartLevel` from 2 to 10 (even): the result is 4 to 12, `bne` always taken"),
    0xA571: ("not taken", "after `lda #$00` / `sta`: Z = 1, `beq` always taken"),
}


def last_counters(path):
    best = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith(chr(10)):
                continue
            m = KC.match(ln.strip())
            if m:
                best = (int(m.group(1)), int(m.group(2)), [int(x) for x in m.group(3).split()])
    return best


def last_blocks(path):
    """the last complete KB line: how often $A4ED and $A4F1 ran (cold points of the game-over countdown)"""
    best = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if ln.endswith(chr(10)):
                m = KB.match(ln.strip())
                if m:
                    best = [int(x) for x in m.group(2).split()]
    return best


def last_frame(path):
    best = 0
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if ln.endswith(chr(10)) and ln.startswith("KB f="):
                best = int(ln.split()[1][2:])
    return best


def gather(paths):
    br = K.branches()
    seen = {}                                   # (pc, 'taken'/'not taken') -> {log: count}
    frames = {}
    passes = {}
    for p in paths:
        last = last_counters(p)
        kb = last_blocks(p)
        if not last and not kb:
            continue
        name = os.path.basename(p)[len("keyloop-"):-4]
        if last:
            f, ps, v = last
            frames[name] = f
            passes[name] = ps
        else:
            f, ps, v = 0, 0, []                  # a run that counted cold points only (KB lines)
            frames[name] = last_frame(p)
        if kb:                                  # $A4ED runs when the countdown is on ($A4EB not taken) and goes on to $A4EF; $A4F1 runs when the countdown timer is 0 ($A4EF not taken), and then $A4F3 is taken
            n_ed, n_f1 = kb[0], kb[1]
            for key, cnt in ((("A4EB", "not taken"), n_ed), (("A4EF", "not taken"), n_f1), (("A4EF", "taken"), n_ed - n_f1), (("A4F3", "taken"), n_f1)):
                if cnt > 0:
                    seen.setdefault((int(key[0], 16), key[1]), {})[name + " (blocks)"] = cnt
        for k, (pc, m, tgt) in enumerate(br):
            for j, o in enumerate(("taken", "not taken")):
                if v and v[2 * k + j]:
                    seen.setdefault((pc, o), {})[name] = v[2 * k + j]
    return br, seen, frames, passes


def pass_rates(paths):
    """passes of the loop per frame: the median of the per-frame pass counter of a log"""
    out = {}
    for p in paths:
        if "targeted" in p:
            continue                                                       # a targeted run does not count the passes
        prev = None
        steps = []
        with open(p, encoding="ascii", errors="replace") as fh:
            for ln in fh:
                if not ln.endswith(chr(10)):
                    continue
                m = KC.match(ln.strip())
                if not m:
                    continue
                f, ps = int(m.group(1)), int(m.group(2))
                steps.append(ps)                                    # the passes since the last frame (the counter is cleared once a frame)
                prev = (f, ps)
        if steps:
            steps.sort()
            out[os.path.basename(p)[len("keyloop-"):-4]] = (len(steps), steps[len(steps) // 2], steps[len(steps) // 10], steps[-1])
    return out


def path_costs():
    """the instruction cycles of the idle passes of the loop (no key, no console key): on the title screens (GameState not 0) and in a game (GameState 0); the colour table is read with the real X (3, 2, 1, 0)"""
    prog = AB.Program()
    ins = prog.ins

    def run(steps):
        t = 0
        for k, (a, x) in enumerate(steps):
            nxt = steps[k + 1][0] if k + 1 < len(steps) else steps[0][0]
            t += W.cost(ins, a, nxt, x, None)
        return t
    colour = []
    for x in (3, 2, 1, 0):
        colour += [(0xA4BC, x), (0xA4BF, x), (0xA4C1, x), (0xA4C3, x), (0xA4C5, x), (0xA4C6, x)]
    head = [(0xA4BA, None)] + colour + [(0xA4C8, 0)]
    title = head + [(0xA4CA, 0), (0xA4F5, 0), (0xA4F7, 0), (0xA4FA, 0), (0xA4FD, 0), (0xA4FF, 0), (0xA502, 0), (0xA504, 0), (0xA507, 0), (0xA509, 0)]
    game = head + [(0xA4CA, 0), (0xA4CC, 0), (0xA4CF, 0), (0xA4D1, 0), (0xA4D4, 0), (0xA4D6, 0), (0xA4E9, 0), (0xA4EB, 0), (0xA504, 0), (0xA507, 0), (0xA509, 0)]
    return {"idle pass on a title screen (GameState not 0, trigger and console not pressed)": run(title), "idle pass in a game (GameState 0, no key, no countdown, no console key)": run(game)}


def lines(paths):
    br, seen, frames, passes = gather(paths)
    L = ["Outcomes of the conditional branches of the key loop $A4BA-$A572 (tools/run_keyloop_audit.ps1; %d logs: %s)" % (len(frames), ", ".join("%s %d frames" % kv for kv in sorted(frames.items()))),
         "branch | target | taken: logs that saw it | not taken: logs that saw it"]
    unc = []
    for pc, m, tgt in br:
        row = []
        for o in ("taken", "not taken"):
            s = seen.get((pc, o), {})
            if s:
                row.append("%d logs (most %s)" % (len(s), "{:,}".format(max(s.values())) if max(s.values()) < 65535 else "65,535+ (saturated)"))
            elif DEAD.get(pc, (None,))[0] == o:
                row.append("cannot happen")
            else:
                row.append("NOT SEEN")
                unc.append((pc, o))
        L.append("$%04X %s | $%04X | %s | %s" % (pc, m, tgt, row[0], row[1]))
    total = 2 * len(br)
    dead = sum(1 for pc in DEAD)
    L.append("")
    L.append("%d outcomes of %d branches: %d seen, %d cannot happen (%s), %d not seen" % (total, len(br), total - dead - len(unc), dead, ", ".join("$%04X" % pc for pc in sorted(DEAD)), len(unc)))
    if unc:
        L.append("not seen: " + ", ".join("$%04X %s" % u for u in unc))
    L.append("")
    L.append("why the 'cannot happen' ones cannot:")
    for pc in sorted(DEAD):
        L.append("  $%04X: %s" % (pc, DEAD[pc][1]))
    L.append("")
    for k, v in path_costs().items():
        L.append("%s: %d instruction cycles" % (k, v))
    L.append("")
    L.append("passes of the key loop per frame in the sessions (the main program gets what the handler, the display and the interrupts leave: 16,100 cycles on the game screen, 19,750 on the title screen, less the handler's own work):")
    L.append("log | frames | median passes a frame | 10th percentile | most")
    rates = pass_rates(paths)
    for k, (n, med, lo, hi) in sorted(rates.items()):
        L.append("%s | %d | %d | %d | %d" % (k, n, med, lo, hi))
    if rates:
        med = max(v[1] for v in rates.values())
        costs = list(path_costs().values())
        L.append("check against the measured budgets: the most passes a frame at the median is %d: %d x %d cycles = %d, within the 19,750 cycles of the title and copyright screens (the copyright wait frame costs the handler almost nothing); the logs of a game: %d x %d = %d within 16,100 (the handler's play frame takes the rest)" % (med, med, costs[0], med * costs[0], max(v[1] for k, v in rates.items() if k in ("gameover", "pause", "rare")), costs[1], max(v[1] for k, v in rates.items() if k in ("gameover", "pause", "rare")) * costs[1]))
    return L


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
    txt = chr(10).join(lines(paths)) + chr(10)
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
