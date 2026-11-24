"""Stage 80a (docs/51): the asset blob (tools/make_c_assets.py) and its C loader (src/c/assets) .
The blob is derived from the ROM; the C loader, built with clang and gcc, loads it through platform/fs.c and its 64 KB RAM image must equal (1) the reference loader of tools/asset_pack.py and
(2) the RAM that the concrete 6502 builds when it runs `Start` (the character sets, the maze, the tables; the OS font page is the pack's font), byte for byte.  The Python reader of the format here is
written separately from the C one.  Negative controls: every way a blob can be wrong is refused with its own message (a flipped byte, a short file, magic, version, schema, a duplicate name, an entry
past the end, a bad kind, a bad name, stray bytes), and a blob with a changed content byte (checksum repaired) is caught by the image comparison."""
import hashlib
import os
import random
import shutil
import struct
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import c_blob  # noqa: E402
import algorithm_models as A  # noqa: E402
import asset_pack as AP  # noqa: E402
import make_c_assets as MA  # noqa: E402

OUT = os.path.join("build", "t80a")
HEADER = 44


def build(cc):
    if not (shutil.which(cc) and shutil.which("cmake") and shutil.which("ninja")):
        return None
    out = os.path.join(ROOT, "build", "c-" + cc)
    subprocess.run(["cmake", "-S", os.path.join(ROOT, "src", "c"), "-B", out, "-G", "Ninja", "-DCMAKE_C_COMPILER=" + cc], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", out], check=True, capture_output=True)
    c_blob.ensure(out)
    return out


def check_exe(folder):
    return os.path.join(folder, "tests", "assets_check" + (".exe" if os.name == "nt" else ""))


def parse(blob):
    """the format of tools/make_c_assets.py read in Python: -> (header dict, [(name, kind, addr, data)])"""
    assert blob[:4] == b"PMAB"
    version, schema, n, reserved = struct.unpack_from("<HHHH", blob, 4)
    assert MA.fnv1a(blob[:-4]) == struct.unpack_from("<I", blob, len(blob) - 4)[0]
    pos, es = HEADER, []
    for _ in range(n):
        ln = blob[pos]
        name = blob[pos + 1:pos + 1 + ln].decode("ascii")
        kind, addr, size = struct.unpack_from("<BII", blob, pos + 1 + ln)
        pos += 1 + ln + 9
        es.append((name, kind, addr, blob[pos:pos + size]))
        pos += size
    assert pos == len(blob) - 4
    return {"version": version, "schema": schema, "count": n, "reserved": reserved, "sha": blob[12:44]}, es


def repair(b):
    """recompute the trailer of a blob that was changed"""
    b = bytearray(b[:-4])
    return bytes(b + struct.pack("<I", MA.fnv1a(b)))


class AssetsInC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(AP.ROM_PATH):
            raise unittest.SkipTest("no ROM (the blob is derived from it)")
        cls.P = AP.build()
        cls.blob = MA.blob(cls.P)
        os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
        cls.rel = os.path.join(OUT, "assets.pmab")
        with open(os.path.join(ROOT, cls.rel), "wb") as fh:
            fh.write(cls.blob)
        cls.folders = [(cc, f) for cc, f in ((cc, build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")
        # the RAM that the concrete 6502 builds when it runs Start's expansion, with the pack's font page
        mem = A.started_machine().mem
        exp = bytearray(0x10000)
        for lo, hi in ((0x3000, 0x3000 + 808), (0x1808, 0x1808 + 192), (0x0800, 0x0800 + 920), (0x0600, 0x0800)):
            exp[lo:hi] = bytes(mem[lo:hi])
        f = bytes.fromhex("".join(cls.P["font"]["rows"]))
        exp[0xE000:0xE000 + len(f)] = f
        cls.expected = bytes(exp)
        cls.exp_rel = os.path.join(OUT, "expected_ram.bin")
        with open(os.path.join(ROOT, cls.exp_rel), "wb") as fh:
            fh.write(cls.expected)

    def run_c(self, folder, *args):
        return subprocess.run([check_exe(folder)] + list(args), cwd=ROOT, capture_output=True, text=True)

    def blob_file(self, name, data):
        rel = os.path.join(OUT, name)
        with open(os.path.join(ROOT, rel), "wb") as fh:
            fh.write(data)
        return rel

    # ---- the blob ----
    def test_the_blob_is_deterministic_and_holds_the_pack(self):
        self.assertEqual(MA.blob(AP.build()), self.blob)
        h, es = parse(self.blob)
        self.assertEqual((h["version"], h["schema"], h["reserved"]), (1, AP.SCHEMA, 0))
        self.assertEqual(h["sha"].hex(), self.P["rom"]["sha256"])
        self.assertEqual(h["count"], 6 + len(self.P["regions"]))
        by = {n: (k, a, d) for n, k, a, d in es}
        for r in self.P["regions"]:
            k, a, d = by["region." + r["name"]]
            self.assertEqual((a, d), (int(r["addr"], 16), bytes.fromhex(r["bytes"])), r["name"])
        self.assertEqual(sum(len(by["region." + r["name"]][2]) for r in self.P["regions"]), 2246)
        self.assertEqual(by["maze"][2], bytes(c for row in self.P["maze"]["codes"] for c in row))
        self.assertEqual(by["ram_0600"][:2], (MA.KIND_RAM, 0x0600))
        self.assertEqual(len(by["ram_0600"][2]), 512)
        self.assertEqual(by["rom_ba00"], (MA.KIND_ROM_WINDOW, 0xBA00, MA.S.ROM[0x1A00:0x2000]))
        self.assertEqual(by["font"][2], bytes.fromhex("".join(self.P["font"]["rows"])))

    # ---- the C loader ----
    def test_loader_image_equals_the_reference_loader_and_the_6502(self):
        ref = bytearray(AP.ram_image(self.P))                                 # the reference loader knows 472 of the 512 table bytes: the 40 after them are the rest of the nibble split
        ref[0x07D8:0x0800] = self.expected[0x07D8:0x0800]
        self.assertEqual(self.expected, bytes(ref))                           # the 6502's RAM and the reference loader agree
        for cc, folder in self.folders:
            r = self.run_c(folder, self.rel, self.exp_rel)
            self.assertEqual(r.returncode, 0, cc + ": " + r.stdout)
            self.assertIn("assets_check: ok, 85 entries", r.stdout)
            dump = os.path.join(OUT, "dump-%s.bin" % cc)
            r = self.run_c(folder, "--dump", self.rel, dump)
            self.assertEqual(r.returncode, 0, r.stdout)
            with open(os.path.join(ROOT, dump), "rb") as fh:
                self.assertEqual(fh.read(), self.expected, cc)

    def test_a_changed_content_byte_is_caught_by_the_image_comparison(self):
        _, es = parse(self.blob)
        pos = HEADER
        for name, kind, addr, data in es:                      # find the maze entry and change one of its bytes, then repair the checksum
            pos += 1 + len(name) + 9
            if name == "maze":
                b = bytearray(self.blob)
                b[pos + 17] ^= 0x20
                rel = self.blob_file("tampered_maze.pmab", repair(bytes(b)))
                for cc, folder in self.folders:
                    r = self.run_c(folder, rel, self.exp_rel)
                    self.assertEqual(r.returncode, 1, cc + ": " + r.stdout)
                    self.assertTrue("FAILED" in r.stdout, r.stdout)       # the maze check and the image comparison both fail
                break
            pos += len(data)
        else:
            self.fail("no maze entry")

    def refused(self, name, data, text):
        rel = self.blob_file(name, data)
        for cc, folder in self.folders:
            r = self.run_c(folder, rel)
            self.assertEqual(r.returncode, 1, "%s %s: %s" % (cc, name, r.stdout))
            self.assertIn("assets_check: error: " + text, r.stdout, "%s %s" % (cc, name))

    def test_every_malformation_is_refused_with_its_own_message(self):
        b = self.blob
        flipped = bytearray(b)
        flipped[300] ^= 1
        self.refused("flip.pmab", bytes(flipped), "bad checksum")
        self.refused("short.pmab", b[:20], "the blob is too short")
        self.refused("cut.pmab", b[:-100], "bad checksum")
        self.refused("empty.pmab", b"", "the blob is too short")
        m = bytearray(b)
        m[0] = ord("X")
        self.refused("magic.pmab", repair(bytes(m)), "bad magic")
        v = bytearray(b)
        v[4] = 2
        self.refused("version.pmab", repair(bytes(v)), "unknown format version")
        s = bytearray(b)
        s[6] = 1
        self.refused("schema.pmab", repair(bytes(s)), "unknown pack schema")
        n = bytearray(b)
        n[8:10] = struct.pack("<H", 129)
        self.refused("many.pmab", repair(bytes(n)), "too many entries")
        # an entry list that ends early: the count says one entry more than there is
        n = bytearray(b)
        n[8:10] = struct.pack("<H", 86)
        self.refused("count_up.pmab", repair(bytes(n)), "an entry is malformed")
        # one entry fewer than there is: stray bytes before the trailer
        n = bytearray(b)
        n[8:10] = struct.pack("<H", 84)
        self.refused("count_down.pmab", repair(bytes(n)), "bytes between the last entry")
        # the first entry's size runs past the end
        e = bytearray(b)
        ln = e[HEADER]
        struct.pack_into("<I", e, HEADER + 1 + ln + 5, 0x7FFFFFFF)
        self.refused("size.pmab", repair(bytes(e)), "an entry is malformed")
        # a kind that does not exist
        e = bytearray(b)
        e[HEADER + 1 + ln] = 9
        self.refused("kind.pmab", repair(bytes(e)), "an entry is malformed")
        # a name with a space, and an empty name
        e = bytearray(b)
        e[HEADER + 1] = 0x20
        self.refused("name.pmab", repair(bytes(e)), "an entry is malformed")
        e = bytearray(b)
        e[HEADER] = 0
        self.refused("noname.pmab", repair(bytes(e)), "an entry is malformed")
        # a duplicate name: the second entry gets the name of the first (same length: "maze" and "font")
        _, es = parse(b)
        first, second = es[2][0], es[4][0]
        self.assertEqual((first, second), ("maze", "font"))
        d = bytearray(b)
        pos = HEADER
        for name, kind, addr, data in es[:4]:
            pos += 1 + len(name) + 9 + len(data)
        d[pos + 1:pos + 1 + 4] = b"maze"
        self.refused("dup.pmab", repair(bytes(d)), "two entries have the same name")

    def test_overlapping_ram_parts_are_refused_by_the_layout_check(self):
        _, es = parse(self.blob)
        pos = HEADER
        for name, kind, addr, data in es:
            pos += 1 + len(name)
            if name == "maze":
                b = bytearray(self.blob)
                struct.pack_into("<I", b, pos + 1, 0x0600)           # the maze where the tables are
                rel = self.blob_file("overlap.pmab", repair(bytes(b)))
                for cc, folder in self.folders:
                    r = self.run_c(folder, rel)
                    self.assertEqual(r.returncode, 1, r.stdout)
                    self.assertIn("FAILED", r.stdout)
                return
            pos += 9 + len(data)
        self.fail("no maze entry")

    def test_the_file_goes_through_the_sandbox(self):
        for cc, folder in self.folders:
            r = self.run_c(folder, os.path.abspath(os.path.join(ROOT, self.rel)))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("cannot be opened", r.stdout)
            r = self.run_c(folder, os.path.join("..", "x.pmab"))
            self.assertIn("cannot be opened", r.stdout)

    def test_a_missing_file_is_refused(self):
        for cc, folder in self.folders:
            r = self.run_c(folder, os.path.join(OUT, "nothing.pmab"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("cannot be opened", r.stdout)


def install_exe(folder):
    return os.path.join(folder, "assets", "install_assets" + (".exe" if os.name == "nt" else ""))


class InstallFromRom(unittest.TestCase):
    """The C port installs its assets itself from the owner's ROM: it recognises the NTSC cartridge by size and sha256, cuts out and expands the data, and writes the blob (src/c/assets/rom_install.c).
    The blob it writes is the one tools/make_c_assets.py writes, byte for byte; a ROM that is not that cartridge is refused and nothing is written."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(AP.ROM_PATH):
            raise unittest.SkipTest("no ROM")
        with open(AP.ROM_PATH, "rb") as fh:
            cls.rom = fh.read()
        cls.blob = MA.blob(AP.build())
        os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
        cls.folders = [(cc, f) for cc, f in ((cc, build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")

    def install(self, folder, rom_rel, out_rel):
        return subprocess.run([install_exe(folder), rom_rel, out_rel], cwd=ROOT, capture_output=True, text=True)

    def put(self, name, data):
        rel = os.path.join(OUT, name)
        with open(os.path.join(ROOT, rel), "wb") as fh:
            fh.write(data)
        return rel

    def test_the_installed_blob_equals_the_python_blob(self):
        rom_rel = self.put("rom_ok.rom", self.rom)
        for cc, folder in self.folders:
            out = os.path.join(OUT, "installed-%s.pmab" % cc)
            if os.path.exists(os.path.join(ROOT, out)):
                os.remove(os.path.join(ROOT, out))
            r = self.install(folder, rom_rel, out)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("install_assets: ok", r.stdout)
            with open(os.path.join(ROOT, out), "rb") as fh:
                self.assertEqual(fh.read(), self.blob, cc)

    def test_the_default_paths(self):
        for cc, folder in self.folders:
            r = subprocess.run([install_exe(folder)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("original/Pac-Man.rom -> resources/pack/assets.pmab", r.stdout)
            with open(os.path.join(ROOT, "resources", "pack", "assets.pmab"), "rb") as fh:
                self.assertEqual(fh.read(), self.blob)

    def refused(self, name, data, text):
        rom_rel = self.put(name, data)
        for cc, folder in self.folders:
            out = os.path.join(OUT, "refused-%s-%s.pmab" % (cc, name))
            if os.path.exists(os.path.join(ROOT, out)):
                os.remove(os.path.join(ROOT, out))
            r = self.install(folder, rom_rel, out)
            self.assertEqual(r.returncode, 1, "%s %s: %s" % (cc, name, r.stdout))
            self.assertIn("install_assets: error: " + text, r.stdout, name)
            self.assertFalse(os.path.exists(os.path.join(ROOT, out)), name + ": nothing may be written")

    def test_a_rom_that_is_not_the_ntsc_cartridge_is_refused_and_nothing_is_written(self):
        for pos in (0, 1, 0x1E2, 0x1D7A, 0x1FFF):                  # one changed byte anywhere: code, a stream, a table, the header
            b = bytearray(self.rom)
            b[pos] ^= 0x01
            self.refused("rom_flip_%04x.rom" % pos, bytes(b), "the ROM is not the NTSC Pac-Man cartridge")
        self.refused("rom_short.rom", self.rom[:-1], "the ROM is not 8192 bytes")
        self.refused("rom_long.rom", self.rom + b"\0", "the ROM is not 8192 bytes")
        self.refused("rom_empty.rom", b"", "the ROM is not 8192 bytes")
        self.refused("rom_zero.rom", bytes(8192), "the ROM is not the NTSC Pac-Man cartridge")
        self.refused("rom_with_header.rom", bytes(16) + self.rom, "the ROM is not 8192 bytes")   # an .car / .a8 style header is not accepted: the plain image only

    def test_a_missing_rom_and_a_path_outside_the_main_folder_are_refused(self):
        for cc, folder in self.folders:
            r = self.install(folder, os.path.join(OUT, "no_such.rom"), os.path.join(OUT, "x.pmab"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("cannot be opened", r.stdout)
            r = self.install(folder, os.path.join("..", "Pac-Man.rom"), os.path.join(OUT, "x.pmab"))
            self.assertIn("cannot be opened", r.stdout)
            rom_rel = self.put("rom_ok2.rom", self.rom)
            r = self.install(folder, rom_rel, os.path.join("..", "escape.pmab"))             # the blob may only be written below the main folder
            self.assertEqual(r.returncode, 1)
            self.assertIn("cannot be written", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(os.path.dirname(ROOT), "escape.pmab")))

    def test_sha256_of_the_c_equals_hashlib_at_every_padding_boundary(self):
        rng = random.Random(80)
        sizes = [0, 1, 3, 55, 56, 57, 63, 64, 65, 119, 120, 121, 127, 128, 129, 1000, 8192, 20000]
        for cc, folder in self.folders:
            for n in sizes:
                data = bytes(rng.randrange(256) for _ in range(n))
                rel = self.put("sha_%d.bin" % n, data)
                r = subprocess.run([check_exe(folder), "--sha256", rel], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.stdout.strip(), hashlib.sha256(data).hexdigest(), "%s %d bytes" % (cc, n))
            rel = self.put("sha_abc.bin", b"abc")
            r = subprocess.run([check_exe(folder), "--sha256", rel], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")   # FIPS 180-4 example

    def test_programs_refuse_to_run_without_the_tables(self):
        """the tables are installed from the blob: a main folder without it gives zero tables, and the test programs say so and stop"""
        empty = os.path.join(ROOT, OUT, "empty_main")
        os.makedirs(empty, exist_ok=True)
        for cc, folder in self.folders:
            for exe in ("vector_runner", "world_check", "platform_check"):
                path = os.path.join(folder, "tests", exe + (".exe" if os.name == "nt" else ""))
                args = [path, "--root", empty, "x.vec"] if exe == "vector_runner" else [path]
                r = subprocess.run(args, cwd=empty, capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, "%s %s: %s" % (cc, exe, r.stdout))
                self.assertIn("tables not installed", r.stdout)

    def test_the_installed_tables_equal_the_python_tables_derived_from_the_rom(self):
        """world_check dumps every table the C holds after the boot; tools/core_tables.py derives the same tables from the ROM with other code"""
        import core_tables as T
        import make_core_tables as MT
        for cc, folder in self.folders:
            exe = os.path.join(folder, "tests", "world_check" + (".exe" if os.name == "nt" else ""))
            img = self.put("zero_image.bin", bytes(65536))
            r = subprocess.run([exe, img, os.path.join(OUT, "wc_back.bin"), os.path.join(OUT, "wc_dump.txt")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            seen = {}
            with open(os.path.join(ROOT, OUT, "wc_dump.txt"), encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("T "):
                        _, name, addr, count, hexs = line.split()
                        seen[name] = (int(addr), int(count), bytes.fromhex(hexs))
            for name, src, addr, n, _ in list(MT.TABLES) + list(MT.IMAGES):
                self.assertEqual(seen[name], (addr, n, bytes(getattr(T, name))), cc + " " + name)

    def test_no_byte_of_the_rom_is_in_the_c_sources(self):
        """every 12-byte window of the ROM (windows that are plain runs excluded) is looked for among the byte literals of every C file: none may be there (the open font is not the ROM's)"""
        import re
        rom = self.rom
        wins = {rom[i:i + 12] for i in range(len(rom) - 11) if len(set(rom[i:i + 12])) >= 4}
        found = []
        for dirpath, _, files in os.walk(os.path.join(ROOT, "src", "c")):
            for f in files:
                if f.endswith((".c", ".h")):
                    with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                        toks = bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})(?![0-9A-Fa-f])", fh.read()))
                    hits = [w for w in wins if w in toks]
                    if hits:
                        found.append((f, len(hits)))
        self.assertEqual(found, [])
        # the scan can fail: a source with 12 ROM bytes in it is caught
        probe = ", ".join("0x%02X" % b for b in next(iter(sorted(wins))))
        toks = bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})(?![0-9A-Fa-f])", probe))
        self.assertTrue(any(w in toks for w in wins))

    def test_the_layout_files_hold_no_byte_of_the_rom(self):
        """rom_layout.c is names, addresses, sizes, the hash and the open font: no run of 8 bytes of the ROM's non-code data appears in it"""
        with open(os.path.join(ROOT, "src", "c", "assets", "rom_layout.c"), encoding="utf-8") as fh:
            text = fh.read().lower()
        _, es = parse(self.blob)
        for name, kind, addr, data in es:
            if name.startswith("region.") and len(data) >= 8:
                needle = ", ".join("0x%02x" % b for b in data[:8])
                self.assertNotIn(needle, text, name)


if __name__ == "__main__":
    unittest.main()
