"""Stages 53-56: tests of tools/analyze_tracing.py, analyze_harnesses.py, analyze_coverage.py, analyze_registers.py and analyze_memory.py and of docs/32-tracing-and-inspection.md.  Run:  python -I tests/test_tracing.py
The raw logs are local; these tests read the committed summaries (analysis/evidence-*-summary.txt) and the harness files."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_harnesses as H  # noqa: E402
import analyze_tracing as T  # noqa: E402


def summary(kind):
    with open(os.path.join(ROOT, "analysis", "evidence-%s-summary.txt" % kind), encoding="utf-8") as fh:
        return fh.read()


class Document(unittest.TestCase):
    def test_document_is_current(self):
        with open(os.path.join(ROOT, "docs", "32-tracing-and-inspection.md"), encoding="utf-8", newline="") as fh:
            have = fh.read().replace("\r\n", "\n")
        self.assertEqual(have, "\n".join(T.report()) + "\n", "run: python -I tools/analyze_tracing.py --write docs/32-tracing-and-inspection.md")
        self.assertNotIn("NOT YET RUN", have)


class Coverage(unittest.TestCase):
    def test_unexecuted_instructions_are_exactly_the_explained_ones(self):
        txt = summary("coverage")
        listed = set()
        for line in txt.split("Instructions never executed, by routine")[1].splitlines()[1:]:
            m = re.match(r"\s+\S+\s+\d+ of\s+\d+: (.*)", line)
            if m:
                listed |= {int(x, 16) for x in m.group(1).split()}
        explained = set()
        for addrs, why in T.NOT_EXECUTED.values():
            explained |= set(addrs)
            self.assertGreater(len(why), 40)
        self.assertEqual(listed, explained)

    def test_coverage_figures(self):
        txt = summary("coverage")
        self.assertIn("36 harness logs, 2920 of 2925 instructions executed", txt)
        self.assertIn("79 of 79 entered at least once", txt)
        self.assertIn("124 of 124 JSR executed", txt)


class TunnelReversal(unittest.TestCase):
    def test_the_right_wrap_in_movepacman_is_the_second_wrap_of_a_reversal(self):
        txt = summary("ov59-tunnel")
        self.assertIn("617 clip wraps of Pac-Man", txt)
        self.assertIn("$B249 hits in all: 616 (every one in the frame after a clip wrap: 616)", txt)
        self.assertIn("by $B249 in MovePacMan 612", txt)
        self.assertIn("$B249 hits in all: 0", txt)                       # the control: the same clip wraps, no push, no hit
        self.assertEqual(txt.count("violations: 0"), 2, txt)
        self.assertNotIn("VIOLATION", txt)

    def test_the_analyzer_notices_a_wrong_log(self):
        import analyze_ov59_tunnel as O
        fr = {10: {"clip": True, "rl": False, "hit": False, "lwrap": False},
              11: {"clip": False, "rl": False, "hit": True, "lwrap": False, "move": {"f": 11, "px": 202, "dir": 4, "z80": 0x0DB7}, "stick": {"f": 11, "stick": 0x07}},
              12: {"clip": False, "rl": False, "hit": False, "lwrap": False, "move": {"f": 12, "px": 43, "dir": 8, "z80": 0x0D8F}, "stick": {"f": 12, "stick": 0x0B}}}
        self.assertEqual(O.check(fr, True)["violations"], [])
        fr[11]["move"]["px"] = 201                                      # the entry is not at $CA: must be reported
        self.assertEqual(len(O.check(fr, True)["violations"]), 1)
        fr[11]["move"]["px"] = 202
        fr[12]["move"]["px"] = 200                                      # no wrap back: must be reported
        self.assertEqual(len(O.check(fr, True)["violations"]), 1)


class DeadPaths(unittest.TestCase):
    """the five instructions no session can execute: the facts the explanations in analyze_tracing.NOT_EXECUTED rest on"""

    def test_bonus_sound_counter_is_written_at_four_places_only(self):
        import analyze_stack as AS
        rom, F, owner = AS.load()
        writers = sorted(a for a, (n, m, mode, op) in rom.ins.items() if m in ("sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror") and op == 0xF7 and mode in ("zp", "zpx", "zpy"))
        self.assertEqual(writers, [0xA96C, 0xABDE, 0xABE8, 0xABF5])
        self.assertEqual([rom.ins[a][1] for a in writers], ["sta", "inc", "inc", "sta"])
        # the counter is set to 1 at $A96C and to 0 at $ABF5; $ABDE (below 7) and $ABE8 (the step 9) are the only increments, and the code at $ABE4 keeps 7 and 8 from reaching $ABE8 by any path but 8 -> 9
        self.assertEqual(rom.ins[0xABE8][1], "inc")

    def test_every_direction_table_holds_only_single_bits(self):
        import algorithm_models as A
        m = A.started_machine()
        self.assertEqual(sorted(set(m.mem[0x0686:0x06AE])), [1, 2, 4, 8, 15])             # StartRoutes: $0F is the end marker, never stored in EntityDir
        self.assertEqual(sorted(set(m.mem[0x06AE:0x06AE + 0xE2])), [0, 1, 2, 4, 8])        # PatrolRoutes: 0 ends a route and is replaced by its first entry
        init = [A.rd(0xBB6F + k) for k in range(20)]
        self.assertEqual(init[15:20], [0x04, 0x02, 0x01, 0x01, 0x04])                      # ZeroPageInit80: the five EntityDir values

    def test_a_joystick_never_makes_pacdirection_more_than_one_bit(self):
        """the ROM's MovePacMan run (tools/cpu6502.py) with every STICK0 value a joystick can give (nothing, one direction, two adjacent directions) from every single-bit start: PacDirection stays a single bit"""
        import algorithm_models as A
        import algorithm_models2 as M2
        base = A.started_machine()
        sticks = [0x0F] + [0x0F ^ d for d in (1, 2, 4, 8)] + [0x0F ^ (u | s) for u in (1, 2) for s in (4, 8)]
        for stick in sticks:
            for start in (1, 2, 4, 8):
                for mask_y, mask_x in ((0x64, 0x76), (0x74, 0x50), (0x3C, 0x3A), (0xA4, 0x7C)):
                    m = A.fresh(base)
                    m.mem[0x93], m.mem[0xAC] = start, start
                    m.mem[0x89], m.mem[0x8E] = mask_y, mask_x
                    m.mem[0x2B] = 0
                    m.mem[0x0278] = stick
                    m.mem[0xAA] = 0
                    m.call(0xB179)
                    self.assertIn(m.mem[0x93], (1, 2, 4, 8), (hex(stick), start, mask_y, mask_x))


class Registers(unittest.TestCase):
    def test_no_violation(self):
        txt = summary("registers")
        self.assertIn("Violations of a claim: 0", txt)
        self.assertIn("12 harness logs", txt)
        self.assertIn("67 routines called (of 81)", txt)


class Memory(unittest.TestCase):
    def test_every_changing_byte_is_explained(self):
        txt = summary("memory")
        self.assertIn("unexplained: 0", txt)
        self.assertIn("Unexplained changing bytes: none", txt)


class Harnesses(unittest.TestCase):
    def test_every_breakpoint_address_is_an_instruction_start(self):
        import analyze_stack as AS
        rom, F, owner = AS.load()
        hs = H.harnesses()
        self.assertGreaterEqual(len(hs), 75)
        inv = H.address_inventory(hs)
        rows = H.resolve(inv)
        self.assertGreater(len(inv), 150)
        txt = "\n".join(T.report())
        self.assertIn("0 violations", txt)

    def test_the_two_player_path_harness_is_in_the_coverage_run(self):
        with open(os.path.join(ROOT, "tools", "run_coverage_audit.ps1"), encoding="utf-8") as fh:
            self.assertIn("'player1_survives'", fh.read())


if __name__ == "__main__":
    unittest.main()
