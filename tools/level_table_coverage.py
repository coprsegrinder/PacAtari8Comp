"""Entry-by-entry coverage of every level-indexed table, computed from live logs (step C11).
Usage: python -I tools/level_table_coverage.py <level-sweep log> [<more logs>...]
For each table it lists which entries the real game read (as shown by the logged events) and which it did not, then checks
every logged value against the ROM. Logs: tools/run_patrol_trace.ps1 -Cmd altirra_levels.cmd (see docs/14-levels.md).
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_levels_log as A  # noqa: E402
import decode_streams as S  # noqa: E402


def rng(v):
    return A._ranges(sorted(v))


def main(paths):
    lines = []
    for p in paths:
        lines += [l.rstrip("\n") for l in open(p, encoding="latin1", errors="replace")]
    used = collections.defaultdict(set)
    levels = set()
    for l in lines:
        m = re.match(r"FRIGHT_TIME level=(\d+)", l)
        if m:
            used["FrightenFrames"].add(int(m[1]))
        m = re.match(r"FRIGHT_END_CHECK level=(\d+)", l)
        if m:
            used["FrightenEndPhase"].add(int(m[1]))
        m = re.match(r"BONUS_SCORE level=(\d+)", l)
        if m:
            used["BonusScore"].add(min(int(m[1]), 12))
        m = re.match(r"BONUS_GLYPHS level=(\d+) g=\$(\w+) \$(\w+)", l)
        if m:
            lv = min(int(m[1]), 12)
            used["BonusScoreGlyphOffsets"].add(lv)
            used["BonusScoreGlyphs (records)"].add(S.rd(0xBD6D + lv) // 5)
        m = re.match(r"BONUS_APPEARS level=(\d+)", l)
        if m:
            used["BonusItemCodes"].add(min(int(m[1]), 12))
        m = re.match(r"INDICATOR level=(\d+)", l)
        if m:
            lv = int(m[1])
            if lv < 6:
                used["BonusItemCodes"].update(range(lv + 1))
            else:
                start = 30 - min(lv, 18)
                used["BonusItemCodes"].update(range(start, start + 7))
        m = re.match(r"MOVE_DELAY ent=(\d) delay=(\d+) cycle=(\d) level=(\d+)", l)
        if m:
            ent, cyc, lv = int(m[1]), int(m[3]), min(int(m[4]), 6)
            base = (A.PAC_BASE if ent == 4 else A.GHOST_BASE)[lv]
            used["MoveDelay"].add(base + cyc)
            used["PacMoveDelayBase" if ent == 4 else "GhostMoveDelayBase"].add(lv)
        m = re.match(r"RELEASE_TIMERS level=\d+ t1=\$(\w+) t2=\$(\w+) t3=\$(\w+)", l)
        if m:
            trip = tuple(int(m[i], 16) for i in (1, 2, 3))
            tbl = [S.rd(0xBBF2 + i) for i in range(6)]
            for y in range(4):
                if (tbl[y + 2], tbl[y + 1], tbl[y]) == trip:
                    used["HouseReleaseTimers (bytes)"].update(range(y, y + 3))
    sizes = {"FrightenFrames": 15, "FrightenEndPhase": 20, "BonusScore": 13, "BonusScoreGlyphOffsets": 13,
             "BonusScoreGlyphs (records)": 8, "BonusItemCodes": 31, "MoveDelay": 24, "PacMoveDelayBase": 7,
             "GhostMoveDelayBase": 7, "HouseReleaseTimers (bytes)": 6}
    out = ["Entry-by-entry coverage of the level-indexed tables (entries the real game read, from the logs):"]
    for name, n in sizes.items():
        got = {i for i in used[name] if i < n}
        miss = sorted(set(range(n)) - got)
        out.append("  %-28s %2d entries: read %2d  never read: %s" % (name, n, len(got), miss or "none"))
    over = lambda name: sorted(i for i in used[name] if i >= sizes[name])
    out.append("  FrightenFrames read past its 15 entries at levels: %s" % rng(over("FrightenFrames")))
    out.append("  FrightenEndPhase read past its 20 entries at levels: %s" % rng(over("FrightenEndPhase")))
    return out


if __name__ == "__main__":
    print("\n".join(main(sys.argv[1:])))
