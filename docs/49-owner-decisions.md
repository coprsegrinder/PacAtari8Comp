# 49 - Owner decisions (checklist stage 5: stages 71-74)

Taken by the project owner on **2026-11-18**, in answer to four questions put with the evidence of `44` to `48`. Each option was offered with a recommendation; the owner chose the recommended one in all four. This record is the reference for stages 75-90; a later change is a new entry here, with a date.

| Stage | Question | Options offered | Decision |
|---|---|---|---|
| 71 | Faithful frame-by-frame port with a thin hardware layer, or a redesign? | faithful port; redesign; faithful core with a redesigned shell | **Faithful port.** The C game has the frame structure and the state of the original: one `play_frame` over the same variables, behind a thin `Platform` layer (`45`). |
| 72 | What must the port prove against the original? | the whole state each frame; visible behaviour and sound; state for the core and behaviour for the rest | **The whole state each frame.** |
| 73 | Language and toolchain | C99 + clang and gcc + CMake; C11 + clang and gcc + CMake; C99 + plain Makefile | **C99, clang and gcc, CMake (Ninja).** |
| 74 | Layout of `src/c` | the layout of `48` section 6; a flatter layout; another | **The layout of `48` section 6.** |

## What each decision means

**71 - faithful port.** The existing evidence stays usable as it is: the Python core (`tools/core_*.py`, 243,000 World-function calls and 8,500 frame runs against the ROM, 0 differences, `44`) is the oracle of the C core, and the measured sessions (`34`, `38`, `43`) are the oracle of the application layer. The parts of the original that are not game logic (the OS, the chip registers, the drawing) are the `Platform` and the renderer; nothing of the program structure is redesigned. The application layer (title, intro, level end, turn control, countdown, key loop) is written to the measured behaviour in `38`, `40`, `43` and `46`.

**72 - the whole state each frame.** After each frame the port must equal the original in: the zero page (the 144 state bytes of `43`, with the declared temporaries excluded), the maze, the status rows, the colour shadows, the ordered list of sound-chip writes, and the number of RANDOM values used. This is exactly what `tools/check_play.py` compares for the Python core, so the C core is held to the same standard by the same vectors. What this level does **not** cover is stated in `48` section 8: the collision geometry (OV-68), PAL colour, and the drawing, which have to be shown equal by their own checks.

**73 - C99, clang and gcc, CMake (Ninja).** Compile with `-std=c99`, extensions off, `-Wall -Wextra -Wpedantic -Wconversion -Werror`. The port relies on 8-bit wrap-around arithmetic (`tests/toolchain_check.c` checks `CHAR_BIT == 8` and the wrap of `uint8_t`); it passes with clang 19.1.1 and gcc 14.2.0 (WinLibs, installed). **MSVC (`cl`) is not installed and is not a target now**; nothing in the core needs more than C99, so it can be added later without changing the code. A plain Makefile is not used.

**74 - the layout.** `src/c/{platform,core,assets,app,render,tests}`; the core is one C file per Python core module, named alike (`ref`, `ghost`, `house`, `pacman`, `score`, `sound`, `frame`, `play`), so that every C function has a Python twin and is tested against it on the same state vectors. The skeleton (`src/c/CMakeLists.txt`, the folders with their `README.md`, `tests/toolchain_check.c`) was added with this record.

## Later decision: the font's provenance (2026-11-18)

The font `EightBit Atari-Regular` (`third-party/`, `47`) has glyphs that equal the Atari OS ROM's character set bit for bit; the OFL covers its author's font software, not anything Atari owns in the shapes, and this was not examined by a lawyer. Options offered: (1) accept it as it is; (2) draw own glyphs from a different font; (3) ship no font and read it from the user's own OS ROM at build time; (4) leave it open. **Decision: (1), accept it as it is.** The font file, `OFL.txt`, `README.upstream.md` and `third-party/README.md` stay; the risk is known and is recorded here, in `47` section 6 and in `third-party/README.md`. Changing it later (option 2 or 3) would only replace the `font` key of the asset pack's source; the schema does not change.

## Later constraint: portability and where the port writes (2026-11-18)

The owner added two requirements for the C port. **(1) The C port must be portable**: standard C99 only in the game logic, every operating-system service behind the `platform/` layer, no assumption about byte order, word size or path syntax, so that the same sources build on another system with another compiler. **(2) The port writes files only in the main folder or its subfolders**: the folder the program lives in (the project folder while it is developed; the folder the port is installed in when it runs) - never the user's home folder, a temp folder, the registry or any other place outside it; a path that reaches outside (an absolute path, `..`) is refused. How the plan meets them: `51-c-port-plan.md` section 2a (every file access goes through one module, `platform/fs.c`, that refuses a path outside the main folder; a scan of the sources in `ctest` fails on any other file or OS call; the build, the vectors and the test outputs live under `build/` and `resources/` of the project).

## Later decision: D1, the source of RANDOM in the playable port (2026-11-18, stage 77b)

Asked at stage 77b with the recommendation of `51` section 6; the owner chose **the POKEY polynomial model**: the 17-bit generator of Altirra's tables (`tools/pokey_noise.py`), seedable, advanced a whole frame at the start of each frame and a fixed number of cycles before each read in a frame, so that a seed replays exactly; the stream stays injectable (`core/random_feed.h`, the scripted platform's `inject_random`), and the equivalence runs always inject the recorded stream. What it does not claim: that its byte equals the hardware's at the same cycle (not measured; `C-103`).

## Later decision: D3, the library of the shell and the sample rate (2026-11-23, stages 80c / 80d)

Asked with the recommendation of `51` section 6 and answered by the owner: **(1) no window, audio or input library now**. Stage 80d delivers the headless shell (the frame loop, the replay of recorded input files, a per-frame state dump and hash, the high score and options under `save/`, logs under `logs/`, all through `platform/fs.c`) and **plain buffers behind `platform/`** (an RGB framebuffer from `render_to_rgb`, the float PCM of `audio_frame`, the inputs as the `Platform` struct of `45`); the window, the sound device and the keyboard / pad layer are chosen with the native Windows 11 port (stage J), so the C code has no third-party dependency. **(2) The output sample rate is 44,100 Hz**: the rate of every recording the audio was verified against (C-115); the model averages the chip's 28-cycle samples into any rate, but no other rate is verified, so another one needs a rate-independence check first. The CRT look and the pixel-aspect stretch stay deferred (owner, 2026-11-22).

## Still open after these decisions

The decisions do not settle: the collision geometry (OV-68) and the C code itself (OV-02, stages 75-80). They are listed in `48` section 8 and in `OPEN-VERIFICATION.md`.
