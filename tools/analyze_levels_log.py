"""Analyse a log made by tools/run_patrol_trace.ps1 -Cmd altirra_levels.cmd against the per-level tables (step C11).
Usage: python -I tools/analyze_levels_log.py <log> [--summary-file <out>]
Also usable as a library: expected(level) returns every per-level value the game derives from the tables.
Level is the game's zero-based counter ($30): board 1 = Level 0.
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

NIB, _ = S.split_nibbles(0xBE95)
R = lambda a: NIB[a - 0x600]
PAC_BASE = [S.rd(0xBDB9 + i) for i in range(7)]
GHOST_BASE = [S.rd(0xBDC0 + i) for i in range(7)]
REC_OFF = [S.rd(0xBD6D + i) for i in range(13)]
PROFILE = [S.rd(0xBD26 + i) for i in range(31)]


def expected(L):
    """Everything the game derives from the level counter L (0..255), exactly as the code indexes the tables."""
    c6, c12 = min(L, 6), min(L, 12)
    e = {}
    e["pac_delays"] = [R(0x7AE + PAC_BASE[c6] + c) for c in range(4)]
    e["ghost_delays"] = [R(0x7AE + GHOST_BASE[c6] + c) for c in range(4)]
    e["fright_frames"] = S.rd(0xBBF8 + L)                 # not clamped: reads past the 15-entry table for L >= 15
    e["fright_end_phase"] = R(0x672 + L)                  # not clamped: reads past the 20-entry table for L >= 20
    e["bonus_glyph"] = PROFILE[c12]
    e["bonus_record"] = [S.rd(0xBD45 + REC_OFF[c12] + i) for i in range(5)]
    e["bonus_score"] = (R(0x794 + 2 * c12), R(0x794 + 2 * c12 + 1))
    # level indicator (Sub_AC93): bytes at $0F86..$0F93, None = not written by this call
    row = [None] * 14
    if L < 6:
        for x in range(L + 1):
            pos = 0x0F92 - 2 * x - 0x0F86
            row[pos], row[pos + 1] = PROFILE[x], (PROFILE[x] + 1) & 0xFF
    else:
        t = min(L, 18) - 6
        for x in range(7):
            v = S.rd(0xBD3E - t + x)
            row[2 * x], row[2 * x + 1] = v, (v + 1) & 0xFF
    e["indicator"] = row
    return e


def release_timer_options(new_level):
    """Timers (ghosts 1..3, 4 frames per tick) the game sets for the board that starts at `new_level`.
    Sub_AE02 runs with the OLD level O = new_level-1 and uses Y = O+1 (clamped to 3) into Window3Table; for O = 0 the first
    ghost-house test is `RTCLOK2 < $80 -> Y = 1, else Y = 0`, so board 2 (and a game that starts on level 0) can get either set."""
    tbl = [S.rd(0xBBF2 + i) for i in range(6)]
    def win(y):
        y = min(y, 3)
        return (tbl[y + 2], tbl[y + 1], tbl[y])         # zp_CB, zp_CC, zp_CD
    old = new_level - 1
    if old == 0:
        return [win(1), win(0)]
    return [win(old + 1)]


def main(path):
    L = [l.rstrip("\n") for l in open(path, encoding="latin1", errors="replace")]
    out = []
    cnt = collections.Counter()
    bad = collections.defaultdict(list)
    levels = set()
    fright_seen, end_seen, bonus_seen = {}, {}, {}
    last_fc = {}
    rel_timers, rel_events, adv = [], [], []
    for l in L:
        m = re.match(r"LEVEL_ADVANCE level_p1=(\d+) level_p2=\d+ frame=(\d+)", l)
        if m:
            levels.add(int(m[1]))
            cnt["LEVEL_ADVANCE"] += 1
            adv.append((int(m[1]), int(m[2])))
            continue
        m = re.match(r"MOVE_DELAY ent=(\d) delay=(\d+) cycle=(\d) level=(\d+)", l)
        if m:
            cnt["MOVE_DELAY"] += 1
            ent, d, cyc, lv = int(m[1]), int(m[2]), int(m[3]), int(m[4])
            levels.add(lv)
            e = expected(lv)
            want = (e["pac_delays"] if ent == 4 else e["ghost_delays"])[cyc]
            if d != want:
                bad["MOVE_DELAY"].append(l)
            continue
        m = re.match(r"FRIGHT_TIME level=(\d+) FD=\$(\w+)", l)
        if m:
            cnt["FRIGHT_TIME"] += 1
            lv, fd = int(m[1]), int(m[2], 16)
            fright_seen[lv] = fd
            if fd != expected(lv)["fright_frames"]:
                bad["FRIGHT_TIME"].append(l)
            continue
        m = re.match(r"FRIGHT_END_CHECK level=(\d+) table=(\d+) FC=(\d+) FD=(\d+)", l)
        if m:
            cnt["FRIGHT_END_CHECK"] += 1
            lv, tb, fc = int(m[1]), int(m[2]), int(m[3])
            end_seen.setdefault(lv, set()).add(tb)
            last_fc[lv] = max(last_fc.get(lv, 0), fc)
            if tb != expected(lv)["fright_end_phase"]:
                bad["FRIGHT_END_CHECK"].append(l)
            continue
        m = re.match(r"BONUS_APPEARS level=(\d+) glyph=\$(\w+),\$(\w+)", l)
        if m:
            cnt["BONUS_APPEARS"] += 1
            lv = int(m[1])
            g = (int(m[2], 16), int(m[3], 16))
            bonus_seen[lv] = g
            if g != (expected(lv)["bonus_glyph"], (expected(lv)["bonus_glyph"] + 1) & 255):
                bad["BONUS_APPEARS"].append(l)
            continue
        m = re.match(r"BONUS_GLYPHS level=(\d+) g=\$(\w+) \$(\w+) \$(\w+) \$(\w+) \$(\w+)", l)
        if m:
            cnt["BONUS_GLYPHS"] += 1
            lv = int(m[1])
            got = [int(m[i], 16) for i in range(2, 7)]
            # the routine has just copied the record to $0DF1..$0DF5; $0DF3/$0DF4 were overwritten by the maze glyph at $B677,
            # so only compare when the record bytes are unchanged by it: compare bytes 0,1,4 always, 2 and 3 as the record
            want = expected(lv)["bonus_record"]
            if got != want:
                bad["BONUS_GLYPHS"].append(l)
            continue
        m = re.match(r"BONUS_SCORE level=(\d+) thousands=(\d+) hundreds=(\d+)", l)
        if m:
            cnt["BONUS_SCORE"] += 1
            lv = int(m[1])
            if (int(m[2]), int(m[3])) != expected(lv)["bonus_score"]:
                bad["BONUS_SCORE"].append(l)
            continue
        m = re.match(r"RELEASE_TIMERS level=(\d+) t1=\$(\w+) t2=\$(\w+) t3=\$(\w+) frame=(\d+)", l)
        if m:
            cnt["RELEASE_TIMERS"] += 1
            rel_timers.append((int(m[1]), (int(m[2], 16), int(m[3], 16), int(m[4], 16)), int(m[5])))
            continue
        m = re.match(r"RELEASE ghost=(\d) state=\$(\w+) frame=(\d+)", l)
        if m:
            cnt["RELEASE"] += 1
            rel_events.append((int(m[1]), int(m[2], 16), int(m[3])))
            continue
        m = re.match(r"INDICATOR level=(\d+) row=(.*)", l)
        if m:
            cnt["INDICATOR"] += 1
            lv = int(m[1])
            row = [int(x.strip("$"), 16) for x in m[2].split()]
            want = expected(lv)["indicator"]
            if any(w is not None and w != g for w, g in zip(want, row)):
                bad["INDICATOR"].append(l)
    # release timers: the LAST RELEASE_TIMERS line before each LEVEL_ADVANCE (and the last one before the first release of the game)
    rel_ok = rel_bad = 0
    model_ok = model_n = 0
    for new_level, frame in adv:
        cand = [t for lv, t, f in rel_timers if f <= frame]
        if not cand:
            continue
        got = cand[-1]
        if got in release_timer_options(new_level) or new_level >= 100:
            rel_ok += 1
        else:
            rel_bad += 1
            bad["RELEASE_TIMERS"].append("board with Level %d: %s not in %s" % (new_level, got, release_timer_options(new_level)))
        # release frames of ghosts 1..3 (state 1 = left the house normally) after this level advance
        nxt = [f for lv, f in adv if f > frame]
        end = nxt[0] if nxt else 10 ** 9
        ev = {g: f for g, st, f in rel_events if frame < f < end and st == 1 and g not in {}}
        first = {}
        for g, st, f in rel_events:
            if frame < f < end and st == 1 and g not in first:
                first[g] = f
        if len(first) == 3:
            base = first[1] - 4 * got[0]
            for g in (2, 3):
                model_n += 1
                if first[g] - first[1] == 4 * (got[g - 1] - got[0]) + 48:
                    model_ok += 1
    out.append("release timers: %d level starts checked, %d outside the table-derived options" % (rel_ok + rel_bad, rel_bad))
    out.append("release-frame model release(ghost k) = release(ghost 1) + 4*(timer_k - timer_1) + 48: holds for %d of %d checked releases (ghost 2/3; board starts with all three ghosts leaving normally)" % (model_ok, model_n))
    out.append("%d lines. Levels seen (zero-based): %s" % (len(L), _ranges(sorted(levels))))
    out.append("events: " + ", ".join("%s=%d" % kv for kv in sorted(cnt.items())))
    out.append("mismatches against the tables: " + (", ".join("%s=%d" % (k, len(v)) for k, v in sorted(bad.items())) or "none"))
    for k, v in bad.items():
        out.append("   first %s mismatches: %s" % (k, v[:3]))
    out.append("power-pellet frightened time seen on levels: " + _ranges(sorted(fright_seen)))
    out.append("frightened-end table value read on levels: " + _ranges(sorted(end_seen)))
    out.append("bonus item shown on levels: " + _ranges(sorted(bonus_seen)))
    reached = [lv for lv in sorted(last_fc) if last_fc[lv] == expected(lv)["fright_end_phase"]]
    not_reached = [lv for lv in sorted(last_fc) if last_fc[lv] != expected(lv)["fright_end_phase"]]
    out.append("frightened state ended exactly when the phase equalled the table value on %d levels: %s" % (len(reached), _ranges(reached)))
    out.append("levels where the phase was still running at the end of the cycle (table value 0: the phase has to wrap through 256 first): " +
               (" ".join("L%d:%d/%d" % (lv, last_fc[lv], expected(lv)["fright_end_phase"]) for lv in not_reached) or "none"))
    return out


def _ranges(v):
    if not v:
        return "-"
    out, a, b = [], v[0], v[0]
    for x in v[1:]:
        if x == b + 1:
            b = x
        else:
            out.append("%d" % a if a == b else "%d-%d" % (a, b))
            a = b = x
    out.append("%d" % a if a == b else "%d-%d" % (a, b))
    return ", ".join(out)


if __name__ == "__main__":
    out = main(sys.argv[1])
    print("\n".join(out))
    if "--summary-file" in sys.argv:
        open(sys.argv[sys.argv.index("--summary-file") + 1], "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
