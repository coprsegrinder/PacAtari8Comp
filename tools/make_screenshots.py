"""The pictures of the README (docs/images/): made by the real program, on the real screen, in a scratch main folder that holds only the player's ROM, the shader files and what each run writes.

  python -I tools/make_screenshots.py [--exe PATH] [--stage gameplay|crt|menus|pads|achievements ...]      (Windows only; needs a display; about 6 minutes for everything)

gameplay      the title screen and the game at two moments (`--selftest N --ppm`: the game played by the scripted keys, the picture as the program draws it, 384 x 240, here shown 3 times as large, nearest pixel)
crt           the three CRT shaders on a frame of play (`--crttest`, 2304 x 1440, here halved)
menus         the pause menu, the Graphics, Controls (keyboard) and Sound pages (`--menutest`: real key messages, the picture the program draws)
pads          the Controls page as it is for an Xbox pad and for a DualSense (`--device`; the same menu test)
achievements  the Achievements page and the toast over the game with a CRT shader on (`--achtest`, with a prepared save file so that the page shows some earned: the picture of the page is of THAT file, an
              illustration of the page, not of one run of the game; the toast is from a real first dot)
The pictures are the program's own output (nothing is drawn by this script but the enlargement); they hold the game's graphics, as any picture of the game does."""
import hashlib
import hmac
import os
import shutil
import stat
import struct
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "images")
WORK = os.path.join(ROOT, "build", "shots-root")
KEY = b"Pac-Man Atari 8-bit achievements"
ACH_N = 27


def run(args, timeout=400):
    r = subprocess.run(args, cwd=WORK, capture_output=True, text=True, timeout=timeout)
    return r.returncode


def setup(exe):
    if os.path.exists(WORK):
        def onerr(f, p, e):
            os.chmod(p, stat.S_IWRITE)
            f(p)
        shutil.rmtree(WORK, onerror=onerr)
    os.makedirs(os.path.join(WORK, "original"))
    shutil.copyfile(os.path.join(ROOT, "original", "Pac-Man.rom"), os.path.join(WORK, "original", "Pac-Man.rom"))
    os.chmod(os.path.join(WORK, "original", "Pac-Man.rom"), stat.S_IWRITE | stat.S_IREAD)
    shutil.copytree(os.path.join(ROOT, "src", "shaders"), os.path.join(WORK, "src", "shaders"))
    shutil.copytree(os.path.join(ROOT, "third-party", "crt-shaders"), os.path.join(WORK, "third-party", "crt-shaders"))
    os.makedirs(os.path.join(WORK, "logs"), exist_ok=True)
    shutil.copyfile(exe, os.path.join(WORK, "pacman_a8_play.exe"))


def exe_args(*a):
    return [os.path.join(WORK, "pacman_a8_play.exe"), "--root", WORK] + list(a)


def save(src, name, scale=None, size=None):
    im = Image.open(src).convert("RGB")
    if scale:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    elif size:
        im = im.resize(size, Image.LANCZOS)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    im.save(path, optimize=True)
    print("%-34s %dx%d  %d KB" % (name, im.width, im.height, os.path.getsize(path) // 1024))


def log(name):
    return os.path.join(WORK, "logs", name)


def stage_gameplay(frames):
    for tag, n in frames:
        name = "shot_%s.ppm" % tag                                # a path inside the scratch main folder (the program's file layer reaches nothing else)
        run(exe_args("--selftest", str(n), "--exact", "--windowed", "--no-audio", "--no-dialogs", "--seed", "7", "--ppm", name))
        save(os.path.join(WORK, name), "gameplay-%s.png" % tag, scale=3)


def stage_crt():
    run(exe_args("--crttest"), timeout=300)
    for src, name in (("crt_crt-guest-advanced-ntsc.ppm", "crt-guest-advanced-ntsc.png"), ("crt_zfast-crt-composite.ppm", "crt-zfast.png"), ("crt_crt-aperture.ppm", "crt-aperture.png")):
        save(log(src), name, size=(1152, 720))


def stage_menus():
    run(exe_args("--menutest", "--windowed", "--seed", "7"))
    for src, name in (("menu_main.ppm", "menu-main.png"), ("menu_graphics.ppm", "menu-graphics.png"), ("menu_controls.ppm", "menu-controls-keyboard.png"), ("menu_sound.ppm", "menu-sound.png")):
        save(log(src), name, scale=3)


def stage_pads():
    for dev, name in (("xbox", "menu-controls-xbox.png"), ("dualsense", "menu-controls-dualsense.png")):
        if os.path.exists(log("menu_controls.ppm")):
            os.remove(log("menu_controls.ppm"))
        run(exe_args("--menutest", "--windowed", "--seed", "7", "--device", dev))          # (the test's own check of the keyboard icons fails here: only the picture is wanted)
        save(log("menu_controls.ppm"), name, scale=3)


def sealed(bits, when):
    body = b"PMAC" + bytes([1, 0, ACH_N, 0]) + struct.pack("<IIII", bits, 600, 12, 3) + b"".join(struct.pack("<I", when.get(i, 0)) for i in range(ACH_N))
    return body + hmac.new(KEY, body, hashlib.sha256).digest()


def stage_achievements():
    ids = [1, 2, 3, 6, 9, 14, 20]                      # Power Up, Ghost Buster, Double Trouble, Clean Sweep, Bonus Life, Warming Up, Dot Collector (First Bite is earned by the run: its toast is the picture)
    bits = sum(1 << i for i in ids)
    day = 1795564800                                    # 2026-11-25 00:00 UTC, an hour apart
    os.makedirs(os.path.join(WORK, "save"), exist_ok=True)
    open(os.path.join(WORK, "save", "achievements.pma"), "wb").write(sealed(bits, {i: day + 3600 * k for k, i in enumerate(ids)}))
    for f in ("menu_ach.ppm", "toast_full.ppm"):
        if os.path.exists(log(f)):
            os.remove(log(f))
    run(exe_args("--achtest", "--crt", "zfast", "--seed", "7"), timeout=300)
    save(log("menu_ach.ppm"), "menu-achievements.png", scale=3)
    save(log("toast_full.ppm"), "achievement-toast.png", size=(1152, 720))


def main():
    a = sys.argv[1:]
    exe = a[a.index("--exe") + 1] if "--exe" in a else os.path.join(ROOT, "build", "c-clang", "platform", "win32", "pacman_a8_play.exe")
    stages = [a[i + 1] for i, x in enumerate(a) if x == "--stage"] or ["gameplay", "crt", "menus", "pads", "achievements"]
    frames = [("title", 100), ("play", 1000), ("chase", 1300)]
    if "--frames" in a:
        frames = [("f%d" % int(n), int(n)) for n in a[a.index("--frames") + 1].split(",")]
    setup(exe)
    if "gameplay" in stages:
        stage_gameplay(frames)
    if "crt" in stages:
        stage_crt()
    if "menus" in stages:
        stage_menus()
    if "pads" in stages:
        stage_pads()
    if "achievements" in stages:
        stage_achievements()


if __name__ == "__main__":
    main()
