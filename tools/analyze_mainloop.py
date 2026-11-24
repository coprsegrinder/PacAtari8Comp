"""Stage 62 (main loop): the frame by frame record of the real game, from the logs of tools/run_mainloop_audit.ps1.

Each frame of the deferred vertical-blank handler is classified by the decisions of FrameDispatch ($A6CC-$A82C, in the order of the code), the sequence of classes is the 'frame by frame story' of a session, and the scan lines the handler needs
(entry $A5FD, return of FrameDispatch $A606, exit $A60D) show how much of the frame the game's own interrupt code uses.
Usage: python -I tools/analyze_mainloop.py analysis/raw-logs/mainloop-*.txt [--write analysis/evidence-mainloop-summary.txt] [--doc docs/38-main-loop.md]"""
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "analysis", "evidence-mainloop-summary.txt")
from video import LINES                          # scan lines per frame: 262 (NTSC) or 312 with PACMAN_VIDEO=pal (OV-62)
VB = re.compile(r"^VB f=(\d+) vp=(\d+) gs=(\d+) v1c=(\d+) v20=(\d+) v21=(\d+) v22=(\d+) v23=(\d+) v24=(\d+) v26=(\d+) v27=(\d+) e5=(\d+) ed=(\d+) p9b=(\d+) a3=(\d+) cnt=(\d+)(?: hp=(\d+))?")
XV = re.compile(r"^(VF|VX) f=(\d+) vp=(\d+)(?: hp=(\d+))?")
FIELDS = ["f", "vp", "gs", "v1c", "v20", "v21", "v22", "v23", "v24", "v26", "v27", "e5", "ed", "p9b", "a3", "cnt"]

# the classes, in the order of the dispatcher's decisions: (name, what the code does)
CLASSES = [
    ("copyright setup", "GameState 1: `InitDisplay2`, clear `$1C00/$1D00/$0F00`, copyright text and logo, GameState := 2 (`$A6D7-$A70A`)"),
    ("copyright wait", "GameState 2: wait for the jiffy clock to change from `$1D`, then GameState := 3 (`$A70D-$A717`)"),
    ("title menu", "GameState 3: the title text, player count, start level (`$A719-$A78B`), every frame"),
    ("title after game", "GameState 4: the same screen as after a game (`$A719-$A78B`)"),
    ("paused", "GameState 0, `Paused` set: `ClearPokeyRegisters` and return (`$A798-$A79C`)"),
    ("board start", "GameState 0, `IntroRequest` = 2: `StartTuneActive` := 1, `DrawLevelIndicator` (`$A7C8`), one frame"),
    ("game-over countdown", "GameState 0, `CountdownActive` set: the labels are redrawn (`$A7AA-$A7B5`)"),
    ("level end", "GameState 0, `LevelComplete` set: the level-end sequence `$AC18-$AC92` (draw, wait, flash, new board)"),
    ("start idle", "GameState 0, play not started and no start tune: return (`$A7C3-$A7C7`)"),
    ("start tune", "GameState 0, `StartTuneActive`: the intro tune stepped every 4th jiffy, `DrawReadyScreen` at step `$28`, play starts at `$40` (`$A7D3-$A800`)"),
    ("turn control", "GameState 0, `WaitState` = 1: `TurnControl` (`$A80D`)"),
    ("ready wait", "GameState 0, `WaitState` = 2: the READY! pause counted down in `$25` (`$A81F-$A82A`)"),
    ("death", "GameState 0, `DeathState` set: `DeathSequence`, `DeathAnimation` (`$A833-$A836`)"),
    ("eaten pause", "GameState 0, `EatPause` set: `GhostEatenPause` (`$A840`)"),
    ("play", "GameState 0, the play frame: the order of `24-function-relationships.md` section 4.3"),
]


def classify(r):
    gs = r["gs"]
    if gs == 1:
        return "copyright setup"
    if gs == 2:
        return "copyright wait"
    if gs == 3:
        return "title menu"
    if gs >= 4:
        return "title after game"
    if r["p9b"]:
        return "paused"
    if r["v1c"] == 2:
        return "board start"
    if r["v20"]:
        return "game-over countdown"
    if r["v26"]:
        return "level end"
    if not r["v21"]:
        return "start tune" if r["v22"] else "start idle"
    if r["v24"] == 1:
        return "turn control"
    if r["v24"] >= 2:
        return "ready wait"
    if r["ed"]:
        return "death"
    if r["e5"]:
        return "eaten pause"
    return "play"


def parse(path):
    """-> list of frame records (dict with the VB fields, 'class', 'vf' (FrameDispatch return) and 'vx' (exit) as absolute scan lines from the entry)"""
    out = []
    cur = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for ln in fh:
            if not ln.endswith(chr(10)):
                continue
            if ln.startswith("VB "):
                m = VB.match(ln)
                if not m:
                    continue
                r = dict(zip(FIELDS, [int(x) for x in m.groups()[:16]]))
                r["hp"] = int(m.group(17)) if m.group(17) else None      # the cycle in the line (logs of -Cycles, OV-63)
                r["class"] = classify(r)
                r["vf"] = r["vx"] = r["vfc"] = r["vxc"] = None
                out.append(r)
                cur = r
                continue
            if cur is not None and (ln.startswith("VF ") or ln.startswith("VX ")):
                m = XV.match(ln)
                if not m:
                    continue
                el = (int(m.group(2)) - cur["f"]) * LINES + int(m.group(3)) - cur["vp"]
                elc = el * 114 + int(m.group(4)) - cur["hp"] if m.group(4) and cur["hp"] is not None else None   # cycles
                if m.group(1) == "VF" and cur["vf"] is None:
                    cur["vf"], cur["vfc"] = el, elc
                elif m.group(1) == "VX" and cur["vx"] is None:
                    cur["vx"], cur["vxc"] = el, elc
    return out


def runs(frames):
    """consecutive frames of the same class -> [(class, first frame, length)]"""
    out = []
    for r in frames:
        if out and out[-1][0] == r["class"] and r["f"] == out[-1][1] + out[-1][2]:
            out[-1][2] += 1
        else:
            out.append([r["class"], r["f"], 1])
    return out


def gather(paths):
    S = {"cyc": defaultdict(list), "margin": [], "sessions": {}, "frames": 0, "gaps": 0, "overrun": 0, "by_class": defaultdict(lambda: {"n": 0, "vf": [], "vx": []}), "trans": Counter(), "runs": defaultdict(list), "first_runs": {}}
    for p in paths:
        name = re.sub(r"^(pal)?mainloop-|\.txt$", "", os.path.basename(p))
        fr = parse(p)
        fr = [r for r in fr if r["f"] > 36]                    # the first frames: the OS boot, before Start installs the handler
        S["sessions"][name] = len(fr)
        for i, r in enumerate(fr):
            if r["vxc"] is not None:
                S["cyc"][r["class"]].append(r["vxc"])
                if i + 1 < len(fr) and fr[i + 1]["f"] == r["f"] + 1 and fr[i + 1]["hp"] is not None:
                    nxt = (fr[i + 1]["f"] * LINES + fr[i + 1]["vp"]) * 114 + fr[i + 1]["hp"]
                    S["margin"].append(nxt - ((r["f"] * LINES + r["vp"]) * 114 + r["hp"] + r["vxc"]))
        for i, r in enumerate(fr):
            S["frames"] += 1
            c = S["by_class"][r["class"]]
            c["n"] += 1
            if r["vf"] is not None:
                c["vf"].append(r["vf"])
            if r["vx"] is not None:
                c["vx"].append(r["vx"])
            if i + 1 < len(fr):
                if fr[i + 1]["f"] != r["f"] + 1:
                    S["gaps"] += 1
                else:
                    S["trans"][(r["class"], fr[i + 1]["class"])] += 1
                if r["vx"] is not None and fr[i + 1]["f"] * LINES + fr[i + 1]["vp"] < r["f"] * LINES + r["vp"] + r["vx"]:
                    S["overrun"] += 1
        rr = runs(fr)
        for cls, f0, n in rr:
            S["runs"][cls].append(n)
        S["first_runs"][name] = rr
    return S


def stat(v):
    return (min(v), int(statistics.median(v)), max(v)) if v else (0, 0, 0)


def summary_lines(paths):
    S = gather(paths)
    L = []
    P = L.append
    P("Main-loop audit (tools/run_mainloop_audit.ps1, tools/analyze_mainloop.py): %d sessions (%s), %d frames of the deferred vertical-blank handler" % (len(S["sessions"]), ", ".join("%s %d" % kv for kv in sorted(S["sessions"].items())), S["frames"]))
    P("frames in a row (no handler entry missed): gaps %d; handler still running when the next entry came: %d" % (S["gaps"], S["overrun"]))
    P("")
    P("class | frames | FrameDispatch scan lines min/median/max | handler (to XITVBV) min/median/max | run length (frames) min/median/max")
    for name, _ in CLASSES:
        c = S["by_class"].get(name)
        if not c or not c["n"]:
            P("%-20s %7d" % (name, 0))
            continue
        P("%-20s %7d | %3d / %3d / %3d | %3d / %3d / %3d | %5d / %5d / %5d  (%d runs)" % ((name, c["n"]) + stat(c["vf"]) + stat(c["vx"]) + stat(S["runs"][name]) + (len(S["runs"][name]),)))
    P("")
    if S["margin"]:
        P("cycles (logs of -Cycles, OV-63): handler entry to the XITVBV jump, per class min/median/max, and the cycles left to the next entry (%d cycles per frame)" % (LINES * 114))
        for name, _ in CLASSES:
            if S["cyc"].get(name):
                P("%-20s %7d | %6d / %6d / %6d" % ((name, len(S["cyc"][name])) + stat(S["cyc"][name])))
        P("margin to the next handler entry: min %d, median %d cycles (%d frames); the least is %.1f%% of a frame" % (min(S["margin"]), statistics.median(S["margin"]), len(S["margin"]), 100.0 * min(S["margin"]) / (LINES * 114)))
        P("")
    P("transitions between classes (frames):")
    for (a, b), n in sorted(S["trans"].items(), key=lambda kv: (-kv[1], kv[0])):
        if a != b:
            P("  %-20s -> %-20s %6d" % (a, b, n))
    P("")
    P("the first session as runs (class, frames):")
    first = S["first_runs"].get("fullgame") or next(iter(S["first_runs"].values()))
    P("  " + "; ".join("%s %d" % (c, n) for c, f0, n in first[:60]))
    return L, S


def doc_lines(paths):
    L0, S = summary_lines(paths)
    out = []
    P = out.append
    bc = S["by_class"]
    allvx = [x for c in bc.values() for x in c["vx"]]
    play = bc["play"]
    worst = sorted(((max(c["vx"]), n) for n, c in bc.items() if c["vx"]), reverse=True)[:3]
    P("# 38 - The Main Loop, frame by frame (stage 62)")
    P("")
    P("GENERATED by `python -I tools/analyze_mainloop.py analysis/raw-logs/mainloop-*.txt --doc docs/38-main-loop.md` from the logs of `tools/run_mainloop_audit.ps1` (7 sessions of the real game, NTSC) and the code of `src/asm/pacman.s`; evidence: `analysis/evidence-mainloop-summary.txt`. Tests: `tests/test_mainloop.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- **The program is two programs.** The **main program** is the key loop `$A4BA-$A559` of `Start`: it never returns and does no game logic; it reads the keys and the console and refreshes four colour bytes. **Everything else runs in interrupts**: the deferred vertical-blank handler `$A5FD` once per frame (all game logic, one call of `FrameDispatch`), and two display-list interrupt handlers (colour bands). The main program changes the game only through five keys: START / trigger (new game, `$A537`), SELECT, OPTION, the space bar (pause) and the end of the game-over countdown.")
    P("- **Every frame has one of %d classes**, fixed by the dispatcher's tests in the order of the code (section 4); all %d frames of the %d sessions fall in them, and only %d different class-to-class transitions occur (section 5)." % (len(CLASSES), S["frames"], len(S["sessions"]), len([1 for (a, b) in S["trans"] if a != b])))
    P("- **The handler never runs late**: in %d consecutive frames no handler entry was missed and the handler was never still running when the next one came (`$A5FD` to `JMP XITVBV`). A play frame takes a median of %d scan lines (max %d) of the %d of a frame; the heaviest frames are %s; the smallest margin is **%d scan lines** (%d%% of a frame)." % (S["frames"], stat(play["vx"])[1], stat(play["vx"])[2], LINES, ", ".join("%s (%d lines)" % (n, m) for m, n in worst), LINES - max(allvx), round(100.0 * (LINES - max(allvx)) / LINES)))
    P("- **The frame by frame story** of a game is a short sequence of classes with fixed lengths (section 6): copyright 247 frames, title menu until START, the start tune 260 frames, then play; a death is 354 frames, the READY! wait 65, an eaten ghost's pause 33, the level end 187, the game-over countdown up to 1,800 (30 s).")
    P("")
    P("## 2. The programs and when they run")
    P("")
    P("| Program | Entry | Runs | What it does |")
    P("|---|---|---|---|")
    P("| main program (key loop) | `$A4BA` (from `Start`, `$A4B6`, `$A537`) | all the time the interrupts leave free, never returns | colour refresh, keys, console, pause, game-over countdown end |")
    P("| deferred vertical-blank handler | `$A5FD`, installed by `SETVBV` at `$A460`, called by the OS after its own vertical-blank work | once per frame (it is entered at line 256 of NTSC's 262 in every frame seen: the vertical blank starts at line 248 and the OS's own work comes first) | clears the band counter `$18`, counts the debounce `$45` down, `FrameDispatch`, the tunnel clip unless the eaten-ghost pause is on, `JMP XITVBV` |")
    P("| display-list interrupt 1 | `$A573` (`VDSLST`) | 5 per frame on the game screen (lines 39, 47, 207, 215, 231) | colours of the next band, `CHBASE` (`35`) |")
    P("| display-list interrupt 2 | `$A5CE` | 5 per frame on the title screen | the same for the title |")
    P("")
    P("The main program and the handler share variables; the only handshakes are the debounce counter `$45` (the main program sets it to 1 and waits for the handler to count it to 0, `$A50D-$A516`) and the clock byte `RTCLOK2`.")
    P("")
    P("## 3. The key loop, pass by pass")
    P("")
    P("```")
    P("$A4BA  for X = 3..0:  DliColors[X] = (ColorsDli[X] xor COLRSH) and DRKMSK          ($A4BC-$A4C6)")
    P("$A4C8  if GameState != 0 goto $A4F5                                                  title / copyright states")
    P("$A4CC  (a game is running)  if $02F1 == 0 and CH == $21 (space): Paused ^= 1; CH = $FF  ($A4CC-$A4E6)")
    P("$A4E9  if CountdownActive == 0 goto $A504")
    P("        if CountdownTimer != 0 goto $A4F5")
    P("        GameState = 4; ATRACT = 4; goto $A4BA                                         the 30 s countdown is over: back to the title ($A4F1, $A552)")
    P("$A4F5  CH = $FF;  if STRIG0 == 0 or STRIG1 == 0 goto $A537                           trigger starts a game ($A4FA-$A502)")
    P("$A504  c = CONSOL;  if c == 7 goto $A4BA                                             no console key")
    P("        $46 = c; $45 = 1; repeat c |= CONSOL until the handler has counted $45 to 0;  if c != $46 goto $A504   debounce ($A50B-$A51A)")
    P("$A51C  wait while CONSOL == c                                                         wait for the key to be released")
    P("        $46 == 6 (START)                      -> goto $A537")
    P("        GameState < 3 (copyright)             -> GameState = 3; ATRACT = 3           any other console key skips the copyright screen ($A550)")
    P("        $46 == 3 (OPTION)                     -> StartLevel: 0 -> 1 -> 2 -> 4 -> 6 -> 8 -> 10 -> 12 -> 0 ($A559-$A56D); GameState = 3")
    P("        $46 == 5 (SELECT)                     -> TwoPlayers ^= 1 ($A544); GameState = 3")
    P("        other values (two keys)               -> goto $A4BA")
    P("$A537  CountdownActive = 0; GameState = 0; IntroRequest = 1; goto $A477             new game: the restart clears $20-$3F, copies the maze, ... (`37`, `21`)")
    P("```")
    P("")
    P("Every outcome of every conditional branch of this loop was run in the real game (47 of 54; the other 7 cannot happen by construction), and a pass costs 111 cycles on a title screen and 114 in a game: `40-key-loop-coverage.md` (OV-65).")
    P("")
    P("The vertical-blank handler (`$A5FD`): `$18` := 0 (the band counter of the display-list interrupts), `$45` -= 1, `FrameDispatch`, `ClipEntitiesOnTunnelRow` unless `EatPause` (`$E5`) is set, `JMP XITVBV`.")
    P("")
    P("## 4. The frame: the dispatcher's decisions in the order of the code, and what each costs")
    P("")
    P("`FrameDispatch` (`$A6CC`) tests in this order; the first class that applies is the frame. Scan lines = from the entry of the handler to the return of `FrameDispatch` (median / max) and to `XITVBV` (max); the sessions are NTSC.")
    P("")
    P("| # | Class | What the code does | Frames seen | Dispatch lines (median / max) | Handler lines (max) |")
    P("|---|---|---|---|---|---|")
    for i, (name, what) in enumerate(CLASSES, 1):
        c = bc.get(name)
        if c and c["n"]:
            P("| %d | %s | %s | %d | %d / %d | %d |" % (i, name, what, c["n"], stat(c["vf"])[1], stat(c["vf"])[2], stat(c["vx"])[2]))
        else:
            P("| %d | %s | %s | 0 | - | - |" % (i, name, what))
    P("")
    P("In state 0 the order is: the countdown byte `$1E` falls every 8th jiffy; **paused** returns first; `BlinkPlayerLabel`; **board start**; **game-over countdown** labels; **level end**; **start idle / start tune**; then `WaitState`: **turn control** (1), **ready wait** (2); then the play frame, in which **death** and the **eaten-ghost pause** come before anything moves and the order of `24-function-relationships.md` section 4.3 follows (Pac-Man first, then the dot, the house, the ghosts from 3 down to 0).")
    P("")
    P("## 5. The frame state machine, as seen")
    P("")
    P("Every change of class between two consecutive frames in the %d sessions (the sessions' own restarts included):" % len(S["sessions"]))
    P("")
    P("| From | To | Times |")
    P("|---|---|---|")
    for (a, b), n in sorted(S["trans"].items(), key=lambda kv: (-kv[1], kv[0])):
        if a != b:
            P("| %s | %s | %d |" % (a, b, n))
    P("")
    P("## 6. The frame by frame story")
    P("")
    P("Length of a stay in each class (frames; the sessions' runs, minimum / median / maximum):")
    P("")
    P("| Class | Runs | Frames per run |")
    P("|---|---|---|")
    for name, _ in CLASSES:
        rr = S["runs"].get(name)
        if rr:
            P("| %s | %d | %d / %d / %d |" % ((name, len(rr)) + stat(rr)))
    P("")
    first = S["first_runs"].get("fullgame") or next(iter(S["first_runs"].values()))
    P("The first session (`fullgame`), from the first handler frame after `Start`: " + "; ".join("%s %d" % (c, n) for c, f0, n in first[:40]) + " ...")
    P("")
    P("Reading it: the copyright screen is 1 frame of setup and 247 of waiting (until the jiffy clock changes, then the menu); a START press gives **start idle** (3 frames: the restart is running in the main program), **board start** (1 frame), the **start tune** (260 frames), then **play**; Pac-Man's death is exactly **354 frames** (freeze, animation, silence), then **turn control** (1 frame) and the **ready wait** (65 frames), then play again; the last death goes to the **game-over countdown** (up to 1,800 frames = 30 s, shorter when a key ends it) and then the **title after the game**.")
    P("")
    P("## 7. The time budget")
    P("")
    P("- The play frame is the long one: a median of %d lines, a maximum of %d (the contacts, the bonus item, Pac-Man and four ghosts moving and drawn). The level end (%d lines at its worst, the board redrawn) and the turn control (%d, the maze copies) are the heaviest single frames; the start tune and the ready wait have one frame of %d lines when the screen is drawn." % (stat(play["vx"])[1], stat(play["vx"])[2], max(bc["level end"]["vx"]), max(bc["turn control"]["vx"]), max(bc["start tune"]["vx"])))
    P("- The handler is entered at line 256 and, on its heaviest frame, ends **%d lines after its entry**: before the next vertical blank (262 lines), with **%d lines to spare**. The main program gets what the handler and the five display-list interrupts leave." % (max(allvx), LINES - max(allvx)))
    P("- **Cycles (OV-63, `analysis/evidence-mainloop-cycles-summary.txt`, `tools/run_mainloop_audit.ps1 -Cycles`):** the same 7 NTSC sessions with the cycle in the line (`hpos`) at the three trace points: 218,392 frame pairs. The heaviest handler run is a level end of **26,729 cycles** (234.5 lines, of 29,868 in a frame), which leaves **3,138 cycles (10.5% of a frame, 27.5 lines)** to the next handler entry; the 100 smallest margins are 61 turn controls and 39 level ends. The line count above was right to a line. The cycles are elapsed machine time from the entry to the `JMP XITVBV`, with the display-list interrupts and ANTIC's DMA inside, not the cycles of the handler's own instructions.")
    P("- **PAL (OV-62, `analysis/evidence-mainloop-pal-summary.txt`, `tools/run_mainloop_audit.ps1 -Video pal`):** the same 7 sessions with `/pal` (312 lines): 184,234 frames, 0 missed entries, 0 frames still running at the next entry, the handler entered at line 256 in every frame, the same 15 classes and the same stays (start tune 258-260 frames, ready wait 65, death 354, eaten pause 33, level end 187, copyright wait 245). The heaviest frame is the level end at **190 lines** (turn control 177, play 65): **122 lines to spare** of 312 (39%), against 28 of 262 in NTSC. The same frames cost fewer lines than in NTSC (level end 190 against 234, turn control 173 against 219, copyright setup 60 against 76), about 45 lines less: the handler starts at line 256, and PAL's vertical blank lasts to line 312 while NTSC's ends at 262, so more of the work falls where the display takes no cycles (a likely cause, not measured).")
    P("- For a port: the original needs less than 90%% of a frame in its worst case and about %d%% in play (%d / %d lines), all of it in one deferred interrupt; a port may run the same sequence once per video frame." % (round(100.0 * stat(play["vx"])[1] / LINES), stat(play["vx"])[1], LINES))
    P("")
    P("## 8. Limits")
    P("")
    P("- The main sessions are NTSC, Altirra 4.40. The same 7 sessions were also run as PAL (`/pal`, 312 lines, section 7); the costs of the first measurement are in scan lines (114 cycles each) at the trace points; the heaviest frames were then measured in cycles (section 7).")
    P("- The sessions run with the test aids of their harnesses (`04`); the frame classes and lengths are the game's own, the bot decides how often a class occurs.")
    P("- Frames before `Start` has installed the handler (the OS boot, frames up to 36) are left out.")
    return out


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--") and a.endswith(".txt") and "evidence" not in a and os.path.isfile(a)]
    L, S = summary_lines(paths)
    txt = chr(10).join(L) + chr(10)
    if "--doc" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--doc") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(chr(10).join(doc_lines(paths)) + chr(10))
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
