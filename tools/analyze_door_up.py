"""OV-57: the eaten ghost that reaches the door square moving UP (the path $B6C6-$B6CC of EyesAndHousePerFrame).

Input: analysis/raw-logs/door-up.txt of tools/altirra_door_up.cmd (run it with tools/run_patrol_trace.ps1 -Seconds 120 -Cmd altirra_door_up.cmd), with the lines
  EATEN g= dir= x= y= st= px= py= f= t5=     a ghost is eaten (the entry of GhostEaten, after the state store)
  EY_DOOR g= dir= st= x= y= f=               EyesAndHousePerFrame: an eyes ghost is on the door square (x $7C, y $64), before the direction test
  EY_UP g= st= f=                            ... and it was moving up: it is turned left ($B6C6)
  EY_STATE44 g= dir= f=                      ... and it became state $44 (enters the house)
  HOME g= st= f=                             the ghost is home again ($B764)
  LEAVE g= y= st= dir= f=                    HouseLeaveStep ($B738), the first instruction of the walk up the door column (every step)
For each ghost the log is cut into episodes EATEN -> HOME.  Checks (each counted): the up case happens (EY_UP > 0) and is exactly the case `dir at the door = 1`; the turn is followed by another visit of the
door square with a direction that is not up, then state $44 and HOME (no ghost is lost); the ghosts eaten while leaving were frightened house ghosts eaten at y 104 moving up, in contact with Pac-Man on the door square.
Usage: python -I tools/analyze_door_up.py analysis/raw-logs/door-up.txt [--write analysis/evidence-door-up-summary.txt]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KV = re.compile(r"(\w+)=\$?([0-9A-Fa-f]+)")


def parse(path):
    ev = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            tag = line.split(" ", 1)[0]
            if tag not in ("EATEN", "EY_DOOR", "EY_UP", "EY_STATE44", "HOME", "LEAVE", "INIT_BOARD", "PELLET"):
                continue
            d = {}
            for k, v in KV.findall(line):
                d[k] = int(v, 16) if k in ("st",) else int(v)
            if "f" in d:
                ev.append((tag, d))
    return ev


def episodes(ev):
    """one episode per EATEN: the events of that ghost up to its HOME (or the next EATEN of the same ghost / a new board)"""
    out, open_ = [], {}
    for tag, d in ev:
        if tag == "INIT_BOARD":
            open_.clear()
            continue
        g = d.get("g")
        if tag == "EATEN":
            open_[g] = {"eaten": d, "door": [], "up": [], "s44": [], "home": []}
            out.append(open_[g])
        elif g in open_:
            e = open_[g]
            if tag == "EY_DOOR":
                e["door"].append(d)
            elif tag == "EY_UP":
                e["up"].append(d)
            elif tag == "EY_STATE44":
                e["s44"].append(d)
            elif tag == "HOME":
                e["home"].append(d)
                del open_[g]
    return out


def summarise(path):
    ev = parse(path)
    eps = episodes(ev)
    c = collections.Counter(e for e, d in ev for e in [e])
    r = {"counts": {k: sum(1 for t, d in ev if t == k) for k in ("INIT_BOARD", "PELLET", "EATEN", "LEAVE", "EY_DOOR", "EY_UP", "EY_STATE44", "HOME")}}
    up = [e for e in eps if e["up"]]
    r["episodes"] = len(eps)
    r["up_episodes"] = len(up)
    r["up_by_ghost"] = collections.Counter(e["eaten"]["g"] for e in up)
    r["up_eaten_dir"] = collections.Counter((e["eaten"]["dir"], e["eaten"]["y"], e["eaten"]["st"]) for e in up)
    r["not_up_eaten"] = collections.Counter((e["eaten"]["g"], e["eaten"]["dir"]) for e in eps if not e["up"])
    # the door visits: dir at the door = 1  <=>  EY_UP follows
    r["door_dir_up"] = sum(1 for e in eps for d in e["door"] if d["dir"] == 1)
    r["door_up_events"] = sum(len(e["up"]) for e in eps)
    r["up_then_second_visit"] = sum(1 for e in up if len(e["door"]) >= 2 and e["door"][-1]["dir"] != 1)
    r["up_then_s44"] = sum(1 for e in up if len(e["s44"]) == 1)
    r["up_then_home"] = sum(1 for e in up if len(e["home"]) == 1)
    r["all_home"] = sum(1 for e in eps if len(e["home"]) == 1)
    r["all_s44"] = sum(1 for e in eps if len(e["s44"]) == 1)
    r["s44_dirs"] = collections.Counter(e["s44"][0]["dir"] for e in eps if e["s44"])
    r["up_journey"] = [e["s44"][0]["f"] - e["up"][0]["f"] for e in up if e["s44"]]
    r["eaten_to_up"] = [e["up"][0]["f"] - e["eaten"]["f"] for e in up]
    r["px_py"] = collections.Counter((e["eaten"]["px"], e["eaten"]["py"]) for e in up)
    r["left"] = [e["up"][0]["f"] for e in up]
    return r


def report(path):
    r = summarise(path)
    c = r["counts"]
    L = []
    P = L.append
    P("Door-up audit (tools/altirra_door_up.cmd, tools/analyze_door_up.py): %d boards, %d power pellets, %d ghosts eaten, %d EyesAndHousePerFrame visits of the door square" % (c["INIT_BOARD"], c["PELLET"], c["EATEN"], c["EY_DOOR"]))
    P("Eaten ghosts that arrived at the door square MOVING UP (the path $B6C6-$B6CC, turned left once): %d of %d episodes (ghost 1: %d, ghost 2: %d, ghost 3: %d, ghost 0: %d)" % (
        r["up_episodes"], r["episodes"], r["up_by_ghost"][1], r["up_by_ghost"][2], r["up_by_ghost"][3], r["up_by_ghost"][0]))
    P("  how they were eaten (direction, y, state after the eating): %s" % ", ".join("dir %d y %d state $%02X: %d" % (k[0], k[1], k[2], v) for k, v in sorted(r["up_eaten_dir"].items())))
    P("  Pac-Man's position at those eatings (the test aid keeps him on the door square): %s" % ", ".join("(%d,%d): %d" % (k[0], k[1], v) for k, v in sorted(r["px_py"].items())))
    P("  frames from the eating to the turn: min %d, max %d" % (min(r["eaten_to_up"]), max(r["eaten_to_up"])))
    P("Door visits with the direction up: %d; turns made by the path ($B6C6): %d  (equal: the path is taken exactly when the direction is up)" % (r["door_dir_up"], r["door_up_events"]))
    P("After the turn: a second visit of the door square with a direction that is not up: %d of %d; state $44 (enters the house) exactly once: %d of %d; home again: %d of %d" % (
        r["up_then_second_visit"], r["up_episodes"], r["up_then_s44"], r["up_episodes"], r["up_then_home"], r["up_episodes"]))
    P("  frames from the turn to state $44: min %d, max %d" % (min(r["up_journey"]), max(r["up_journey"])))
    P("All eaten ghosts: state $44 reached %d of %d, home again %d of %d; direction at state $44: %s" % (r["all_s44"], r["episodes"], r["all_home"], r["episodes"], ", ".join("%d: %d" % kv for kv in sorted(r["s44_dirs"].items()))))
    P("Eaten ghosts that did not take the path (direction when eaten): %s" % ", ".join("ghost %d dir %d: %d" % (k[0], k[1], v) for k, v in sorted(r["not_up_eaten"].items())))
    return L, r


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        args = [a for a in args if a != out]
    L, r = report(args[0])
    txt = "\n".join(L) + "\n"
    if out:
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
