# 54 - Performance and compatibility (checklist stage 88)

Hand-written, 2026-11-23. Checklist stage 88: "Compare performance characteristics and verify compatibility with intended operating systems, hardware, and environments." The intended environment of the port is portable C99 (owner decision 73, `49`) with every system service behind `platform/` and files only in the main folder (`51` section 2a). The Windows 11 port with a window and a sound device is stage J and is locked until A-I are verified; what is checked here is the portable core, app, renderer, audio and the headless shell.

## 1. Compatibility

### 1.1 A second operating system: Linux

Until this stage the port had only ever been built on Windows, and `51` said "a second operating system is not available for testing". It is: the machine has WSL2 with Ubuntu 26.04 (kernel 6.18, x86-64) and its own `gcc` 15.2.0. There is no CMake there, and nothing was installed, so `tools/build_test_posix.sh` repeats what `CMakeLists.txt` and `tests/CMakeLists.txt` do with a plain shell script: the same sources, the same flags (`-std=c99 -Wall -Wextra -Wpedantic -Wconversion -Werror`), the same tests with the same expected output.

**It found a defect on the first run.** `platform/fs.c`, the one file that opens files, has a POSIX branch (`lstat`, `S_ISLNK`, `mkdir` from `<sys/stat.h>`). That branch had never been compiled. With a strict `-std=c99` build, glibc does not declare `lstat` unless `_POSIX_C_SOURCE` is defined: `error: implicit declaration of function 'lstat'`. So **the port did not build on Linux at all**. Fixed with `#define _POSIX_C_SOURCE 200809L` at the top of `fs.c` (and the same in the new `timer.c`), on non-Windows systems only.

After the fix: **59 of 59 steps pass on Linux**: 13 builds (the shell, the installer and 11 test programs, 0 warnings), the toolchain check, the World check, the vector runner and its three negative controls (a broken state, a broken RANDOM, the opposite byte order), the file sandbox, the platform and asset checks, the audio and shell self-tests, **the 21 vector-set tests (85 recorded vector files)**, and 13 whole games.

- **The same asset blob.** The installer, run on Linux on the owner's ROM, writes a blob byte-identical to the one made on Windows.
- **The same games.** The 13 replays (the four 79d sessions, six seeded random games, three games played on purpose: 117,300 frames) run on Linux give **the same state hash after every frame, the same run digest, the same video digest and the same audio digest** as the Windows gcc build: compared file by file. The float audio chain gives identical PCM digests across Windows gcc, Windows clang and Linux gcc.
- **Sanitizers.** gcc's AddressSanitizer, UndefinedBehaviorSanitizer (`-fno-sanitize-recover`) and LeakSanitizer exist on that Linux, so the whole of the above was run again with `-O1 -g -fsanitize=address,undefined`: **59 of 59 pass**, including the 117,300 frames with the renderer and the audio chip on: **no out-of-bounds access, no undefined behaviour, no leak in the port**. The first sanitizer run reported **one leak, in the test harness**: `vec_open` (`tests/vector.c`) left the file open on every error return (8 bytes, only in the negative controls that feed it a bad file). Fixed: a file that is not a good vector file is closed again.

### 1.2 Compilers, optimisation levels, language standards

| What | Result |
|---|---|
| clang 19.1.1, gcc 14.2.0 (Windows), gcc 15.2.0 (Linux) | all build with 0 warnings under `-Wall -Wextra -Wpedantic -Wconversion -Werror` |
| Optimisation: `-O0 -O1 -O2 -O3 -Os` with clang and gcc (10 builds), 4 replays (38,358 frames) with video and audio | all 10 give **the same output and the same hash of every frame** as the reference build |
| Standard: `-std=c99`, `c11`, `c17`, `c2x` with clang, gcc (Windows) and gcc (Linux) | **all 39 sources compile in every one of the 12 combinations**, `-Werror` |
| Directory with spaces, started from another directory with `--root` | works (the project's own folder has spaces) |

### 1.3 What could not be tested here (OV-72)

No **macOS**, no **MSVC** (`cl` is not installed; it is not a target now, `49`), no **32-bit** build (the installed gcc has no 32-bit libraries and the clang target fails in the linker), no **big-endian** or **ARM** machine (byte order is covered by the swapped-reader negative control, `tests/CMakeLists.txt`, not by a machine), no other C library than glibc and the Windows UCRT (musl, bionic), no clang on Linux, no older or newer compilers than the three above, **no real Windows port** (stage J: window, input, sound device). Linux on x86-64 under WSL2 is a real second operating system and a real second C library, but it is one machine.

## 2. Performance

`pacman_a8 run REPLAY --time` (new in this stage; `platform/timer.[ch]` is the one place the port reads the clock) times, for every frame of the run, the game (`shell_frame`: the whole frame logic), the renderer (`render_frame`) and the sound chip model (`audio_frame`: the 735 samples of the frame), and prints the mean, median, 99th percentile and worst. It changes nothing: the run, its digests and the hash of every frame are the same with and without it (`tests/test_shell.py`). Ten replays, 81,300 frames, each run three times, all three parts on (`analysis/evidence-compat-perf-summary.txt`), on the owner's machine:

| System | Game: mean / median / 99th | Renderer: mean / median / 99th | Sound chip: mean / median / 99th |
|---|---|---|---|
| Windows 11, gcc 14.2 `-O3` | 19.1 / 18.1 / 42.0 us | 169 / 143 / 561 us | 54 / 37 / 113 us |
| Windows 11, clang 19.1 `-O3` | 19.8 / 18.5 / 44.4 us | 341 / 302 / 958 us | 51 / 34 / 104 us |
| WSL2 Ubuntu, gcc 15.2 `-O2` | 22.2 / 21.6 / 51.1 us | 639 / 579 / 1,253 us | 65 / 48 / 127 us |

- **Against the budget.** A frame of the NTSC machine is 16,667 us. The whole of one frame (logic, picture and sound) costs a mean of **0.25 ms on Windows with gcc (1.5% of the frame)**, 0.41 ms with clang, 0.73 ms on WSL2; the logic alone is **about 0.1% of the frame**. The slowest single frame seen anywhere was 7.2 ms (a renderer frame on WSL2); the slowest game frame 4.6 ms (WSL2). Those worst frames are one-off: the median of the per-run worst is 0.8 ms for the game, and they are scheduler and cache effects of a desktop operating system, not a class of frames (the 99th percentile is 42-51 us). **The port runs in real time with a wide margin; headless it runs a game at about 50,000 frames a second** (state only).
- **Against the original.** The original's handler gets 16,100 cycles of the 6502 a frame on the game screen (about 9 ms of the machine's time, `39`), and the heaviest play frame found on the real handler costs 14,278 cycles (89% of it); the static bound is 32,049 and could not be tightened (OV-64, a documented limit). The C port has no such question: it is 0.1% of its frame on this machine.
- **Start-up**: making the asset blob from the ROM takes about 6 ms (the first run 35 ms, the file cache); the blob is 9,392 bytes; starting the shell, loading the blob and the tables and running one frame takes about 11-13 ms.
- **Size**: `pacman_a8` is 200 KB (gcc, 124 KB of code), 180 KB (clang), 115 KB on Linux. The static memory is 18.3 MB, of which 16 MB is the shell's buffer for a replay file and 0.8 MB the new timing arrays; the game's own state is the 7,052-byte World plus a sound-write log. Nothing allocates while a game runs.

## 3. Limits

The timings are one machine (12 logical processors, Windows 11), one load; the worst frames include what the operating system does between two frames. The performance of the real front end (window, sound device) is stage J. "Compatibility" here is source and behaviour: the same sources build and give bit-identical games on the three compiler and operating system pairs available; it is not a statement about machines not tried (OV-72). No code coverage was measured (the unit tests are not measured for the lines they reach; stage 87 measured the routines of the handler by call count, `53`).

## 4. Files

`tools/build_test_posix.sh` (the CMake-free build and test run: `sh tools/build_test_posix.sh gcc build/posix-gcc [flags]`), `src/c/platform/timer.[ch]`, `src/c/shell/main.c` (`--time`), the fix in `src/c/platform/fs.c`, the fix in `src/c/tests/vector.c`, `tests/test_shell.py` (`--time`), `analysis/evidence-compat-perf-summary.txt`.
