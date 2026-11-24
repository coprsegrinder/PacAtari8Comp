/* pacman_a8 - the headless shell of the Pac-Man (Atari 8-bit) port (stage 80d).
 *   pacman_a8 run REPLAY [--root DIR] [--frames N] [--hashes FILE] [--states FILE] [--time] [--video] [--audio] [--ppm FILE] [--keep-high-score] [--log]
 *   pacman_a8 info REPLAY [--root DIR]
 * `run` plays a recorded replay (shell/replay.h) through the whole program and prints the hash of the state after the last frame and the digest of the run (a hash over the hash of every frame):
 * two runs of the same replay give the same digest on any machine, and a replay made from a recorded session gives the hashes of that session's frames.  --hashes writes "frame hash" for every frame;
 * --states writes, for every frame, the packed state (PM_STATE_SIZE bytes), the number of sound-chip writes of the frame (u32 LE) and each write (u16 address, u8 value), and the RANDOM bytes read (u32 LE);
 * --time measures, for the frames run (the first 65,536 at most), the time the game, the renderer and the sound chip take for each frame and prints mean, median, 99th percentile and worst (stage 88);
 * --video renders every frame and hashes the colour bytes; --audio runs the sound chip and hashes the PCM (16-bit); --ppm writes the last frame as a P6 picture.  By default nothing is read from or written to
 * save/ and logs/ (a replay must not depend on what an earlier game left there); --keep-high-score loads the high score before the replay and saves it after, --log appends a line to logs/shell.log.
 * Everything goes through platform/fs.c: paths are relative to the main folder (the current folder, or --root).  The asset blob is made from original/Pac-Man.rom when it is not there.  Exit code 0, 1 (replay
 * or file error), 2 (usage or boot error). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../audio/audio.h"
#include "../platform/fs.h"
#include "../platform/timer.h"
#include "../render/render.h"
#include "replay.h"
#include "shell.h"

#define TIMING_MAX 65536u

static uint8_t replay_buf[1u << 24];
static uint8_t blob_buf[ASSET_BLOB_MAX];
static uint8_t ram_image[65536];
static uint8_t colour[RENDER_W * RENDER_H];
static uint8_t rgb[RENDER_W * RENDER_H * 3];
static float pcm[4096];
static Assets assets;
static Shell shell;
static Renderer renderer;
static Audio audio;
static Replay replay;
static int time_on;                  /* --time: how long each frame takes (stage 88) */
static uint32_t t_game[TIMING_MAX], t_video[TIMING_MAX], t_audio[TIMING_MAX];   /* microseconds-times-ten (100 ns units) of every frame, up to TIMING_MAX frames */
static const char *states_path;     /* --states FILE: the whole state after every frame, for tools/check_c_vs_rom.py (stage 86) */

static int boot(void)
{
    AssetsError e = assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf);

    if (e == ASSETS_OPEN_FAILED) {                         /* the first run: the port installs its assets from the owner's ROM */
        RomError r = rom_install(ROM_DEFAULT_PATH, ASSET_DEFAULT_PATH);
        if (r != ROM_OK) {
            printf("pacman_a8: the asset blob %s is not there and cannot be made from %s: %s\n", ASSET_DEFAULT_PATH, ROM_DEFAULT_PATH, rom_error_text(r));
            return 2;
        }
        printf("pacman_a8: made %s from %s\n", ASSET_DEFAULT_PATH, ROM_DEFAULT_PATH);
        e = assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf);
    }
    if (e != ASSETS_OK || assets_install_tables(&assets) != ASSETS_OK) {
        printf("pacman_a8: the asset blob %s is not usable: %s\n", ASSET_DEFAULT_PATH, assets_error_text(e));
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    return 0;
}

static uint64_t fnv64(uint64_t h, const uint8_t *p, size_t n)
{
    size_t i;

    for (i = 0; i < n; i++) {
        h = (h ^ p[i]) * 0x100000001B3ull;
    }
    return h;
}

static uint64_t hash_pcm(uint64_t h, const float *x, size_t n)
{
    size_t i;

    for (i = 0; i < n; i++) {
        double v = floor((double)x[i] * 32767.0 + 0.5);
        int s = v > 32767.0 ? 32767 : (v < -32768.0 ? -32768 : (int)v);
        uint8_t b[2];
        b[0] = (uint8_t)(s & 0xFF);
        b[1] = (uint8_t)((s >> 8) & 0xFF);
        h = fnv64(h, b, 2);
    }
    return h;
}

static int cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return x < y ? -1 : (x > y ? 1 : 0);
}

/* mean, median, 99th percentile and worst of the first n times (units of 100 ns), printed in microseconds */
static void print_timing(const char *what, uint32_t *t, size_t n, uint64_t total_100ns)
{
    size_t mid = n / 2, p99 = (n * 99u) / 100u;

    if (n == 0) {
        return;
    }
    qsort(t, n, sizeof t[0], cmp_u32);
    printf("time %-6s: mean %.1f us, median %.1f us, 99th percentile %.1f us, worst %.1f us (%lu frames)\n", what, (double)total_100ns / (double)n / 10.0, (double)t[mid] / 10.0,
           (double)t[p99] / 10.0, (double)t[n - 1] / 10.0, (unsigned long)n);
}

static int cmd_info(const char *path)
{
    ReplayError e = replay_load(&replay, path, replay_buf, sizeof replay_buf);

    if (e != REPLAY_OK) {
        printf("pacman_a8: %s: %s\n", path, replay_error_text(e));
        return 1;
    }
    printf("replay %s: %u frames, RANDOM %s, seed %u, power-on clock %u\n", path, (unsigned)replay.nframes, (replay.flags & REPLAY_FLAG_RANDOM) ? "in the frames" : "from the model",
           (unsigned)replay.seed, (unsigned)replay.start_clock);
    return 0;
}

static int cmd_run(const char *path, long max_frames, const char *hashes_path, int video, int audio_on, const char *ppm_path, int keep_high, int log_on)
{
    ReplayError e = replay_load(&replay, path, replay_buf, sizeof replay_buf);
    PmFile *hf = NULL, *sf = NULL;
    FrameInput in;
    uint64_t h = 0, vdig = 0xCBF29CE484222325ull, adig = 0xCBF29CE484222325ull;
    long n = 0;
    char line[300];
    uint64_t tg = 0, tv = 0, ta = 0, t0, t1;

    if (e != REPLAY_OK) {
        printf("pacman_a8: %s: %s\n", path, replay_error_text(e));
        return 1;
    }
    if (hashes_path != NULL) {
        hf = pm_fs_open(hashes_path, "wb");
        if (hf == NULL) {
            printf("pacman_a8: cannot write %s\n", hashes_path);
            return 1;
        }
    }
    if (states_path != NULL) {
        sf = pm_fs_open(states_path, "wb");
        if (sf == NULL) {
            printf("pacman_a8: cannot write %s\n", states_path);
            return 1;
        }
    }
    shell_init(&shell, ram_image + 0x3000, replay.seed, replay.start_clock);
    if (keep_high && shell_highscore_load(&shell) == 0) {
        printf("high score loaded: %06ld\n", shell_highscore_value(&shell));
    }
    if (video) {
        render_init(&renderer, ram_image);
    }
    if (audio_on) {
        audio_init(&audio, 44100.0);
    }
    while ((max_frames < 0 || n < max_frames) && replay_next(&replay, &in)) {
        t0 = time_on ? pm_time_ns() : 0;
        h = shell_frame(&shell, &in);
        if (time_on) {
            t1 = pm_time_ns();
            tg += (t1 - t0) / 100u;
            if ((size_t)n < TIMING_MAX) {
                t_game[n] = (uint32_t)((t1 - t0) / 100u);
            }
        }
        if (hf != NULL) {
            pm_fs_printf(hf, "%ld %016llx\n", n, (unsigned long long)h);
        }
        if (sf != NULL) {
            uint32_t k, cnt = shell.world.pokey_n, rr = shell.stream_pos;
            uint8_t b[4];
            pm_fs_write(sf, shell.pack, sizeof shell.pack);
            for (k = 0; k < 4; k++) {
                b[k] = (uint8_t)(cnt >> (8 * k));
            }
            pm_fs_write(sf, b, 4);
            for (k = 0; k < cnt; k++) {
                uint8_t e[3];
                e[0] = (uint8_t)(shell.world.pokey_addr[k] & 0xFF);
                e[1] = (uint8_t)(shell.world.pokey_addr[k] >> 8);
                e[2] = shell.world.pokey_val[k];
                pm_fs_write(sf, e, 3);
            }
            for (k = 0; k < 4; k++) {
                b[k] = (uint8_t)(rr >> (8 * k));
            }
            pm_fs_write(sf, b, 4);
        }
        if (video) {
            t0 = time_on ? pm_time_ns() : 0;
            render_frame(&renderer, &shell.world, colour);
            if (time_on) {
                t1 = pm_time_ns();
                tv += (t1 - t0) / 100u;
                if ((size_t)n < TIMING_MAX) {
                    t_video[n] = (uint32_t)((t1 - t0) / 100u);
                }
            }
            vdig = fnv64(vdig, colour, sizeof colour);
        }
        if (audio_on) {
            size_t got;
            t0 = time_on ? pm_time_ns() : 0;
            got = audio_frame(&audio, &shell.world, pcm, 4096);
            if (time_on) {
                t1 = pm_time_ns();
                ta += (t1 - t0) / 100u;
                if ((size_t)n < TIMING_MAX) {
                    t_audio[n] = (uint32_t)((t1 - t0) / 100u);
                }
            }
            adig = hash_pcm(adig, pcm, got);
        }
        n++;
    }
    if (hf != NULL) {
        pm_fs_close(hf);
    }
    if (sf != NULL) {
        pm_fs_close(sf);
    }
    printf("frames run: %ld of %u\n", n, (unsigned)replay.nframes);
    printf("final state hash: %016llx\n", (unsigned long long)h);
    printf("run digest: %016llx\n", (unsigned long long)shell_digest(&shell));
    if (shell_highscore_value(&shell) >= 0) {
        printf("high score: %06ld\n", shell_highscore_value(&shell));
    } else {
        printf("high score: none\n");
    }
    if (shell.stream_overrun != 0) {
        printf("RANDOM bytes missing from the replay: %u reads\n", (unsigned)shell.stream_overrun);
    }
    if (time_on) {
        size_t m = (size_t)n < TIMING_MAX ? (size_t)n : TIMING_MAX;
        print_timing("game", t_game, m, tg);
        if (video) {
            print_timing("video", t_video, m, tv);
        }
        if (audio_on) {
            print_timing("audio", t_audio, m, ta);
        }
    }
    if (video) {
        printf("video digest: %016llx\n", (unsigned long long)vdig);
    }
    if (audio_on) {
        printf("audio digest: %016llx\n", (unsigned long long)adig);
    }
    if (ppm_path != NULL) {
        PmFile *pf;
        if (!video) {
            render_init(&renderer, ram_image);
            render_frame(&renderer, &shell.world, colour);
        }
        render_to_rgb(colour, rgb);
        pf = pm_fs_open(ppm_path, "wb");
        if (pf == NULL) {
            printf("pacman_a8: cannot write %s\n", ppm_path);
            return 1;
        }
        pm_fs_printf(pf, "P6\n%d %d\n255\n", RENDER_W, RENDER_H);
        pm_fs_write(pf, rgb, sizeof rgb);
        pm_fs_close(pf);
    }
    if (keep_high) {
        if (shell_highscore_save(&shell) == 0) {
            printf("high score saved: %06ld\n", shell_highscore_value(&shell));
        }
    }
    if (log_on) {
        snprintf(line, sizeof line, "run %s frames=%ld state=%016llx digest=%016llx", path, n, (unsigned long long)h, (unsigned long long)shell_digest(&shell));
        if (shell_log(line) != 0) {
            printf("pacman_a8: cannot write the log\n");
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *hashes = NULL, *ppm = NULL, *replay_path = NULL;
    long frames = -1;
    int video = 0, audio_on = 0, keep = 0, log_on = 0, i;
    int is_run, is_info;

    if (argc < 3) {
        printf("usage: pacman_a8 run REPLAY [--root DIR] [--frames N] [--hashes FILE] [--states FILE] [--time] [--video] [--audio] [--ppm FILE] [--keep-high-score] [--log]\n"
               "       pacman_a8 info REPLAY [--root DIR]\n");
        return 2;
    }
    is_run = strcmp(argv[1], "run") == 0;
    is_info = strcmp(argv[1], "info") == 0;
    if (!is_run && !is_info) {
        printf("pacman_a8: unknown command %s\n", argv[1]);
        return 2;
    }
    for (i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--root") == 0 && i + 1 < argc) {
            if (pm_fs_set_root(argv[++i]) != 0) {
                printf("pacman_a8: bad main folder\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--frames") == 0 && i + 1 < argc) {
            frames = atol(argv[++i]);
        } else if (strcmp(argv[i], "--hashes") == 0 && i + 1 < argc) {
            hashes = argv[++i];
        } else if (strcmp(argv[i], "--time") == 0) {
            time_on = 1;
        } else if (strcmp(argv[i], "--states") == 0 && i + 1 < argc) {
            states_path = argv[++i];
        } else if (strcmp(argv[i], "--ppm") == 0 && i + 1 < argc) {
            ppm = argv[++i];
        } else if (strcmp(argv[i], "--video") == 0) {
            video = 1;
        } else if (strcmp(argv[i], "--audio") == 0) {
            audio_on = 1;
        } else if (strcmp(argv[i], "--keep-high-score") == 0) {
            keep = 1;
        } else if (strcmp(argv[i], "--log") == 0) {
            log_on = 1;
        } else if (argv[i][0] != '-' && replay_path == NULL) {
            replay_path = argv[i];
        } else {
            printf("pacman_a8: unknown option %s\n", argv[i]);
            return 2;
        }
    }
    if (replay_path == NULL) {
        printf("pacman_a8: no replay given\n");
        return 2;
    }
    if (is_info) {
        return cmd_info(replay_path);
    }
    if (boot() != 0) {
        return 2;
    }
    return cmd_run(replay_path, frames, hashes, video, audio_on, ppm, keep, log_on);
}
