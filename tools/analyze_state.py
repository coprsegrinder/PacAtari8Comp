"""Stage 65 (state management): the evidence and the chapter docs/43-state-management.md, from the two experiments on the concrete 6502 (tools/state_probe.py: which bytes influence the future; tools/state_events.py: what each event
resets, keeps and computes), the names of docs/25, the structures and lifetimes of docs/30, and the curated text of this file.
Usage: python -I tools/analyze_state.py [--write analysis/evidence-state-summary.txt] [--doc docs/43-state-management.md]"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def names():
    """address -> name (with the index of an array) from docs/25"""
    out = {}
    for m in re.finditer(r"^\| `\$([0-9A-F]{2})(?:-\$([0-9A-F]{2}))?` \| ([A-Za-z0-9_]+)\*? \| (\d+) \|", read("docs/25-variable-catalogue.md"), re.M):
        a = int(m.group(1), 16)
        n = int(m.group(4))
        for k in range(n):
            out[a + k] = m.group(3) + ("[%d]" % k if n > 1 else "")
    return out


def structures():
    """address -> (structure, lifetime) from docs/30 section 3"""
    t = read("docs/30-structures.md")
    sec = t[t.index("## 3. The structures"):t.index("## 4.")]
    out = {}
    cur = None
    for ln in sec.splitlines():
        m = re.match(r"^### (\w+)", ln)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"^\| ([a-z_0-9\[\]\.]+) \| [^|]+ \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ", ln)
        if m and cur:
            life = m.group(4).strip()
            for lo, hi in re.findall(r"\$([0-9A-F]{2})(?:-\$([0-9A-F]{2}))?", m.group(3)):
                lo_i = int(lo, 16)
                hi_i = int(hi, 16) if hi else lo_i
                for x in range(lo_i, hi_i + 1):
                    out[x] = (cur, life)
    return out


def sensitivity():
    d = json.load(open(os.path.join(ROOT, "analysis", "raw-logs", "state-probe.json")))
    res = {int(k): v for k, v in d["result"].items()}
    extra = os.path.join(ROOT, "analysis", "raw-logs", "state-probe-extra.json")
    n_extra = [0, 0]
    if os.path.isfile(extra):
        e = json.load(open(extra))
        for k, v in e["result"].items():
            n_extra[0] += 1
            if v:
                if not res.get(int(k)):
                    n_extra[1] += 1                          # a byte the main run did not show as state
                res[int(k)] = v if not res.get(int(k)) else res[int(k)] + v
    return res, d, n_extra


def ranges(addrs):
    addrs = sorted(addrs)
    out = []
    for a in addrs:
        if out and a == out[-1][1] + 1:
            out[-1][1] = a
        else:
            out.append([a, a])
    return ", ".join("$%02X" % lo if lo == hi else "$%02X-$%02X" % (lo, hi) for lo, hi in out)


PLAYER_BYTES = {0: [0x2C, 0x2E, 0x30, 0x32, 0x34, 0x36, 0x43], 1: [0x2D, 0x2F, 0x31, 0x33, 0x35, 0x37, 0x44]}

# why a byte is not state although docs/30 gives it a lifetime, or is state although docs/30 calls it temporary (curated; checked against the experiment)
EXPLAIN = OrderedDict([
    ("ScoreAdd (`$94-$99`)", "docs/30 said 'temporary (set before use)'; the experiment says STATE: `AddToScore` adds all six digits and clears them, and the callers set only the digit they need (`$98` for a dot), so **the other five must be zero between uses** - a zero-at-rest invariant, not a temporary (docs/30 now says so)"),
    ("WantVert / WantHoriz (`$D6-$DD`), PacHold (`$A7`)", "docs/30 said board; experiment: no influence - `SteerToTarget` writes the wanted directions before it reads them, `$A7` is set every frame before `MovePacMan`: **temporaries of one call or one frame** (docs/30 now says so)"),
    ("EyesReturning (`$F2`), DeathFreeze (`$EE`)", "no influence in 400 trials: `$F2` is recomputed from the ghost states every frame (`EyesAndHousePerFrame`), `$EE` is set when the death starts"),
    ("OS and the interrupts' inputs (`$10`, `$18`, `$4D-$4F`, `$5E-$61`, `$A0`)", "read by the display-list interrupts, `Start` or the OS, not by the frame handler the experiment runs: **state of the machine, not of the frame** (the colours, the attract timer)"),
    ("The key loop's bytes (`$1E`, `$45`, `$46`)", "read by the main program (`38`, `40`), not by the handler"),
    ("Rare in the sample (`$9E`, `$C1`, `$C2`, `$C5`, `$C8`, `$D4`, `$D5`, `$5A-$5D`)", "docs/30 and the experiment agree once the trials are enough: 1 to 35 of 400 trials show a difference (these bytes matter only in some ghost states or on some frames)"),
])


def build():
    nm, st = names(), structures()
    sens, data, n_extra = sensitivity()
    S = {b for b, v in sens.items() if v}
    modes = {b: sorted({m for m, _, _ in v}) for b, v in sens.items() if v}
    data["extra"] = n_extra
    return nm, st, sens, S, modes, data


def lifetime_table(st, S):
    cnt = Counter()
    for b in range(256):
        if b in st:
            life = st[b][1]
            key = "temporary" if life.startswith("temporary") else ("board" if life.startswith("board") else ("zero at rest" if life.startswith("zero") else life.split()[0]))
            cnt[(key, b in S)] += 1
    L = ["| Lifetime of docs/30 | Bytes | Influence the future | Do not |", "|---|---|---|---|"]
    for k in ("board", "game", "kept", "start-up", "OS", "frame", "zero at rest", "temporary"):
        a, b = cnt[(k, True)], cnt[(k, False)]
        if a + b:
            L.append("| %s | %d | %d | %d |" % (k, a + b, a, b))
    return "\n".join(L)


def structure_table(st, S, nm):
    groups = defaultdict(list)
    for b in range(256):
        if b in S:
            groups[st[b][0] if b in st else "(not in docs/30)"].append(b)
    L = ["| Structure (docs/30) | State bytes | Count |", "|---|---|---|"]
    for g, addrs in sorted(groups.items(), key=lambda kv: (kv[0].startswith("("), kv[0])):
        L.append("| %s | %s | %d |" % (g, ranges(addrs), len(addrs)))
    return "\n".join(L)


def events_tables(st, nm):
    ev = json.load(open(os.path.join(ROOT, "analysis", "raw-logs", "state-events.json")))
    groups_names = sorted({st[b][0] for b in st}) + ["(other)"]
    rows = ["| Event | Case | Trials | Reset to a constant | Kept | Computed |", "|---|---|---|---|---|---|"]
    detail = []
    for name, v in ev.items():
        for lab, g in v["groups"].items():
            rows.append("| `%s` | %s | %d | %d | %d | %d |" % (name, lab, g["trials"], len(g["reset"]), len(g["kept"]), len(g["computed"])))
        detail.append((name, v))
    return "\n".join(rows), ev


def lines_evidence():
    nm, st, sens, S, modes, data = build()
    ev = json.load(open(os.path.join(ROOT, "analysis", "raw-logs", "state-events.json")))
    L = ["State management (stage 65): two experiments on the concrete 6502.",
         "Sensitivity (tools/state_probe.py): %d trials a byte and mode, %d frames each, 4 modes (a game of player 1, of player 2, the title, the frame classes): %d of the 256 zero-page bytes influence the future (outputs or the state after the frames), %d do not" % (data["trials"], data["frames"], len(S), 256 - len(S)),
         "state bytes: " + ranges(S),
         "player 1 on turn only: " + ranges([b for b in PLAYER_BYTES[0] if b in S and not any(m == "play2" for m in modes[b])]) + "; player 2 on turn only: " + ranges([b for b in PLAYER_BYTES[1] if b in S and not any(m == "play1" for m in modes[b])]),
         "", "lifetimes of docs/30 against the experiment:", lifetime_table(st, S), ""]
    L.append("events (tools/state_events.py): per event and case the bytes reset to a constant / kept / computed:")
    for name, v in ev.items():
        for lab, g in v["groups"].items():
            L.append("  %-13s %-44s %4d trials: %3d reset, %3d kept, %3d computed" % (name, lab, g["trials"], len(g["reset"]), len(g["kept"]), len(g["computed"])))
    return L


def name_list(addrs, nm, limit=40):
    out = []
    for a in sorted(addrs):
        out.append("`%s`" % nm.get(a, "$%02X" % a))
    s = ", ".join(out[:limit])
    return s + (" ... (%d in all)" % len(out) if len(out) > limit else "")


def chapter():
    nm, st, sens, S, modes, data = build()
    ev = json.load(open(os.path.join(ROOT, "analysis", "raw-logs", "state-events.json")))
    used = set(nm)
    bg = [b for b in st if st[b][1].startswith(("board", "game"))]
    bg_all, bg_yes = len(bg), sum(1 for b in bg if b in S)
    P = []
    w = P.append
    w("# 43 - State management (stage 65)")
    w("")
    w("GENERATED by `python -I tools/analyze_state.py --write analysis/evidence-state-summary.txt --doc docs/43-state-management.md` from the two experiments of `tools/state_probe.py` and `tools/state_events.py` (the concrete 6502 of `tools/cpu6502.py`), the names of `25`, the structures and lifetimes of `30` and the curated text of the tool; tests: `tests/test_state.py`. The transition rules of the state variables are `34` (stage 58: 68 rules proved against the code); the two players are `19`; the levels `14`; the ghost states `17`, `18`. This chapter is the **state itself**: which bytes are state, which are scratch, what each event does to them, and what a port has to keep.")
    w("")
    w("## 1. The result")
    w("")
    w("- **The state of a running game is %d zero-page bytes** (section 2) **plus the maze, the saved mazes and the score cells**: the experiment changed each of the 256 bytes in a running game, and for %d of them the outputs or the state a few frames later differ; the other %d are scratch, OS shadows, constants of the interrupts, or unused. The catalogue of `25` / `30` is right about the structures: of the bytes it calls board or game, %d of %d influence the future (all the game bytes), and every one of its temporaries does not (after the corrections of section 3)." % (len(S), len(S), 256 - len(S), bg_yes, bg_all))
    w("- **The disagreements with `30` are findings** (section 3): the six `ScoreAdd` digits are not temporaries but **zero-at-rest** state (the callers set only one digit and `AddToScore` adds all six); `WantVert`, `WantHoriz` and `PacHold` are temporaries of one call, not board state; and the bytes only the display-list interrupts, the key loop and `Start` read do not show in a frame experiment.")
    ib = len(ev["InitBoard"]["groups"]["player 1 on turn"]["reset"])
    rs = len(ev["restart"]["groups"]["player 1 on turn"]["reset"])
    tn = [g for lab, g in ev["turn control"]["groups"].items() if lab.startswith("next board")][0]
    w("- **Each state-management event has a measured effect** (section 4): `InitBoard` resets %d bytes to constants (every board and every turn), the restart of a game %d, `NewBoardInit` and `ClearPlayerCounters` only the player's counters, a turn hand-over only the stage of the switch; the table gives every case." % (ib, rs))
    w("- **The two players are two copies of seven variables** (section 5): the experiment finds exactly `Lives`, `ExtraLifeFlag`, `Level`, `PelletFlags`, `DotsEaten` (lo, hi) and `BonusCount` of the player **on turn** as state, and the other player's seven as no influence at all while the first plays; the other player's maze lives in `SavedMaze1/2` and nothing else is swapped.")
    w("")
    w("## 2. The state vector")
    w("")
    w("**The experiment** (`tools/state_probe.py`): a game state (a frame of play for player 1, for player 2, a title frame, or one of the frame classes of `38` with its dispatcher variables, entities on junction cells, ghosts in the documented states, Pac-Man on a dot half of the time) is copied; one byte of the zero page is changed in the copy (to 0, a power of two, `$FF`, its complement, its successor, the value of another byte, Pac-Man's X or Y); both copies run the real frame handler for %d frames with the same random numbers and the same clock; every store to an output region and the state at the end (the zero page except the changed byte, the maze screen, the status rows) are compared. A byte for which any trial shows a difference **influences the future**. %d trials a byte and mode; a second run of 400 trials for the %d bytes that the first run left doubtful (%d more showed up as state)." % (data["frames"], data["trials"], data["extra"][0], data["extra"][1]))
    w("")
    w("State bytes by the structures of `30`:")
    w("")
    w(structure_table(st, S, nm))
    w("")
    w("The rest of the machine's state is not in the zero page: **the maze screen** `$0C00-$0F97` (the dots and pellets still on the board: 23 rows of 40), **the other player's maze** `$1000-$13FF` / `$1400-$17FF`, **the score cells** `$202A-$202F` (player 1) and `$2047-$204C` (player 2) and the **high score** `$2039-$203E` in the status rows (`19`, `21`), the bonus item's cells in the maze rows, and the **frozen frame** the player-missile pages show (derived: redrawn from the entity state every frame). Everything else (the tables of `Start`, the original maze, the character sets) is constant after `Start`.")
    w("")
    w("## 3. The experiment against the lifetimes of `30` (and three corrections to it)")
    w("")
    w(lifetime_table(st, S))
    w("")
    w("Where they differ (the byte lists are in `analysis/evidence-state-summary.txt`):")
    w("")
    for k, v in EXPLAIN.items():
        w("- **%s**: %s." % (k, v))
    w("")
    w("## 4. What each event does to the state")
    w("")
    w("`tools/state_events.py` runs the real routine on the concrete 6502 from hundreds of random game states (play frames with the entities where the maze lets them stand) and compares the zero page before and after: a byte with **one** value after whatever it was before is **reset** to that constant, a byte equal before and after in every trial is **kept**, the rest is **computed** (a function of the state, the level, the player on turn or the inputs).")
    w("")
    rows, _ = events_tables(st, nm)
    w(rows)
    w("")
    w("What is reset and what is computed, for the events that matter (the bytes by name):")
    w("")
    for name in ("InitBoard", "restart", "NewGameInit", "NewBoardInit", "AdvanceLevel", "ghost eaten", "power pellet", "add to score"):
        v = ev[name]
        lab = sorted(v["groups"])[0]
        g = v["groups"][lab]
        w("- **%s** (%s): resets %d bytes%s; computes %s." % (name, v["desc"], len(g["reset"]), (" - " + name_list([int(b) for b in g["reset"]], nm, 28)) if len(g["reset"]) <= 40 or name in ("InitBoard", "restart") else "", name_list(g["computed"], nm, 12) or "none"))
    w("")
    w("**The turn control** (`$AA2D`) decides what happens when a life is lost or a board is cleared (`19`, `34`): its cases are the labelled rows of the table: while a hand-over is in progress (`TurnSwitchState` 1 to 4) it keeps the zero page and works on the maze copies and the labels; when the turn ends with the other player next it sets `TurnSwitchState` to 1 or 2 and waits (`$25` = `$30` frames); when the same player continues it calls `InitBoard` (%d bytes reset, as in the table); when both are out it starts the game-over countdown (the high-score comparison, `CountdownActive`, the countdown timer)." % len(tn["reset"]))
    w("")
    w("## 5. Two players")
    w("")
    w("The experiment ran the same game once with player 1 on turn and once with player 2. The bytes that influence the future **only for the player on turn**:")
    w("")
    w("| Player on turn | Bytes | Variables |")
    w("|---|---|---|")
    for p in (0, 1):
        sel = [b for b in PLAYER_BYTES[p] if b in S and not any(m == ("play2" if p == 0 else "play1") for m in modes[b])]
        w("| %d | %s | %s |" % (p + 1, ranges(sel), name_list(sel, nm)))
    w("")
    w("These are `Lives`, `ExtraLifeFlag`, `Level`, `PelletFlags`, `DotsEatenLo`, `DotsEatenHi` and `BonusCount`: the `Player[2]` structure of `30`, found by experiment. **No other zero-page byte is per player**: Pac-Man's position, the ghosts and every timer belong to the board in play, and `InitBoard` clears or refills them at each turn (section 4), so nothing is carried from one player's turn to the other's. What the turn hand-over moves is the **maze**: the leaving player's maze goes to `SavedMaze1` or `SavedMaze2` (`Copy0C00To1000` / `Copy0C00To1400`) and the arriving player's maze comes back to `$0C00` (`$AA94-$AACC`), with the labels 1UP / 2UP redrawn and `CurrentPlayer` toggled; the score digits stay where they are, in the two sets of cells of the status rows.")
    w("")
    w("## 6. The state machines")
    w("")
    w("The top-level machine is `GameState` (`$19`): 1 (copyright set up), 2 (copyright shown), 3 (title menu), 4 (title after a game), 0 (a game or the game-over countdown); START leaves any of them for 0 through the restart, any other console key goes from 0, 1 or 2 to 3 (`41` section 4). **In a game** the machine is the one of `38` (15 frame classes, 25 transitions seen) over these state variables, each with its values and its writers in `34`: `IntroRequest`, `PlayStarted`, `StartTuneActive` (the board start and the start tune), `WaitState` (the READY! wait and the turn handling), `TurnSwitchState`, `LevelComplete` with `LevelEndStep` (the level end), `DeathState` with `PacFrozen`, `DeathAnimActive` (the death), `EatPause` (the eaten-ghost pause), `Paused`, `CountdownActive`, `FrightenPhase` and the four `GhostState`s (the ghost machines of `17`, `18`). The 68 rules of `34` say which write is allowed in which state; this chapter's experiment says which bytes carry the state between frames.")
    w("")
    w("## 7. For the port")
    w("")
    w("- **A save state** is the %d state bytes of section 2 (their addresses are listed), the maze screen (920 bytes), the other player's maze (1,024) if two players, and the score and high-score cells (18 bytes: `$202A-$202F`, `$2039-$203E`, `$2047-$204C`); the picture buffers, the player-missile pages and the colour bands are derived and redrawn. A port may hold the same data in structures (`30` section 7 has the proposal) as long as it keeps the **invariants** the code relies on: the six `ScoreAdd` digits are zero between uses; `MazePtr` (`$80-$81`) points at Pac-Man's cell of the maze screen; `zp_83` / `zp_84` hold the last cell a dot was tested at; `PacDirection` is 1, 2, 4 or 8 (or 0 before the first move) and the wanted direction a subset of the four bits (`41`)." % len(S))
    w("- **Reset at the right moments**: every turn and every board calls `InitBoard` (the %d constants of section 4: the start positions, the timers, the ghost states, the flags); a new game adds the restart's %d (the lives, the level, the counters, the maze copies); a new level adds `AdvanceLevel`'s. A port that rebuilds a struct at those moments and keeps the rest across frames reproduces the game's state management." % (ib, rs))
    w("- **Scratch is free**: the %d bytes that do not influence the future may be locals; but `ScoreAdd` is not scratch." % (256 - len(S)))
    w("")
    w("## 8. Limits")
    w("")
    w("- The experiment is a sensitivity analysis: a byte is called state when a trial shows a difference, so the **state is a lower bound** (a byte that matters only in a rare state may be missed: the doubtful ones were re-run with 400 trials, and %d of %d more showed up); a byte that never showed a difference in thousands of trials with the entities, ghosts and dispatcher in the documented states is scratch in practice." % (data["extra"][1], data["extra"][0]))
    w("- Only the frame handler is run: the bytes read only by the display-list interrupts, the key loop and `Start` (the colours, the attract timer, the key debounce, the countdown timer's reader) are not seen as state, though they are state of the machine; section 3 lists them.")
    w("- The events are run from random states of the stage-55 set-ups with the entities placed where the maze lets them stand; a **restart** from the title (GameState 3 or 4) skips `InitBoard` at `$A48D` and is not the case measured (START in play and from the title menu both come through `$A537`, which sets GameState 0 first).")
    w("- Altirra 4.40 was not needed for this chapter: the experiments are on the concrete 6502; the live sessions of `34` and `38` are the check that the states they visit are the game's.")
    return chr(10).join(P) + chr(10)


def main():
    a = sys.argv
    txt = chr(10).join(lines_evidence()) + chr(10)
    if "--write" in a:
        with open(os.path.join(ROOT, a[a.index("--write") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(txt)
    if "--doc" in a:
        with open(os.path.join(ROOT, a[a.index("--doc") + 1]), "w", encoding="utf-8", newline=chr(10)) as fh:
            fh.write(chapter())
    print(txt)


if __name__ == "__main__":
    main()
