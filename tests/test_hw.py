"""Stage 59 (API / hardware tracing): the analyzer tools/analyze_hw.py on a synthetic log (it must notice a chip that does not follow its shadow or its last write), and the committed evidence summary and chapter."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_hw as H  # noqa: E402

DUMP = """DMACTL = {dmactl:02X}  : normal
CHACTL = 02  : invert
DLIST  = BF81
PMBASE = 20
CHBASE = E0
NMIEN  = C0  : dli vbi
Player  0: color = 44, pos = 50, size=0, data = 00
Player  1: color = 4A, pos = 00, size=0, data = 00
Player  2: color = D8, pos = 00, size=0, data = 00
Player  3: color = 28, pos = 00, size=0, data = 00
Missile 0: color = 28, pos = 00, size=0, data = 00
Missile 1: color = 28, pos = 00, size=0, data = 00
Missile 2: color = 28, pos = 00, size=0, data = 00
Missile 3: color = 28, pos = 00, size=0, data = 00
Playfield colors: 00 | 28 CA 94 46
PRIOR:  11 (pri= 0 , normal)
GRACTL: 03, player DMA, missile DMA
AUDF1: 10  AUDC1: A8  Output: 1
AUDF2: 00  AUDC2: 00  Output: 1
AUDF3: 00  AUDC3: 00  Output: 1
AUDF4: 00  AUDC4: 00  Output: 1
AUDCTL: 00, 17-bit poly, 64KHz
SKCTL: 07 | x
IRQEN:  C0, break key, keyboard
"""

VBI = "VBI f=%d rtclok=%d sdmctl=$3E sdl=$BF81 gprior=$11 col=28,CA,94,46,00 pcol=44,4A,D8,28 pokmsk=$C0 atract=00 drk=FE colrsh=00 chbas=E0 chact=02\n"


def log(dmactl, audf1):
    out = ["SETVBV a=$07 x=$A5 y=$FD f=39\n", "SETVBV_DONE vvblkd=$A5FD vvblki=$E7AE f=39\n"]
    for a, v in ((0xD000, 0x50), (0xD200, 0x10), (0xD201, 0xA8), (0xD400, 0x3E)):
        out.append("HWW a=$%04X v=$%02X pc=$A900 f=70 vp=10\n" % (a, v))
    out.append("DLI1 f=70 vp=39\n")
    out.append(VBI % (70, 5))
    out.append(DUMP.format(dmactl=dmactl).replace("AUDF1: 10", "AUDF1: %02X" % audf1))
    out.append(VBI % (71, 6))
    out.append(DUMP.format(dmactl=dmactl).replace("AUDF1: 10", "AUDF1: %02X" % audf1))
    return "".join(out)


def run(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "hw-test.txt")
        with open(p, "w") as fh:
            fh.write(text)
        S = H.new_state()
        H.process(p, S)
    return S


class Analyzer(unittest.TestCase):
    def test_good_log_has_no_violation(self):
        S = run(log(0x3E, 0x10).replace("f=70", "f=70"))
        S2 = run(log(0x3E, 0x10).replace("VBI f=70", "VBI f=100").replace("VBI f=71", "VBI f=101"))
        n = sum(v[0] for v in S2["checks"].values())
        self.assertGreater(n, 20)
        self.assertEqual(sum(v[1] for v in S2["checks"].values()), 0)
        self.assertEqual(sum(v[1] for v in S2["consistency"].values()), 0)
        self.assertEqual(S["vbi"], 2)
        self.assertEqual(S["vbi_gaps"], 0)

    def _late(self, dmactl, audf1):
        return run(log(dmactl, audf1).replace("VBI f=70", "VBI f=100").replace("VBI f=71", "VBI f=101"))

    def test_chip_that_differs_from_its_shadow_is_noticed(self):
        S = self._late(0x22, 0x10)
        self.assertGreater(S["checks"]["DMACTL = SDMCTL"][1], 0)
        self.assertGreater(S["consistency"]["DMACTL"][1], 0)

    def test_chip_that_differs_from_the_last_write_is_noticed(self):
        S = self._late(0x3E, 0x11)
        self.assertGreater(S["consistency"]["AUDF1"][1], 0)
        self.assertEqual(S["checks"]["DMACTL = SDMCTL"][1], 0)

    def test_frame_gap_is_noticed(self):
        S = run(log(0x3E, 0x10).replace("VBI f=71", "VBI f=75"))
        self.assertEqual(S["vbi_gaps"], 1)

    def test_writers(self):
        self.assertEqual(H.who(0xE791), "os")
        self.assertEqual(H.who(0xA573), "dli")
        self.assertEqual(H.who(0xA5FD), "game")
        self.assertEqual(H.who(0xB042), "game")


class Evidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(H.SUMMARY, encoding="utf-8") as fh:
            cls.txt = fh.read()

    def test_no_violation_anywhere(self):
        for ln in self.txt.splitlines():
            if "violations" in ln:
                self.assertIn(" 0 violations", ln, ln)

    def test_api_and_frame_facts(self):
        self.assertIn("SETVBV a=$07 x=$A5 y=$FD", self.txt)
        self.assertIn("vvblkd=$A5FD", self.txt)
        self.assertIn("frame gaps 0, OS clock (RTCLOK2) gaps 0", self.txt)

    def test_every_static_chip_write_site_was_seen(self):
        self.assertIn("71 of the 71 static chip-write sites; not a static site (or wrong register): 0", self.txt)
        self.assertIn("never seen writing in these sessions: none", self.txt)

    def test_static_site_count(self):
        self.assertEqual(len(H.static_write_sites()), 71)

    def test_chapter_exists(self):
        with open(os.path.join(ROOT, "docs", "35-api-hardware-tracing.md"), encoding="utf-8") as fh:
            doc = fh.read()
        for s in ("## 1. The result", "## 2. The OS side", "## 3. Shadow to chip", "## 4. The chips as the CPU drives them", "## 5. Reads", "## 6. Limits"):
            self.assertIn(s, doc)
        self.assertIn("0 violations", doc)


if __name__ == "__main__":
    unittest.main()
