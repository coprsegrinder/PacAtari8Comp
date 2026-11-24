"""Stage 57: tests of tools/analyze_io.py and docs/33-input-output.md.  Run:  python -I tests/test_io.py   (the raw logs are local; the tests read analysis/evidence-io-summary.txt)"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_io as I  # noqa: E402


def summary():
    with open(I.SUMMARY, encoding="utf-8") as fh:
        return fh.read()


class Static(unittest.TestCase):
    def test_inventory(self):
        st = I.sites()
        self.assertEqual(len(st), 133)
        regs = {I.key_of(s) for s in st}
        self.assertEqual(len(regs), 51)
        for r in regs:
            self.assertIn(r, I.PURPOSE, hex(r))
        for s in st:
            self.assertFalse(0xD300 <= s["op"] <= 0xD3FF)                          # the PIA is never addressed
            self.assertTrue(s["op"] in I.OS_ZP or 0x0200 <= s["op"] <= 0x02FF or 0xD000 <= s["op"] <= 0xD7FF)

    def test_no_other_hardware_or_os_address_is_addressed(self):
        import analyze_stack as AS
        rom, F, owner = AS.load()
        found = {a: (m, op) for a, (n, m, mode, op) in rom.ins.items() if isinstance(op, int) and mode in ("abs", "abx", "aby", "zp", "zpx") and (0xD000 <= op <= 0xFFFF or 0x0300 <= op <= 0x03FF or 0x0200 <= op <= 0x02FF)}
        calls = {a: v for a, v in found.items() if v[0] in ("jsr", "jmp")}
        self.assertEqual(calls, {0xA460: ("jsr", 0xE45C), 0xA60D: ("jmp", 0xE462)})   # SETVBV (Start) and XITVBV (the end of the vertical-blank handler): the only two uses of the OS ROM
        self.assertEqual(set(found) - set(calls), {s["pc"] for s in I.sites() if s["op"] >= 0x0200})

    def test_directions(self):
        by = {s["pc"]: s for s in I.sites()}
        self.assertEqual(by[0xA504]["dir"], "r")                                   # lda CONSOL
        self.assertEqual(by[0xA4FA]["dir"], "r")                                   # lda STRIG0
        self.assertEqual(by[0xB1A1]["dir"], "r")                                   # lda STICK0,x
        self.assertEqual(by[0xA453]["dir"], "w")                                   # sta IRQEN

    def test_probe_lines(self):
        L = I.probe_lines()
        self.assertEqual(len(L), 133)
        self.assertIn('bt a507 "IO A504 a=%04X v=%02X" $D01F @a', L)             # a load is traced at the next instruction: the value the game gets
        self.assertIn('bt a451 "IO A451 a=%04X v=%02X" $0010 @a', L)


class Live(unittest.TestCase):
    def test_every_instruction_executed(self):
        t = summary()
        self.assertIn("133 I/O instructions in the ROM, 133 executed in these runs", t)
        self.assertIn("I/O instructions not executed in these runs: 0", t)
        self.assertIn("11 harness logs", t)

    def test_input_values(self):
        lines = {l.split()[0]: l for l in summary().splitlines() if l.startswith(("STICK0", "STRIG0", "STRIG1", "CONSOL", "CH ", "RANDOM", "M2PF"))}
        self.assertIn("0278 0279", lines["STICK0"])                                # both players' sticks were read
        for v in ("06", "07", "0A", "0B", "0D", "0E", "0F"):
            self.assertIn(v, lines["STICK0"].split("|")[-1].split())
        self.assertEqual(lines["STRIG0"].split("|")[-1].split(), ["00", "01"])
        self.assertEqual(lines["STRIG1"].split("|")[-1].split(), ["00", "01"])
        self.assertEqual(lines["CONSOL"].split("|")[-1].split(), ["00", "01", "02", "03", "04", "05", "06", "07"])
        self.assertEqual(lines["CH"].split("|")[-1].split(), ["21", "FF"])


class Document(unittest.TestCase):
    def test_document_is_current(self):
        with open(os.path.join(ROOT, "docs", "33-input-output.md"), encoding="utf-8", newline="") as fh:
            have = fh.read().replace("\r\n", "\n")
        self.assertEqual(have, "\n".join(I.doc_lines()) + "\n", "run: python -I tools/analyze_io.py --doc docs/33-input-output.md")
        self.assertNotIn("NOT DESCRIBED", have)
        self.assertNotIn("NOT YET RUN", have)

    def test_summary_aggregation_notices_missing_instructions(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "io-x.txt")
            with open(p, "w") as fh:
                fh.write("IO A504 a=D01F v=07\nIO A504 a=D01F v=06\nnoise\n".replace("\n", "\n"))
            L = I.summary_lines([p])
            self.assertIn("133 I/O instructions in the ROM, 1 executed in these runs, 2 accesses printed", L[0])
            self.assertTrue(any("not executed" in x and "132" in x for x in L))


if __name__ == "__main__":
    unittest.main()
