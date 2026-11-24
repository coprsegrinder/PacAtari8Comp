"""Stage 97 (build and dependency documentation): ONE chapter that says what is needed to build, test and run the project, what each dependency is for, how it is configured and how to do each thing, step by step; the steps were run on a clean
copy of the project (tools/check_clean_build.py; evidence in analysis/evidence-clean-build-summary.txt).  GENERATED from the CMake files (the targets, the tests, the flags), the Python sources (which tools need which third-party module), the generators and
the harnesses in tools/; the curated parts (the verified versions, the recipes, the dependency table) are the tables at the top.
Usage: python -I tools/analyze_build_docs.py [--doc docs/63-build-and-dependencies.md]
Tests: tests/test_build_docs.py (the chapter is current; the CMake facts hold; the commands it gives exist; the clean-build evidence says ALL PASSED)."""
import ast
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# what was used and what was verified with it (the dates and registers are where the evidence is)
VERIFIED = [
    ("clang", "19.1.1 (WinLibs, Windows 11)", "C-81 to C-88, C-117, C-118, C-124"),
    ("gcc", "14.2.0 (WinLibs, Windows 11); 15.2.0 (Ubuntu 26.04 in WSL2)", "C-117, C-124"),
    ("CMake", "3.30.4 (the files ask for 3.16)", "C-117"),
    ("Ninja", "1.12.1", "C-117"),
    ("Python", "3.14.0", "all"),
    ("numpy", "2.5.4", "the audio analyses"),
    ("Pillow", "13.0.0", "the asset pack, the screenshot checks"),
    ("cc65 (ca65, ld65)", "V2.19, Git eebf54a snapshot", "C-10 (the byte-exact rebuild)"),
    ("Altirra", "4.40 (NTSC Atari 800, OS Rev B)", "docs/04, all live evidence"),
    ("WSL2 + Ubuntu", "26.04, kernel 6.18, x86-64", "C-124"),
]

# dependency, needed for, kind, source, licence
DEPENDENCIES = [
    ("a C99 compiler (gcc or clang)", "building the C port", "**required**", "any system compiler; tried: WinLibs gcc / clang (winget `BrechtSanders.WinLibs.POSIX.UCRT.LLVM`), Ubuntu gcc", "GPL with the runtime exception / Apache-2.0 with LLVM exceptions"),
    ("CMake 3.16 or later, and a generator (Ninja)", "building the C port the supported way", "**required** (or `tools/build_test_posix.sh` with `cc`, `ar` and `sh`)", "cmake.org, ninja-build.org", "BSD-3-Clause / Apache-2.0"),
    ("the owner's `Pac-Man.rom` (8,192 bytes, SHA-256 in `03`)", "running the port: the installer makes the asset blob from it", "**required**, never shipped: `original/Pac-Man.rom`", "the owner", "copyrighted: not part of the project"),
    ("Python 3 (3.14 used), standard library only", "the derived test data, the generators of the C sources, the replays, the regression run, the documentation generators", "**required for the tests**, not for building or running the port", "python.org", "PSF"),
    ("numpy", "the audio and spectrum analyses (`tools/analyze_*sound*.py`, `check_audio_c.py` ...)", "optional: re-verifying the sound against recordings", "PyPI", "BSD-3-Clause"),
    ("Pillow", "the asset pack's font rendering and the PNG previews, the screenshot checks", "optional: `tools/asset_pack.py`, `check_assets.py`; the C installer does not need it", "PyPI", "HPND"),
    ("git", "`tools/run_regression.py --full` and `tools/check_clean_build.py` (the file list)", "optional", "git-scm.com", "GPL-2.0"),
    ("cc65 (`ca65`, `ld65`)", "rebuilding the ROM from `src/asm/pacman.s` byte for byte (`tools/build_rom.py`)", "optional: the analysis side", "cc65.github.io (`external-tools/cc65`)", "zlib"),
    ("Altirra 4.40, PowerShell, the NTSC OS ROM `original/Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom`", "the live evidence: the traces, recordings and screenshots of the real game (`tools/*.ps1`, `tools/*.cmd`)", "optional: re-running the measurements; Windows only", "virtualdub.org (`external-tools/Altirra`)", "GPL-2.0-or-later"),
    ("WSL2 with a Linux distribution that has `gcc`", "the Linux build and tests (`tools/build_test_posix.sh`)", "optional", "Microsoft", "-"),
    ("EightBit Atari-Regular font", "the OS character set the text lines use", "shipped in `third-party/`", "github.com/a8bit/EightBit-Atari-Fonts", "SIL OFL 1.1"),
]

# the recipes: the title, the commands, what you get
RECIPES = [
    ("A. Build the C port and run its tests (the minimum)", [
        "# put your own ROM at original/Pac-Man.rom",
        "cmake -S src/c -B build/c -G Ninja -DCMAKE_BUILD_TYPE=Release        # add -DCMAKE_C_COMPILER=clang (or gcc) to choose",
        "cmake --build build/c",
        "ctest --test-dir build/c --output-on-failure",
    ], "`pacman_a8` and the tests under `build/c/`. The first `ctest` run makes `resources/pack/assets.pmab` from the ROM (the installer); the tests that need recorded vectors are **skipped, not passed**, until recipe C has been run."),
    ("B. Build and test without CMake (any POSIX system with a C99 compiler)", [
        "sh tools/build_test_posix.sh gcc build/posix-gcc                       # extra flags after the folder: -O0, -fsanitize=address,undefined ...",
    ], "the same sources, flags and tests as recipe A, in `build/posix-gcc/` (59 steps; used on Ubuntu in WSL2)."),
    ("C. Make the derived test data", [
        "python -I tools/make_vectors.py",
        "python -I tools/make_app_sequences.py",
    ], "the recorded calls and sessions in `resources/vectors/` (from the ROM; standard library only; about 17 and 2 minutes); then recipe A's `ctest` passes 37 of its 39 tests. **The other two (`vectors_gtia`, `vectors_gtia_world`) stay skipped**: their vectors are made by `tools/make_collide_vectors.py` from the emulator's collision logs (`analysis/raw-logs`, not reproducible without Altirra; the collision model is also checked on the live game by `50`)."),
    ("D. Play a game headless", [
        "python -I tools/make_rom_fuzz_replays.py build/replays 1 --frames 12000    # or tools/make_replay.py --script FILE OUT.pmrp",
        "build/c/shell/pacman_a8 run build/replays/fuzz1.pmrp --video --audio --ppm last.ppm --time",
    ], "the state hash, the run, video and audio digests, the time per frame, and the last picture. Options: `--frames N`, `--hashes FILE`, `--states FILE`, `--root DIR`, `--keep-high-score`, `--log`; `pacman_a8 info REPLAY`. The program writes only below the main folder."),
    ("E. Regenerate the generated C sources", [
        "python -I tools/make_c_world.py; python -I tools/make_c_tables.py; python -I tools/make_c_assets.py",
        "python -I tools/make_c_rom_layout.py; python -I tools/make_c_palette.py; python -I tools/make_c_constants.py",
    ], "`src/c/core/world.[ch]`, `tables.[ch]`, `constants.h`, `src/c/assets/rom_layout.[ch]`, `src/c/render/palette.[ch]`; `tests/test_regression.py` runs all of them and checks that they write the same bytes."),
    ("F. Check the whole project at once", [
        "python -I tools/run_regression.py                  # about 6 minutes: build, ctest, 30 golden games, the Python tests",
        "python -I tools/run_regression.py --full           # adds clang, the C against the ROM on every game, the Linux build with sanitizers",
        "python -I tools/check_clean_build.py                # the instructions of this chapter, on a clean copy of the project",
    ], "a pass or a list of what differs; the golden digests are `analysis/golden-digests.txt`."),
    ("G. Rebuild the ROM from the disassembly (the analysis side)", [
        "python -I tools/build_rom.py",
    ], "assembles `src/asm/pacman.s` with ca65 / ld65 (`external-tools/cc65`) and compares size and SHA-256 with `original/Pac-Man.rom`: byte-identical or the first differing offset."),
    ("H. The Python tests", [
        "python -m unittest discover -s tests -p \"test_*.py\"      # all; or name modules: python -m unittest tests.test_shell tests.test_behaviour",
    ], "every test module (%(py_tests)d of them); the long ones (the comparisons with the ROM) take minutes."),
]


def cmake_facts():
    """parse src/c/**/CMakeLists.txt"""
    f = {"libs": [], "exes": [], "tests": [], "fixtures": 0}
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "c", "**", "CMakeLists.txt"), recursive=True)):
        with open(p, encoding="utf-8") as fh:
            t = fh.read()
        f["libs"] += re.findall(r"add_library\((\w+)", t)
        f["exes"] += re.findall(r"add_executable\((\w+)", t)
        f["tests"] += re.findall(r"add_test\(NAME (\w+)", t)
        f["tests"] += re.findall(r"pm_vector_test\((\w+)", t)
    with open(os.path.join(ROOT, "src", "c", "CMakeLists.txt"), encoding="utf-8") as fh:
        top = fh.read()
    f["min"] = re.search(r"cmake_minimum_required\(VERSION ([\d.]+)\)", top).group(1)
    f["std"] = re.search(r"CMAKE_C_STANDARD (\d+)", top).group(1)
    f["flags"] = re.search(r"add_compile_options\(([^)]*)\)", top).group(1)
    return f


def third_party():
    std = set(sys.stdlib_module_names)
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "tools", "*.py")) + glob.glob(os.path.join(ROOT, "tests", "*.py"))):
        try:
            with open(p, encoding="utf-8") as fh:
                t = ast.parse(fh.read())
        except SyntaxError:
            continue
        for n in ast.walk(t):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                names = [n.module.split(".")[0]]
            for m in names:
                if m not in std and not os.path.exists(os.path.join(ROOT, "tools", m + ".py")) and not os.path.exists(os.path.join(ROOT, "tests", m + ".py")):
                    out.setdefault(m, set()).add(os.path.basename(p))
    return out


def imports_of(path):
    with open(path, encoding="utf-8") as fh:
        t = ast.parse(fh.read())
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out


def third_party_closure(script):
    """the third-party modules a tool reaches through the tools it imports"""
    std = set(sys.stdlib_module_names)
    seen, found, stack = set(), set(), [script]
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        p = os.path.join(ROOT, "tools", m + ".py")
        if not os.path.exists(p):
            continue
        for i in imports_of(p):
            if os.path.exists(os.path.join(ROOT, "tools", i + ".py")):
                stack.append(i)
            elif i not in std:
                found.add(i)
    return found


# the scripts the recipes use
RECIPE_SCRIPTS = ["make_vectors", "make_app_sequences", "make_replay", "make_rom_fuzz_replays", "make_rom_edge_replays", "make_rom_bot_replay", "make_c_world", "make_c_tables", "make_c_assets", "make_c_rom_layout", "make_c_palette", "make_c_constants",
                  "run_regression", "check_clean_build", "check_c_vs_rom", "check_behaviour", "build_rom", "verify_originals", "analyze_source_docs", "analyze_original_architecture", "analyze_binary_docs", "analyze_data_docs", "analyze_behaviour_docs", "analyze_resources_docs", "analyze_build_docs"]


def counts():
    c = {}
    c["ps1"] = len(glob.glob(os.path.join(ROOT, "tools", "*.ps1")))
    c["cmd"] = len(glob.glob(os.path.join(ROOT, "tools", "*.cmd")))
    c["py_tools"] = len(glob.glob(os.path.join(ROOT, "tools", "*.py")))
    c["py_tests"] = len(glob.glob(os.path.join(ROOT, "tests", "test_*.py")))
    c["gens"] = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "tools", "make_c_*.py")))
    return c


def doc():
    cm = cmake_facts()
    tp = third_party()
    c = counts()
    L = []
    W = L.append
    W("# 63 - Build and Dependencies (checklist stage 97)")
    W("")
    W("GENERATED by `python -I tools/analyze_build_docs.py --doc docs/63-build-and-dependencies.md` from the CMake files, the Python sources and the tool folder; the verified versions, the dependency table and the recipes are tables in the tool. Tests: `tests/test_build_docs.py`. **The instructions were run on a clean copy of the project** (`tools/check_clean_build.py`, `analysis/evidence-clean-build-summary.txt`).")
    W("")
    W("Checklist stage 97: \"Document the compiler, libraries, frameworks, external dependencies, configuration, and build instructions.\" The project has **three layers with different needs**: the **C port** (a C99 compiler, CMake, your ROM), the **tests and tools** (Python, standard library, and two optional packages), and the **evidence** (an emulator and PowerShell, Windows only). Nothing needs the network at build time.")
    W("")
    W("## 1. What you need")
    W("")
    W("| Dependency | Needed for | Required? | Where from | Licence |")
    W("|---|---|---|---|---|")
    for a, b, k, d, e in DEPENDENCIES:
        W("| %s | %s | %s | %s | %s |" % (a, b, k, d, e))
    W("")
    W("**To build and run the port you need three things**: a C99 compiler, CMake with Ninja (or a POSIX shell), and your own `Pac-Man.rom` at `original/Pac-Man.rom`. No operating-system ROM, no emulator, no Python and no third-party library is needed for that. The **PAL OS ROM is not used** (the owner's decision of 2026-11-23: only the NTSC OS ROM, and only for the evidence).")
    W("")
    W("## 2. What it was verified with")
    W("")
    W("| Tool | Version | Evidence |")
    W("|---|---|---|")
    for a, b, d in VERIFIED:
        W("| %s | %s | %s |" % (a, b, d))
    W("")
    W("Not tried (OV-72): MSVC, macOS, a 32-bit or big-endian target, other C libraries than glibc and the Windows UCRT, other compiler versions.")
    W("")
    W("## 3. How the C port is built")
    W("")
    W("- **CMake %s or later**, C standard %s with extensions off, and for clang and gcc `%s`. No option of its own: the compiler is chosen with `-DCMAKE_C_COMPILER`, the build type with `-DCMAKE_BUILD_TYPE` (Release and Debug are tested)." % (cm["min"], cm["std"], cm["flags"]))
    W("- **%d libraries** (`%s`), **%d executables** (`%s`) and **%d tests** under `ctest`. The program is `shell/pacman_a8`; the installer `assets/install_assets` makes the asset blob from the ROM." % (len(cm["libs"]), "`, `".join(sorted(cm["libs"])), len(cm["exes"]), "`, `".join(sorted(cm["exes"])), len(cm["tests"])))
    W("- **No library but the C standard library** (`-lm` on Unix for the sound model); everything else is in `platform/` behind a small interface: files only through `fs.c` under the main folder, the clock through `timer.c`.")
    W("- **Configuration at run time**: none in files or the environment. The **main folder** is the current folder, or `--root DIR`; the ROM is `original/Pac-Man.rom` under it, the blob `resources/pack/assets.pmab`, the high score and options `save/`, the log `logs/`; nothing outside the main folder is ever read or written.")
    W("")
    W("## 4. The recipes")
    W("")
    W("All commands run from the project's root (the main folder).")
    W("")
    for title, cmds, result in RECIPES:
        W("### " + title)
        W("")
        W("```")
        for x in cmds:
            W(x)
        W("```")
        W("")
        W(result % c if "%(" in result else result)
        W("")
    W("## 5. The Python side")
    W("")
    W("**%d tools** in `tools/` and **%d test modules** in `tests/`, all Python 3 with the standard library, **except**:" % (c["py_tools"], c["py_tests"]))
    W("")
    W("| Module | Files that import it | Used for |")
    W("|---|---|---|")
    use = {"numpy": "spectra and correlations of the sound recordings", "PIL": "the font, PNG previews, screenshot comparison"}
    for m in sorted(tp):
        W("| `%s` | %d (%s%s) | %s |" % (m, len(tp[m]), ", ".join("`%s`" % x for x in sorted(tp[m])[:4]), ", ..." if len(tp[m]) > 4 else "", use.get(m, "")))
    W("")
    needs = {m: third_party_closure(m) for m in RECIPE_SCRIPTS}
    pil = [m for m in RECIPE_SCRIPTS if "PIL" in needs[m]]
    other = sorted({x for v in needs.values() for x in v} - {"PIL"})
    W("**Neither module is needed to build or run the port, to make the recorded vectors (recipe C) or the replays (recipe D), to compare the C with the ROM (`check_c_vs_rom.py`, `check_behaviour.py`) or to rebuild the ROM.** The scripts of the recipes that import Pillow, directly or through `asset_pack.py`, are: %s. So recipe E (two of the six generators), the documentation generators and the Python tests of `run_regression.py` that use them need Pillow; no recipe script imports numpy%s." % (", ".join("`%s`" % m for m in pil), ("; other third-party modules reached: " + ", ".join(other)) if other else ""))
    W("")
    W("## 6. The generators")
    W("")
    W("The C sources `core/world.[ch]`, `tables.[ch]`, `constants.h`, `assets/rom_layout.[ch]` and `render/palette.[ch]` are written by %s (every one starts with `GENERATED by`; do not edit them by hand): they need the ROM and Python only." % ", ".join("`tools/%s`" % g for g in c["gens"]))
    W("")
    W("## 7. The evidence side")
    W("")
    W("%d PowerShell scripts (`tools/*.ps1`) and %d Altirra debugger scripts (`tools/*.cmd`) run the real game in Altirra 4.40 unattended and record traces, audio and screenshots into `analysis/` (`04` has the settings, the quirks of the debugger, and the fast-run copy of the settings). They need Windows, PowerShell, `external-tools/Altirra`, the NTSC OS ROM and your game ROM; none of the tests needs them, and their results are in `analysis/` and the register." % (c["ps1"], c["cmd"]))
    W("")
    W("## 8. Checked on a clean copy")
    W("")
    W("`python -I tools/check_clean_build.py` copies every file Git would keep (no `build/`, no `resources/`, no `original/`) into `build/clean-check/tree`, adds only your cartridge ROM, and then does recipes A, C, A again and D: **the build has no warnings; `ctest` with no derived data passes its tests and skips the ones that need the vectors; the vectors are made from the ROM; `ctest` then runs and passes all %d tests; a replay is made and played, and its state, run, video and audio digests equal those of the golden game** (`analysis/evidence-clean-build-summary.txt`). The copy has no file that is not in the project." % len(cm["tests"]))
    W("")
    W("## 9. Limits")
    W("")
    W("The instructions are for Windows (WinLibs) and Ubuntu (WSL2); other systems are untried (OV-72). The Python side is Python 3.14 only. The derived data (`resources/`) is rebuilt, never shipped; a release would ship source and instructions, not the ROM or anything derived from it (stage 99).")
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
