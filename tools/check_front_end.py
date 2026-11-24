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
  8  `--menutest` (docs/68): the pause menu and the graphics options driven by real key messages: the game is frozen while a menu is open, both display modes and all 20 resolutions give the layout
     of `display_fit` and the picture the window really shows (read back from the screen: 1.6:1, centred, black around it, nearest pixel), and the game recorded through the menu replays headless to the same digests.
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
    shutil.copytree(os.path.join(ROOT, "third-party", "crt-shaders"), os.path.join(root, "third-party", "crt-shaders"))        # the CRT shaders the program reads (docs/70)
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
    # the pause menu and the graphics options (docs/68): real key messages (ESC, arrows, Enter, F11, Alt+Enter); frozen game; every display mode and resolution; what the window really shows
    if os.path.exists(os.path.join(root, "logs")):
        shutil.rmtree(os.path.join(root, "logs"))
    t = time.time()
    for attempt in (1, 2):
        r = run([play, "--root", root, "--menutest", "--windowed", "--seed", "7"], timeout=300)
        rep = os.path.join(root, "logs", "menutest.txt")
        text = open(rep, encoding="utf-8").read() if os.path.exists(rep) else ""
        if r.returncode == 0 or "NOTE" not in text:
            break
        print("      (the window was minimised by something outside the program during the menu test: once more)", flush=True)       # Windows does this in long runs; the program notes it and restores the window, a measurement it spoiled is made again
    m = re.search(r"RESULT: (\d+) passed, (\d+) failed", text)
    step("%s: the menu test: every check passed (menu keys, frozen game, both display modes, every resolution, F11, Alt+Enter, Quit Game)" % cc,
         r.returncode == 0 and bool(m) and m.group(2) == "0" and int(m.group(1)) >= 95 and "script finished: yes" in text, "%s passed, %s failed, %.0f s" % (m.group(1) if m else "?", m.group(2) if m else "?", time.time() - t))
    frozen = re.findall(r"PASS  game frozen: .*", text)
    step("%s: the game was frozen while the help or a menu was open (frames run and the whole state hash unchanged), three times" % cc, len(frozen) == 3, "%d checks" % len(frozen))
    pics = re.findall(r"^PASS  (?:windowed|fullscreen) \d+x\d+.*aspect 1\.6:1, centred yes, outside the picture 0 pixels not black, inside \d+ of \d+ differ from the centre rule, 0 blended", text, re.M)
    step("%s: all 20 resolutions in both display modes: 1.6:1, centred, black around, nearest pixel (nothing blended)" % cc, len(pics) >= 40, "%d pictures checked" % len(pics))
    fpsl = re.findall(r"^PASS  fps choice \d+ \(-?\d+\): .*", text, re.M)
    cpu = [int(c) for c in re.findall(r"CPU (\d+) % of one core", text)]
    step("%s: every FPS choice (native, 30 to 180, uncapped) measured in the running game: the pictures a second are the number chosen, the game stays at 59.92" % cc, len(fpsl) == 10 and "NOTE" not in text, "%d choices, CPU %d to %d %% of one core" % (len(fpsl), min(cpu) if cpu else 0, max(cpu) if cpu else 0))
    # the game as the player starts it: nothing set; it must start in borderless fullscreen at the monitor's resolution and refresh rate (or the nearest entries of the lists)
    if os.path.exists(os.path.join(root, "logs", "startuptest.txt")):
        os.remove(os.path.join(root, "logs", "startuptest.txt"))
    r2 = run([play, "--root", root, "--startuptest", "--seed", "7"], timeout=120)
    st_path = os.path.join(root, "logs", "startuptest.txt")
    st = open(st_path, encoding="utf-8").read() if os.path.exists(st_path) else ""
    m3 = re.search(r"RESULT: (\d+) passed, (\d+) failed", st)
    step("%s: started with nothing set: borderless fullscreen, the monitor's resolution and refresh rate chosen from the lists (exact or nearest)" % cc, r2.returncode == 0 and bool(m3) and m3.group(2) == "0" and m3.group(1) == "4", "; ".join(re.findall(r"PASS  (?:starts at the monitor.s \w+|starts in borderless fullscreen): (.*)", st))[:260])
    # the game's own logic does not depend on how the picture is made: the same scenario with several FPS choices and CRT shaders, each recorded and replayed headless (the state, run, video and sound digests of the
    # recording equal the replay's), the game at its own speed, the sound not running dry more than the start of a shader makes it
    for label, extra in (("native", ["--fps", "native"]), ("native + guest shader", ["--fps", "native", "--crt", "guest"]), ("60 + zfast shader", ["--fps", "60", "--crt", "zfast"]),
                         ("180", ["--fps", "180"]), ("180 + guest shader", ["--fps", "180", "--crt", "guest"]), ("uncapped + aperture shader", ["--fps", "uncapped", "--crt", "aperture"])):
        t = time.time()
        r5 = run([play, "--root", root, "--windowed", "--selftest", "600", "--seed", "5", "--record", "logs/mx.pmrp"] + extra, timeout=200)
        rp = os.path.join(root, "logs", "selftest.txt")
        tx = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
        h5 = run([head, "run", "logs/mx.pmrp", "--video", "--audio", "--root", root])
        a5, b5 = digests(tx), digests(h5.stdout)
        fps5 = re.search(r"\(([\d.]+) frames/s", tx)
        ur = re.search(r"underruns: (\d+)", tx)
        ok5 = r5.returncode == 0 and "frames run: 600" in tx and a5 == b5 and "?" not in a5.values() and bool(fps5) and 58.0 <= float(fps5.group(1)) <= 61.0 and bool(ur) and int(ur.group(1)) <= 3
        step("%s, %s: the game made through it (600 frames) replays headless to the same digests, at the game's own speed, the sound not running dry" % (cc, label), ok5,
             "%s frames/s, %s underruns, %.0f s" % (fps5.group(1) if fps5 else "?", ur.group(1) if ur else "?", time.time() - t))
    crts = re.findall(r"^PASS  crt shader \d \(.*", text, re.M)
    step("%s: each CRT shader (guest-advanced-ntsc, zfast-crt-composite, aperture) and off, chosen through the menu in the running game: the picture read back from the OpenGL window is lit, differs from the plain picture, no pass failed" % cc, len(crts) == 4, "%d of 4: %s" % (len(crts), "; ".join(re.findall(r"PASS  crt shader \d \((\S+)\): (\d+x\d+) picture from the chain \((\d+) passes\)", text) and ["%s %s %s passes" % t for t in re.findall(r"PASS  crt shader \d \((\S+)\): (\d+x\d+) picture from the chain \((\d+) passes\)", text)])))
    r3 = run([play, "--root", root, "--crttest", "--seed", "7"], timeout=200)
    ct_path = os.path.join(root, "logs", "crttest.txt")
    ct = open(ct_path, encoding="utf-8").read() if os.path.exists(ct_path) else ""
    m4 = re.search(r"RESULT: (\d+) passed, (\d+) failed", ct)
    step("%s: the three CRT shaders on a frame of play at the monitor's resolution, fullscreen: all compiled and linked, every pass ran, the pictures are lit" % cc, r3.returncode == 0 and bool(m4) and m4.group(1) == "3" and m4.group(2) == "0", "; ".join(re.findall(r"PASS  (\S+): (\d+ passes compiled in \d+ ms, picture \d+x\d+)", ct) and ["%s %s" % t for t in re.findall(r"PASS  (\S+): (\d+ passes compiled in \d+ ms, picture \d+x\d+)", ct)]))
    for nm in ("crt-guest-advanced-ntsc", "zfast-crt-composite", "crt-aperture"):                  # the pictures, for the eye
        src_ppm = os.path.join(root, "logs", "crt_%s.ppm" % nm)
        if os.path.exists(src_ppm):
            os.makedirs(os.path.join(WORK, "pictures"), exist_ok=True)
            shutil.copy2(src_ppm, os.path.join(WORK, "pictures", "%s-%s.ppm" % (cc, nm)))
    h = run([head, "run", "logs/menutest.pmrp", "--video", "--audio", "--root", root])
    a2, b2 = digests(text), digests(h.stdout)
    step("%s: the game recorded through the menu run headless gives the same state, run, video and audio digests" % cc, a2 == b2 and "?" not in a2.values(), "%s" % a2["run"])


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
