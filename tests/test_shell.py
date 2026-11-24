"""Stage 80d (docs/51, docs/49 D3): the headless shell (src/c/shell, `pacman_a8`).
 * the recorded sessions of stage 79d (a one-player game from power-on to the game over and the title, a session of keys, a clock that wraps, a two-player game of 10,617 frames) become replays
   (tools/make_replay.py) and the shell reproduces the hash of the state after EVERY frame of the recording, with clang and gcc; the level session differs exactly at its test aid (frame 600: the recording
   pokes LevelComplete, which no input can do);
 * the run is deterministic (state, video and audio digests), the compilers agree on the state and the picture, another input or another seed gives another run;
 * a damaged replay (cut, a changed byte, another magic or version) is refused, an unknown option is refused, a path outside the main folder is refused;
 * the high score and the log are kept under save/ and logs/ of the main folder only when asked; the first run makes the asset blob from the ROM; the last picture can be written as a PPM.
The session vectors are derived data (resources/vectors, made by tools/make_app_sequences.py); without them those tests are skipped.  The pure C tests are `ctest shell_selftest`."""
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import make_replay as M  # noqa: E402
import test_c_ghost as TG  # noqa: E402

VEC = os.path.join(ROOT, "resources", "vectors")
WORK = os.path.join(ROOT, "build", "t80d-test")


def hashes_of(path):
    with open(path, encoding="utf-8") as fh:
        return [line.split()[1] for line in fh if line.strip()]


class Shell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")
        if not os.path.exists(os.path.join(ROOT, "resources", "pack", "assets.pmab")):
            raise unittest.SkipTest("no asset blob (the ROM is needed: install_assets)")
        cls.exe = {cc: os.path.join(f, "shell", "pacman_a8" + (".exe" if os.name == "nt" else "")) for cc, f in cls.folders}
        os.makedirs(WORK, exist_ok=True)

    def run_shell(self, cc, *args, cwd=ROOT):
        return subprocess.run([self.exe[cc]] + list(args), cwd=cwd, capture_output=True, text=True)

    def rel(self, p):
        return os.path.relpath(p, ROOT)

    def session(self, name):
        vec = os.path.join(VEC, "session_%s.vec" % name)
        if not os.path.exists(vec):
            self.skipTest("no " + vec + " (python -I tools/make_app_sequences.py)")
        rep, hs = os.path.join(WORK, name + ".pmrp"), os.path.join(WORK, name + ".hashes")
        if not os.path.exists(hs) or os.path.getmtime(hs) < os.path.getmtime(vec):
            M.from_vector(vec, rep, hs)
        return rep, hashes_of(hs)

    # ---- the recorded sessions ----
    def test_the_recorded_sessions_replay_to_the_hash_of_every_frame(self):
        total = 0
        for name in ("clock", "keys", "1p", "2p"):
            rep, want = self.session(name)
            for cc, _ in self.folders:
                out = os.path.join(WORK, "%s.%s.hashes" % (name, cc))
                r = self.run_shell(cc, "run", self.rel(rep), "--hashes", self.rel(out))
                self.assertEqual(r.returncode, 0, r.stdout)
                got = hashes_of(out)
                self.assertEqual(len(got), len(want), name)
                self.assertEqual(got, want, "%s %s: the state differs from the recording at frame %d" % (name, cc, next(i for i, (a, b) in enumerate(zip(got, want)) if a != b) if got != want else -1))
            total += len(want)
        self.assertGreater(total, 20000)

    def test_the_level_session_differs_exactly_at_its_test_aid(self):
        rep, want = self.session("level")
        for cc, _ in self.folders:
            out = os.path.join(WORK, "level.%s.hashes" % cc)
            self.assertEqual(self.run_shell(cc, "run", self.rel(rep), "--hashes", self.rel(out)).returncode, 0)
            got = hashes_of(out)
            self.assertEqual(got[:600], want[:600])                      # every input-driven frame before the poke of LevelComplete
            self.assertNotEqual(got[600], want[600], "the recording's poke is not an input")

    # ---- determinism ----
    def test_runs_are_deterministic_and_the_compilers_agree(self):
        rep, _ = self.session("keys")
        outs = {}
        for cc, _ in self.folders:
            a = self.run_shell(cc, "run", self.rel(rep), "--video", "--audio", "--frames", "1500").stdout
            b = self.run_shell(cc, "run", self.rel(rep), "--video", "--audio", "--frames", "1500").stdout
            self.assertEqual(a, b, cc + ": two runs differ")
            outs[cc] = dict(line.split(": ", 1) for line in a.splitlines() if ": " in line)
            self.assertEqual(outs[cc]["frames run"], "1500 of 2600")
        if len(outs) == 2:
            c0, c1 = list(outs.values())
            for k in ("final state hash", "run digest", "video digest"):
                self.assertEqual(c0[k], c1[k], "clang and gcc differ in the " + k)

    def test_another_input_or_another_seed_gives_another_run(self):
        rep, want = self.session("keys")
        with open(rep, "rb") as fh:
            r = M.read_replay(fh.read())
        n = next(i for i, f in enumerate(r["frames"]) if f["console"] != 7)
        frames = [dict(f) for f in r["frames"]]
        frames[n]["console"] = 7
        frames[n + 1]["console"] = 7 if n + 1 < len(frames) else frames[n + 1]["console"]
        changed = os.path.join(WORK, "changed.pmrp")
        M.write_replay(changed, frames, seed=r["seed"], start_clock=r["start_clock"], with_random=True)
        for cc, _ in self.folders:
            out = os.path.join(WORK, "changed.%s.hashes" % cc)
            self.assertEqual(self.run_shell(cc, "run", self.rel(changed), "--hashes", self.rel(out)).returncode, 0)
            got = hashes_of(out)
            self.assertEqual(got[:n], want[:n])
            self.assertNotEqual(got, want, "a changed console at frame %d must change the run" % n)
        # RANDOM: the recorded game carries the bytes of the frames that read it (the game reads RANDOM rarely: 23 bytes in 9,000 frames); without them the model's seed gives them: the same seed
        # the same game, another seed another game, and none of them the recorded one
        rep1p, _ = self.session("1p")
        with open(rep1p, "rb") as fh:
            r1 = M.read_replay(fh.read())
        recorded = self.run_shell(self.folders[0][0], "run", self.rel(rep1p)).stdout.split("run digest: ")[1].split()[0]
        digests = []
        for seed in (1, 2, 1):
            p = os.path.join(WORK, "nostream%d.pmrp" % seed)
            M.write_replay(p, r1["frames"], seed=seed, start_clock=r1["start_clock"], with_random=False)
            digests.append(self.run_shell(self.folders[0][0], "run", self.rel(p)).stdout.split("run digest: ")[1].split()[0])
        self.assertEqual(digests[0], digests[2])
        self.assertNotEqual(digests[0], digests[1])
        self.assertNotIn(recorded, digests)

    # ---- damaged replays and misuse ----
    def test_a_damaged_replay_is_refused(self):
        rep, _ = self.session("clock")
        with open(rep, "rb") as fh:
            good = fh.read()
        cases = {"cut": good[:-100], "cut_header": good[:12], "flipped": good[:500] + bytes([good[500] ^ 1]) + good[501:], "magic": b"XXXX" + good[4:], "version": good[:4] + b"\x02" + good[5:],
                 "empty": b"", "longer": good + b"\0"}
        for name, data in cases.items():
            p = os.path.join(WORK, "bad_%s.pmrp" % name)
            with open(p, "wb") as fh:
                fh.write(data)
            for cc, _ in self.folders:
                r = self.run_shell(cc, "run", self.rel(p))
                self.assertEqual(r.returncode, 1, "%s %s: %s" % (cc, name, r.stdout))
                self.assertIn("pacman_a8:", r.stdout)
                self.assertNotIn("final state hash", r.stdout)
        cc = self.folders[0][0]
        self.assertEqual(self.run_shell(cc, "run", self.rel(os.path.join(WORK, "no_such.pmrp"))).returncode, 1)
        self.assertEqual(self.run_shell(cc, "run", self.rel(rep), "--no-such-option").returncode, 2)
        self.assertEqual(self.run_shell(cc, "frob", self.rel(rep)).returncode, 2)
        self.assertEqual(self.run_shell(cc).returncode, 2)
        r = self.run_shell(cc, "run", self.rel(rep), "--hashes", "../hashes_outside.txt")
        self.assertEqual(r.returncode, 1)                                   # a path outside the main folder
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(ROOT), "hashes_outside.txt")))
        r = self.run_shell(cc, "run", self.rel(rep), "--frames", "10")
        self.assertIn("frames run: 10 of 700", r.stdout)
        r = self.run_shell(cc, "info", self.rel(rep))
        self.assertIn("700 frames, RANDOM in the frames, seed 0, power-on clock 250", r.stdout)

    # ---- what is kept between runs ----
    def make_root(self, name, blob=True, rom=False):
        root = os.path.join(WORK, name)
        if os.path.exists(root):
            for d, _, files in os.walk(root):
                for f in files:
                    os.chmod(os.path.join(d, f), 0o666)
            shutil.rmtree(root)
        os.makedirs(os.path.join(root, "resources", "pack"))
        if blob:
            shutil.copy(os.path.join(ROOT, "resources", "pack", "assets.pmab"), os.path.join(root, "resources", "pack", "assets.pmab"))
        if rom:
            os.makedirs(os.path.join(root, "original"), exist_ok=True)
            with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as src, open(os.path.join(root, "original", "Pac-Man.rom"), "wb") as dst:
                dst.write(src.read())
        return root

    def test_the_high_score_the_options_and_the_log_are_kept_when_asked(self):
        rep, _ = self.session("1p")
        cc = self.folders[0][0]
        root = self.make_root("keep")
        shutil.copy(rep, os.path.join(root, "game.pmrp"))
        plain = self.run_shell(cc, "run", "game.pmrp", "--root", root)
        self.assertEqual(plain.returncode, 0, plain.stdout)
        self.assertFalse(os.path.exists(os.path.join(root, "save")), "nothing is written unless asked")
        self.assertFalse(os.path.exists(os.path.join(root, "logs")))
        first = self.run_shell(cc, "run", "game.pmrp", "--root", root, "--keep-high-score", "--log")
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertIn("high score saved:", first.stdout)
        self.assertTrue(os.path.exists(os.path.join(root, "save", "highscore.pmo")))
        with open(os.path.join(root, "logs", "shell.log"), encoding="utf-8") as fh:
            self.assertIn("run game.pmrp frames=9000", fh.read())
        saved = int(first.stdout.split("high score saved: ")[1].split()[0])
        second = self.run_shell(cc, "run", "game.pmrp", "--root", root, "--keep-high-score", "--log")
        self.assertIn("high score loaded: %06d" % saved, second.stdout)
        if saved > 0:
            self.assertNotEqual(second.stdout.split("final state hash: ")[1].split()[0] + second.stdout.split("run digest: ")[1].split()[0],
                                plain.stdout.split("final state hash: ")[1].split()[0] + plain.stdout.split("run digest: ")[1].split()[0],
                                "a saved high score is part of the machine's state")
        with open(os.path.join(root, "logs", "shell.log"), encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().strip().splitlines()), 2)
        # a damaged save is ignored, not used
        with open(os.path.join(root, "save", "highscore.pmo"), "wb") as fh:
            fh.write(b"\x55" * 20)
        third = self.run_shell(cc, "run", "game.pmrp", "--root", root, "--keep-high-score")
        self.assertNotIn("high score loaded", third.stdout)
        self.assertEqual(third.stdout.split("run digest: ")[1].split()[0], plain.stdout.split("run digest: ")[1].split()[0])

    def test_the_first_run_makes_the_asset_blob_from_the_rom(self):
        rep, _ = self.session("clock")
        cc = self.folders[0][0]
        root = self.make_root("firstrun", blob=False, rom=True)
        shutil.copy(rep, os.path.join(root, "r.pmrp"))
        r = self.run_shell(cc, "run", "r.pmrp", "--root", root, "--frames", "50")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("made resources/pack/assets.pmab from original/Pac-Man.rom", r.stdout)
        with open(os.path.join(root, "resources", "pack", "assets.pmab"), "rb") as a, open(os.path.join(ROOT, "resources", "pack", "assets.pmab"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        # no ROM and no blob: refused, with the reason
        root = self.make_root("norom", blob=False, rom=False)
        shutil.copy(rep, os.path.join(root, "r.pmrp"))
        r = self.run_shell(cc, "run", "r.pmrp", "--root", root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot be made from original/Pac-Man.rom", r.stdout)
        # a ROM that is not the NTSC cartridge: refused
        root = self.make_root("badrom", blob=False, rom=True)
        shutil.copy(rep, os.path.join(root, "r.pmrp"))
        p = os.path.join(root, "original", "Pac-Man.rom")
        with open(p, "rb") as fh:
            data = bytearray(fh.read())
        data[100] ^= 1
        with open(p, "wb") as fh:
            fh.write(bytes(data))
        r = self.run_shell(cc, "run", "r.pmrp", "--root", root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not the NTSC Pac-Man cartridge", r.stdout)

    def test_the_time_option_measures_and_changes_nothing(self):
        """stage 88: `--time` prints the time of the game, the renderer and the sound chip per frame (mean, median, 99th percentile, worst) and the run, its digests and the state of every frame are the same as without it"""
        import re
        rep, _ = self.session("keys")
        for cc, _ in self.folders:
            plain = self.run_shell(cc, "run", self.rel(rep), "--video", "--audio")
            timed = self.run_shell(cc, "run", self.rel(rep), "--video", "--audio", "--time")
            self.assertEqual(timed.returncode, 0, timed.stdout)
            keep = lambda t: [l for l in t.stdout.replace(chr(13), "").splitlines() if not l.startswith("time ")]
            self.assertEqual(keep(plain), keep(timed))
            for what in ("game", "video", "audio"):
                m = re.search(r"time %s\s*: mean ([\d.]+) us, median ([\d.]+) us, 99th percentile ([\d.]+) us, worst ([\d.]+) us \((\d+) frames\)" % what, timed.stdout)
                self.assertIsNotNone(m, what)
                mean, med, p99, worst = (float(m.group(i)) for i in range(1, 5))
                self.assertTrue(0 < med <= p99 <= worst and mean > 0, (what, m.group(0)))
                self.assertEqual(int(m.group(5)), 2600)
            self.assertNotIn("time", plain.stdout)

    def test_the_last_picture_can_be_written(self):
        rep, _ = self.session("keys")
        cc = self.folders[0][0]
        ppm = os.path.join(WORK, "last.ppm")
        r = self.run_shell(cc, "run", self.rel(rep), "--frames", "1200", "--ppm", self.rel(ppm))
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(ppm, "rb") as fh:
            data = fh.read()
        self.assertTrue(data.startswith(b"P6\n384 240\n255\n"))
        self.assertEqual(len(data), len(b"P6\n384 240\n255\n") + 384 * 240 * 3)
        body = data[len(b"P6\n384 240\n255\n"):]
        self.assertGreater(len(set(body[i:i + 3] for i in range(0, len(body), 3 * 50))), 3, "a picture, not one colour")


if __name__ == "__main__":
    unittest.main()
