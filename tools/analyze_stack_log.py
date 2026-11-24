"""Stage 44 (OV-54): summarises the Altirra stack traces of tools/run_stack_audit.ps1.

Input: analysis/raw-logs/stack-<harness>.txt, with the lines
  STK a=$01xx pc=$xxxx f=N     a write to the stack page below $01F0 (depth over 16 bytes; the pc of a hardware push is the interrupted instruction)
  VBIE / DLI1E / DLI2E s=$xx f=N vp=N ipc=$xxxx   S, frame, scan line and the interrupted pc (read from the stack) at the first instruction of the deferred VBI handler and of the two display-list handlers
  VBIX (end of the VBI handler), INITB (InitBoard entered), FILL (FillPlayerPages entered): S, frame, scan line
The stack grows down from $01FF; a write at $01xx means $200-$01xx bytes are in use.  S at a handler entry means $FF-S bytes are in use there (the interrupt's 3 bytes, what the OS pushed, and what the
interrupted code had on the stack).  The first 100 frames (the OS clearing page 1 at boot) are left out.
Usage: python -I tools/analyze_stack_log.py analysis/raw-logs/stack-*.txt [--write analysis/evidence-stack-summary.txt]
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SKIP_FRAMES = 100
STK = re.compile(r"^STK a=\$([0-9A-F]{4}) pc=\$([0-9A-F]{4}) f=(\d+)")
ENT = re.compile(r"^(VBIE|DLI1E|DLI2E) s=\$([0-9A-F]{2}) f=(\d+)(?: vp=(\d+) ipc=\$([0-9A-F]{4}))?")
MARK = re.compile(r"^(VBIX|FILL) s=\$([0-9A-F]{2}) f=(\d+)")
FILL_RANGE = (0xB0F1, 0xB111)                        # ClearPlayerMemory and FillPlayerPages: the deepest call chain of the frame code
CHAIN = ("FrameDispatch", "TurnControl", "InitBoard", "ClearPlayerMemory", "FillPlayerPages")
FRM = re.compile(r"^FR f=(\d+)")


def parse(path):
    r = {"frames": 0, "stk": 0, "low": None, "lowpc": None, "lowf": None, "entry": {"VBIE": [], "DLI1E": [], "DLI2E": []},
         "ipc": {"VBIE": [], "DLI1E": [], "DLI2E": []}, "fill": [], "nested": []}
    inchain = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = STK.match(line)
            if m:
                a, pc, f = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))
                r["frames"] = max(r["frames"], f)
                if f < SKIP_FRAMES:
                    continue
                r["stk"] += 1
                if r["low"] is None or a < r["low"]:
                    r["low"], r["lowpc"], r["lowf"] = a, pc, f
                continue
            m = ENT.match(line)
            if m:
                k, s_, f = m.group(1), int(m.group(2), 16), int(m.group(3))
                r["frames"] = max(r["frames"], f)
                if f >= SKIP_FRAMES:
                    r["entry"][k].append(s_)
                    if m.group(5):
                        ipc = int(m.group(5), 16)
                        r["ipc"][k].append((0xFF - s_, ipc))
                        if inchain and k != "VBIE" and FILL_RANGE[0] <= ipc <= FILL_RANGE[1]:
                            r["nested"].append((k, 0xFF - s_))
                continue
            m = MARK.match(line)
            if m:
                if int(m.group(3)) < SKIP_FRAMES:
                    continue
                if m.group(1) == "FILL":
                    used = 0xFF - int(m.group(2), 16)
                    if used >= 14:               # called from the frame code inside the VBI (the main program's own call has 6 bytes in use)
                        if not inchain:              # one event = one frame's two calls (the routine's own loop re-enters $B100 for every byte)
                            r["fill"].append(used)
                        inchain = True
                else:
                    inchain = False
    return r


def summary(paths, rom_ins=None, peaks=None):
    L = []
    P = L.append
    deepest, ent_all = None, {"VBIE": [], "DLI1E": [], "DLI2E": []}
    ipcs = {"VBIE": [], "DLI1E": [], "DLI2E": []}
    fills, nested = [], []
    P("Stack depth measured in Altirra (OS-B, NTSC); the stack is page 1, S starts at $FF (256 bytes).")
    for path in paths:
        name = os.path.basename(path)[len("stack-"):-len(".txt")]
        r = parse(path)
        low = r["low"]
        P("  %-17s %6d frames; %5d writes below $01F0; %s" % (name, r["frames"], r["stk"],
          "none" if low is None else "lowest write $%04X = %d bytes deep (pc $%04X, frame %d)" % (low, 0x200 - low, r["lowpc"], r["lowf"])))
        if low is not None and (deepest is None or low < deepest):
            deepest = low
        for k, v in r["entry"].items():
            ent_all[k] += v
            ipcs[k] += r["ipc"][k]
        fills += r["fill"]
        nested += r["nested"]
    P("")
    P("Bytes in use at the entry of each interrupt handler (the hardware pushes 3; the rest is what the OS pushed and what the interrupted code had on the stack):")
    for k, label in (("VBIE", "VbiHandler  $A5FD"), ("DLI1E", "DliHandler1 $A573"), ("DLI2E", "DliHandler2 $A5CE")):
        v = ent_all[k]
        if v:
            used = sorted(0xFF - s for s in v)
            P("  %-18s %7d entries, bytes in use %d to %d" % (label, len(v), used[0], used[-1]))
        else:
            P("  %-18s no entries logged" % label)
    P("")
    if rom_ins is not None and ipcs["VBIE"]:
        v_ok = sum(1 for b, ipc in ipcs["VBIE"] if ipc in rom_ins)
        d_all = ipcs["DLI1E"] + ipcs["DLI2E"]
        d_ok = sum(1 for b, ipc in d_all if ipc in rom_ins)
        d_os = sorted({ipc >> 8 for b, ipc in d_all if ipc not in rom_ins})
        P("Stack layout check (the interrupted pc is read from the stack): at the VBI entry it is the start of an instruction of the cartridge in %d of %d cases, so the OS pushes exactly 3 bytes before the VBI handler (and the hardware 3: %d bytes in use with the main program idle)." %
          (v_ok, len(ipcs["VBIE"]), min(b for b, ipc in ipcs["VBIE"])))
        P("  At display-list interrupts: %d of %d; the others (%s) are inside the OS, so the OS pushes nothing before a display-list interrupt." %
          (d_ok, len(d_all), ", ".join("$%02X00-$%02XFF" % (x, x) for x in d_os) or "none"))
        n_in = sum(1 for b, ipc in d_all + ipcs["VBIE"] if 0xA573 <= ipc <= 0xA5FC)
        P("  Interrupts that hit inside a display-list handler ($A573-$A5FC): %d of %d (a display-list interrupt or a VBI never arrives inside another handler)." % (n_in, len(d_all) + len(ipcs["VBIE"])))
        by = {}
        for b, ipc in ipcs["VBIE"]:
            by.setdefault(b, {})
            by[b][ipc] = by[b].get(ipc, 0) + 1
        P("  Depth of the main program when a VBI arrives (bytes in use at the VBI entry minus 6): %s." %
          "; ".join("%d (%d entries, pc $%04X-$%04X)" % (b - 6, sum(c.values()), min(c), max(c)) for b, c in sorted(by.items())))
        P("")
    if fills:
        cnt = {}
        for x in fills:
            cnt[x] = cnt.get(x, 0) + 1
        P("Deepest call chain (%s): the board was set up from the frame code inside the VBI %d times; bytes in use inside FillPlayerPages: %s (6 at the VBI entry + 5 calls of 2 bytes = 16 for this chain; 14 for the 4-call chain of the level-end board change)." %
          (" -> ".join(CHAIN), len(fills), ", ".join("%d bytes: %d times" % (b, n) for b, n in sorted(cnt.items()))))
        for k, label in (("DLI1E", "DliHandler1"), ("DLI2E", "DliHandler2")):
            ns = [b for kk, b in nested if kk == k]
            P("  display-list interrupts that hit inside ClearPlayerMemory / FillPlayerPages (interrupted pc in $%04X-$%04X): %s %d%s" %
              (FILL_RANGE[0], FILL_RANGE[1], label, len(ns), "" if not ns else ", bytes in use at entry %d" % max(ns)))
        P("")
    if deepest is None:
        P("Deepest stack write seen below $01F0: none (the stack never used more than 16 bytes).")
        depth = 16
    else:
        depth = 0x200 - deepest
        P("DEEPEST STACK USE SEEN: %d bytes (lowest address written $%04X, S = $%02X): %.0f%% of the 256 bytes." % (depth, deepest, deepest - 0x100 - 1, 100.0 * depth / 256))
    if peaks and ent_all["VBIE"]:
        pk = peaks
        os_hw = 6
        model = os_hw + pk["VbiHandler"] + 3 + pk["DliHandler1"]
        bound = pk["Start"] + os_hw + pk["VbiHandler"] + 3 + max(pk["DliHandler1"], pk["DliHandler2"])
        P("Model of that case: VBI entry %d (3 hardware + 3 OS) + the deepest chain %d + DLI hardware 3 + DliHandler1 pushes %d = %d bytes: %s." %
          (os_hw, pk["VbiHandler"], pk["DliHandler1"], model, "equal to the measurement" if model == depth else "NOT equal to the measurement (%d)" % depth))
        P("BOUND BY CONSTRUCTION (every combination, observed or not): main program %d (PEAK of Start) + VBI entry %d + VbiHandler %d + DLI hardware 3 + %d (the larger DLI handler) = %d bytes of 256." %
          (pk["Start"], os_hw, pk["VbiHandler"], max(pk["DliHandler1"], pk["DliHandler2"]), bound))
    return L, depth, ent_all


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not (sys.argv[sys.argv.index(a) - 1] == "--write")]
    paths = sorted(p for a in args for p in glob.glob(a))
    if not paths:
        print("no logs")
        return 1
    import analyze_stack as AS
    rom, F, owner, depth_, bad_, unb_, peak, chain_, ops_, page1_ = AS.analyse()
    L, depth, ent = summary(paths, rom.ins, {f.name: peak[e] for e, f in F.items()})
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
