"""OV-64 (part 2): how much CPU time ANTIC's DMA and the display-list interrupts leave the vertical-blank handler on the game screen (NTSC).

The handler is entered at line 256 (cycle 20 of the line, measured) and runs through the end of the vertical blank (lines 256-261 and 0-7) into the visible screen. The game screen's display list is
$BFA3 (ROM): 3 blank-8 groups, a mode 2 line, mode 4 lines and 5 display-list interrupts (docs/38: lines 39, 47, 207, 215, 231); DMACTL = $3E (standard playfield, players and missiles, single line).
Cycles ANTIC takes from the CPU in a scan line (the most that can be taken, 114 cycles per line):
  refresh 9 on every line;  display list: 1 byte for an instruction, 3 with a load-memory-scan, on the first line of its mode line (a blank line: 1);  screen memory: the width of the mode (40 bytes in
  modes 2 and 4) on the first line of a mode line;  character data: the same width on every line of a mode 2 or 4 line;  players and missiles: 5 on every line (single-line resolution; counted on every line).
A scan line with a display-list interrupt is counted as lost to the interrupt (it ends in WSYNC, which halts the CPU to the end of the line), and 16 cycles of the next line go to the end of the interrupt
(PLA, PLA, RTI and the return); 2 cycles per line are counted as lost to the way the CPU is halted.  These are the model; it is checked against the measured frames in docs/39.
Usage: python -I tools/dma_model.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as _fh:
    ROM = _fh.read()

LINE = 114
LINES = 262
FIRST_VISIBLE = 8
ENTRY_LINE, ENTRY_HP = 256, 20
SCAN = {2: 8, 3: 10, 4: 8, 5: 16, 6: 8, 7: 16}
WIDTH = {2: 40, 3: 40, 4: 40, 5: 40, 6: 20, 7: 20}


def display_list(addr):
    """-> [(kind, mode, scan lines, lms, dli)]"""
    i = addr - 0xA000
    out = []
    while True:
        b = ROM[i]
        m = b & 15
        if m == 0:
            out.append(("blank", 0, ((b >> 4) & 7) + 1, False, bool(b & 0x80)))
            i += 1
        elif m == 1:
            break
        else:
            out.append(("mode", m, SCAN[m], bool(b & 0x40), bool(b & 0x80)))
            i += 3 if b & 0x40 else 1
    return out


def steal_table(addr=0xBFA3):
    """-> (steal per frame line 0..261, set of the lines that end in a display-list interrupt)"""
    steal = [9] * LINES                                            # refresh
    dli = set()
    line = FIRST_VISIBLE
    for kind, mode, n, lms, d in display_list(addr):
        for k in range(n):
            ln = line + k
            if ln >= 248:
                break
            steal[ln] += 5                                         # players and missiles
            if k == 0:
                steal[ln] += 3 if lms else 1                       # the display-list instruction (and its address)
                if kind == "mode":
                    steal[ln] += WIDTH[mode]                       # screen memory
            if kind == "mode":
                steal[ln] += WIDTH[mode]                           # character data
        if d:
            dli.add(line + n - 1)
        line += n
    return steal, dli


def available(addr=0xBFA3, halt=2, dli_tail=16):
    """CPU cycles the handler's thread has in each frame line"""
    steal, dli = steal_table(addr)
    av = [max(0, LINE - s - halt) for s in steal]
    for ln in dli:
        av[ln] = 0
        if ln + 1 < LINES:
            av[ln + 1] = max(0, av[ln + 1] - dli_tail)
    return av


def elapsed(cycles, addr=0xBFA3, **kw):
    """the cycles from the entry of the handler until `cycles` instruction cycles have run (None: more than two frames)"""
    av = available(addr, **kw)
    ln = ENTRY_LINE
    left = cycles
    got = LINE - ENTRY_HP - 9 - 2
    t = 0
    first = True
    while t < 2 * LINES * LINE:
        a = got if first else av[ln % LINES]
        first = False
        if left <= a:
            return t + int(left * (LINE / max(a, 1))) if a else t
        left -= a
        t += LINE
        ln += 1
        got = None
    return None


def budget(addr=0xBFA3, **kw):
    """the instruction cycles the handler's thread gets between one entry and the next (one frame later)"""
    av = available(addr, **kw)
    total = LINE - ENTRY_HP - 9 - 2
    ln = ENTRY_LINE + 1
    for k in range(LINES):
        total += av[ln % LINES]
        ln += 1
    return total - (LINE - ENTRY_HP - 9 - 2)                        # the last line is the entry line again, only up to the entry cycle


if __name__ == "__main__":
    st, dl = steal_table()
    print("display list lines:", sum(n for _, _, n, _, _ in display_list(0xBFA3)), "(the display ends at line 231; below it only refresh)")
    print("display-list interrupts at lines:", sorted(dl))
    print("instruction cycles per frame the handler thread gets:", budget())
    for c in (3014, 5839, 13229, 16901, 18516):
        print(c, "->", elapsed(c))
