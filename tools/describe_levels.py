"""Print the per-level parameters derived from the ROM tables (step C11). Usage: python -I tools/describe_levels.py [last_level]
Level is the game's zero-based counter; board N = Level N-1. Same formulas as analyze_levels_log.expected()."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_levels_log as A  # noqa: E402

last = int(sys.argv[1]) if len(sys.argv) > 1 else 24
print("| Board | Level | Pac-Man delays | Ghost delays | Frightened solid (frames) | End phase | Flash (frames) | Total (frames) | Bonus | Item codes |")
print("|---|---|---|---|---|---|---|---|---|---|")
for L in range(last + 1):
    e = A.expected(L)
    fd, ph = e["fright_frames"], e["fright_end_phase"]
    # measured live: the frightened-end test runs (phase-2)*24+2 frames for phase >= 2, 1 frame for phase 1; phase 0 must wrap the counter (256 steps)
    flash = ((ph if ph else 256) - 2) * 24 + 2 if ph != 1 else 1
    print("| %d | %d | `%s` | `%s` | %d | %d | %d | %d | %d | `%02X %02X` |" % (
        L + 1, L, "".join(map(str, e["pac_delays"])), "".join(map(str, e["ghost_delays"])), fd, ph, flash, fd + flash,
        e["bonus_score"][0] * 1000 + e["bonus_score"][1] * 100, e["bonus_glyph"], e["bonus_glyph"] + 1))
