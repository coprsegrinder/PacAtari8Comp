# shell/ - the headless shell: replay, state hash, high score (stage 80d, docs/49 D3, docs/51)

`replay.[ch]`: the replay format `PMRP` (the inputs of a game frame by frame, optionally the RANDOM bytes; checksum). `shell.[ch]`: the whole program on a platform that takes its inputs from a replay,
a hash of the state after every frame, the high score / options / log under `save/` and `logs/` through `platform/fs.c`. `main.c`: the program `pacman_a8`:

    pacman_a8 run REPLAY [--frames N] [--hashes FILE] [--video] [--audio] [--ppm FILE] [--keep-high-score] [--log] [--root DIR]
    pacman_a8 info REPLAY

Replays are made by `tools/make_replay.py` (from a recorded session, or from a text script) or by a front end. No window, sound device or input library (decision D3): a front end gives `FrameInput`
records and takes `render_to_rgb` and `audio_frame` buffers. The first run makes `resources/pack/assets.pmab` from `original/Pac-Man.rom`. Checked by `tests/test_shell.py` and `ctest shell_selftest`;
see OPEN-VERIFICATION.md C-116.
