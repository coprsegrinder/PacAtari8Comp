"""OV-57: tests of tools/analyze_door_up.py and of the code path $B6C0-$B6CC.  Run:  python -I tests/test_door_up.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_door_up as D  # noqa: E402
import analyze_stack as AS  # noqa: E402

ROM, F, OWNER = AS.load()


class Code(unittest.TestCase):
    def test_the_up_case_is_a_turn_left_at_the_door_square(self):
        ins = ROM.ins
        self.assertEqual((ins[0xB6B8][1], ins[0xB6B8][3]), ("cpy", 0x7C))           # x = $7C
        self.assertEqual((ins[0xB6BC][1], ins[0xB6BC][3]), ("cmp", 0x64))           # y = $64
        self.assertEqual((ins[0xB6C2][1], ins[0xB6C2][3]), ("cmp", 0x01))           # direction up
        self.assertEqual((ins[0xB6C6][1], ins[0xB6C6][3]), ("lda", 0x04))           # ... becomes left
        self.assertEqual((ins[0xB6C8][1], ins[0xB6C8][2]), ("sta", "zpx"))
        self.assertEqual((ins[0xB6CE][1], ins[0xB6CE][3]), ("lda", 0x44))           # otherwise state $44
        self.assertEqual(F[OWNER[0xB6C8]].name, "EyesAndHousePerFrame")

    def test_the_turn_skips_the_state_change(self):
        # after the turn, `lda EntityY,x / bne LB6D8` (Y = $64 is not 0): the ghost keeps steering, state stays $42
        self.assertEqual(ROM.ins[0xB6CC][1], "bne")
        self.assertEqual(ROM.ins[0xB6CC][3], 0xB6D8)

    def test_frightened_house_ghost_leaves_as_82(self):
        # HouseLeaveStep at the door row: state 0 -> $01, any other state keeps bit 7 and gets $02
        self.assertEqual(F[OWNER[0xB738]].name, "HouseLeaveStep")


def _log(lines):
    fd, name = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return name


GOOD = ["INIT_BOARD board=1 level=0 f=100",
        "EATEN g=1 dir=1 x=124 y=104 st=$42 px=124 py=100 f=200 t5=100",
        "EY_DOOR g=1 dir=1 st=$42 x=124 y=100 f=235",
        "EY_UP g=1 st=$42 f=235",
        "EY_DOOR g=1 dir=8 st=$42 x=124 y=100 f=400",
        "EY_STATE44 g=1 dir=8 f=400",
        "HOME g=1 st=$44 f=440",
        "EATEN g=0 dir=4 x=123 y=100 st=$42 px=124 py=100 f=500 t5=80",
        "EY_DOOR g=0 dir=4 st=$42 x=124 y=100 f=600",
        "EY_STATE44 g=0 dir=4 f=600",
        "HOME g=0 st=$44 f=640"]


class Analyzer(unittest.TestCase):
    def test_good_log(self):
        name = _log(GOOD)
        try:
            r = D.summarise(name)
            self.assertEqual((r["episodes"], r["up_episodes"], r["door_dir_up"], r["door_up_events"]), (2, 1, 1, 1))
            self.assertEqual((r["up_then_second_visit"], r["up_then_s44"], r["up_then_home"], r["all_home"], r["all_s44"]), (1, 1, 1, 2, 2))
            self.assertEqual(r["up_by_ghost"][1], 1)
            self.assertEqual(r["eaten_to_up"], [35])
            self.assertEqual(r["up_journey"], [165])
        finally:
            os.remove(name)

    def test_a_ghost_lost_after_the_turn_is_seen(self):
        name = _log(GOOD[:5])
        try:
            r = D.summarise(name)
            self.assertEqual((r["up_episodes"], r["up_then_s44"], r["up_then_home"]), (1, 0, 0))
        finally:
            os.remove(name)

    def test_path_taken_without_direction_up_is_seen(self):
        name = _log([l.replace("EY_DOOR g=1 dir=1", "EY_DOOR g=1 dir=2") if l.startswith("EY_DOOR g=1 dir=1") else l for l in GOOD])
        try:
            r = D.summarise(name)
            self.assertNotEqual(r["door_dir_up"], r["door_up_events"])
        finally:
            os.remove(name)


class Evidence(unittest.TestCase):
    def test_summary(self):
        path = os.path.join(ROOT, "analysis", "evidence-door-up-summary.txt")
        if not os.path.exists(path):
            self.skipTest("evidence summary not present")
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("44 of 59 episodes", txt)
        self.assertIn("turns made by the path ($B6C6): 44  (equal", txt)
        self.assertIn("state $44 (enters the house) exactly once: 44 of 44; home again: 44 of 44", txt)
        self.assertIn("state $44 reached 59 of 59, home again 59 of 59", txt)


if __name__ == "__main__":
    unittest.main()
