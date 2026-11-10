"""Step C10: rebuild the ROM from src/asm/pacman.s and compare it with the original.

Usage (project root):  python -I tools/build_rom.py [--source FILE]
Assembles with ca65, links with ld65 (layout: src/asm/pacman.cfg) into build/pacman.rom, then compares
size and SHA-256 with original/Pac-Man.rom and reports the first differing offset if any.
Exit code 0 = byte-identical, 1 = build error or difference. Never modifies original/.
Toolchain location: env CC65_BIN, default F:/Ports/Pac-Man-tools/cc65/bin.
"""
import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.environ.get("CC65_BIN", r"F:\Ports\Pac-Man-tools\cc65\bin")


def build(source, outdir):
    os.makedirs(outdir, exist_ok=True)
    obj = os.path.join(outdir, "pacman.o")
    rom = os.path.join(outdir, "pacman.rom")
    cfg = os.path.join(ROOT, "src", "asm", "pacman.cfg")
    for exe in ("ca65.exe", "ld65.exe"):
        if not os.path.exists(os.path.join(BIN, exe)):
            raise SystemExit("toolchain not found: " + os.path.join(BIN, exe))
    subprocess.run([os.path.join(BIN, "ca65.exe"), "--cpu", "6502", source, "-o", obj], check=True)
    subprocess.run([os.path.join(BIN, "ld65.exe"), "-C", cfg, obj, "-o", rom], check=True)
    return rom


def compare(built, original):
    with open(built, "rb") as fa, open(original, "rb") as fb:
        a, b = fa.read(), fb.read()
    print("built    : %d bytes, SHA-256 %s" % (len(a), hashlib.sha256(a).hexdigest()))
    print("original : %d bytes, SHA-256 %s" % (len(b), hashlib.sha256(b).hexdigest()))
    if a == b:
        return True
    diffs = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    print("DIFFERENT: size %s, %d differing bytes, first at offset $%04X (address $%04X)"
          % ("equal" if len(a) == len(b) else "differs", len(diffs), diffs[0] if diffs else 0,
             0xA000 + (diffs[0] if diffs else 0)))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join(ROOT, "src", "asm", "pacman.s"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build"))
    args = ap.parse_args()
    try:
        rom = build(args.source, args.out)
    except subprocess.CalledProcessError:
        print("BUILD FAILED")
        return 1
    ok = compare(rom, os.path.join(ROOT, "original", "Pac-Man.rom"))
    print("BYTE-IDENTICAL" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
