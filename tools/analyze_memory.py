"""Stage 55: runtime memory inspection - which RAM bytes change while the real game runs, and are they all in the variable catalogue (docs/25)?

Input: analysis/raw-logs/memory-<harness>.txt of tools/run_memory_audit.ps1: a line `SNAP <EVENT>` followed by the debugger's hex dump of $0000-$9FFF (`AAAA: xx xx ... |text|`, 16 bytes a line), one block per event the first time it happens.
Every byte that has different values in two snapshots of the same harness (or of the same event in two harnesses) is a CHANGING byte.  Each is assigned to a catalogue entry (a zero-page variable, a RAM area of docs/25 section 3) or to
a documented class (the 6502 stack page, the OS variable pages $0200-$05FF, the expanded character sets).  A changing byte that fits nowhere is reported.
Usage: python -I tools/analyze_memory.py analysis/raw-logs/memory-*.txt [--write analysis/evidence-memory-summary.txt]
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_variables as V  # noqa: E402

ROOT = os.path.dirname(HERE)
DUMP = re.compile(r"^([0-9A-F]{4}): ((?:[0-9A-F]{2} ){16})")
SIZE = 0xA000

# documented classes outside the catalogue (name, first, last, why)
CLASSES = [
    ("OS jiffy clock", 0x0012, 0x0013, "RTCLOK1 and RTCLOK0 ($12 / $13), the high bytes of the OS clock counted by the OS vertical-blank routine; the game reads only RTCLOK2 ($14)"),
    ("stack", 0x0100, 0x01FF, "the 6502 stack page (28-stack.md)"),
    ("OS", 0x0200, 0x05FF, "the OS variable pages (shadow registers, vectors, IOCBs, buffers: the game uses only the entries of docs/25 section 3)"),
    ("title charset", 0x1808, 0x18C7, "title-screen glyphs expanded at start-up (`TitleCharsetStream` and its tail, 12)"),
    ("charset", 0x3000, 0x33FF, "the game character set expanded at start-up (`CharsetStream`, 12; `CHBASE` = $30)"),
]


def parse(path):
    snaps = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("SNAP "):
                cur = [line.split()[1], bytearray(SIZE), 0]
                snaps.append(cur)
                continue
            if cur is None:
                continue
            m = DUMP.match(line)
            if m:
                a = int(m.group(1), 16)
                vals = bytes(int(x, 16) for x in m.group(2).split())
                if a + 16 <= SIZE:
                    cur[1][a:a + 16] = vals
                    cur[2] += 16
    return [(n, b, c) for n, b, c in snaps if c == SIZE]


def catalogue():
    cat = {}
    for first, n, name, kind, role, ev in V.ZP:
        for i in range(n):
            cat[first + i] = "zp:" + name
    for first, last, name, *rest in V.AREAS:
        for a in range(first, last + 1):
            cat.setdefault(a, "ram:" + name)
    return cat


def classify(a, cat):
    if a in cat:
        return cat[a]
    for name, first, last, why in CLASSES:
        if first <= a <= last:
            return "class:" + name
    return None


def summarise(paths):
    cat = catalogue()
    snaps = {}
    for p in paths:
        name = os.path.basename(p)[len("memory-"):-len(".txt")]
        snaps[name] = parse(p)
    changing = collections.defaultdict(set)                       # address -> set of (harness pair descriptions)
    nsnap = sum(len(v) for v in snaps.values())
    for name, lst in snaps.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i][1], lst[j][1]
                for k in range(SIZE):
                    if a[k] != b[k]:
                        changing[k].add("%s:%s>%s" % (name, lst[i][0], lst[j][0]))
    byev = collections.defaultdict(list)
    for name, lst in snaps.items():
        for ev, b, c in lst:
            byev[ev].append((name, b))
    for ev, lst in byev.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i][1], lst[j][1]
                for k in range(SIZE):
                    if a[k] != b[k]:
                        changing[k].add("%s>%s:%s" % (lst[i][0], lst[j][0], ev))
    return snaps, changing, cat, nsnap


def ranges(addrs):
    out, start, prev = [], None, None
    for a in sorted(addrs):
        if start is None:
            start = prev = a
        elif a == prev + 1:
            prev = a
        else:
            out.append((start, prev))
            start = prev = a
    if start is not None:
        out.append((start, prev))
    return out


def report(paths):
    snaps, changing, cat, nsnap = summarise(paths)
    L = []
    P = L.append
    events = collections.Counter(ev for lst in snaps.values() for ev, b, c in lst)
    P("Memory audit (tools/run_memory_audit.ps1, tools/analyze_memory.py): %d harness logs, %d snapshots of $0000-$9FFF (%s)" % (len(snaps), nsnap, ", ".join("%s %d" % kv for kv in sorted(events.items()))))
    for name, lst in snaps.items():
        P("  %-12s %s" % (name, ", ".join(ev for ev, b, c in lst)))
    P("")
    by = collections.defaultdict(list)
    unexplained = []
    for a in sorted(changing):
        c = classify(a, cat)
        if c is None:
            unexplained.append(a)
        else:
            by[c].append(a)
    P("Changing bytes: %d  (in the catalogue: %d; in a documented class: %d; unexplained: %d)" % (
        len(changing), sum(len(v) for k, v in by.items() if not k.startswith("class:")), sum(len(v) for k, v in by.items() if k.startswith("class:")), len(unexplained)))
    P("")
    P("Changing bytes per catalogue entry / class:")
    kinds = collections.OrderedDict()
    for k in sorted(by, key=lambda x: (x.split(":")[0] != "zp", x.split(":")[0], min(by[x]))):
        kinds[k] = by[k]
    for k, v in kinds.items():
        P("  %-28s %5d bytes  (%s)" % (k, len(v), ", ".join("$%04X-$%04X" % r if r[0] != r[1] else "$%04X" % r[0] for r in ranges(v)[:5]) + (" ..." if len(ranges(v)) > 5 else "")))
    P("")
    P("Unexplained changing bytes: %s" % (", ".join("$%04X-$%04X" % r if r[0] != r[1] else "$%04X" % r[0] for r in ranges(unexplained)) or "none"))
    # catalogue entries that never changed in any snapshot pair (they may still be written with the same value)
    never = collections.defaultdict(int)
    names = collections.OrderedDict()
    for first, n, name, kind, role, ev in V.ZP:
        if all((first + i) not in changing for i in range(n)):
            names[name] = (first, n)
    P("")
    P("Zero-page variables whose value was the same in every snapshot (%d of %d): %s" % (len(names), len(V.ZP), ", ".join(sorted(names))))
    return L, unexplained, changing, by, snaps


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        args = [a for a in args if a != out]
    paths = sorted(p for a in args for p in glob.glob(a))
    L = report(paths)[0]
    txt = "\n".join(L) + "\n"
    if out:
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
