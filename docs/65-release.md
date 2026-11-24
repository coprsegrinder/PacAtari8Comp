# 65 - Reproducible build and release preparation (checklist stage 99)

Checklist stage 99: "Establish a repeatable build process, organize release files, prepare necessary metadata, and verify the resulting deliverables." Owner decisions of 2026-11-24: the **licence is MIT** for the project's own files, and the release **includes the disassembly** `src/asm/pacman.s`. Nothing is published by this stage: it makes the archive on the local disk (stage 100 and the GitHub step need your approval).

## 1. What the release is

One source archive, `build/release/pacman-a8-port-<version>-src.zip` (git-ignored; version in `tools/make_release.py`, now `0.1.0`), with its `.sha256` and a `release-info.json` beside it. It holds every file Git tracks or would track (`git ls-files -co --exclude-standard`): the C port (`src/c`), the disassembly (`src/asm`), the Python tools and tests, the documentation and the evidence summaries (`analysis/`), `third-party/` with the font licence, `LICENSE`, `NOTICE`, and `RELEASE-MANIFEST.json` (every file with its size and SHA-256).

**Never in it** (checked, not just intended): the cartridge ROM and the OS ROMs (`original/`, any `*.rom`), the derived data (`resources/`, rebuilt on the user's machine), builds (`build/`), the emulator and tools (`external-tools/`), compiled files, pictures, logs, and `Personal notes.txt`.

The user supplies the ROM at `original/Pac-Man.rom`; the port installs its non-code data from it at start-up (C-112, C-113).

## 2. Metadata

| File | What |
|---|---|
| `LICENSE` | MIT, "Pac-Man Preservation Project", 2026 |
| `NOTICE` | what the MIT licence does not cover: the original game and its disassembly (no right in the original code is given), the OS ROMs (not shipped), the OFL font (its own licence, `third-party/`), and what the user must supply |
| `RELEASE-MANIFEST.json` (inside) | name, version, every file's path, size and SHA-256 |
| `*.sha256`, `release-info.json` (beside) | the archive's hash; date-independent facts that vary by machine: Git commit and whether the tree was clean, Python version, counts |

## 3. Why it is reproducible

The archive is a function of the file contents only: sorted member names, one fixed time stamp, fixed permissions, text files with LF line ends (a Windows checkout with CRLF gives the same bytes as a Linux one), fixed compression. No clock, user name or path is stored. `release-info.json` is kept outside so that the archive's hash does not change with the machine.

## 4. The commands

```
python -I tools/make_release.py                      # make the archive
python -I tools/make_release.py --verify             # + the checks of section 5, 1 to 3
python -I tools/make_release.py --verify --build     # + extract, add only the ROM, build and test with gcc and clang
```

The build part runs `tools/check_clean_build.py --tree DIR` on the extracted archive (the same steps as docs/63 section 4: configure, strict C99 `-Werror` build, `ctest` with no derived data, the vectors, `ctest` again, a replay played by `pacman_a8` whose digests equal `analysis/golden-digests.txt`).

## 5. What was verified

See `analysis/evidence-release-summary.txt` for the run. Checks: (1) the archive made twice is byte-identical; (2) every member equals its manifest hash and the manifest lists exactly the members; (3) no forbidden path, no member contains a 32-byte piece of the cartridge or OS ROMs (sampled along all three ROMs), the required files are present; (4) the extracted copy builds and passes on both compilers.

## 6. Limits

- **The Git tree was not clean** when the archive was made: the work of stages 63 to 99 is not committed (the last commit is Stage 62), so the archive cannot yet be tied to a commit; `release-info.json` says so. Committing is the owner's step.
- The sampled-window ROM check proves no verbatim 32-byte run (at the sampled offsets) of the ROMs is in the archive; it cannot show that nothing *derived* from them is. The disassembly is derived by design (owner decision above); the `docs/` chapters quote addresses and short code excerpts.
- Windows 11 (WinLibs) and one Ubuntu (WSL2) only (OV-72); MSVC, macOS untried.
- A licence is not legal advice; the `NOTICE` states what the project can and cannot give.
- The archive is a source release: no binary (the playable `.exe` is stage J).
