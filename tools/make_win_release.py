"""The Windows release of the program (docs/75): a zip with the game, its shader files and the licences, which the player needs only the cartridge ROM to play.

  python -I tools/make_win_release.py                    build the program (clang, Release) in build/win-release and make build/release/pacman-a8-port-<version>-win64.zip (+ .sha256)
  python -I tools/make_win_release.py --exe PATH         use this built program instead of building one
  python -I tools/make_win_release.py --cc gcc           another compiler (the default is clang: it links only the Windows system libraries)

What goes in (a folder named for the version): pacman_a8_play.exe; README.txt (for the player; packaging/windows/); LICENSE and NOTICE; the shader files the Graphics Options read
(src/shaders, third-party/crt-shaders with its licences); the font's licence (third-party/EightBit-Atari-Fonts/OFL.txt: the glyphs are in the program); original/README.txt (the folder where a ROM may be
put, empty otherwise); FILES.sha256 (the hash of every file).  What never goes in: the cartridge ROM or any ROM (checked by tools/check_win_release.py in the program as well as in the files), the derived
data (resources/: the player's own first start makes it), saved data, logs.
The zip is deterministic: sorted names, one fixed time stamp, fixed permissions, LF text files: the same program gives the same bytes.
The version is the one line of the file VERSION."""
import hashlib
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "build", "release")
STAMP = (2026, 11, 25, 0, 0, 0)
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
NAME = "pacman-a8-port"
TOP = "Pac-Man-Atari8-C-port-%s" % VERSION
TEXT_SUFFIX = (".txt", ".md", ".slang", ".slangp", ".json")


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def build_exe(cc):
    build = os.path.join(ROOT, "build", "win-release" + ("-gcc" if cc == "gcc" else ""))
    r = run(["cmake", "-S", "src/c", "-B", build, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc, "-DCMAKE_BUILD_TYPE=Release"])
    if r.returncode:
        sys.exit("configure failed:\n" + r.stdout + r.stderr)
    r = run(["cmake", "--build", build, "--target", "pacman_a8_play"], timeout=1800)
    if r.returncode:
        sys.exit("build failed:\n" + r.stdout + r.stderr)
    return os.path.join(build, "platform", "win32", "pacman_a8_play.exe")


def tree_files(rel):
    base = os.path.join(ROOT, rel)
    out = []
    for r, _, fs in os.walk(base):
        for f in fs:
            out.append(os.path.relpath(os.path.join(r, f), ROOT).replace(os.sep, "/"))
    return sorted(out)


def read(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if path.lower().endswith(TEXT_SUFFIX):
        data = data.replace(b"\r\n", b"\n")                    # LF whatever the checkout: the same bytes on every machine
    return data


def collect(exe):
    files = {}                                                 # name inside the zip -> bytes
    files["pacman_a8_play.exe"] = (read(exe), 0o755)
    files["README.txt"] = (read(os.path.join(ROOT, "packaging", "windows", "README.txt")), 0o644)
    files["original/README.txt"] = (read(os.path.join(ROOT, "packaging", "windows", "original-README.txt")), 0o644)
    for name in ("LICENSE", "NOTICE", "VERSION"):
        files[name] = (read(os.path.join(ROOT, name)), 0o644)
    for rel in tree_files("src/shaders") + tree_files("third-party/crt-shaders") + ["third-party/EightBit-Atari-Fonts/OFL.txt", "third-party/README.md"]:
        files[rel] = (read(os.path.join(ROOT, rel)), 0o644)
    lines = ["%s  %s" % (hashlib.sha256(files[n][0]).hexdigest(), n) for n in sorted(files)]
    files["FILES.sha256"] = (("\n".join(lines) + "\n").encode("ascii"), 0o644)
    return files


def make_zip(files, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            data, mode = files[name]
            zi = zipfile.ZipInfo(TOP + "/" + name, STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o100000 | mode) << 16
            zi.create_system = 3
            z.writestr(zi, data)


def main():
    a = sys.argv[1:]
    exe = a[a.index("--exe") + 1] if "--exe" in a else None
    cc = a[a.index("--cc") + 1] if "--cc" in a else "clang"
    if exe is None:
        exe = build_exe(cc)
    if not os.path.exists(exe):
        sys.exit("no program at " + exe)
    files = collect(exe)
    path = os.path.join(OUT, "%s-%s-win64%s.zip" % (NAME, VERSION, "-gcc" if cc == "gcc" else ""))
    make_zip(files, path)
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with open(path + ".sha256", "w", encoding="ascii", newline="\n") as fh:
        fh.write("%s  %s\n" % (digest, os.path.basename(path)))
    print("%s  %d files, %d bytes, sha256 %s" % (path, len(files), os.path.getsize(path), digest))


if __name__ == "__main__":
    main()
