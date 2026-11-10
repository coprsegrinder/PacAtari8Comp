"""Step C11: what the contents of the sight blocker lists ($BBAB-$BBE1) mean, compared with the maze's junction map.

Reading (from the scan in GhostSeesPacMan, $BA3F-$BAAE): a list element e blocks the pair of junction coordinates (lo, hi) when lo <= e < hi.
Hypothesis tested here: for each junction row (x lists) and each junction column (y lists), the elements mark the places where the corridor between two neighbouring junctions of that
row/column is CLOSED in the maze (JunctionExits, RAM $060E): the midpoint of the closed gap between two adjacent junction coordinates (or the coordinate of a junction that is missing).
Usage: python -I tools/describe_sight_lists.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402
import sight_model as M  # noqa: E402

rd = S.rd
NIB, _ = S.split_nibbles(0xBE95)
J = [[NIB[0x60E - 0x600 + 10 * r + c] for c in range(10)] for r in range(10)]      # exits per lattice point: 1 up, 2 down, 4 left, 8 right


def lst(base, off):
    out, k = [], 0
    while rd(base + off + k) != 0xFF:
        out.append(rd(base + off + k))
        k += 1
    return out


ROW_LISTS = [lst(0xBBAB, rd(0xBBB8 + i)) for i in range(10)]     # by junction row, through the offset table (what the data is laid out for)
COL_LISTS = [lst(0xBBC2, rd(0xBBD8 + i)) for i in range(10)]     # by junction column

# The three places where the shipped lists differ from the maze (see docs/15-small-tables.md): the corrections that make them agree with it completely
CORRECTED_ROW = {7: [0x4C, 0xAC]}                  # shipped $3C, $AC: the left blocker of row 7 sits one gap too far left
CORRECTED_COL = {2: [0xBC], 7: [0xBC],             # shipped $3C: columns 2 and 7 are closed between rows 8 and 9, not between rows 0 and 1
                 0: [0x64, 0x84, 0xAC], 9: [0x64, 0x84, 0xAC]}      # columns 0 and 9 lack the closed gap between rows 7 and 8 ($AC)


def connected_row(r, a, b):
    return all((J[r][c] & 8) and (J[r][c + 1] & 4) for c in range(a, b))


def connected_col(c, a, b):
    return all((J[r][c] & 2) and (J[r + 1][c] & 1) for r in range(a, b))


def agreement(rows, cols):
    """(agreeing, total) pairs of junctions on a row, and on a column: 'list says clear' == 'maze says connected'."""
    t = ok = 0
    for r in range(10):
        for a in range(10):
            for b in range(a + 1, 10):
                if J[r][a] and J[r][b]:
                    t += 1
                    ok += (not any(M.XS[a] <= e < M.XS[b] for e in rows[r])) == connected_row(r, a, b)
    t2 = ok2 = 0
    for c in range(10):
        for a in range(10):
            for b in range(a + 1, 10):
                if J[a][c] and J[b][c]:
                    t2 += 1
                    ok2 += (not any(M.YS[a] <= e < M.YS[b] for e in cols[c])) == connected_col(c, a, b)
    return (ok, t), (ok2, t2)


def corrected():
    rows = [list(l) for l in ROW_LISTS]
    cols = [list(l) for l in COL_LISTS]
    for r, v in CORRECTED_ROW.items():
        rows[r] = list(v)
    for c, v in CORRECTED_COL.items():
        cols[c] = list(v)
    return rows, cols


def closed_gaps_row(r):
    return [(M.XS[c] + M.XS[c + 1]) // 2 for c in range(9) if not (J[r][c] & 8 and J[r][c + 1] & 4)]


def closed_gaps_col(c):
    return [(M.YS[r] + M.YS[r + 1]) // 2 for r in range(9) if not (J[r][c] & 2 and J[r + 1][c] & 1)]


def main():
    print("junction columns x:", M.XS)
    print("junction rows    y:", M.YS)
    print("\nROWS: closed gaps between neighbouring junctions (midpoint x) | blocker list used by the data layout")
    for r in range(10):
        print("  row %d (y=%3d): present %-28s closed gaps %-22s list %s" % (r, M.YS[r], [c for c in range(10) if J[r][c]], closed_gaps_row(r), ["$%02X" % e for e in ROW_LISTS[r]]))
    print("\nCOLUMNS: closed gaps (midpoint y) | blocker list")
    for c in range(10):
        print("  col %d (x=%3d): present rows %-28s closed gaps %-32s list %s" % (c, M.XS[c], [r for r in range(10) if J[r][c]], closed_gaps_col(c), ["$%02X" % e for e in COL_LISTS[c]]))
    print("\nagreement with the maze (junction pairs on a row, on a column):")
    print("  as shipped :", agreement(ROW_LISTS, COL_LISTS))
    rows, cols = corrected()
    print("  corrected  :", agreement(rows, cols), " (row 7 $3C->$4C; columns 2,7 $3C->$BC; columns 0,9 add $AC)")


if __name__ == "__main__":
    main()
