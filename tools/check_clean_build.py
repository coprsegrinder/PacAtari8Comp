"""Stage 97 (build and dependency documentation): proves the build instructions of docs/63 on a CLEAN copy of the project.
It copies every file that Git would keep (`git ls-files -co --exclude-standard`: tracked and new, never the ignored ones: no `build/`, no `resources/`, no `original/`) into build/clean-check/tree, adds ONLY the owner's cartridge ROM
as `original/Pac-Man.rom`, and then does what the documentation says, step by step, with nothing else in place:
  1  configure and build the C port (CMake, Ninja, one compiler)                            -> the build has 0 warnings (strict C99, -Werror)
  2  ctest with no derived data: the tests that need the recorded vectors are SKIPPED, not passed; the installer makes the asset blob from the ROM
  3  make the derived test data (the recorded vectors) with the Python tools                -> from the ROM, standard library only
  4  ctest again: every test runs and passes
  5  make a replay with a Python tool and play it with pacman_a8: its digests equal the golden ones of analysis/golden-digests.txt (the same game, built from nothing)
Usage: python -I tools/check_clean_build.py [--cc gcc|clang] [--skip-vectors] [--tree DIR] [--write analysis/evidence-clean-build-summary.txt]
  --tree DIR: do not copy from Git; use the already extracted tree DIR (stage 99: the unpacked release archive) and only add the ROM to it
Exit code 0 when every step passed.  The copy is made below build/ of the project (the only place the tools write)."""
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "build", "clean-check")
TREE = os.path.join(WORK, "tree")
EXE = "pacman_a8.exe" if os.name == "nt" else "pacman_a8"
LOG = []
EXTERNAL = "--tree" in sys.argv
if EXTERNAL:
    TREE = os.path.abspath(sys.argv[sys.argv.index("--tree") + 1])


def step(name, ok, detail=""):
    LOG.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""), flush=True)
    return ok


def run(cmd, cwd=TREE, timeout=7200):
    t = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r, time.time() - t


def make_tree():
    if EXTERNAL:
        os.makedirs(os.path.join(TREE, "original"), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, "original", "Pac-Man.rom"), os.path.join(TREE, "original", "Pac-Man.rom"))
        n = sum(len(f) for _, _, f in os.walk(TREE))
        return n, [d for d in ("build", "resources") if os.path.exists(os.path.join(TREE, d))]
    if os.path.exists(TREE):
        def writable(func, path, exc):                       # the copy of the ROM is read-only, like the original
            os.chmod(path, 0o666)
            func(path)
        shutil.rmtree(TREE, onexc=writable)
    r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    files = [f for f in r.stdout.splitlines() if f and f != "Personal notes.txt"]
    for f in files:
        src = os.path.join(ROOT, *f.split("/"))
        if os.path.isfile(src):
            dst = os.path.join(TREE, *f.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    os.makedirs(os.path.join(TREE, "original"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "original", "Pac-Man.rom"), os.path.join(TREE, "original", "Pac-Man.rom"))
    leftovers = [d for d in ("build", "resources") if os.path.exists(os.path.join(TREE, d))]
    return len(files), leftovers


def ctest_counts(text):
    """-> (tests, failed, the names of the skipped ones)"""
    m = re.search(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)", text)
    skipped = re.findall(r"Test\s+#\d+: (\w+) \.+\*\*\*Skipped", text)
    return (int(m.group(3)), int(m.group(2)), skipped) if m else (0, 0, [])


def main():
    a = sys.argv[1:]
    cc = a[a.index("--cc") + 1] if "--cc" in a else "gcc"
    write = a[a.index("--write") + 1] if "--write" in a else None
    t0 = time.time()
    n, left = make_tree()
    step("a clean copy of the project: %d files, no build/ and no resources/, only the cartridge ROM added" % n, not left, "leftovers: %s" % left if left else "")
    build = os.path.join(TREE, "build", "c")
    r, t = run(["cmake", "-S", "src/c", "-B", build, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc, "-DCMAKE_BUILD_TYPE=Release"])
    step("1a configure with %s" % cc, r.returncode == 0, "%.0f s" % t)
    r, t = run(["cmake", "--build", build])
    warn = len(re.findall(r"warning|error", r.stdout + r.stderr, re.I))
    step("1b build (strict C99, -Werror)", r.returncode == 0 and warn == 0, "%.0f s, %d warnings or errors" % (t, warn))
    r, t = run(["ctest", "--test-dir", build, "--output-on-failure"])
    total, failed, skipped = ctest_counts(r.stdout)
    step("2 ctest with no derived data", total >= 37 and failed == 0, "%d tests, %d failed, %d skipped (the recorded vectors are not there yet), %.0f s" % (total, failed, len(skipped), t))
    pack = os.path.exists(os.path.join(TREE, "resources", "pack", "assets.pmab"))
    step("2b the installer made resources/pack/assets.pmab from the ROM", pack)
    if "--skip-vectors" not in a:
        r, t = run([sys.executable, "-I", "tools/make_vectors.py"])
        step("3a make the recorded vectors (tools/make_vectors.py)", r.returncode == 0, "%.0f s" % t)
        r, t = run([sys.executable, "-I", "tools/make_app_sequences.py"])
        step("3b make the application sequences and sessions (tools/make_app_sequences.py)", r.returncode == 0, "%.0f s" % t)
        r, t = run(["ctest", "--test-dir", build, "--output-on-failure"])
        total2, failed2, skipped2 = ctest_counts(r.stdout)
        step("4 ctest with the vectors: every test passes except the two that need the emulator's collision logs", total2 >= 39 and failed2 == 0 and sorted(skipped2) == ["vectors_gtia", "vectors_gtia_world"], "%d tests, %d failed, skipped: %s, %.0f s" % (total2, failed2, ", ".join(skipped2) or "none", t))
    r, t = run([sys.executable, "-I", "tools/make_rom_fuzz_replays.py", "build/replays", "1", "--frames", "12000"])
    step("5a make a replay (tools/make_rom_fuzz_replays.py)", r.returncode == 0)
    exe = os.path.join(build, "shell", EXE)
    r, t = run([exe, "run", "build/replays/fuzz1.pmrp", "--video", "--audio"])
    got = {k: (re.search(pat, r.stdout).group(1) if re.search(pat, r.stdout) else "?") for k, pat in (("state", r"final state hash: (\w+)"), ("run", r"run digest: (\w+)"), ("video", r"video digest: (\w+)"), ("audio", r"audio digest: (\w+)"))}
    gold = None
    with open(os.path.join(ROOT, "analysis", "golden-digests.txt"), encoding="utf-8") as fh:
        for line in fh:
            p = line.split()
            if p and p[0] == "fuzz1":
                gold = {"state": p[2], "run": p[3], "video": p[4], "audio": p[5]}
    step("5b pacman_a8 plays it and gives the digests of the golden game `fuzz1`", r.returncode == 0 and got == gold, "%s" % got if got != gold else "state, run, video and audio digests equal; %.1f s" % t)
    ok = all(x[1] for x in LOG)
    text = "\n".join("%s  %s%s" % ("PASS" if x[1] else "FAIL", x[0], ("  (" + x[2] + ")") if x[2] else "") for x in LOG) + "\n%s: %d steps, %d failed, %.0f s (compiler %s)\n" % ("ALL PASSED" if ok else "FAILURES", len(LOG), sum(1 for x in LOG if not x[1]), time.time() - t0, cc)
    print(text)
    if write:
        with open(os.path.join(ROOT, write), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("Stage 97 (docs/63-build-and-dependencies.md): the build instructions run on a clean copy of the project (tools/check_clean_build.py), 2026-11-23\n\n" + text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
