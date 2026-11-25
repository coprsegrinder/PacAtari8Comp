"""Checks the Windows release zip (docs/75) the way a player meets it: unpacked in an empty folder with nothing else, only their ROM given.

  python -I tools/check_win_release.py [ZIP]        (default: build/release/pacman-a8-port-<version>-win64.zip; Windows only; the ROM is original/Pac-Man.rom of this working folder)
  python -I tools/check_win_release.py --write analysis/evidence-win-release-summary.txt

1  the zip: every file equals FILES.sha256; the files a player needs are there; no ROM (a ".rom" file) and no 32-byte piece of the cartridge or the OS ROMs in ANY file, the program included
2  made twice from the same files, the zip is byte-identical (tools/make_win_release.py)
3  the first start, with the ROM given by --rom from outside the folder: the data file resources/pack/assets.pmab is made, the ROM is NOT copied into the folder (no original/Pac-Man.rom)
4  the second start, no ROM given: runs, the data file is not touched (same bytes, same time stamp): the ROM is read once
5  started from another current folder (as a shortcut may): the same game folder is used (no new data file asked for)
6  no ROM and no data file, no dialogs allowed: it stops (exit 2) with the reason in logs/shell.log, makes nothing
7  a file that is not the cartridge (a wrong size, one byte changed, the OS ROM): refused with the reason, nothing made; a ROM that cannot be opened: said so
8  a damaged data file, the ROM given: made again, equal to the first; a damaged data file and no ROM: stops (exit 2), asks (no dialogs: says so)
9  a ROM left at original/Pac-Man.rom (the older layout): used without asking
10 a folder that cannot be written to (a file where the folder resources should be): stops (exit 2) with the write-protect text
11 no ROM, dialogs allowed (a real desktop): the question and the file chooser appear; cancelling leaves with exit 2 and makes nothing
Every start is `pacman_a8_play.exe --selftest 60 --exact --windowed --no-audio --no-dialogs` (a real window for a second; no dialog can block the check)."""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
LOG = []


def step(name, ok, detail=""):
    LOG.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""), flush=True)
    return ok


def rmtree(p):
    def onerr(f, path, e):
        os.chmod(path, stat.S_IWRITE)
        f(path)
    shutil.rmtree(p, onerror=onerr)


def start(folder, *extra, cwd=None, timeout=90):
    cmd = [os.path.join(folder, "pacman_a8_play.exe")] + list(extra) + ["--selftest", "60", "--exact", "--windowed", "--no-audio", "--no-dialogs", "--seed", "1"]
    return subprocess.run(cmd, cwd=cwd or folder, capture_output=True, text=True, timeout=timeout)


def log_text(folder):
    """the log of the last start only (the log is appended to; the text of the start before is cut off at the line that names the version)"""
    p = os.path.join(folder, "logs", "shell.log")
    t = open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""
    k = t.rfind("pacman_a8_play ")
    return t if k < 0 else t[k:]


def dialog_flow(folder):
    """starts the program with no ROM and dialogs allowed, reads the question, presses OK, finds the file chooser, closes it"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    proc = subprocess.Popen([os.path.join(folder, "pacman_a8_play.exe")], cwd=folder)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def windows_of(pid):
        found = []

        def cb(h, _):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, buf, 256)
                cls = buf.value
                user32.GetWindowTextW(h, buf, 256)
                found.append((h, cls, buf.value))
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return found

    def children_text(h):
        out = []

        def cb(c, _):
            buf = ctypes.create_unicode_buffer(1200)
            user32.GetWindowTextW(c, buf, 1200)
            cl = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(c, cl, 64)
            out.append((c, cl.value, buf.value))
            return True
        user32.EnumChildWindows(h, WNDENUMPROC(cb), 0)
        return out

    def wait_for(pred, secs):
        t = time.time()
        while time.time() - t < secs:
            for w in windows_of(proc.pid):
                if pred(w):
                    return w
            if proc.poll() is not None:
                return None
            time.sleep(0.2)
        return None

    try:
        q = wait_for(lambda w: w[1] == "#32770" and "Pac-Man" in w[2], 20)
        if q is None:
            return False, "no question appeared"
        kids = children_text(q[0])
        text = " ".join(t for _, c, t in kids if c == "Static")
        has = "ROM" in text and "8,192" in text and "once" in text.lower()
        ok_btn = next((c for c, cl, t in kids if cl == "Button" and t.replace("&", "").upper() == "OK"), None)
        if ok_btn is None:
            return False, "no OK button: %s" % [t for _, _, t in kids]
        user32.SendMessageW(ok_btn, 0x00F5, 0, 0)                  # BM_CLICK
        fc = wait_for(lambda w: w[1] == "#32770" and "Choose your Pac-Man" in w[2], 20)
        if fc is None:
            proc.kill()
            return False, "the file chooser did not appear (question text ok: %s)" % has
        user32.PostMessageW(fc[0], 0x0010, 0, 0)                   # WM_CLOSE
        try:
            rc = proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            return False, "did not leave after the chooser was closed"
        return has and rc == 2, "question named the ROM, 8,192 bytes and once: %s; chooser '%s'; exit %d" % (has, fc[2][:40], rc)
    finally:
        if proc.poll() is None:
            proc.kill()


def main():
    a = sys.argv[1:]
    zpath = next((x for x in a if x.endswith(".zip")), os.path.join(ROOT, "build", "release", "pacman-a8-port-%s-win64.zip" % VERSION))
    write = a[a.index("--write") + 1] if "--write" in a else None
    rom_path = os.path.join(ROOT, "original", "Pac-Man.rom")
    roms = [rom_path] + [os.path.join(ROOT, "original", f) for f in os.listdir(os.path.join(ROOT, "original")) if f.lower().endswith(".rom") and f != "Pac-Man.rom"]
    rom = open(rom_path, "rb").read()
    work = tempfile.mkdtemp(prefix="pm-release-")
    try:
        # 1 the zip
        z = zipfile.ZipFile(zpath)
        names = z.namelist()
        top = names[0].split("/")[0]
        z.extractall(os.path.join(work, "x"))
        folder = os.path.join(work, "x", top)
        sums = dict((l.split("  ", 1)[1], l.split("  ", 1)[0]) for l in open(os.path.join(folder, "FILES.sha256"), encoding="ascii").read().split("\n") if l)
        bad = [n for n in sums if hashlib.sha256(open(os.path.join(folder, n), "rb").read()).hexdigest() != sums[n]]
        allfiles = sorted(os.path.relpath(os.path.join(r, f), folder).replace(os.sep, "/") for r, _, fs in os.walk(folder) for f in fs)
        step("zip: every file equals FILES.sha256, and FILES.sha256 lists all the others (%d files)" % len(allfiles), not bad and sorted(list(sums) + ["FILES.sha256"]) == allfiles, "differ: %s" % bad[:3])
        need = ["pacman_a8_play.exe", "README.txt", "LICENSE", "NOTICE", "VERSION", "original/README.txt", "src/shaders/plain.slangp", "third-party/crt-shaders/COPYING-GPL-2.0.txt", "third-party/crt-shaders/crt/zfast-crt-composite.slangp",
                "third-party/EightBit-Atari-Fonts/OFL.txt"]
        step("zip: the files a player needs are there; the folder original holds only its README", all(n in allfiles for n in need) and [n for n in allfiles if n.startswith("original/")] == ["original/README.txt"], "missing: %s" % [n for n in need if n not in allfiles])
        # no ROM bytes anywhere (windows of 32 bytes, sampled all along each ROM)
        hits = []
        glyph_note = 0
        blobs = {}
        for n in allfiles:
            blobs[n] = open(os.path.join(folder, n), "rb").read()
        for rp in roms:
            data = open(rp, "rb").read()
            is_os = "Atari OS" in rp
            # the program holds the 64 glyphs of the open font EightBit Atari-Regular (SIL OFL; third-party/README.md): bit for bit the first 64 glyphs of the OS character set (ROM bytes 2048..2560).  Pieces that are
            # only glyph bytes of that set are not the OS ROM's code or tables; they are allowed, and counted.  Nothing of the cartridge, and nothing else of the OS ROM, may be in any file.
            glyph_pieces = set(data[o:o + 32] for o in range(2048, 2560 - 31)) if is_os else set()
            for off in range(0, len(data) - 32, 16):
                piece = data[off:off + 32]
                if len(set(piece)) < 4:
                    continue                                       # all zeros or a fill: found in anything
                for n, b in blobs.items():
                    if piece in b:
                        if piece in glyph_pieces:
                            glyph_note += 1
                        else:
                            hits.append((os.path.basename(rp)[:12], n, off))
                        break
        step("zip: no ROM file; nothing of the cartridge and nothing of the OS ROM but the font's glyph bytes (%d pieces, the open font's bit-for-bit copy of the OS glyphs) in any file, the program included" % glyph_note, not [n for n in allfiles if n.lower().endswith((".rom", ".bin", ".car", ".atr"))] and not hits, "hits: %s" % hits[:3])
        # 2 reproducible
        h0 = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "make_win_release.py"), "--exe", os.path.join(folder, "pacman_a8_play.exe")], cwd=ROOT, capture_output=True, text=True)
        z2 = os.path.join(ROOT, "build", "release", "pacman-a8-port-%s-win64.zip" % VERSION)
        h1 = hashlib.sha256(open(z2, "rb").read()).hexdigest()
        step("made again from the same program, the zip is byte-identical", r.returncode == 0 and h0 == h1, "sha256 %s" % h1[:16])
        blob = os.path.join(folder, "resources", "pack", "assets.pmab")
        other = os.path.join(work, "elsewhere")
        os.makedirs(other)
        # 3 the first start
        ext = os.path.join(work, "my-rom.bin")                     # the player's file, anywhere, any name
        open(ext, "wb").write(rom)
        r = start(folder, "--rom", ext)
        step("first start with the ROM given from outside the folder: runs; the data file is made; the ROM is not copied into the folder", r.returncode == 0 and os.path.exists(blob) and not os.path.exists(os.path.join(folder, "original", "Pac-Man.rom")) and "original/Pac-Man.rom" not in [n for n in sorted(os.path.relpath(os.path.join(rr, f), folder).replace(os.sep, "/") for rr, _, fs in os.walk(folder) for f in fs)],
             "exit %d, data file %d bytes" % (r.returncode, os.path.getsize(blob) if os.path.exists(blob) else -1))
        first = open(blob, "rb").read()
        m1 = os.path.getmtime(blob)
        # 4 second start, no ROM
        time.sleep(1.2)
        r = start(folder)
        step("second start, no ROM anywhere: runs; the data file is untouched (the ROM is read once)", r.returncode == 0 and open(blob, "rb").read() == first and os.path.getmtime(blob) == m1, "exit %d" % r.returncode)
        # 5 another current folder
        r = start(folder, cwd=other)
        step("started from another current folder (a shortcut): the same game folder, no new data file", r.returncode == 0 and os.listdir(other) == [] and os.path.getmtime(blob) == m1, "exit %d, files made in the other folder: %s" % (r.returncode, os.listdir(other)))
        # 6 no ROM, no data file
        os.remove(blob)
        r = start(folder)
        step("no ROM and no data file: stops with exit 2, says why in logs/shell.log, makes nothing", r.returncode == 2 and not os.path.exists(blob) and "--rom" in log_text(folder), "exit %d" % r.returncode)
        # 7 refused files
        wrongs = [("a file of the wrong size", rom[:-1]), ("one byte changed", rom[:1234] + bytes([rom[1234] ^ 1]) + rom[1235:]), ("all zeros", bytes(8192))]
        osrom = next((rp for rp in roms if "Atari OS" in rp), None)
        if osrom:
            wrongs.append(("the Atari OS ROM", open(osrom, "rb").read()))
        okc = True
        for label, data in wrongs:
            p = os.path.join(work, "wrong.bin")
            open(p, "wb").write(data)
            r = start(folder, "--rom", p)
            okc = okc and r.returncode == 2 and not os.path.exists(blob)
            if not (r.returncode == 2 and not os.path.exists(blob)):
                print("   not refused:", label, r.returncode)
        step("not the cartridge (%s): refused with exit 2, nothing made" % ", ".join(l for l, _ in wrongs), okc)
        lt = log_text(folder)
        step("the reason is in the log (the size, the hash)", "sha256 differs" in lt or "8192" in lt or "8,192" in lt, lt.strip().split("\n")[-1][:140])
        r = start(folder, "--rom", os.path.join(work, "no-such-file.bin"))
        step("a ROM file that cannot be opened: said so (exit 2)", r.returncode == 2 and "cannot be opened" in log_text(folder))
        # 8 damaged data file
        r = start(folder, "--rom", ext)
        assert os.path.exists(blob)
        again = open(blob, "rb").read()
        open(blob, "wb").write(b"damaged")
        r = start(folder, "--rom", ext)
        step("a damaged data file with the ROM given: made again, equal to the first time", r.returncode == 0 and open(blob, "rb").read() == first == again, "exit %d" % r.returncode)
        open(blob, "wb").write(b"damaged")
        r = start(folder)
        step("a damaged data file and no ROM: stops with exit 2 (it would ask for the ROM), the damaged file is left", r.returncode == 2 and open(blob, "rb").read() == b"damaged", "exit %d" % r.returncode)
        # 9 the older layout
        os.remove(blob)
        os.makedirs(os.path.join(folder, "original"), exist_ok=True)
        shutil.copyfile(rom_path, os.path.join(folder, "original", "Pac-Man.rom"))
        r = start(folder)
        step("a ROM left at original/Pac-Man.rom is used without asking", r.returncode == 0 and open(blob, "rb").read() == first, "exit %d" % r.returncode)
        # 10 unwritable
        rmtree(os.path.join(folder, "resources"))
        os.chmod(os.path.join(folder, "original", "Pac-Man.rom"), stat.S_IWRITE)
        os.remove(os.path.join(folder, "original", "Pac-Man.rom"))
        open(os.path.join(folder, "resources"), "wb").write(b"x")
        r = start(folder, "--rom", ext)
        step("a folder that cannot be written to: stops with exit 2 and the write-protect text", r.returncode == 2 and "write-protected" in log_text(folder), "exit %d" % r.returncode)
        # 11 the dialogs a player sees (needs a desktop): the question, then the file chooser; cancelling leaves without a word and makes nothing
        z.extractall(os.path.join(work, "dlg"))
        dfolder = os.path.join(work, "dlg", top)
        ok, detail = dialog_flow(dfolder)
        step("no ROM, dialogs allowed: the program asks (the text names the ROM, 8,192 bytes, once), OK opens the file chooser, closing it leaves with exit 2 and makes nothing", ok and not os.path.exists(os.path.join(dfolder, "resources")), detail)
    finally:
        rmtree(work)
    fails = [n for n, ok, _ in LOG if not ok]
    print("%s: %d steps, %d failed" % ("ALL PASSED" if not fails else "FAILURES", len(LOG), len(fails)))
    if write:
        with open(os.path.join(ROOT, write), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("Windows release check (tools/check_win_release.py), version %s: %d steps, %d failed\n" % (VERSION, len(LOG), len(fails)))
            for n, ok, d in LOG:
                fh.write("%s  %s%s\n" % ("PASS" if ok else "FAIL", n, ("  (" + d + ")") if d else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
