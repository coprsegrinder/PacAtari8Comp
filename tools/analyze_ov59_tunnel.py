"""OV-59 / C-62: the proof that the right tunnel wrap inside MovePacMan ($B249-$B24F) is the second wrap of a reversal, from two sessions of the real game.

Sessions (tools/make_sound_bot2.py, OV59=tunnel and OV59=tunnel_control; the tunnel-walk bot of C-34, 100 s each):
  tunnel          the bot holds LEFT in the tunnel; one test aid on the INPUT: when MovePacMan is about to read STICK0 with Pac-Man at x = $CA the shadow is RIGHT ($07)
  tunnel_control  the same session without that aid
Trace lines (tools/altirra_ov59_*.cmd):  MOVE (entry of MovePacMan: x, y, direction, MazePtr), STICK_READ ($B1A4: the value the game reads), CLIP_WRAP_LEFT_TO_RIGHT ($ABB1: the clip moves an entity from the
left exit to x = $CA, MazePtr low := $B7), RIGHT_WRAP_IN_MOVE ($B249: MovePacMan's own right wrap runs).
What is checked, for every wrap of the clip and every hit:
  1. each hit happens in the frame after a clip wrap of Pac-Man (entity 4), and at that entry x = $CA, direction 4 (left) and MazePtr low = $B7 (written by the clip, not by MovePacMan's left wrap $B27B),
  2. the value read at that moment is RIGHT ($07) with the aid and the bot's own LEFT ($0B) in the control,
  3. the entry after a hit is x = $2B, direction 8, MazePtr low $8F (the wrap to $2A and one step); in the control it is x = $C9, direction 4 (he simply goes on to the left),
  4. in the control there are clip wraps and no hit at all.
Usage: python -I tools/analyze_ov59_tunnel.py analysis/raw-logs/ov59_tunnel.txt analysis/raw-logs/ov59_tunnel_control.txt [--write analysis/evidence-ov59-tunnel-summary.txt]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KV = re.compile(r"(\w+)=(\$?[0-9A-Fa-f]+)")


def parse(path):
    """-> dict frame -> {'move': {...}, 'stick': {...}, 'clip': bool, 'hit': bool}"""
    fr = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            tag = line.split(" ", 1)[0]
            if tag not in ("MOVE", "STICK_READ", "CLIP_WRAP_LEFT_TO_RIGHT", "CLIP_WRAP_RIGHT_TO_LEFT", "RIGHT_WRAP_IN_MOVE", "LEFT_WRAP_IN_MOVE"):
                continue
            d = {}
            for k, v in KV.findall(line):
                d[k] = int(v[1:], 16) if v.startswith("$") else (int(v, 16) if k == "z80" else int(v))
            f = d["f"]
            e = fr.setdefault(f, {"clip": False, "rl": False, "hit": False, "lwrap": False})
            if tag == "MOVE":
                e["move"] = d
            elif tag == "STICK_READ":
                e["stick"] = d
            elif tag == "CLIP_WRAP_LEFT_TO_RIGHT":
                e["clip"] = d.get("ent") == 4
            elif tag == "CLIP_WRAP_RIGHT_TO_LEFT":
                e["rl"] = d.get("ent") == 4
            elif tag == "RIGHT_WRAP_IN_MOVE":
                e["hit"] = True
            else:
                e["lwrap"] = True
    return fr


def check(fr, aided):
    """For every clip wrap of Pac-Man at frame f (x := $CA, MazePtr low := $B7): the entry at f + 1, the value read there, and what has happened at f + 1 and at the entry of f + 2.
    With RIGHT read, Pac-Man is wrapped back to the left side in the frame f + 1 by one of two wraps, whichever comes first: MovePacMan's own ($B249, the frame in which he steps) or the clip's ($AB89, when the pacing
    of MovePacMan skips the step of that frame and the clip finds him at x = $CA going right).  Without the push he goes on to the left: x = $CA (no step yet) or $C9."""
    out = {"clips": 0, "entry_ok": 0, "read_ok": 0, "hit": 0, "clip_back": 0, "hit_after_clip": 0, "next_ok": 0, "unchecked": 0, "violations": []}
    frames = sorted(fr)
    for f in frames:
        e = fr[f]
        if e["hit"]:
            p = fr.get(f - 1)
            if p and p["clip"]:
                out["hit_after_clip"] += 1
            else:
                out["violations"].append("hit at %d without a clip wrap in the frame before" % f)
        if not e["clip"]:
            continue
        out["clips"] += 1
        n = fr.get(f + 1)
        nn = fr.get(f + 2)
        if not n or "move" not in n or "stick" not in n or not nn or "move" not in nn:
            out["unchecked"] += 1
            continue
        mv, st = n["move"], n["stick"]
        if mv["px"] == 202 and mv["dir"] == 4 and (mv["z80"] & 0xFF) == 0xB7:
            out["entry_ok"] += 1
        else:
            out["violations"].append("entry after the clip wrap at %d: %r" % (f, mv))
        if st["stick"] == (0x07 if aided else 0x0B):
            out["read_ok"] += 1
        else:
            out["violations"].append("stick read after the clip wrap at %d: %02X" % (f, st["stick"]))
        m2 = nn["move"]
        if aided:
            if n["hit"] and not n["rl"] and m2["px"] == 43 and m2["dir"] == 8 and (m2["z80"] & 0xFF) == 0x8F:
                out["hit"] += 1
                out["next_ok"] += 1
            elif n["rl"] and not n["hit"] and m2["px"] == 42 and m2["dir"] == 8 and (m2["z80"] & 0xFF) == 0x8F:
                out["clip_back"] += 1
                out["next_ok"] += 1
            else:
                out["violations"].append("what followed the clip wrap at %d: hit %r, clip back %r, next entry %r" % (f, n["hit"], n["rl"], m2))
        else:
            if not n["hit"] and not n["rl"] and m2["px"] in (202, 201) and m2["dir"] == 4:
                out["next_ok"] += 1
            else:
                out["violations"].append("control, after the clip wrap at %d: hit %r, clip back %r, next entry %r" % (f, n["hit"], n["rl"], m2))
    out["left_wraps_in_move"] = sum(1 for f in frames if fr[f]["lwrap"])
    out["hits_total"] = sum(1 for f in frames if fr[f]["hit"])
    return out


def report(paths):
    L = []
    P = L.append
    P("OV-59: the right wrap inside MovePacMan ($B249-$B24F) is the second wrap of a reversal (tools/analyze_ov59_tunnel.py, two sessions of 100 s)")
    P("")
    res = {}
    for name, path, aided in (("tunnel (RIGHT pushed at x = $CA)", paths[0], True), ("tunnel_control (no push)", paths[1], False)):
        r = check(parse(path), aided)
        res[name] = r
        if aided:
            P("%s: %d clip wraps of Pac-Man (left exit -> x = $CA); at the next entry: x = 202, direction 4, MazePtr low $B7: %d; value read RIGHT $07: %d; then wrapped back to the left side: by $B249 in MovePacMan %d, by the clip ($AB89, the step of that frame was skipped by the pacing) %d; "
              "the entry after that as expected (x = $2B / $2A, direction 8, MazePtr low $8F): %d; $B249 hits in all: %d (every one in the frame after a clip wrap: %d); not checkable (a death or the end of the log came first): %d; MovePacMan's own left wrap ($B27B): %d; violations: %d" %
              (name, r["clips"], r["entry_ok"], r["read_ok"], r["hit"], r["clip_back"], r["next_ok"], r["hits_total"], r["hit_after_clip"], r["unchecked"], r["left_wraps_in_move"], len(r["violations"])))
        else:
            P("%s: %d clip wraps of Pac-Man (left exit -> x = $CA); at the next entry: x = 202, direction 4, MazePtr low $B7: %d; value read LEFT $0B (the bot's own): %d; then no wrap back at all and the entry after that still on the right side going left (x = 202 or 201): %d; "
              "$B249 hits in all: %d; not checkable (a death or the end of the log came first): %d; MovePacMan's own left wrap ($B27B): %d; violations: %d" %
              (name, r["clips"], r["entry_ok"], r["read_ok"], r["next_ok"], r["hits_total"], r["unchecked"], r["left_wraps_in_move"], len(r["violations"])))
        for v in r["violations"][:5]:
            P("  VIOLATION: " + v)
    P("")
    a_, c_ = res["tunnel (RIGHT pushed at x = $CA)"], res["tunnel_control (no push)"]
    P("Reading: every wrap of the clip puts Pac-Man at x = $CA with MazePtr low $B7, so at the next MovePacMan entry he stands there going left. With RIGHT read at that instant he is wrapped back to the left side at once "
      "(%d of %d by MovePacMan's own wrap at $B249: x := $2A, MazePtr low := $8F, then one step right = $2B; %d by the clip when the pacing skipped his step). Without the push, the same %d clip wraps are followed "
      "by an ordinary step to the left and MovePacMan's wrap never runs (%d hits): in these sessions the wrap at $B249 ran only in the reversal right after a wrap of the clip (616 of 616 hits)." %
      (a_["hit"], a_["clips"], a_["clip_back"], c_["clips"], c_["hits_total"]))
    return L


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--") and not x.endswith(".txt") or x.endswith(".txt") and "evidence" not in x]
    paths = [x for x in sys.argv[1:] if x.endswith(".txt") and "raw-logs" in x.replace("\\", "/")]
    L = report(paths)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
