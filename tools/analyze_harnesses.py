"""Stage 54: the inventory of the Altirra debugger harnesses (tools/altirra_*.cmd) - the breakpoints, tracepoints and watches the project has set, resolved against the ROM.

For each command file: its purpose (header comment), the number of `bp` / `bt` / `bta` lines, the test aids it uses (PC skips, RAM writes), the analyzers and tests that read its logs and the chapters that cite it.
For each address: the routine it is in, whether it is an instruction start (a breakpoint anywhere else never fires), the event names the tracepoints print and the harnesses that use it.
Usage: python -I tools/analyze_harnesses.py   (prints a summary)   -  the document is written by tools/analyze_tracing.py
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)
CMD = re.compile(r"^(bp|bt|bta|ba)\s+(.*)$")
EVENT = re.compile(r'"([A-Za-z][A-Za-z0-9_]*)')
HEX = re.compile(r"^[0-9a-fA-F]{1,4}$")


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().replace("\r\n", "\n").split("\n")


def parse_harness(path):
    """-> dict with header, counts, probes [(kind, addr, text)], aids"""
    lines = read_lines(path)
    header = [l.lstrip("#").strip() for l in lines if l.startswith("#") and not l.startswith("#COMPLETE")]
    h = {"file": os.path.basename(path), "header": header, "bp": 0, "bt": 0, "bta": 0, "ba": 0, "probes": [], "pcskip": 0, "ramwrite": 0, "regwrite": 0, "lines": 0, "uses_sentinel": False}
    for l in lines:
        if not l.strip() or l.startswith("#"):
            continue
        h["lines"] += 1
        m = CMD.match(l)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        h[kind] += 1
        toks = rest.split()
        if toks and toks[0] == "-n":
            toks = toks[1:]
        if kind == "bta":
            toks = toks[1:] if toks and toks[0] in ("r", "w", "rw") else toks
        addr = None
        if toks and HEX.match(toks[0]):
            addr = int(toks[0], 16)
        h["probes"].append((kind, addr, rest))
        if kind == "bp":
            if re.search(r'\br\s+pc\b', rest):
                h["pcskip"] += 1
            if re.search(r'\be[bwd]\s', rest):
                h["ramwrite"] += 1
            if re.search(r'\br\s+[axy]\b', rest):
                h["regwrite"] += 1
        if addr == 0xA386 and "SENT" in rest:
            h["uses_sentinel"] = True
    return h


def harnesses():
    out = {}
    for p in sorted(glob.glob(os.path.join(HERE, "altirra_*.cmd"))):
        h = parse_harness(p)
        out[h["file"][len("altirra_"):-len(".cmd")]] = h
    return out


def references(names):
    """for each harness name: the analyzers, tests and chapters that cite `altirra_<name>.cmd`"""
    ana = {n: [] for n in names}
    tst = {n: [] for n in names}
    doc = {n: [] for n in names}
    cache = {}

    def text(p):
        if p not in cache:
            with open(p, encoding="utf-8", errors="replace") as fh:
                cache[p] = fh.read()
        return cache[p]
    for n in names:
        key = "altirra_%s.cmd" % n
        for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
            if key in text(p):
                ana[n].append(os.path.basename(p))
        for p in sorted(glob.glob(os.path.join(ROOT, "tests", "*.py"))):
            if key in text(p):
                tst[n].append(os.path.basename(p))
        for p in sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))):
            if os.path.basename(p).startswith("32-"):
                continue                                    # docs/32 is generated from this scan: counting it would make its own output depend on its previous version (found in stage 98)
            if key in text(p):
                doc[n].append(os.path.basename(p).split("-")[0])
    # a test belongs to the harness when it imports an analyzer of the harness
    for n in names:
        for a in ana[n]:
            mod = a[:-3]
            for p in sorted(glob.glob(os.path.join(ROOT, "tests", "*.py"))):
                if re.search(r"\b%s\b" % re.escape(mod), text(p)) and os.path.basename(p) not in tst[n]:
                    tst[n].append(os.path.basename(p))
    return ana, tst, doc


def address_inventory(hs):
    """address -> {'harnesses': set, 'events': set, 'kinds': set}"""
    inv = collections.defaultdict(lambda: {"harnesses": set(), "events": set(), "kinds": set()})
    for name, h in hs.items():
        for kind, addr, rest in h["probes"]:
            if addr is None:
                continue
            e = inv[addr]
            e["harnesses"].add(name)
            e["kinds"].add(kind)
            m = EVENT.search(rest)
            if m and kind in ("bt", "bta"):
                e["events"].add(m.group(1))
    return inv


def resolve(inv):
    rom, F, owner = AS.load()
    rows = []
    for addr, e in sorted(inv.items()):
        if 0xA000 <= addr <= 0xBFFF:
            ok = addr in rom.ins
            rn = F[owner[addr]].name if ok else "(inside an instruction or data)"
            where = "ROM"
        elif addr >= 0xC000:
            ok, rn, where = True, "(OS)", "OS ROM"
        else:
            ok, rn, where = True, "(RAM)", "RAM"
        rows.append((addr, where, ok, rn, e))
    return rows


def main():
    hs = harnesses()
    inv = address_inventory(hs)
    rows = resolve(inv)
    print("%d harnesses, %d bp, %d bt, %d bta lines, %d distinct addresses (%d in the ROM, %d not instruction starts)" % (
        len(hs), sum(h["bp"] for h in hs.values()), sum(h["bt"] for h in hs.values()), sum(h["bta"] for h in hs.values()), len(inv),
        sum(1 for r in rows if r[1] == "ROM"), sum(1 for r in rows if r[1] == "ROM" and not r[2])))
    for r in rows:
        if r[1] == "ROM" and not r[2]:
            print("NOT AN INSTRUCTION: %04X used by %s" % (r[0], ", ".join(sorted(r[4]["harnesses"]))))


if __name__ == "__main__":
    main()
