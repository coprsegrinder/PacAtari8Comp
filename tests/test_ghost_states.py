"""Evidence tests for the ghost state machine around the patrol routes (step C11). Run:  python -I tests/test_ghost_states.py
Byte-level checks of the code that docs/13-ghost-patrols.md describes; the live results are in analysis/evidence-patrol-summary.txt.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402

at = lambda a, n: bytes(S.rd(a + i) for i in range(n))
hx = bytes.fromhex


class Dispatcher(unittest.TestCase):
    def test_states_and_handlers(self):
        # GhostBehaviour: not frightened -> 1: GhostStartRoute ($B827), 2: chase while ChaseTimer<>0 else corner, 8: travel, $10: patrol, $20: corner
        self.assertEqual(at(0xB7F5, 4), hx("B5CE1006"))                   # LDA GhostState,X / BPL
        self.assertEqual(at(0xB7FF, 4), hx("C901F024"))                   # CMP #1 / BEQ $B827
        self.assertEqual(at(0xB803, 8), hx("C902D00AA5ADD003"))           # CMP #2 ... LDA ChaseTimer / BNE chase
        self.assertEqual(at(0xB80B, 3), hx("4CC5B8"))                     # else JMP GhostGoToCorner
        self.assertEqual(at(0xB811, 7), hx("C908D0034C78B8"))             # CMP #8 -> GhostPatrolTravel
        self.assertEqual(at(0xB818, 7), hx("C910D0034C9AB8"))             # CMP #$10 -> GhostPatrol
        self.assertEqual(at(0xB81F, 7), hx("C920D0034CC5B8"))             # CMP #$20 -> GhostGoToCorner
        self.assertEqual(at(0xB80E, 3), hx("4CEFB8"))                     # JMP GhostChase

    def test_chase_target_is_pac_man(self):
        self.assertEqual(at(0xB8EF, 8), hx("A58E95C2A58995C6"))           # TargetX = PacX, TargetY = PacY
        self.assertEqual(at(0xB8EB, 4), hx("A90295CE"))                   # state := 2

    def test_selection_travel_patrol_corner(self):
        self.assertEqual(at(0xB851, 4), hx("A90895CE"))                   # state := 8 (patrol travel)
        self.assertEqual(at(0xB859, 8), hx("AD0AD2290F95BA0A"))           # route := RANDOM AND $0F
        self.assertEqual(at(0xB86D, 4), hx("A99695CA"))                   # GhostTimer := $96
        self.assertEqual(at(0xB878, 5), hx("B5CAD0034C"))                 # travel: timer zero -> corner
        self.assertEqual(at(0xB893, 4), hx("A91095CE"))                   # target reached: state := $10 (patrol)
        self.assertEqual(at(0xB89A, 4), hx("B5CAF027"))                   # patrol: timer zero -> corner
        self.assertEqual(at(0xB8C5, 4), hx("A92095CE"))                   # corner: state := $20
        self.assertEqual(at(0xB8E8, 3), hx("4C51B8"))                     # corner reached -> GhostSelectPatrol

    def test_timers(self):
        self.assertEqual(at(0xA9DD, 12), hx("A5142907D006B5CAF002D6CA"))   # every 8th jiffy: GhostTimer--
        self.assertEqual(at(0xB5C7, 12), hx("A5142907D006A5ADF002C6AD"))   # ... and ChaseTimer--
        self.assertEqual(8 * 0x96, 1200)                                                         # 150 ticks x 8 jiffies = 1200 frames = 20 s at 60 Hz

    def test_chase_triggers(self):
        self.assertEqual(at(0xBAB7, 8), hx("A90295CEA9A085AD"))           # sight: state := 2, ChaseTimer := $A0
        self.assertEqual(at(0xB84A, 7), hx("A950" "85AD4CEBB8"))           # ghost 0 at the end of its start route: ChaseTimer := $50, chase

    def test_corner_targets_are_lattice_corners(self):
        ys = [S.rd(0xBB83 + i) for i in range(10)]
        xs = [S.rd(0xBB8D + i) for i in range(10)]
        corners = [(S.rd(0xBD0E + 2 * i), S.rd(0xBD0E + 2 * i + 1)) for i in range(4)]
        self.assertEqual([(ys.index(y), xs.index(x)) for x, y in corners], [(0, 9), (0, 0), (9, 9), (9, 0)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
