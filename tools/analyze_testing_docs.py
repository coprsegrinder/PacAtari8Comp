"""Stage 98 (testing and verification documentation): ONE chapter that records HOW the project was tested (the procedures and how to run each), WHAT came out (the results, with their numbers), what it was tested ON (the compatibility information),
what is KNOWN not to be verified (known issues and the open items of the register) and what is DIFFERENT and unresolved (the discrepancies).  GENERATED from the register (docs/OPEN-VERIFICATION.md: the counts of its items, the open ones), the test
modules (their number and the number of test functions, by area), the CMake tests, the evidence summaries and the ledger of discrepancies (docs/56); the curated parts (the chain of verification, the claims table, the procedures) are the tables at the top.
Usage: python -I tools/analyze_testing_docs.py [--doc docs/64-testing-and-verification.md]
Tests: tests/test_testing_docs.py (the chapter is current; every claim names register entries and chapters that exist; the counts are the real ones)."""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import analyze_build_docs as BD  # noqa: E402

# the claims of the project and how each was verified: claim, how, result, register entries, chapters
CLAIMS = [
    ("The disassembly is the ROM", "the listing assembles with ca65 / ld65; size and SHA-256 compared with the original; the recursive trace covers every byte once", "byte-identical; 2,925 instructions, 5,946 + 2,246 bytes, no byte uncovered", "C-10", "`09`, `10`, `59`"),
    ("Every routine and instruction was observed", "36 live sessions of the real game in Altirra, traced instruction by instruction; the 5 never executed are dead paths shown from the code", "2,920 of 2,925 instructions; 79 of 79 routines entered; 124 of 124 `JSR` sites run", "C-61, C-62, OV-59", "`32`"),
    ("The data formats and tables are right", "every byte of every region decoded by a tool and compared with the RAM the ROM's own `Start` builds on the concrete 6502", "byte-equal; 19 of 19 checks of the asset pack", "C-90", "`12`, `47`"),
    ("The 22 algorithms and 81 routines behave as documented", "each algorithm written as a model and run against the ROM on the concrete 6502 over random states, the whole memory compared after every call", "0 differences in about 940,000 calls; every instruction executed", "C-59, C-60", "`31`"),
    ("The state machines are what the rules say", "68 rules written from the code, every transition of 20 sessions checked, every pair run on the interpreter, and proved by abstract interpretation", "0 transitions without a rule; 68 of 68 rules seen; 0 stores that no rule allows", "C-64, C-65, C-66", "`34`"),
    ("The interface to the machine is closed and complete", "the 14 inputs read by 35 instructions; the whole game run twice with every undeclared external cell random", "0 differences in 3,000 runs; every chip write traced live (4.66 million, 0 outside the 71 sites)", "C-67, C-88", "`35`, `45`"),
    ("The timing fits the frame", "the handler measured over 219,987 frames; static bound per class; heaviest play frame searched", "never late; 12 of 15 classes proved; the play frame **not proved** (bound 2x the budget; the heaviest found 89%)", "C-71 to C-82, OV-64 (limit)", "`38`, `39`"),
    ("The sound is the original's", "register writes traced and the audio recorded in Altirra; a model of the POKEY compared by spectra", "every one of the 31 write sites run; the model within 0.5% of the emulator's level; **phase** not matched", "C-08 to C-23, C-115", "`22`"),
    ("The collision geometry is the hardware's", "73,111 random scenes and 27,193 frames of real play compared with the real GTIA's registers in Altirra", "0 differences in all 16 registers", "C-94, C-95", "`50`"),
    ("The Python port equals the ROM", "the port-form core and the application layer run beside the ROM on the concrete 6502, the whole state compared after every call or frame", "0 differences in 243,000 core calls, 8,500 frame runs and the application sessions", "C-87, C-104 to C-107", "`44`"),
    ("The C port equals the Python port", "the recorded calls of the Python port replayed through the C (85 vector files, 21 ctest sets), every region of the World compared", "0 differences; the vectors are shown to see a wrong byte, RANDOM value and byte order", "C-96 to C-111", "`51`"),
    ("**The C port equals the ROM**", "the C and the ROM run side by side on the same inputs and RANDOM bytes, the whole state, the ordered chip writes and the RANDOM reads compared after every frame", "**709,116 frames, 0 differences**: the recorded sessions, random and edge games, games played on purpose, long games, a final sweep", "C-122, C-123, C-125, C-126", "`52`-`56`"),
    ("The C port behaves like the ROM", "the frame classes, the changes of the 20 state variables and the handler's routine call counts compared", "171,300 frames, 0 differences; 46 of 55 routine counts equal, the 9 others explained by number", "C-123", "`53`"),
    ("The picture and the sound of the port look and sound like the original's", "the renderer compared pixel by pixel with Altirra's captures; the sound by spectra", "7 of 12 captures exact everywhere, 212 pixels in 5 captures at moving objects; the pitch, level and timing of the sound, not its phase", "C-114, C-115", "`42`, `22`"),
    ("The port builds and plays the same on another system and compiler", "clang and gcc at five optimisation levels, four language standards, Windows and Ubuntu, with the sanitizers; 13 games bit-identical", "59 of 59 Linux steps; 0 warnings; the same hash on every frame", "C-117, C-118, C-124", "`54`"),
    ("A clean checkout builds and passes", "the instructions of `63` run on a copy with no derived file", "10 of 10 steps; 37 of 39 tests (2 need the emulator's logs)", "C-134", "`63`"),
    ("A later change does not break any of this", "the regression run: build, `ctest`, 30 golden games with state / run / video / audio digests, the Python tests; shown to see a one-line mutation", "passes in about 6 minutes", "C-125", "`55`"),
]

# the procedures: what, command, what it needs, how long, what a pass means
PROCEDURES = [
    ("Unit and integration tests of the C port", "`ctest --test-dir build/c --output-on-failure`", "the build; the ROM for the blob; the vectors (recipe C of `63`) for the vector sets", "10 s", "39 tests; a test whose data is missing is **skipped, never passed**"),
    ("Python tests", "`python -m unittest discover -s tests -p \"test_*.py\"`", "the ROM; Pillow for some modules; the build for the C ones", "34 minutes for all 864", "every module OK; `tests.test_c_*` and the comparisons are the long ones"),
    ("The regression run", "`python -I tools/run_regression.py`", "gcc or clang, CMake, the ROM, the vectors", "6 minutes", "ALL PASSED; `--full` adds clang, the ROM comparison and Linux with sanitizers"),
    ("The C against the ROM, frame by frame", "`python -I tools/check_c_vs_rom.py REPLAY`", "the build, the ROM, a replay with RANDOM bytes (`make_rom_*_replays.py`)", "1 to 4 minutes per 6,000 frames", "`NO DIFFERENCE`; a difference is reported at the first frame with the bytes that differ"),
    ("Behaviour: classes, state variables, paths", "`python -I tools/check_behaviour.py REPLAY ... [--exe COVERAGE_BUILD]`; `--paths` for the routine counts", "the same, and a `gcc --coverage` build for the paths", "25 minutes for 117,000 frames", "0 differences in classes and transitions; the call counts equal or explained"),
    ("Games played on purpose / edge games / sweeps", "`make_rom_bot_replay.py`, `make_rom_edge_replays.py`", "the ROM played by a look-ahead player (tens of minutes per level)", "-", "the C equals the ROM on them (`53`, `55`)"),
    ("Linux and sanitizers", "`sh tools/build_test_posix.sh gcc build/posix-gcc [-fsanitize=address,undefined]`", "WSL2 with gcc", "2.5 minutes", "59 of 59"),
    ("A clean copy", "`python -I tools/check_clean_build.py`", "git, the build tools, the ROM", "19 minutes (17 for the vectors)", "ALL PASSED, 10 steps"),
    ("The original's integrity", "`python -I tools/verify_originals.py`", "`original/`", "1 s", "ALL OK"),
    ("The live evidence", "`tools/run_*.ps1` with `tools/*.cmd`", "Windows, PowerShell, Altirra 4.40, the NTSC OS ROM, the ROM", "minutes to hours per session", "the evidence summaries of `analysis/`, the register"),
    ("Regenerating a chapter", "`python -I tools/analyze_*_docs.py --doc docs/NN-....md`", "Python (Pillow for some)", "seconds", "the chapter's own test says it is current"),
]

# the areas of the test modules, by name
AREAS = [
    ("the C port against its oracles", ("test_c_", "test_shell", "test_behaviour", "test_regression", "test_constants")),
    ("the documentation generators", ("test_source_docs", "test_original_architecture", "test_binary_docs", "test_data_docs", "test_behaviour_docs", "test_resources_docs", "test_build_docs", "test_testing_docs", "test_correlation", "test_relationships", "test_variables", "test_structures", "test_pointers", "test_locals", "test_stack", "test_function", "test_cfg")),
    ("the analysis of the binary", ("test_disasm", "test_rebuild", "test_labels", "test_zp_names", "test_streams", "test_nibble", "test_decode", "test_tables", "test_levels", "test_ghost", "test_data", "test_formats")),
    ("the models and the Python port", ("test_algorithms", "test_app", "test_core", "test_play", "test_draw", "test_input", "test_output", "test_state", "test_iface", "test_comm", "test_absint", "test_collide", "test_gtia", "test_world", "test_vectors")),
    ("the sound and the emulator evidence", ("test_sound", "test_pokey", "test_mixer", "test_hp", "test_full_waveform", "test_ghost_sweep", "test_video", "test_audio", "test_render", "test_hw", "test_io", "test_startup", "test_mainloop", "test_tracing", "test_coverage", "test_memory", "test_register")),
]


def register():
    with open(os.path.join(ROOT, "docs", "OPEN-VERIFICATION.md"), encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    ov = []
    for l in lines:
        if l.startswith("| OV-"):
            c = [x.strip() for x in l.split("|")]
            ov.append((c[1], c[2], c[3], c[4] if len(c) > 4 else ""))
    cs = [l for l in lines if re.match(r"\| C-\d+ ", l)]
    return ov, cs


def test_inventory():
    mods = sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py")))
    per = collections.OrderedDict((a, [0, 0]) for a, p in AREAS)
    other = [0, 0]
    total = 0
    for p in mods:
        name = os.path.basename(p)[:-3]
        with open(p, encoding="utf-8") as fh:
            n = len(re.findall(r"^\s+def test_", fh.read(), re.M))
        total += n
        for a, prefixes in AREAS:
            if name.startswith(prefixes):
                per[a][0] += 1
                per[a][1] += n
                break
        else:
            other[0] += 1
            other[1] += n
    return per, other, len(mods), total


def cmake_tests():
    return BD.cmake_facts()["tests"]


def ledger_items():
    with open(os.path.join(ROOT, "docs", "56-discrepancy-analysis.md"), encoding="utf-8") as fh:
        return len(re.findall(r"^\| \d+ \| stage", fh.read(), re.M))


def first_sentence(t, n=170):
    s = re.split(r"(?<=[.;])\s", t, maxsplit=1)[0]
    s = re.sub(r"\*\(closed[^)]*\)\*\s*", "", s)
    return (s[:n - 3] + "...") if len(s) > n else s


def doc():
    ov, cs = register()
    st = collections.Counter(x[2] for x in ov)
    per, other, nmods, ntests = test_inventory()
    ct = cmake_tests()
    ev = len(glob.glob(os.path.join(ROOT, "analysis", "evidence-*-summary.txt")))
    L = []
    W = L.append
    W("# 64 - Testing and Verification (checklist stage 98)")
    W("")
    W("GENERATED by `python -I tools/analyze_testing_docs.py --doc docs/64-testing-and-verification.md` from the register `OPEN-VERIFICATION.md` (its counts and its open items), the test modules, the CMake tests, the evidence summaries and the ledger `56`; the claims table and the procedures are tables in the tool. Tests: `tests/test_testing_docs.py`.")
    W("")
    W("Checklist stage 98: \"Record testing procedures, results, compatibility information, known issues, and unresolved discrepancies.\" This chapter is the **map of the verification**: what was claimed, how each claim was checked, what came out, what it was checked on, and what is not verified. The register is the full list (every check that was skipped, partial or done with an aid, one line each); the numbered chapters hold the evidence.")
    W("")
    W("## 1. The result in short")
    W("")
    W("- **The C port equals the original ROM, frame by frame, in the whole state, the ordered sound-chip writes and the RANDOM reads: 709,116 frames, 0 differences** (`52`-`56`), and in the frame classes, the state variables and the outputs on 171,300 frames (`53`). Every difference found along the way had a cause and was corrected (`56`: " + str(ledger_items()) + " items, none a difference in what the game does).")
    W("- **The register holds %d verification items (OV-nn): %d closed, %d of them closed as a documented limit, %d open** (section 6), and %d numbered results (C-nn). **%d evidence summaries** are kept in `analysis/`." % (len(ov), sum(v for k, v in st.items() if k.startswith("CLOSED")), sum(v for k, v in st.items() if "limit" in k or "simulated" in k), st.get("OPEN", 0) + st.get("PARTIAL", 0), len(cs), ev))
    W("- **%d test modules with %d test functions** in `tests/` (Python) and **%d tests** under `ctest` (C); every one passes (`run_regression.py`: ALL PASSED)." % (nmods, ntests, len(ct)))
    W("- **Nothing was verified on real hardware**: every measurement is against Altirra 4.40 (NTSC, Atari 800, OS Rev B), by the owner's decision (OV-01, OV-42b; C-27).")
    W("")
    W("## 2. The chain of verification")
    W("")
    W("```mermaid")
    W("flowchart LR")
    W("  HW[the real game<br/>in Altirra 4.40] -->|traces, recordings, captures| ROM[the ROM on the<br/>6502 interpreter]")
    W("  ROM -->|0 differences| PY[the Python port<br/>and the models]")
    W("  PY -->|vectors, sessions| C[the C port]")
    W("  ROM -->|709,116 frames, whole state| C")
    W("  C --> POSIX[Linux, sanitizers,<br/>other compilers]")
    W("  C --> CLEAN[a clean copy]")
    W("```")
    W("")
    W("Each arrow is a comparison that was made and shown to see a difference (a corrupted byte, RANDOM value, chip write or state variable is reported at the frame it was put in). The comparison with the ROM does **not** go through the Python port: the C and the interpreted ROM get the same inputs and the same RANDOM bytes.")
    W("")
    W("## 3. What was claimed, how it was checked, what came out")
    W("")
    W("| Claim | How it was checked | Result | Register | Chapters |")
    W("|---|---|---|---|---|")
    for a, b, c, d, e in CLAIMS:
        W("| %s | %s | %s | %s | %s |" % (a, b, c, d, e))
    W("")
    W("## 4. The procedures")
    W("")
    W("| What | Command | Needs | Time | A pass means |")
    W("|---|---|---|---|---|")
    for a, b, c, d, e in PROCEDURES:
        W("| %s | %s | %s | %s | %s |" % (a, b, c, d, e))
    W("")
    W("### 4.1 The C tests (`ctest`)")
    W("")
    W("%d tests: %s." % (len(ct), ", ".join("`%s`" % t for t in ct)))
    W("")
    W("### 4.2 The Python tests, by area")
    W("")
    W("| Area | Modules | Test functions |")
    W("|---|---|---|")
    for a, (n, t) in per.items():
        W("| %s | %d | %d |" % (a, n, t))
    W("| other | %d | %d |" % tuple(other))
    W("| **all** | **%d** | **%d** |" % (nmods, ntests))
    W("")
    W("## 5. What it was checked on (compatibility)")
    W("")
    W("| Environment | Result | Chapter |")
    W("|---|---|---|")
    W("| Windows 11, gcc 14.2.0 and clang 19.1.1 (WinLibs), x86-64 | builds with 0 warnings under `-std=c99 -Wall -Wextra -Wpedantic -Wconversion -Werror`; all tests pass; the reference of every measurement | `54`, `63` |")
    W("| Ubuntu 26.04 in WSL2, gcc 15.2.0 | 59 of 59 steps; also with AddressSanitizer, UndefinedBehaviorSanitizer and LeakSanitizer; 13 games bit-identical to Windows | `54` |")
    W("| Optimisation `-O0 -O1 -O2 -O3 -Os`, standards C99 / C11 / C17 / C2x | the same hash on every frame; every source compiles | `54` |")
    W("| A clean copy of the project | builds, installs the blob from the ROM, runs, reproduces a golden game | `63` |")
    W("| The original under PAL timing and Altirra's built-in OS | the same game (sound verified; historical, the project now uses only the NTSC OS ROM) | `38`, `22`, C-24 to C-26 |")
    W("| **Not tried** | MSVC, macOS, 32-bit, big-endian, ARM, other C libraries, other compiler versions, the real front end (stage J), real hardware | OV-72, OV-01 |")
    W("")
    W("## 6. Known issues and open items")
    W("")
    W("**Open in the register** (`OPEN-VERIFICATION.md`):")
    W("")
    W("| ID | What | Status |")
    W("|---|---|---|")
    for i, text, status, how in ov:
        if status in ("OPEN", "PARTIAL"):
            W("| %s | %s | %s |" % (i, first_sentence(text).replace("|", "/"), status))
    W("")
    W("**Closed as a documented limit** (not verified, by decision or by the nature of the evidence):")
    W("")
    W("| ID | What |")
    W("|---|---|")
    for i, text, status, how in ov:
        if "limit" in status or "simulated" in status:
            W("| %s | %s |" % (i, first_sentence(text).replace("|", "/")))
    W("")
    W("**The whole Python suite was run once** (2026-11-23): 864 tests in 33 minutes (`analysis/evidence-python-suite-summary.txt`); 2 failed, both generated chapters that were stale (`32`, `63`), regenerated; every other test passed. **Known issues of the tests themselves:** two of the 39 C tests (`vectors_gtia`, `vectors_gtia_world`) need the emulator's collision logs and are skipped on a clean copy; a C test whose derived data is missing is skipped, never passed; the comparison of quick console changes is not made (they are a race of the original, OV-73); the Python tests that use the asset pack need Pillow; the full vector generation takes about 17 minutes.")
    W("")
    W("## 7. Unresolved discrepancies")
    W("")
    W("**None between the C port and the ROM**: every difference found was explained and either corrected or recorded as a decision or a limit (`56`). What differs by decision or by the limit of the evidence (RANDOM from a model, NTSC only, the GTIA model, the picture at moving objects, the phase of the sound, no frame pacing, the input races, the quirks of the original kept) is the table in `56` section 3 and `61` section 5.2. The two open items of section 6 are comparisons not made, not differences found.")
    W("")
    W("## 8. How to read the evidence")
    W("")
    W("`OPEN-VERIFICATION.md` is the index: each **OV-nn** is a check that was skipped, partial or done with an aid, closed with a **C-nn** result that says what was run, on what, with what outcome and what it does not show. Each C-nn names its evidence file (`analysis/evidence-*-summary.txt`) and its test. The rule (the owner's, 2026-11-11): whenever a check is skipped, only partly done, done with an aid, or a result is unexplained, a line is added at once; nothing is called verified without it.")
    return "\n".join(L) + "\n"


def main():
    text = doc()
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o) if not os.path.isabs(o) else o, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote", o)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
