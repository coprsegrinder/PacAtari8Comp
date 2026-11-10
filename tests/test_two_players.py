"""Evidence tests for the two-player machinery (step C11, docs/19-two-players.md). Run:  python -I tests/test_two_players.py
Static part: every instruction of the game that touches a per-player variable takes its index from CurrentPlayer ($2B), except the two start-of-game initialisations
(which write both players on purpose). The live results (a real two-player game in Altirra) are in analysis/evidence-two-players-summary.txt.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402
import disasm6502 as D  # noqa: E402

BASE = 0xA000
DATA = bytes(S.rd(BASE + i) for i in range(0x2000))
CODE, _ = D.trace(DATA, BASE, [0xA386, 0xA6B4, 0xA5FD, 0xA573, 0xA5CE])
ADDRS = sorted(CODE)
at = lambda a, n: bytes(S.rd(a + i) for i in range(n))
hx = bytes.fromhex

PER_PLAYER_X = {0x2C: "lives", 0x2E: "extra-life flag", 0x30: "Level", 0x32: "power pellets left", 0x34: "dots eaten (low byte)", 0x36: "dots eaten (high byte)", 0x43: "bonus-item counter"}
# explicit player-1 / player-2 accesses (not indexed): the switch logic and the new-game initialisation
EXPLICIT = {0xAAA5, 0xAAA9, 0xAAC2, 0xAAC6, 0xADF3, 0xADF5, 0xADF9, 0xADFB}


def index_source(addr, reg):
    """The last instruction before addr (in address order, within 12 instructions) that changes the index register; returns its text."""
    i = ADDRS.index(addr)
    for b in reversed(ADDRS[max(0, i - 12):i]):
        n, m, mode, op = D.decode(DATA, BASE, b)
        loads = {"x": ("ldx", "tax", "inx", "dex", "tsx"), "y": ("ldy", "tay", "iny", "dey")}[reg]
        if m in loads:
            return b, m, mode, op
    return None


class Indexing(unittest.TestCase):
    def test_every_indexed_access_uses_current_player(self):
        sites = []
        for a in ADDRS:
            n, m, mode, op = D.decode(DATA, BASE, a)
            if mode == "zpx" and op in PER_PLAYER_X:
                sites.append((a, "x"))
            if mode == "aby" and op == 0x30:
                sites.append((a, "y"))
        self.assertEqual(len(sites), 33)
        others = []
        for a, reg in sites:
            src = index_source(a, reg)
            if src is None or not (src[1] == "ld" + reg and src[2] == "zp" and src[3] == 0x2B):
                others.append((hex(a), src))
        # the address-order search cannot resolve two accesses reached by a branch: $B5E2 (reached from $B5D7, X still = CurrentPlayer from $B5D3) and $B662 (X loaded at $B64A,
        # nothing between changes X: checked below)
        self.assertEqual([o[0] for o in others], ["0xb5e2", "0xb662"])
        self.assertEqual(at(0xB5D3, 6), hx("A62BB536F009"))            # LDX CurrentPlayer / LDA zp_36,X / BEQ $B5E2
        for b in ADDRS:
            if 0xB64A < b < 0xB662:
                self.assertNotIn(D.decode(DATA, BASE, b)[1], ("ldx", "tax", "inx", "dex", "tsx"), hex(b))
        # Sub_AE1E ($AE1E-$AE28) has two entries: the level code falls into it from LDX CurrentPlayer ($AE1C), the new-game code calls it with X = 1 (player 2), see below

    def test_level_sites(self):
        # ten reads/writes of Level, all through CurrentPlayer; the only direct stores are the start-of-game ones
        lv = [a for a in ADDRS if D.decode(DATA, BASE, a)[2] in ("zpx", "aby") and D.decode(DATA, BASE, a)[3] == 0x30]
        self.assertEqual([hex(a) for a in lv], ["0xa93f", "0xa974", "0xac7c", "0xaca4", "0xadbe", "0xae0a", "0xaf71", "0xb3f7", "0xb5a5", "0xb662"])
        for a in (0xA93D, 0xA972, 0xAC78, 0xACA2, 0xADBC, 0xAE08, 0xAF6F, 0xB3F5):
            self.assertEqual(at(a, 2), hx("A62B"), hex(a))            # LDX CurrentPlayer
        self.assertEqual(at(0xB5A3, 2), hx("A42B"))                    # LDY CurrentPlayer ... LDA $0030,Y
        self.assertEqual(at(0xB5A5, 3), hx("B93000"))
        self.assertEqual(at(0xB64A, 2), hx("A62B"))                    # ... LDA Level,X at $B662 with X unchanged
        self.assertEqual(at(0xAC7A, 4), hx("F62CF630"))                # INC lives,X ; INC Level,X (AdvanceLevel)
        # direct stores: both counters := StartLevel at the start of a game
        self.assertEqual(at(0xADF7, 6), hx("A51B85308531"))

    def test_new_game_initialises_both_players(self):
        self.assertEqual(at(0xADF1, 12), hx("A903852C852DA51B85308531"))      # lives 3 and 3; Level and zp_31 := StartLevel
        self.assertEqual(at(0xADFD, 5), hx("A201201EAE"))                    # LDX #1 / JSR Sub_AE1E: player 2's power-pellet flags, bonus counter and dot counters
        self.assertEqual(at(0xAE1E, 11), hx("A90F9532A9009543953495"))       # Sub_AE1E: flags := $0F, bonus counter := 0, dots (low) := 0 ... for player X

    def test_scores_per_player(self):
        # AddToScore: player 1 adds into the digits ending at $202F, player 2 into those ending at $204C
        self.assertEqual(at(0xB428, 12), hx("A52BF004A24CD002A22FA005"))

    def test_the_two_mazes_are_swapped_at_a_switch(self):
        # each player's maze (dots left) is kept in its own copy: player 1 at $1000-$13FF, player 2 at $1400-$17FF; the playing player's copy is at $0C00-$0FFF.
        # At the end of a turn the working copy is saved ($B13D: $0C00 -> $1000, $B15B: $0C00 -> $1400) and the other player's copy is loaded
        # (zp_23 = 1 at $AA3B: $1000 -> $0C00 and CurrentPlayer := 0; zp_23 = 2 at $AA65: $1400 -> $0C00 and CurrentPlayer := 1).
        self.assertEqual(at(0xB13D, 30), hx("A200BD000C9D0010BD000D9D0011BD000E9D0012BD000F9D0013E8D0E560"))
        self.assertEqual(at(0xB15B, 30), hx("A200BD000C9D0014BD000D9D0015BD000E9D0016BD000F9D0017E8D0E560"))
        self.assertEqual(at(0xAA3B, 37), hx("C901D026A200BD00109D000CBD00119D000DBD00129D000EBD00139D000FE8D0E52087ADA9"))
        self.assertEqual(at(0xAA65, 36), hx("C902D026A200BD00149D000CBD00159D000DBD00169D000EBD00179D000FE8D0E5209FAD"))

    def test_player_count_flag(self):
        # SELECT on the title screen toggles zp_1A (0 = one player, 1 = two): LDA zp_1A / BNE / LDA #1 ... LDA #0 / STA zp_1A
        self.assertEqual(at(0xA544, 11), hx("A51AD004A901D002A90085"))
        # in the game, after a life is lost, the turn passes only if zp_1A is non-zero and the other player has lives left
        self.assertEqual(at(0xAA9D, 8), hx("A51AF03FA52BD01D"))
        self.assertEqual(at(0xAAA5, 8), hx("A52DF037A52CD00A"))        # player 1 playing: needs player 2's lives (zp_2D)
        self.assertEqual(at(0xAAC2, 8), hx("A52CF01AA52DD00A"))        # player 2 playing: needs player 1's lives (zp_2C)


if __name__ == "__main__":
    unittest.main(verbosity=2)
