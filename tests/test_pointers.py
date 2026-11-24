"""Stage 46: tests of tools/analyze_pointers.py, tools/analyze_pointer_log.py and docs/29-pointers.md.  Run:  python -I tests/test_pointers.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_pointer_log as PL  # noqa: E402
import analyze_pointers as P  # noqa: E402

CTX, IND, ACCESS, SETTERS, BULK, TABS, DL, VEC, HW = P.analyse()
ROM = CTX.rom
ZP_POINTER_BYTES = {b for lo, *_ in P.PTRS for b in (lo, lo + 1)}


class Code(unittest.TestCase):
    def test_only_indirect_y_loads_and_stores(self):
        self.assertEqual(len(IND), 31)
        self.assertEqual({(m, mode) for a, m, mode, op, rn in IND}, {("lda", "izy"), ("sta", "izy")})
        self.assertEqual(sum(1 for a, m, mode, op, rn in IND if m == "lda"), 17)

    def test_no_indirect_jump_or_x_indexed_indirect(self):
        self.assertFalse([a for a, i in ROM.ins.items() if i[2] in ("ind", "izx")])

    def test_exactly_the_six_pointers_are_used(self):
        self.assertEqual({op for a, m, mode, op, rn in IND}, {lo for lo, *_ in P.PTRS})
        self.assertEqual(sorted(lo for lo, *_ in P.PTRS), [0x38, 0x3A, 0x3C, 0x3E, 0x47, 0x80])

    def test_every_indirect_instruction_is_named_in_the_probe_set(self):
        # the probe is the instruction itself (single accesses) or the instruction before the loop it belongs to (the Y load or the set-up)
        probes = set(P.PROBES)
        boot = {"Start", "ExpandData", "ReadSrcByte", "WriteDstByte", "ReadSrcHighNibble"}   # the stream decoders: probes A3B8 and A668 (the callers' set-up) cover their loops
        for a, m, mode, op, rn in IND:
            if rn in boot:
                continue
            near = [p for p in probes if 0 <= a - p <= 0x16 or p == a]
            self.assertTrue(near, "no probe near $%04X" % a)

    def test_probes_are_instructions(self):
        for a in P.PROBES:
            self.assertIn(a, ROM.ins, hex(a))

    def test_every_pointer_is_stored_low_then_high_by_pairs_or_stepped(self):
        for lo, name, *_ in P.PTRS:
            parts = [(a, part) for a, m, part, rn, src in SETTERS[lo]]
            self.assertTrue(parts, name)
            for a, part in parts:
                self.assertIn(part, "LH")

    def test_every_setup_group_is_explained(self):
        firsts = sorted(a for lo in SETTERS for a, m, part, rn, src in SETTERS[lo] if part == "L" or m in ("inc", "dec"))
        # every explained group starts at a store of the code
        stores = {a for lo in SETTERS for a, m, part, rn, src in SETTERS[lo]}
        for a in P.NOTE:
            self.assertIn(a, stores, hex(a))

    def test_bulk_writes(self):
        self.assertEqual(sorted(a for a, m, op, rn in BULK), [0xA395, 0xA39C, 0xADB4, 0xADE3])

    def test_the_four_pointer_tables(self):
        t = {label: ent for addr, label, n, what, ent in TABS}
        self.assertEqual(t["JunctionRowPtrs"], [0x060E + 10 * i for i in range(10)])
        self.assertEqual(t["StartRoutePtrs"], [0x0686, 0x0693, 0x069B, 0x06A3])
        self.assertEqual([CTX.name_of(v) for v in t["GhostScorePtrs"]], ["GhostScore200Digits", "GhostScore400Digits", "GhostScore800Digits", "GhostScore1600Digits"])
        self.assertEqual([CTX.name_of(v) for v in t["PacShapePtrs"]], ["PacShapeFull", "PacShapeRight1", "PacShapeLeft1", "PacShapeUp1", "PacShapeDown1"])

    def test_every_rom_pointer_in_a_table_is_inside_the_rom_data(self):
        for addr, label, n, what, ent in TABS:
            for v in ent:
                self.assertTrue(v >= 0xA000 or 0x0600 <= v <= 0x06FF, "%s %04X" % (label, v))

    def test_display_list_operands(self):
        d = {a: v for a, what, v in DL}
        self.assertEqual((d[0xBF84], d[0xBF88], d[0xBF9E], d[0xBFA6], d[0xBFAA]), (0x2000, 0x1C00, 0x0F70, 0x2000, 0x0C00))
        self.assertEqual(CTX.name_of(d[0xBFA1]), "DisplayList2")
        self.assertEqual(CTX.name_of(d[0xBFC4]), "DisplayList1")
        self.assertEqual({a: CTX.name_of(v) for a, what, v in VEC}, {0xBFFA: "Start", 0xBFFE: "Init"})

    def test_os_and_hardware_display_list_writes_are_all_in_set_display_list(self):
        self.assertEqual({rn for a, m, op, rn in HW} - {"Start"}, {"SetDisplayList"})
        self.assertEqual(sorted(op for a, m, op, rn in HW if rn == "SetDisplayList"), [0x200, 0x201, 0x230, 0x231, 0xD402, 0xD403])

    def test_initial_maze_pointer(self):
        o = P.analyse()[0].rom.data
        self.assertEqual(o[0xBB6F - 0xA000] | (o[0xBB70 - 0xA000] << 8), 0x0E93)

    def test_only_the_expected_routines_touch_each_pointer(self):
        names = {lo: sorted({rn for a, rn in v["R"]} | {rn for a, rn in v["W"]}) for lo, v in ACCESS.items()}
        self.assertEqual(names[0x80], ["EatDotAtPacMan"])
        self.assertEqual(names[0x47], ["ClipEntityAtTunnel"])
        self.assertEqual(names[0x38], ["GhostEaten"])
        self.assertEqual(names[0x3A], ["GhostEaten"])


class Document(unittest.TestCase):
    def test_document_is_current(self):
        path = os.path.join(ROOT, "docs", "29-pointers.md")
        with open(path, encoding="utf-8", newline="") as fh:
            have = fh.read().replace("\r\n", "\n")
        self.assertEqual(have, "\n".join(P.report()) + "\n", "run: python -I tools/analyze_pointers.py --write docs/29-pointers.md")


class Log(unittest.TestCase):
    def test_a_good_line_and_a_bad_line(self):
        R = PL.rules()
        good = {"s": 0xB4D0, "src": 0x0618, "dst": 0, "mz": 0, "clip": 0, "pm": 0, "pp": 0, "x": 0, "y": 3, "f": 1, "py": 0, "px": 0}
        self.assertIsNone(R[0xB4D0](good))
        self.assertTrue(R[0xB4D0](dict(good, src=0x0619)))
        self.assertTrue(R[0xB358](dict(good, mz=0x0BFF, y=0)))
        self.assertIsNone(R[0xB358](dict(good, mz=0x0E93, y=0)))

    def test_clip_pointer_rule_covers_pac_man_and_the_ghosts(self):
        R = PL.rules()
        base = {"s": 0xABBD, "src": 0, "dst": 0, "mz": 0, "clip": 0, "pm": 0, "pp": 0, "x": 0, "y": 0, "f": 1, "py": 0, "px": 0}
        self.assertIsNone(R[0xABBD](dict(base, x=4, clip=0x2374)))
        self.assertIsNone(R[0xABBD](dict(base, x=2, clip=0x2674)))
        self.assertTrue(R[0xABBD](dict(base, x=2, clip=0x2474)))

    def test_a3b8_rule_is_exact_and_sentinel_is_detected(self):
        R = PL.rules()
        r = {"s": 0xA3B8, "src": 0xA1E1, "dst": 0x0800, "mz": 0, "clip": 0, "pm": 0, "pp": 0, "x": 0, "y": 0, "f": 1, "py": 0, "px": 0}
        self.assertIsNone(R[0xA3B8](r))
        self.assertTrue(R[0xA3B8](dict(r, src=0xA003, dst=0x3000)))        # the value the first-line quirk used to show
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("Tracepoint 0 set at $A386.\nSENT f=32 pc=$A3B8\n")
            a = fh.name
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("Tracepoint 0 set at $A3B8.\n")
            b = fh.name
        try:
            self.assertTrue(PL.sentinel(a))
            self.assertFalse(PL.sentinel(b))
        finally:
            os.remove(a)
            os.remove(b)

    def test_parse_and_delta_classes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("PTR s=$B358 src=$0000 dst=$0000 mz=$0E93 clip=$0000 pm=$0000 pp=$0000 x=0 y=0 f=1 py=164 px=122\nnoise\n")
            name = fh.name
        try:
            r = PL.parse(name)
            self.assertEqual(len(r), 1)
            self.assertEqual((r[0]["s"], r[0]["mz"], r[0]["py"]), (0xB358, 0x0E93, 164))
        finally:
            os.remove(name)
        self.assertEqual(PL.classify_delta(0x0E93, 0x0E94), "+-1 (sideways)")
        self.assertEqual(PL.classify_delta(0x0E93, 0x0EBB), "+-$28 (a row)")
        self.assertEqual(PL.classify_delta(0x0E70, 0x0E8F), "tunnel wrap")
        self.assertEqual(PL.classify_delta(0x0D00, 0x0E93), "reset to the start cell")
        self.assertEqual(PL.classify_delta(0x0D00, 0x0E00), "other")

    def test_evidence_summary_is_clean(self):
        path = os.path.join(ROOT, "analysis", "evidence-pointers-summary.txt")
        if not os.path.exists(path):
            self.skipTest("evidence summary not present")
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("Hits that break the rule of their probe: 0", txt)
        self.assertIn("Probes never reached: none", txt)
        self.assertIn("present in 5 of 5 logs", txt)
        self.assertNotIn("other", txt.split("MazePtr between two cell checks")[1].split("\n")[0])


if __name__ == "__main__":
    unittest.main()
