"""Colours of the ghosts: normal, frightened (solid blue, flashing white/blue), eaten (score pop-up, eyes), restore. Checks the log of tools\\altirra_ghostcolors.cmd against the rules read from the code:
  * $AFBE-$AFD6: every frame while the frightened phase runs, each ghost with state bit 7 set gets $84 (blue) when FrightenPhase (FC) is odd, $0C (white) when even.
  * $AF81-$AF84: when the phase reaches the table value, ghosts with bit 7 get their own colour back (ColorsGame $44 $4A $D8 $28), then $AF9A/$AF9E set the new states.
  * $A8A6-$A8AB: a ghost that is eaten gets the pop-up colour $DC (also COLOR3); $B09D-$B0AA (after the pause): the player holding $DC gets $0C (the eyes); $B766-$B769: at home the own colour is restored.
Usage: python -I tools/analyze_ghostcolors_log.py <log> [--summary-file out]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_levels_log as AL  # noqa: E402
import decode_streams as S  # noqa: E402

OWN = [S.rd(0xBBE2 + i) for i in range(4)]            # ColorsGame[0..3]
RE_COLS = re.compile(r"COLS st=\$(..),\$(..),\$(..),\$(..) c=\$(..),\$(..),\$(..),\$(..) FC=(\d+) FD=(\d+) lv=(\d+) f=(\d+)(?: pc=\$(..))?")
RE_FC = re.compile(r"FRIGHT_COLOR ghost=(\d) y=\$(..) FC=(\d+) FD=(\d+) st=\$(..) f=(\d+)")
RE_EV = re.compile(r"^(END_RESTORE|POPUP|EYES|HOME_RESTORE|GHOST_EATEN|PELLET|LOAD_SHADOW|LEVEL_ADVANCE|LEVEL_SETUP)\b")


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    cols, fc_writes, evs = [], [], []
    for line in open(path, errors="replace"):
        m = RE_COLS.search(line)
        if m:
            g = m.groups()
            cols.append(dict(st=[int(g[i], 16) for i in range(4)], c=[int(g[4 + i], 16) for i in range(4)], fc=int(g[8]), fd=int(g[9]), lv=int(g[10]), f=int(g[11]), pc=int(g[12], 16) if g[12] else None))
            continue
        m = RE_FC.search(line)
        if m:
            fc_writes.append(dict(g=int(m.group(1)), y=int(m.group(2), 16), fc=int(m.group(3)), fd=int(m.group(4)), st=int(m.group(5), 16), f=int(m.group(6))))
            continue
        m = RE_EV.match(line)
        if m:
            f = re.search(r"f=(\d+)", line)
            gh = re.search(r"ghost=(\d)", line)
            evs.append((m.group(1), int(gh.group(1)) if gh else None, int(f.group(1)), line.strip()))
    bad = collections.defaultdict(list)
    cnt = collections.Counter()
    P("COLS frames:", len(cols), " FRIGHT_COLOR writes:", len(fc_writes), " events:", dict(collections.Counter(e[0] for e in evs)))

    # 1. the write at $AFD0: colour = $84 iff FC odd, only for ghosts with bit 7
    for w in fc_writes:
        exp = 0x84 if w["fc"] & 1 else 0x0C
        cnt["colour writes at $AFD0 (frightened ghosts, every frame)"] += 1
        if w["y"] != exp:
            bad["frightened colour not blue-for-odd / white-for-even"].append(w)
        if not w["st"] & 0x80 or w["st"] & 0x40:
            bad["colour write to a ghost without bit 7 or with bit 6"].append(w)
    cnt["  ... blue ($84) writes"] = sum(1 for w in fc_writes if w["y"] == 0x84)
    cnt["  ... white ($0C) writes"] = sum(1 for w in fc_writes if w["y"] == 0x0C)

    # 2. END_RESTORE writes own colour; HOME_RESTORE writes own colour for a ghost whose state is $44
    for k, g, f, line in evs:
        if k == "END_RESTORE":
            cnt["end-of-frightened restores ($AF84)"] += 1
            if int(re.search(r"val=\$(..)", line).group(1), 16) != OWN[g]:
                bad["end restore value"].append(line)
        if k == "HOME_RESTORE":
            cnt["home restores ($B769, an eaten ghost reaching its house)"] += 1
            if int(re.search(r"val=\$(..)", line).group(1), 16) != OWN[g]:
                bad["home restore value"].append(line)
            st = int(re.search(r"st=\$(..)", line).group(1), 16)
            if st != 0x04:            # the tracepoint at $B769 is reached after the store at $B764: state AND $0F of $44 = $04
                bad["home restore for a ghost whose state is not $04"].append(line)

    # 3. state vs. colour, every frame (the sample is taken once per frame; the writes can come later in the same frame, so a mismatch that is gone in the next sample is a 'transition')
    seen = collections.Counter()
    for i, c in enumerate(cols):
        for g in range(4):
            st, col = c["st"][g], c["c"][g]
            if st & 0x80 and not st & 0x40:
                kind = "frightened"
            elif st & 0x40:
                kind = "eaten"
            else:
                kind = "normal"
            seen[(kind, col)] += 1
    P()
    P("colour of the ghost player registers ($02C0-$02C3) per frame, by ghost state class (counts of ghost-frames):")
    for (kind, col), n in sorted(seen.items()):
        P("  %-11s colour $%02X : %d" % (kind, col, n))
    # rules: normal -> own colour; frightened -> $84/$0C; eaten -> $DC (pop-up) or $0C (eyes)
    trans = collections.Counter()
    for i, c in enumerate(cols):
        for g in range(4):
            st, col = c["st"][g], c["c"][g]
            if st & 0x80 and not st & 0x40:
                ok = col in (0x84, 0x0C)
                exp_fc = 0x84 if c["fc"] & 1 else 0x0C
                if ok and col != exp_fc:
                    # stale by one frame is allowed only if FC changed between this and the previous sample
                    prev = cols[i - 1] if i else None
                    ok = prev is not None and prev["fc"] != c["fc"]
                    trans["frightened colour of the previous phase in the sample at a phase change"] += int(ok)
            elif st & 0x40:
                ok = col in (0xDC, 0x0C)
            else:
                ok = col == OWN[g]
            if not ok:
                trans["%s state $%02X colour $%02X" % ("mismatch", st, col)] += 1
    P()
    P("ghost-frames whose colour was not the rule's (grouped by state, colour; these should be the single-frame transitions around a write):")
    tot = 0
    for k, n in sorted(trans.items()):
        P("  ", k, n)
        if k.startswith("mismatch"):
            tot += n
    P("  total mismatching ghost-frames:", tot, "of", 4 * len(cols))

    # 4. what the registers hold between POPUP and EYES, and between EYES and HOME_RESTORE, per eaten ghost
    eaten = collections.Counter()
    pop_to_eyes = []
    last_pop = {}
    for k, g, f, line in evs:
        if k == "POPUP":
            last_pop[g] = f
        if k == "EYES" and g in last_pop:
            pop_to_eyes.append(f - last_pop.pop(g))
    P()
    P("score pop-up -> eyes: %d eaten ghosts, frames between (pop-up colour $DC held):" % len(pop_to_eyes), sorted(collections.Counter(pop_to_eyes).items()))
    # eyes seen for every eaten ghost until home restore
    in_eyes = {}
    for k, g, f, line in evs:
        if k == "EYES":
            in_eyes[g] = f
        if k == "HOME_RESTORE" and g in in_eyes:
            eaten["eyes ($0C) until home restore"] += 1
            in_eyes.pop(g)
    for k in sorted(eaten):
        P("  ", k, eaten[k])
    # colour of a ghost in state $42/$44 in every sample: only $DC (pop-up) or $0C (eyes)
    # 6. COLOR3 ($02C7, the colour of Pac-Man, "COLPF3") while a score pop-up is shown
    if cols and cols[0]["pc"] is not None:
        spans = []
        pops = {}
        for k, g, f, line in evs:
            if k == "POPUP":
                pops[g] = f
            if k == "EYES" and g in pops:
                spans.append((pops.pop(g), f))
        pcs = collections.Counter()
        for c in cols:
            if c["pc"] is None:
                continue
            inside = any(a < c["f"] <= b for a, b in spans)
            pcs[("during a pop-up" if inside else "otherwise", c["pc"])] += 1
        P()
        P("COLOR3 ($02C7, Pac-Man's colour) per frame:", dict(sorted(pcs.items())))
    # 5. the colour sequence of every frightened period against the model of the code: FD frames blue (phase 1), then phases 2..end-1 of 24 frames each (white for even, blue for odd), then
    #    phase `end` shown for one frame (the next frame the end check fires). A period = the writes between a power pellet / end event and the next one; the 32-frame pop-up pause writes nothing.
    P()
    P("colour sequence of every frightened period against the model (blue FrightenFrames, then (end phase - 2) runs of 24 frames alternating white/blue, then the end phase for 1 frame):")
    bounds = sorted({e[2] for e in evs if e[0] in ("PELLET", "END_RESTORE", "LEVEL_SETUP", "LOAD_SHADOW")})
    import bisect
    segs = collections.defaultdict(dict)
    for w in fc_writes:
        i = bisect.bisect_right(bounds, w["f"] - 1)          # events at frame f - 1 or earlier close the previous period
        segs[i].setdefault(w["f"], w)
    lv_at = {c["f"]: c["lv"] for c in cols}
    periods = collections.Counter()
    shown_levels = set()
    compared_levels = {}
    for i in sorted(segs):
        fr = segs[i]
        fs = sorted(fr)
        lvl = lv_at.get(fs[0])
        if lvl is None:
            continue
        e = AL.expected(lvl)
        FDv, endp = e["fright_frames"], e["fright_end_phase"]
        if fr[fs[0]]["fc"] != (1 if FDv else 2):          # with FrightenFrames = 0 the first colour write is already phase 2
            periods["period not starting at the first phase (pellet re-armed inside it, or cut by the end of the log)"] += 1
            continue
        runs = []
        for f in fs:
            col = "blue" if fr[f]["y"] == 0x84 else "white"
            if runs and runs[-1][0] == col:
                runs[-1][1] += 1
            else:
                runs.append([col, 1])
        model = []
        if FDv:
            model.append(["blue", FDv])
        for p in range(2, endp):
            model.append(["white" if p % 2 == 0 else "blue", 24])
        if endp > 1:
            model.append(["white" if endp % 2 == 0 else "blue", 1])
        # runs of the same colour that the model produces next to each other (FD = 0, end phase 2) are merged the same way
        mm = []
        for r in model:
            if mm and mm[-1][0] == r[0]:
                mm[-1][1] += r[1]
            else:
                mm.append(list(r))
        # a period that is cut by the end of the log or re-armed by another pellet cannot be compared; an end event inside the period closes it
        closed = (bounds[bisect.bisect_right(bounds, fs[-1]) - 1] >= fs[-1] - 1) if bounds else False
        end_follows = any(ev[0] == "END_RESTORE" and fs[-1] <= ev[2] <= fs[-1] + 2 for ev in evs)
        if not end_follows:
            periods["period cut before its end (re-armed by a new pellet or log end)"] += 1
            continue
        ok = runs == mm
        compared_levels.setdefault(lvl, []).append(ok)
        periods["periods compared with the model: " + ("identical" if ok else "DIFFERENT")] += 1
        if not ok:
            bad["colour sequence differs from the model"].append((lvl, fs[0], FDv, endp, runs, mm))
        key = (FDv, endp)
        if ok and key not in shown_levels:
            shown_levels.add(key)
            P("  level %3d  FrightenFrames=%3d EndPhase=%2d : %s" % (lvl, FDv, endp, " ".join("%s%d" % (r[0], r[1]) for r in runs) or "(no frightened colour at all)"))
    for k in sorted(periods):
        P("  ", k, periods[k])
    P("levels (zero-based counter) with at least one complete frightened period compared, and how many were identical to the model:",
      {l: "%d/%d" % (sum(v), len(v)) for l, v in sorted(compared_levels.items())})
    P()
    P("violations:", {k: len(v) for k, v in bad.items()} or "none")
    for k, v in bad.items():
        P("  first", k, v[:2])
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
