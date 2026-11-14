"""Runs the sound session of tools/altirra_sound_levels.cmd at many levels and dot counts and audits every trace (OPEN-VERIFICATION.md OV-11, OV-12).  Usage:
  python -I tools/run_sound_levels.py [name ...]      (default: all configurations)    ->  analysis/raw-logs/sound-level-<name>.txt, analysis/sound-levels/<name>.txt, analysis/evidence-sound-levels-summary.txt
Each configuration: a level counter poked at $ADFD (hex, or "natural" = the game's own StartLevel) and/or a number of OPTION presses at the title (the real StartLevel path).
Sequential (run_patrol_trace.ps1 uses one shared batch file).  Takes up to 3 minutes per configuration (the speed of the emulator varies with the machine load).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIGS = [
    ("L0", "db($1b)", 0), ("L1", "$01", 0), ("L4", "$04", 0), ("L8", "$08", 0), ("L12", "$0C", 0), ("L13", "$0D", 0), ("L18", "$12", 0), ("L19", "$13", 0), ("L20", "$14", 0),
    ("L40", "$28", 0), ("L70", "$46", 0), ("L100", "$64", 0), ("L254", "$FE", 0), ("L255", "$FF", 0),
    ("S4", "db($1b)", 3), ("S12", "db($1b)", 7),          # 3 / 7 OPTION presses: StartLevel 4 / 12 through the game's own menu
]


def audit(name):
    out_dir = os.path.join(ROOT, "analysis", "sound-levels")
    os.makedirs(out_dir, exist_ok=True)
    log = os.path.join("analysis", "raw-logs", "sound-level-%s.txt" % name)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "analyze_sound_events.py"), os.path.join(ROOT, log), "--lenient", "--summary-file", os.path.join(out_dir, name + ".txt")], capture_output=True, text=True, cwd=ROOT)
    return r.stdout, r.returncode


def episodes(name):
    """Length in game frames (frames with the ghost-eaten sound running not counted) of every run of FrightenPhase <> 0 in the trace."""
    sys.path.insert(0, HERE)
    import analyze_sound_events as A
    W, FR, EV = A.parse(os.path.join(ROOT, "analysis", "raw-logs", "sound-level-%s.txt" % name))
    fs = sorted(FR)
    runs, cur, n = [], False, 0
    for f in fs:
        if FR[f]["fc"] > 0:
            cur = True
            if FR[f]["e5"] == 0:
                n += 1
        elif cur:
            runs.append(n)
            cur, n = False, 0
    return runs


def run(name, level, opts):
    tpl = open(os.path.join(HERE, "altirra_sound_levels.cmd"), encoding="utf-8").read()
    cmd = "_sl_%s.cmd" % name
    open(os.path.join(HERE, cmd), "w", encoding="utf-8").write(tpl.replace("@@LEVEL@@", level).replace("@@OPTS@@", str(opts)))
    log = os.path.join("analysis", "raw-logs", "sound-level-%s.txt" % name)
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join("tools", "run_patrol_trace.ps1"), "-Log", log, "-Seconds", "170", "-Cmd", cmd],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    finally:
        try:
            os.remove(os.path.join(HERE, cmd))
        except OSError:
            pass
    out_dir = os.path.join(ROOT, "analysis", "sound-levels")
    os.makedirs(out_dir, exist_ok=True)
    summ = os.path.join(out_dir, name + ".txt")
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "analyze_sound_events.py"), os.path.join(ROOT, log), "--lenient", "--summary-file", summ], capture_output=True, text=True, cwd=ROOT)
    return r.stdout, r.returncode


def digest(text):
    g = lambda pat, d="-": (re.search(pat, text) or [None, d])[1] if re.search(pat, text) else d
    frames = g(r"\((f=\d+\.\.\d+)\)")
    ev = g(r"Events: (\{.*\})")
    tune = re.search(r"game 1: 64 steps from f=(\d+).*level counter (\d+), StartLevel (\w+)", text)
    siren = re.search(r"siren: (\d+) calls.*\((\d+) mismatches\); steps seen (\{.*\})", text)
    frt = re.search(r"frightened: (\d+) calls in (\d+) episodes.*\((\d+) mismatches\)", text)
    eyes = re.search(r"eyes: (\d+) calls.*\((\d+) mismatches\)", text)
    ghosts = len(re.findall(r"ok   ghost eaten at", text))
    ghosts_bad = len(re.findall(r"FAIL ghost eaten at", text))
    bonus = len(re.findall(r"ok   episode f=", text))
    bonus_bad = len(re.findall(r"FAIL episode f=", text))
    prob = "none" if re.search(r"PROBLEMS: none", text) else "SEE FILE"
    return dict(frames=frames, tune=("%s lv %s sl %s" % (tune.group(1), tune.group(2), tune.group(3))) if tune else "no tune", siren=("%s calls, %s mism., steps %s" % siren.groups()) if siren else "-",
                frightened=("%s calls/%s ep./%s mism." % frt.groups()) if frt else "-", eyes=("%s calls/%s mism." % eyes.groups()) if eyes else "-", ghosts="%d ok %d bad" % (ghosts, ghosts_bad), bonus="%d ok %d bad" % (bonus, bonus_bad), problems=prob, events=ev)


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    audit_only = "--audit-only" in sys.argv
    todo = [c for c in CONFIGS if not names or c[0] in names]
    rows = []
    for (name, level, opts) in todo:
        print("running", name, level, opts, flush=True)
        text, rc = audit(name) if audit_only else run(name, level, opts)
        d = digest(text)
        try:
            ep = sorted(episodes(name))
            d["episodes"] = "frightened game frames per pellet (runs of FrightenPhase <> 0, sweep frames excluded): n=%d min %d median %d max %d" % (len(ep), ep[0], ep[len(ep) // 2], ep[-1]) if ep else "no frightened run"
        except Exception as e:                                  # noqa: BLE001
            d["episodes"] = "episodes: %s" % e
        d["name"], d["level"], d["opts"], d["rc"] = name, level, opts, rc
        rows.append(d)
        print("  ->", d["problems"], d["tune"], d["siren"], flush=True)
    lines = ["Sound session at other levels and dot counts (tools/run_sound_levels.py, tools/altirra_sound_levels.cmd, analysis/sound-levels/<name>.txt per run)", ""]
    for d in rows:
        lines.append("%-5s level poke %-9s OPTION presses %d | trace %s | PROBLEMS %s" % (d["name"], d["level"], d["opts"], d["frames"], d["problems"]))
        lines.append("      start tune: %s | siren: %s" % (d["tune"], d["siren"]))
        lines.append("      frightened: %s | eyes: %s | ghost eaten: %s | bonus: %s" % (d["frightened"], d["eyes"], d["ghosts"], d["bonus"]))
        lines.append("      %s" % d["episodes"])
        lines.append("      events: %s" % d["events"])
    if not names or audit_only:
        with open(os.path.join(ROOT, "analysis", "evidence-sound-levels-summary.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if all(d["problems"] == "none" for d in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
