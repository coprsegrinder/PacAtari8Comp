"""Stage J (the Windows 11 front end, docs/67): checks the interactive program `pacman_a8_play` against the headless shell, for each compiler.
Per compiler (gcc, clang): build the whole C port from scratch in build/play/<cc> (strict C99, -Werror); make a scratch main folder with only the owner's ROM; then
  1  `pacman_a8_play --selftest 1200 --exact`: a real window, real key messages posted to it (START, the four directions with arrows and WASD, the pause key twice), the real sound device as the clock;
  2  the replay it recorded, run by the headless `pacman_a8 run --video --audio`, gives the same four digests (state, run, video, audio): the front end adds nothing to the game, the picture and the sound;
  3  the window's own pixels (copied back out of the screen) equal the frame: 0 differing;
  4  the sound device never ran dry (0 underruns) and no picture interval was over 40 ms;
  5  the frame rate over the run is within 0.5 % of the original's 59.923 frames a second (the sound device is the clock);
  6  the pause key was recorded as exactly two presses (CH = $21);
  6b the sound the device really played (captured by WASAPI loopback of this process alone, at a low volume of 0.3 = an amplitude of 0.09) matches the sound handed to it: the loudness curves
     of 10 ms blocks correlate >= 0.95, the device played 98 % or more of the blocks with sound, and its level is 0.9 to 1.1 of what was handed over;
  7  the same with `--no-audio` (the system timer is the clock): the digests equal, the rate within 1 %.
Usage: python -I tools/check_front_end.py [--cc gcc|clang ...] [--write analysis/evidence-front-end-summary.txt]   (Windows only; needs a display and a sound device)"""
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "build", "front-end")
LOG = []


def step(name, ok, detail=""):
    LOG.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""), flush=True)
    return ok


def run(cmd, cwd=ROOT, timeout=900):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def digests(text):
    out = {}
    for k, pat in (("state", r"final state hash: (\w+)"), ("run", r"run digest: (\w+)"), ("video", r"video digest: (\w+)"), ("audio", r"audio digest: (\w+)")):
        m = re.search(pat, text)
        out[k] = m.group(1) if m else "?"
    return out


def pause_presses(replay_path):
    with open(replay_path, "rb") as fh:
        b = fh.read()
    n = int.from_bytes(b[12:16], "little")
    flags = int.from_bytes(b[6:8], "little")
    assert flags == 0
    return sum(1 for i in range(n) if b[20 + 10 * i + 5] == 0x21)


def one(cc):
    d = os.path.join(WORK, cc)
    if os.path.exists(d):
        shutil.rmtree(d, onexc=lambda f, pth, e: (os.chmod(pth, 0o666), f(pth)))    # the copy of the ROM is read-only, like the original
    os.makedirs(d)
    build = os.path.join(d, "build")
    r = run(["cmake", "-S", "src/c", "-B", build, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc, "-DCMAKE_BUILD_TYPE=Release"])
    r2 = run(["cmake", "--build", build], timeout=1800)
    warn = len(re.findall(r"warning|error", r2.stdout + r2.stderr, re.I))
    play = os.path.join(build, "platform", "win32", "pacman_a8_play.exe")
    head = os.path.join(build, "shell", "pacman_a8.exe")
    if not step("%s: build everything (strict C99, -Werror): pacman_a8_play and pacman_a8" % cc, r.returncode == 0 and r2.returncode == 0 and warn == 0 and os.path.exists(play), "%d warnings or errors" % warn):
        return
    # Windows keeps the mute and the volume of a program in its volume mixer BY PROGRAM NAME: a player who muted the game must not disable the test, and the test must not change the player's mixer.
    # So the test runs a byte-identical copy under a name of its own.
    shutil.copy2(play, os.path.join(os.path.dirname(play), "pacman_a8_selftest.exe"))
    play = os.path.join(os.path.dirname(play), "pacman_a8_selftest.exe")
    root = os.path.join(d, "root")
    os.makedirs(os.path.join(root, "original"))
    shutil.copy2(os.path.join(ROOT, "original", "Pac-Man.rom"), os.path.join(root, "original", "Pac-Man.rom"))
    for label, extra, tol in (("sound device is the clock", [], 0.5), ("system timer is the clock", ["--no-audio"], 1.0)):
        if os.path.exists(os.path.join(root, "logs")):
            shutil.rmtree(os.path.join(root, "logs"))
        t = time.time()
        r = run([play, "--root", root, "--selftest", "1200", "--exact", "--seed", "12345", "--record", "logs/self.pmrp", "--ppm", "logs/last.ppm"] + extra)
        rep = os.path.join(root, "logs", "selftest.txt")
        text = open(rep, encoding="utf-8").read() if os.path.exists(rep) else ""
        step("%s, %s: 1,200 frames of a real window with real key messages" % (cc, label), r.returncode == 0 and "frames run: 1200" in text, "%.1f s" % (time.time() - t))
        h = run([head, "run", "logs/self.pmrp", "--video", "--audio", "--root", root])
        a, b = digests(text), digests(h.stdout)
        step("%s, %s: the recorded game run headless gives the same state, run, video and audio digests" % (cc, label), a == b and "?" not in a.values(), "%s" % a["run"])
        if not extra:
            m = re.search(r"window pixels differing from the frame: (\d+) of (\d+)", text)
            step("%s: the window's own pixels equal the frame" % cc, bool(m) and m.group(1) == "0", "%s of %s differ" % (m.group(1), m.group(2)) if m else "no result")
            m = re.search(r"underruns: (\d+)", text)
            late = re.search(r"over 40 ms: (\d+)", text)
            step("%s: the sound device never ran dry and no picture gap passed 40 ms" % cc, bool(m) and m.group(1) == "0" and bool(late) and late.group(1) == "0", "underruns %s, gaps %s" % (m.group(1) if m else "?", late.group(1) if late else "?"))
        m = re.search(r"\(([\d.]+) frames/s", text)
        fps = float(m.group(1)) if m else 0.0
        step("%s, %s: the frame rate is within %.1f %% of 59.923" % (cc, label, tol), abs(fps - 59.9227) / 59.9227 * 100 <= tol, "%.3f frames/s" % fps)
        if not extra:
            step("%s: the pause key was recorded as exactly two presses" % cc, pause_presses(os.path.join(root, "logs", "self.pmrp")) == 2)
            shl = os.path.join(root, "logs", "shell.log")
            muted = os.path.exists(shl) and "muted in the Windows volume mixer" in open(shl, encoding="utf-8").read()
            sc = re.search(r"loopback: scope: (.*)", text)
            g = re.search(r"game handed over [\d.]+ s, (\d+) blocks.*device played (\d+) such", text)
            m = re.search(r"correlation ([\d.-]+) at a delay of (\d+) ms, level ratio [\d.]+ .*played ([\d.]+) of what", text)
            ok = bool(sc) and sc.group(1) == "this process only" and bool(g) and bool(m) and not muted
            if ok:
                ok = float(m.group(1)) >= 0.95 and int(g.group(2)) >= 0.98 * int(g.group(1)) and 0.9 <= float(m.group(3)) <= 1.1
            detail = ("this program is muted in the Windows volume mixer: unmute it there" if muted else
                      "%s; correlation %s at %s ms, %s of %s blocks played, level %s" % (sc.group(1) if sc else "?", m.group(1) if m else "?", m.group(2) if m else "?", g.group(2) if g else "?", g.group(1) if g else "?", m.group(3) if m else "?"))
            step("%s: the sound the device played (loopback capture) matches the sound handed to it" % cc, ok, detail)


def main():
    a = sys.argv[1:]
    ccs = [a[i + 1] for i, x in enumerate(a) if x == "--cc"] or ["gcc", "clang"]
    write = a[a.index("--write") + 1] if "--write" in a else None
    t0 = time.time()
    for cc in ccs:
        one(cc)
    ok = all(x[1] for x in LOG)
    text = "\n".join("%s  %s%s" % ("PASS" if x[1] else "FAIL", x[0], ("  (" + x[2] + ")") if x[2] else "") for x in LOG) + "\n%s: %d steps, %d failed, %.0f s\n" % ("ALL PASSED" if ok else "FAILURES", len(LOG), sum(1 for x in LOG if not x[1]), time.time() - t0)
    print(text)
    if write:
        with open(os.path.join(ROOT, write), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("Stage J (docs/67-windows-front-end.md): the interactive front end checked against the headless shell (tools/check_front_end.py), 2026-11-24\n\n" + text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
