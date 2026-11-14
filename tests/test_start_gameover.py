"""Evidence tests for the start of a game, game over and the return to the title (docs/21-start-gameover-title.md). Run:  python -I tests/test_start_gameover.py
Static: the code bytes of the main-loop checks (countdown, triggers, START/SELECT/OPTION), the new-game entry, the tune loop, the start-of-play code, the game-over code and Sub_AB26;
the tune tables; and the software model of Sub_AB26 (tools/analyze_fullgame_log.py), which the live session (analysis/evidence-fullgame-summary.txt) matches call by call.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_fullgame_log as A  # noqa: E402
import decode_streams as S  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))
hx = bytes.fromhex


class Code(unittest.TestCase):
    def test_main_loop_countdown_and_triggers(self):
        self.assertEqual(at(0xA4E9, 12), hx("A520F017A51ED004A904D05D"))      # zp_20 = 0 -> poll CONSOL; else zp_1E <> 0 -> triggers; zp_1E = 0 -> A := 4 -> $A552 (zp_19 := A, ATRACT := A)
        self.assertEqual(at(0xA4F5, 15), hx("A9FF8DFC02AD8402F038AD8502F033"))  # CH := $FF; STRIG0 = 0 -> $A537; STRIG1 = 0 -> $A537
        self.assertEqual(at(0xA537, 13), hx("A90085208519A901851C4C77A4"))      # new game: zp_20 := 0, zp_19 := 0, zp_1C := 1, restart at $A477
        self.assertEqual(at(0xA544, 29), hx("A51AD004A901D002A900851AA9038519854D4CBAA4A51BC902B004E61B"))  # SELECT: toggle zp_1A; zp_19 := 3, ATRACT := 3 (via $A550)
        self.assertEqual(at(0xA559, 26), hx("A51BC902B004E61BD0EDC90CF006E61BE61BD0E3A900851BF0DD"))      # OPTION: StartLevel 0,1,2 -> +1, 2..$0A -> +2, $0C -> 0

    def test_countdown_and_start_of_play(self):
        self.assertEqual(at(0xA78C, 12), hx("A51EF008A5142907D002C61E"))       # zp_1E counts down when RTCLOK2 AND 7 = 0
        self.assertEqual(at(0xA7C8, 11), hx("E622A900854D851C4C93AC"))         # zp_22++, ATRACT := 0, zp_1C := 0, DrawLevelIndicator (READY!)
        self.assertEqual(at(0xA7D3, 43), hx("A5142903D0EEA6A3E040F01FBD50BC8D00D2BD90BC8D02D2A9A88D01D2A9A48D03D2E6A3E028D0CC4C0EAD"))  # the tune: every 4th frame; step $28 -> Sub_AD0E
        self.assertEqual(at(0xA7FE, 13), hx("E621E6CE205EADA524F023C901"))      # step $40: zp_21++, ghost 0 state++, Sub_AD5E (clear READY!)

    def test_game_over_and_high_score(self):
        self.assertEqual(at(0xAAEF, 55), hx("A9ACA2009DED0D186901E8E00ED0F5A9448DC7028D19D0A523D0D5A22A2026ABA2472026ABA9008524A9018520A9E2851E209FAD4C5AB5"))
        self.assertEqual(at(0xAB26, 34), hx("A000BD0020D93920F0049015B007E8C8C006D0EE60BD0020993920E8C8C006D0F460"))

    def test_tune_tables(self):
        self.assertEqual(len(A.TUNE1), 64)
        self.assertEqual(len(A.TUNE2), 64)
        self.assertEqual(A.TUNE1[:4], [rd(0xBC50 + i) for i in range(4)])


class Model(unittest.TestCase):
    def test_compare_cases(self):
        h = [0, 0, 0, 0x11, 0x10, 0x10]
        self.assertEqual(A.model_ab26([0, 0, 0, 0x11, 0x10, 0x10], h), (h, "equal"))
        self.assertEqual(A.model_ab26([0, 0, 0, 0x11, 0x10, 0x11], h), ([0, 0, 0, 0x11, 0x10, 0x11], "copy"))
        self.assertEqual(A.model_ab26([0, 0, 0, 0x10, 0x19, 0x19], h), (h, "less"))
        self.assertEqual(A.model_ab26([0, 0, 0x11, 0x10, 0x10, 0x10], h), ([0, 0, 0x11, 0x10, 0x10, 0x10], "copy"))   # more digits wins (leading blank = 0)
        self.assertEqual(A.model_ab26([0, 0, 0, 0, 0x10, 0x10], [0] * 6)[1], "copy")                                   # "00" beats a blank high score


if __name__ == "__main__":
    unittest.main()
