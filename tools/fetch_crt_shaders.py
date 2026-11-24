"""Downloads the three CRT shaders of the Graphics Options (docs/70) from the libretro slang-shaders repository, at one pinned commit, with everything they refer to (the shader files, the files they #include, the
lookup textures of the presets), into third-party/crt-shaders/ (the same paths as in the repository), and writes third-party/crt-shaders/SOURCES.txt: every file's URL and SHA-256.  The three presets:
crt/crt-guest-advanced-ntsc.slangp (guest.r), crt/zfast-crt-composite.slangp (SoltanGris42), crt/crt-aperture.slangp (DariusG).  The files are data for the program to read at run time; they are not changed.
Usage: python -I tools/fetch_crt_shaders.py [--check]      (--check: only compares the files on disk with SOURCES.txt, no network)"""
import hashlib
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEST = os.path.join(ROOT, "third-party", "crt-shaders")
COMMIT = "02bf134555c4595bd6b69be89feaff923da83754"           # libretro/slang-shaders master of 2026-11-20
BASE = "https://raw.githubusercontent.com/libretro/slang-shaders/%s/" % COMMIT
PRESETS = ["crt/crt-guest-advanced-ntsc.slangp", "crt/zfast-crt-composite.slangp", "crt/crt-aperture.slangp"]
MANIFEST = os.path.join(DEST, "SOURCES.txt")


def fetch(rel):
    req = urllib.request.Request(BASE + rel, headers={"User-Agent": "pacman-port-preservation"})
    return urllib.request.urlopen(req, timeout=60).read()


def norm(base_rel, ref):
    return os.path.normpath(os.path.join(os.path.dirname(base_rel), ref)).replace("\\", "/")


def refs(rel, data):
    """the files a file refers to: shaders and textures of a preset (and the presets it #reference s), the #include s of a shader"""
    text = data.decode("utf-8", errors="replace")
    out = []
    if rel.endswith((".slangp", ".glslp")):
        for line in text.splitlines():
            line = line.split("#")[0] if not line.strip().startswith("#reference") else line
            m = re.match(r'\s*#reference\s+"?([^"\s]+)"?', line)
            if m:
                out.append(norm(rel, m.group(1)))
                continue
            m = re.match(r'\s*(shader\d+|\w+)\s*=\s*"?([^"\n]+?)"?\s*$', line)
            if m and re.search(r"\.(slang|glsl|png|slangp|glslp)\s*$", m.group(2).strip()):
                out.append(norm(rel, m.group(2).strip()))
    else:
        for m in re.finditer(r'^\s*#include\s+"([^"]+)"', text, re.M):
            out.append(norm(rel, m.group(1)))
    return out


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if "--check" in sys.argv:
        bad = 0
        for line in open(MANIFEST, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            h, rel = line.split()[:2]
            p = os.path.join(DEST, rel)
            if not os.path.exists(p) or sha(open(p, "rb").read()) != h:
                print("DIFFERS:", rel)
                bad += 1
        print("ok" if bad == 0 else "%d files differ" % bad)
        sys.exit(1 if bad else 0)
    seen, todo, rows = set(), list(PRESETS), []
    while todo:
        rel = todo.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        data = fetch(rel)
        p = os.path.join(DEST, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        rows.append((sha(data), rel, len(data)))
        if not rel.endswith(".png"):
            todo.extend(refs(rel, data))
    # the licence texts that belong to the files (the repository's own)
    for extra in ("LICENSE", "README.md"):
        try:
            data = fetch(extra)
            with open(os.path.join(DEST, "slang-shaders-" + extra), "wb") as fh:
                fh.write(data)
            rows.append((sha(data), "slang-shaders-" + extra, len(data)))
        except Exception as e:                                         # not every repository has both
            print("no", extra, e)
    rows.sort(key=lambda r: r[1])
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# the files of the CRT shaders of docs/70, made by tools/fetch_crt_shaders.py from https://github.com/libretro/slang-shaders at commit %s\n# sha256, path (relative to this folder), bytes\n" % COMMIT)
        for h, rel, n in rows:
            fh.write("%s %s %d\n" % (h, rel, n))
    print("%d files, %d bytes in %s" % (len(rows), sum(r[2] for r in rows), DEST))


if __name__ == "__main__":
    main()
