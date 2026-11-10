"""Evidence tests for the ghost state transitions (step C11). Run:  python -I tests/test_ghost_transitions.py
Static part: every instruction in the ROM that can WRITE GhostState ($CE-$D1) is one of 13 known stores, and each store's surrounding bytes are what
docs/17-ghost-transitions.md describes. The live results (all 13 sites reached, every write matching the rule, no hidden writer) are in
analysis/evidence-ghost-transitions-summary.txt (tools/altirra_transitions.cmd, tools/analyze_transitions_log.py).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)
import decode_streams as S  # noqa: E402
import disasm6502 as D  # noqa: E402
import analyze_transitions_log as A  # noqa: E402

at = lambda a, n: bytes(S.rd(a + i) for i in range(n))
hx = bytes.fromhex
BASE = 0xA000
DATA = bytes(S.rd(BASE + i) for i in range(0x2000))
ENTRIES = [0xA386, 0xA6B4, 0xA5FD, 0xA573, 0xA5CE]          # the same entry points as tools/make_asm.py
WRITES = {"sta", "inc", "dec", "asl", "lsr", "rol", "ror", "stx", "sty"}
SITES = [0xA800, 0xA888, 0xAFA0, 0xB40A, 0xB626, 0xB6D0, 0xB756, 0xB764, 0xB853, 0xB895, 0xB8C7, 0xB8ED, 0xBAB9]


class Writers(unittest.TestCase):
    def test_exactly_thirteen_instructions_write_ghost_state(self):
        code, _ = D.trace(DATA, BASE, ENTRIES)
        found = []
        for a in sorted(code):
            n, m, mode, op = D.decode(DATA, BASE, a)
            if m in WRITES and mode in ("zp", "zpx") and 0xCE <= op <= 0xD1:
                found.append(a)
            # absolute / indexed-absolute addressing of the zero page (STA $00CE,X) would also show up as a write
            if m in WRITES and mode in ("abs", "abx", "aby") and 0x00CE <= op <= 0x00D1:
                found.append(a)
        self.assertEqual(found, SITES)

    def test_store_instructions(self):
        for a in SITES[1:]:
            self.assertEqual(at(a, 2), hx("95CE"), hex(a))           # STA GhostState,X
        self.assertEqual(at(0xA800, 2), hx("E6CE"))                  # INC GhostState (ghost 0)

    def test_sites_and_values(self):
        self.assertEqual(at(0xA886, 4), hx("A94295CE"))              # GhostEaten: state := $42
        self.assertEqual(at(0xAF8C, 8), hx("B5CE1012C980F006"))      # frightened time over: only frightened ghosts; $80 -> 0
        self.assertEqual(at(0xAF94, 6), hx("29BBF00AD004"))          # other frightened states: AND $BB, nonzero -> $20
        self.assertEqual(at(0xAF9A, 6), hx("A900F002A920"))
        self.assertEqual(at(0xB401, 10), hx("B5CE0A3017B5CE098095"))   # power pellet: skip eaten ghosts (bit 6), else state OR $80
        self.assertEqual(at(0xB616, 16), hx("B5CEC908F008C910F004C920D004A902"))   # dots threshold: states 8 / $10 / $20 -> 2
        self.assertEqual(at(0xB6CE, 6), hx("A94495CEA9FF"))          # eaten ghost at the door square: state := $44
        self.assertEqual(at(0xB73E, 6), hx("B5CED004A901"))          # house door row: state 0 -> 1
        self.assertEqual(at(0xB746, 4), hx("29800902"))              # otherwise (state AND $80) OR 2
        self.assertEqual(at(0xB760, 6), hx("B5CE290F95CE"))          # back inside the house: state AND $0F
        self.assertEqual(at(0xBAAF, 17), hx("E002D004A5143008A90295CEA9A085AD60"))   # sight: state := 2, ChaseTimer := $A0

    def test_init_board_clears_the_states(self):
        # InitBoard ($ADAF): JSR Sub_B0F1, LDX #$7F, STA zp_80,X / DEX / BPL: clears $80-$FF (so $CE-$D1 become 0 at every board start)
        self.assertEqual(at(0xADAF, 10), hx("20F1B0A27F9580CA10FB"))


class LiveRules(unittest.TestCase):
    """The rules the analyzer checks the log against (derived from the code above)."""

    def test_new_values(self):
        E = A.expect_new
        self.assertEqual(E(0xA800, 0, 0), 1)
        self.assertEqual([E(0xAFA0, 0, o) for o in (0x80, 0x81, 0x82, 0x88, 0x90, 0xA0)], [0, 0x20, 0x20, 0x20, 0x20, 0x20])
        self.assertEqual([E(0xB40A, 0, o) for o in (1, 2, 8, 0x10, 0x20)], [0x81, 0x82, 0x88, 0x90, 0xA0])
        self.assertEqual((E(0xB756, 0, 0x00), E(0xB756, 0, 0x04), E(0xB756, 0, 0x84)), (1, 2, 0x82))
        self.assertEqual(E(0xB764, 0, 0x44), 0x04)


if __name__ == "__main__":
    unittest.main(verbosity=2)
