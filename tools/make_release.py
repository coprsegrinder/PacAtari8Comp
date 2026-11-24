"""Stage 99 (reproducible build and release preparation): makes the release archive of the project and verifies it.

  python -I tools/make_release.py                 make build/release/pacman-a8-port-<version>-src.zip (+ .sha256, release-info.json)
  python -I tools/make_release.py --verify        make it, then verify (see below)
  python -I tools/make_release.py --verify --build [--cc gcc|clang ...]   also build and test an extracted copy (tools/check_clean_build.py --tree)
  python -I tools/make_release.py --write analysis/evidence-release-summary.txt

What goes in: every file Git tracks or would track (`git ls-files -co --exclude-standard`), minus the ones listed in EXCLUDE_*.
Never in: the owner's ROM and the OS ROMs (`original/`, any *.rom), the derived data (`resources/`), builds (`build/`), the emulator and
third-party tools (`external-tools/`), `Personal notes.txt`, emulator pictures and raw logs (git-ignored anyway).
The archive is deterministic: sorted names, one fixed time stamp, fixed permissions, text files with LF line ends (so Windows and Linux checkouts give the
same bytes), the same compression every time. The manifest inside it (RELEASE-MANIFEST.json) lists every file with its SHA-256.
Outside the archive, release-info.json records what varies by machine (date, Git commit and whether the tree was clean, tool versions).

Verification (--verify): (1) the archive made twice is byte-identical; (2) every member equals its manifest hash; (3) no forbidden path; no member contains
32-byte pieces of the cartridge or OS ROMs (sampled all along them); `Personal notes.txt` is absent; LICENSE, NOTICE and the font licence are present;
(4) with --build, the extracted copy plus only the ROM is built (strict C99, -Werror) and tested like a user would (tools/check_clean_build.py)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "build", "release")
NAME = "pacman-a8-port"
VERSION = "0.1.0"
STAMP = (2026, 11, 24, 0, 0, 0)                 # the one time stamp of every member (no clock is read: the archive is reproducible)
MANIFEST = "RELEASE-MANIFEST.json"
EXCLUDE_DIRS = ("original/", "resources/", "build/", "external-tools/")
EXCLUDE_FILES = ("Personal notes.txt", "a800.zip")
EXCLUDE_SUFFIX = (".rom", ".bin", ".car", ".atr", ".xex", ".a8", ".5200", ".os", ".exe", ".obj", ".o", ".lst", ".lab", ".pyc", ".log", ".png", ".jpg")
REQUIRED = ("LICENSE", "NOTICE", "docs/63-build-and-dependencies.md", "docs/65-release.md", "src/c/CMakeLists.txt", "third-party/EightBit-Atari-Fonts/OFL.txt", "tools/check_clean_build.py")
ROMS = ("Pac-Man.rom", "Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom", "Atari OS Rev B (19xx)(Atari)(PAL)[a800.zip MAME].rom")


def selected():
    """-> sorted list of (name, path) of the files in the release, and the list of the files left out with the reason"""
    r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True)
    keep, left = [], []
    for f in sorted(set(x for x in r.stdout.splitlines() if x)):
        path = os.path.join(ROOT, *f.split("/"))
        if not os.path.isfile(path):
            continue
        if f in EXCLUDE_FILES or f.startswith(EXCLUDE_DIRS) or f.lower().endswith(EXCLUDE_SUFFIX):
            left.append(f)
        else:
            keep.append((f, path))
    return keep, left


def content(path):
    """the bytes of the file as the archive keeps them: text with LF line ends, binary as it is"""
    with open(path, "rb") as fh:
        b = fh.read()
    return b if b"\0" in b else b.replace(b"\r\n", b"\n")


def build_archive(dest):
    keep, left = selected()
    members = [(n, content(p)) for n, p in keep]
    man = {"name": NAME, "version": VERSION, "files": [{"path": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in members]}
    mbytes = (json.dumps(man, indent=1, sort_keys=True) + "\n").encode("utf-8")
    members.append((MANIFEST, mbytes))
    members.sort(key=lambda m: m[0])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n, b in members:
            zi = zipfile.ZipInfo(NAME + "-" + VERSION + "/" + n, STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3
            zi.external_attr = (0o755 if n.endswith(".sh") else 0o644) << 16
            z.writestr(zi, b, compresslevel=9)
    return man, left


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def rom_pieces():
    """-> sampled 32-byte windows of the ROMs (every 256 bytes, skipping windows of one repeated byte)"""
    out = []
    for n in ROMS:
        p = os.path.join(ROOT, "original", n)
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as fh:
            b = fh.read()
        for i in range(0, len(b) - 32, 256):
            w = b[i:i + 32]
            if len(set(w)) > 4:
                out.append((n, i, w))
    return out


def verify(arc, man_expected_count, report):
    ok = True

    def step(name, good, detail=""):
        nonlocal ok
        ok = ok and good
        line = "%s  %s%s" % ("PASS" if good else "FAIL", name, ("  (" + detail + ")") if detail else "")
        print(line, flush=True)
        report.append(line)
    second = arc + ".again"
    build_archive(second)
    step("1 the archive made twice is byte-identical", sha256(arc) == sha256(second), sha256(arc)[:16])
    os.remove(second)
    pre = NAME + "-" + VERSION + "/"
    pieces = rom_pieces()
    bad_hash, forbidden, rom_hits, names = [], [], [], set()
    with zipfile.ZipFile(arc) as z:
        man = json.loads(z.read(pre + MANIFEST))
        want = {f["path"]: f["sha256"] for f in man["files"]}
        for zi in z.infolist():
            n = zi.filename[len(pre):]
            names.add(n)
            b = z.read(zi)
            if n != MANIFEST and hashlib.sha256(b).hexdigest() != want.get(n):
                bad_hash.append(n)
            if n.startswith(EXCLUDE_DIRS) or n in EXCLUDE_FILES or n.lower().endswith(EXCLUDE_SUFFIX):
                forbidden.append(n)
            for rn, off, w in pieces:
                if w in b:
                    rom_hits.append("%s: %s @%d" % (n, rn, off))
                    break
    step("2 every member equals its manifest hash; the manifest lists %d files" % len(want), not bad_hash and len(want) == man_expected_count and set(want) | {MANIFEST} == names, ", ".join(bad_hash[:3]))
    step("3a no forbidden path (ROMs, original/, resources/, build/, external-tools/, binaries, Personal notes.txt)", not forbidden and "Personal notes.txt" not in names, ", ".join(forbidden[:3]))
    step("3b no member contains a piece of the cartridge or OS ROMs (%d sampled 32-byte windows)" % len(pieces), not rom_hits and len(pieces) > 0, "; ".join(rom_hits[:3]) or ("the ROMs are not at original/: the check could not run" if not pieces else ""))
    missing = [r for r in REQUIRED if r not in names]
    step("3c the required files are in (%s)" % ", ".join(REQUIRED[:3]) + ", ...", not missing, ", ".join(missing))
    return ok


def build_check(arc, ccs, report):
    ok = True
    pre = NAME + "-" + VERSION + "/"
    for cc in ccs:
        base = os.path.join(OUT, "verify-" + cc)
        tree = os.path.join(base, "tree")
        if os.path.exists(base):
            shutil.rmtree(base, onexc=lambda f, p, e: (os.chmod(p, 0o666), f(p)))
        with zipfile.ZipFile(arc) as z:                  # a fresh copy for every compiler: nothing of the other build is in it
            for zi in z.infolist():
                dst = os.path.join(tree, *zi.filename[len(pre):].split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as fh:
                    fh.write(z.read(zi))
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "check_clean_build.py"), "--cc", cc, "--tree", tree], cwd=ROOT, capture_output=True, text=True)
        tail = [l for l in r.stdout.splitlines() if l.startswith(("ALL PASSED", "FAILURES"))]
        good = r.returncode == 0
        ok = ok and good
        line = "%s  4 %s: the archive extracted to build/release/verify-%s/tree + only the ROM: build, ctest, vectors, a replay with the golden digests  (%s)" % ("PASS" if good else "FAIL", cc, cc, tail[0] if tail else "no result line")
        print(line, flush=True)
        report.append(line)
        if not good:
            print(r.stdout[-3000:], r.stderr[-1500:])
    return ok


def main():
    a = sys.argv[1:]
    write = a[a.index("--write") + 1] if "--write" in a else None
    ccs = [a[i + 1] for i, x in enumerate(a) if x == "--cc"] or ["gcc", "clang"]
    arc = os.path.join(OUT, "%s-%s-src.zip" % (NAME, VERSION))
    man, left = build_archive(arc)
    digest = sha256(arc)
    with open(arc + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%s *%s\n" % (digest, os.path.basename(arc)))
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip() == ""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    info = {"archive": os.path.basename(arc), "sha256": digest, "bytes": os.path.getsize(arc), "files": len(man["files"]) + 1, "version": VERSION,
            "git_head": head, "git_tree_clean": clean, "python": sys.version.split()[0], "left_out": len(left)}
    with open(os.path.join(OUT, "release-info.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(info, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("made %s: %d files, %d bytes, sha256 %s (%d candidate files left out; git tree %s)" % (os.path.relpath(arc, ROOT), info["files"], info["bytes"], digest, len(left), "clean" if clean else "NOT clean: not committed"))
    ok = True
    report = ["archive %s  sha256 %s  %d files, %d bytes; %d candidate files left out; git tree %s" % (os.path.basename(arc), digest, info["files"], info["bytes"], len(left), "clean" if clean else "not clean (uncommitted changes)")]
    if "--verify" in a:
        ok = verify(arc, len(man["files"]), report)
        if "--build" in a and ok:
            ok = build_check(arc, ccs, report)
        report.append("ALL PASSED" if ok else "FAILURES")
        print(report[-1])
    if write:
        with open(os.path.join(ROOT, write), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("Stage 99 (docs/65-release.md): the release archive made and verified (tools/make_release.py)\n\n" + "\n".join(report) + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
