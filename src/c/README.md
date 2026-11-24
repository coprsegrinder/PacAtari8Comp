# src/c

C port of the game (faithful frame-by-frame port, owner decisions of 2026-11-18, `docs/49-owner-decisions.md`).

- **Language and build**: C99 (`-std=c99`, extensions off, `-Wall -Wextra -Wpedantic -Wconversion -Werror`), clang and gcc, CMake (Ninja). `tests/toolchain_check.c` checks the 8-bit wrap-around arithmetic the core relies on.
- **Portable, and files only in the main folder** (owner constraint, `docs/49`, `docs/51` section 2a): standard C99 in `core/` and `app/`; every system service, files included, only in `platform/`; every file is opened through `platform/fs.c`, which refuses a path outside the main folder or its subfolders.
- **Layout** (`docs/48-architecture.md`, section 6): `platform/`, `core/`, `assets/`, `app/`, `render/`, `audio/`, `shell/`, `tests/`.
- **Equivalence**: the whole state (zero page, maze, status rows, shadows, ordered sound-chip writes, RANDOM count) equals the original's every frame; the Python core (`tools/core_*.py`, 0 differences against the ROM) is the oracle (`docs/44`, `docs/48` section 7).

Build and test:

```
cmake -S src/c -B build/c -G Ninja -DCMAKE_C_COMPILER=clang   (or gcc)
cmake --build build/c
ctest --test-dir build/c --output-on-failure
```

Without CMake (any POSIX system with a C99 compiler, e.g. WSL / Linux; stage 88, `docs/54`): `sh tools/build_test_posix.sh gcc build/posix-gcc [extra flags such as -fsanitize=address,undefined]` builds everything with the same flags and runs the tests and 13 whole games. `pacman_a8 run REPLAY --time` prints the time the game, the renderer and the sound chip take per frame.

Regression (stage 89, `docs/55`): `python -I tools/run_regression.py` (about 6 minutes) builds, runs `ctest` and plays 30 golden games, whose state / run / video / audio digests must equal `analysis/golden-digests.txt`; `--full` adds clang, the comparison with the ROM on every game and the Linux build with sanitizers.
