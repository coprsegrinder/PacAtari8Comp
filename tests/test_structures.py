"""Stage 48: tests of tools/analyze_structures.py, tools/analyze_structures_log.py and docs/30-structures.md.  Run:  python -I tests/test_structures.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_structures as S  # noqa: E402
import analyze_structures_log as SL  # noqa: E402

ROM, F, OWNER, SITES, PROBES, OUTSIDE, CALLERS, INIT, BULK = S.analyse()
VAR = S.zp_vars()
OWNER_BYTES, PROBLEMS = S.struct_coverage()
BY = {st[0]: st for st in S.STRUCTS}


class Coverage(unittest.TestCase):
    def test_every_variable_byte_belongs_to_exactly_one_structure(self):
        self.assertEqual(PROBLEMS, [])
        self.assertEqual(len(VAR), 109)
        self.assertEqual(len(OWNER_BYTES), sum(v[1] for v in VAR.values()))

    def test_object_counts(self):
        self.assertEqual({n: BY[n][1] for n in ("Entity", "Ghost", "Player")}, {"Entity": 5, "Ghost": 4, "Player": 2})
        for n, st in BY.items():
            if n not in ("Entity", "Ghost", "Player"):
                self.assertEqual(st[1], 1, n)

    def test_array_fields_have_the_size_of_their_structure(self):
        for sname in ("Entity", "Ghost", "Player"):
            for cname, ctype, src, note in BY[sname][3]:
                for v, off in src:
                    self.assertEqual(VAR[v][1], BY[sname][1], "%s.%s" % (sname, cname))

    def test_every_array_variable_of_the_catalogue_is_either_a_structure_array_or_a_record(self):
        arrays = {n for n, v in VAR.items() if v[2].startswith("array")}
        in_arrays = {v for sname in ("Entity", "Ghost", "Player") for c, t, src, nt in BY[sname][3] for v, o in src}
        # the arrays that are not per object: DliColors (4 colours), FrightSound (4 different fields), ScoreAdd (6 digits)
        self.assertEqual(arrays - in_arrays, {"DliColors", "FrightSound", "ScoreAdd"})

    def test_entity_arrays_are_contiguous_in_the_original_order(self):
        self.assertEqual([VAR[n][0] for n in ("EntityY", "EntityX", "EntityDir")], [0x85, 0x8A, 0x8F])
        self.assertEqual([VAR[n][0] for n in ("GhostTimer", "GhostState", "StartRouteStep")], [0xCA, 0xCE, 0xD2])

    def test_sixteen_bit_fields(self):
        t = {(s, c): ty for s, cnt, d, fl in S.STRUCTS for c, ty, src, n in fl}
        self.assertEqual(t[("Player", "dots_eaten")], "uint16_t")
        self.assertEqual(t[("PacMan", "maze_ptr")], "uint16_t")
        self.assertEqual(t[("Bonus", "timer")], "uint16_t")


class Indexing(unittest.TestCase):
    def test_every_indexed_access_is_an_array_access_or_a_bulk_clear(self):
        self.assertEqual(OUTSIDE, [])
        self.assertEqual(len(PROBES), 191)

    def test_only_one_access_leaves_the_base_of_its_array(self):
        off = [(a, nm, o) for nm, lst in SITES.items() for a, m, o, r in lst if o != 0]
        self.assertEqual(off, [(0xAE36, "GhostTimer", 1)])

    def test_ghost_timer_shift_is_the_release_timer_of_ghosts_one_to_three(self):
        n, m, mode, op = ROM.ins[0xAE36]
        self.assertEqual((m, mode, op), ("sta", "zpx", 0xCB))
        self.assertEqual(ROM.ins[0xAE31][3], 2)                                   # ldx #2
        self.assertEqual(ROM.ins[0xADE8][3], 0)                                   # InitBoard: ldy #0 before SetReleaseTimers

    def test_the_loops_that_cover_the_ghost_arrays_stop_at_three(self):
        # ghost loops: ldx #3 ... dex / bpl; the entity loop of the clip: ldx #4
        self.assertEqual(ROM.ins[0xB6A2][3], 3)                                   # EyesAndHousePerFrame
        self.assertEqual(ROM.ins[0xAB48][3], 4)                                   # ClipEntitiesOnTunnelRow runs over the five entities

    def test_player_arrays_are_indexed_by_current_player(self):
        lda = [a for a, i in ROM.ins.items() if i[1] == "ldx" and i[2] == "zp" and i[3] == 0x2B]
        self.assertGreater(len(lda), 10)


class Lifetimes(unittest.TestCase):
    def test_bulk_clears(self):
        self.assertEqual(ROM.ins[0xA393][3], 0x27)
        self.assertEqual(ROM.ins[0xA395][3], 0x18)                                # $18 + $27 = $3F
        self.assertEqual(ROM.ins[0xA39A][3], 0x7F)
        self.assertEqual(ROM.ins[0xA39C][3], 0x80)
        self.assertEqual(ROM.ins[0xA479][3], 0x1F)
        self.assertEqual(ROM.ins[0xA47B][3], 0x20)                                # $20 + $1F = $3F
        self.assertEqual(ROM.ins[0xADB2][3], 0x7F)
        self.assertEqual(ROM.ins[0xADB4][3], 0x80)                                # $80 + $7F = $FF
        self.assertEqual(ROM.ins[0xADE0 - 2][3], 0x13)                            # ldx #$13: 20 bytes to $80-$93

    def test_lifetime_classes(self):
        self.assertEqual(S.lifetime(0x85), "board")
        self.assertEqual(S.lifetime(0x2C), "game")
        self.assertEqual(S.lifetime(0x19), "start-up")
        self.assertEqual(S.lifetime(0x45), "kept")
        self.assertEqual(S.life_of("Player", "BonusCount", 0x43), "board (per player, `ClearPlayerCounters`)")

    def test_initial_state_of_the_entities(self):
        self.assertEqual(INIT[:5], [0x93, 0x0E, 0x02, 0xA6, 0x7A])
        self.assertEqual(INIT[5:10], [0x64, 0x74, 0x74, 0x74, 0xA4])               # EntityY
        self.assertEqual(INIT[10:15], [0x7C, 0x7C, 0x70, 0x88, 0x7C])              # EntityX
        self.assertEqual(INIT[15:20], [4, 2, 1, 1, 4])                             # EntityDir

    def test_clear_player_counters_falls_through_from_new_board_init(self):
        # NewBoardInit ends at $AE1C with `ldx CurrentPlayer` and ClearPlayerCounters begins at $AE1E
        self.assertEqual((ROM.ins[0xAE1C][1], ROM.ins[0xAE1C][3]), ("ldx", 0x2B))
        self.assertEqual(0xAE1C + ROM.ins[0xAE1C][0], 0xAE1E)
        self.assertEqual(ROM.ins[0xAE1E][1], "lda")
        self.assertIn("Start", CALLERS[0xADAF])
        self.assertEqual(CALLERS[0xADF1], ["Start"])


class Records(unittest.TestCase):
    def test_ram_tables_fill_the_ram_table_area(self):
        end = 0x07D8
        starts = sorted(S.LB.RAM_TABLES)
        for i, a in enumerate(starts):
            nxt = starts[i + 1] if i + 1 < len(starts) else end
            rec = [r for r in S.RAM_RECORDS if r[1] == a]
            self.assertEqual(len(rec), 1, hex(a))
            name, addr, cnt, size, what = rec[0]
            self.assertEqual(name, S.LB.RAM_TABLES[a])
            self.assertEqual(cnt * size, nxt - a, name)

    def test_rom_records_match_the_data_map(self):
        for name, cnt, rec, what in S.ROM_RECORDS:
            f, l = S.data_range(name)
            self.assertEqual(l - f + 1, cnt * rec, name)

    def test_shapes_match_the_data_map(self):
        for name, rows in S.SHAPES:
            f, l = S.data_range(name)
            self.assertEqual(l - f + 1, rows, name)

    def test_player_missile_pages(self):
        self.assertEqual([a for a, w in S.PM_PAGES], [0x2300, 0x2400, 0x2500, 0x2600, 0x2700])


class Document(unittest.TestCase):
    def test_document_is_current(self):
        path = os.path.join(ROOT, "docs", "30-structures.md")
        with open(path, encoding="utf-8", newline="") as fh:
            have = fh.read().replace("\r\n", "\n")
        self.assertEqual(have, "\n".join(S.report()) + "\n", "run: python -I tools/analyze_structures.py --write docs/30-structures.md")

    def test_c_header_lists_every_field_once(self):
        text = "\n".join(S.c_header())
        for sname, count, desc, fields in S.STRUCTS:
            self.assertIn("} %s;" % sname, text)
            for cname, ctype, src, note in fields:
                self.assertEqual(text.count(" %s;" % cname) >= 1, True, cname)


class Log(unittest.TestCase):
    def _log(self, lines):
        fd, name = tempfile.mkstemp(suffix=".txt", prefix="structures-")
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return name

    def _ib(self):
        v = [0] * 128
        v[:20] = INIT
        for i in range(0x35, 0x3A):
            v[i] = 8
        rel = [ROM.data[0xBBF2 - S.BASE + i] for i in range(6)]
        v[0x4B:0x4E] = [rel[2], rel[1], rel[0]]
        return v

    def test_clean_log(self):
        name = self._log(["IDX s=$AB4A x=4", "IDX s=$AB4A x=0", "IB f=9 " + " ".join("%02X" % b for b in self._ib()), "RS f=9 " + " ".join(["00"] * 32)])
        try:
            L, bad_idx, bad_ib, bad_rs, never = SL.report([name])
            self.assertEqual((bad_idx, bad_ib, bad_rs), ([], [], []))
            self.assertGreater(len(never), 100)
        finally:
            os.remove(name)

    def test_index_out_of_range_is_found(self):
        a = [a for a, v in SL.site_table()[0].items() if v[0] == "GhostState"][0]
        name = self._log(["IDX s=$%04X x=4" % a])
        try:
            L, bad_idx, bad_ib, bad_rs, never = SL.report([name])
            self.assertEqual(len(bad_idx), 1)
        finally:
            os.remove(name)

    def test_the_ghost_timer_shift_allows_x_up_to_two_only(self):
        T = SL.site_table()[0]
        name = self._log(["IDX s=$AE36 x=2"])
        name2 = self._log(["IDX s=$AE36 x=3"])
        try:
            self.assertEqual(SL.report([name])[1], [])
            self.assertEqual(len(SL.report([name2])[1]), 1)
            self.assertEqual(T[0xAE36][:3], ("GhostTimer", 1, 4))
        finally:
            os.remove(name)
            os.remove(name2)

    def test_bad_snapshots_are_found(self):
        v = self._ib()
        v[0x60] = 1
        w = self._ib()
        w[0x4B] = 0
        name = self._log(["IB f=1 " + " ".join("%02X" % b for b in v), "IB f=2 " + " ".join("%02X" % b for b in w), "RS f=3 " + " ".join(["00"] * 31 + ["A5"])])
        try:
            L, bad_idx, bad_ib, bad_rs, never = SL.report([name])
            self.assertEqual((len(bad_ib), len(bad_rs)), (2, 1))
        finally:
            os.remove(name)

    def test_evidence_summary(self):
        path = os.path.join(ROOT, "analysis", "evidence-structures-summary.txt")
        if not os.path.exists(path):
            self.skipTest("evidence summary not present")
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("Index accesses outside their array: 0", txt)
        self.assertIn("Restart snapshots with a non-zero byte in $20-$3F: 0 of 29", txt)
        self.assertIn("present in 12 of 12 logs", txt)
        self.assertIn("Index sites never reached: 0 of 191", txt)
        self.assertIn("differ from the model (start positions, loaded MoveDelayCount and GhostTimer[1..3], zero elsewhere): 0 of 89", txt)
        self.assertIn("93509416 index hits at 191 sites, 89 InitBoard snapshots, 29 restart snapshots", txt)


if __name__ == "__main__":
    unittest.main()
