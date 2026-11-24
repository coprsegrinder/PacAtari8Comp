/* platform/win32/win_main.c - the Windows 11 front end of the port: a window, the keyboard and XInput pads, the sound device (stage J, docs/67).
 *   pacman_a8_play [--root DIR] [--scale N] [--fullscreen] [--no-audio] [--seed N] [--record FILE] [--ppm FILE] [--selftest FRAMES] [--exact]
 * It is the interactive twin of the headless shell: the same Shell, the same renderer, the same sound model, driven by the player instead of a replay.  What it adds is only what a machine does around the game:
 *   - keyboard / pad -> FrontKeys -> FrameInput (shell/frontend.c, portable and tested), one per frame;
 *   - the frame clock: the sound device's buffer (the game runs a frame whenever the device has less than two frames of sound queued), or the system timer when there is no device (--no-audio);
 *   - the picture: the renderer's 384 x 240 pixels, stretched to the window at the 4:3 shape of an Atari picture tube, black bars around it;
 *   - the high score under save/, the replay of the game under --record (a recorded game replays headlessly to the same digests: the proof that this front end adds nothing to the game).
 * Keys: arrows / WASD stick, Ctrl / Z / X / Enter fire (Enter also START), F2 START, F3 SELECT, F4 OPTION, Space / P pause, Alt+Enter or F11 full screen, Esc quit.  Pads (XInput): D-pad or left stick,
 * A / B fire, Start = START, Back = SELECT, X / Y = OPTION; pad 2 is player 2; the keyboard drives both ports (hot-seat play on one keyboard).
 * --selftest FRAMES: plays a built-in scenario by posting real key messages to its own window, runs FRAMES frames, writes logs/selftest.txt (the digests, the timing, the sound device's underruns, a comparison of
 * the window's pixels with the frame) and quits.  --exact makes the window client exactly 384 x 240 pixels with no stretching (the pixel comparison needs it). */
#include <windows.h>

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../assets/assets.h"
#include "../../assets/rom_install.h"
#include "../../audio/audio.h"
#include "../../render/render.h"
#include "../../shell/frontend.h"
#include "../../shell/replay.h"
#include "../../shell/shell.h"
#include "../fs.h"
#include "../timer.h"
#include "win_audio.h"

#define AUDIO_RATE 44100.0
#define FRAME_HZ 59.9227                 /* NTSC: 1,789,772.5 Hz / 29,868 cycles a frame */
#define QUEUE_TARGET_FRAMES 1500         /* the device keeps about two game frames of sound queued */
#define MAX_CATCH_UP 4
#define SELFTEST_VOLUME 0.3f             /* the self test plays at a low volume (the capture is of the sound after it) */
#define SELFTEST_GAIN ((double)SELFTEST_VOLUME * (double)SELFTEST_VOLUME)   /* Windows volume scalars are an audio taper: the amplitude is the square of the scalar */
#define RECORD_CAP (1u << 23)
#define TITLE "Pac-Man (Atari 8-bit) - C port"

typedef struct Options {
    int scale, fullscreen, no_audio, exact;
    long selftest;
    uint32_t seed;
    int have_seed;
    const char *record, *ppm, *root;
} Options;

static Options opt;
static uint8_t blob_buf[ASSET_BLOB_MAX];
static uint8_t ram_image[65536];
static uint8_t colour[RENDER_W * RENDER_H];
static uint8_t rgb[RENDER_W * RENDER_H * 3];
static uint8_t bgra[RENDER_W * RENDER_H * 4];
static float pcm[4096];
static uint8_t record_buf[RECORD_CAP];
static Assets assets;
static Shell shell;
static Renderer renderer;
static Audio audio;
static Frontend front;
static ReplayWriter writer;
static WinAudio *wa;
static WinLoop *wloop;                   /* selftest only: the loopback capture of what the device plays */
#define GAME_PCM_MAX ((size_t)(44100 * 40))
static float *game_pcm;                  /* selftest only: the samples handed to the device, in order */
static size_t game_pcm_n;
static long long game_t0;                /* QueryPerformanceCounter (100 ns) when the first samples were handed over */
static HWND hwnd;
static volatile int quit;
static uint8_t key_down[256];
static int pause_edge;
static int fullscreen;
static WINDOWPLACEMENT saved_place;
static LONG saved_style;

/* ---------------------------------------------------------------- digests (the same as the headless shell's, so that a recorded game can be compared) */

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

/* ---------------------------------------------------------------- the game's start-up (the same as the headless shell's) */

static int boot(char *why, size_t cap)
{
    AssetsError e = assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf);

    if (e == ASSETS_OPEN_FAILED) {                         /* the first run: the port installs its assets from the owner's ROM */
        RomError r = rom_install(ROM_DEFAULT_PATH, ASSET_DEFAULT_PATH);
        if (r != ROM_OK) {
            snprintf(why, cap, "The asset blob %s is not there and cannot be made from %s:\n%s\n\nPut your own Pac-Man (Atari 8-bit) cartridge ROM at %s in the main folder (the current folder, or --root DIR).",
                     ASSET_DEFAULT_PATH, ROM_DEFAULT_PATH, rom_error_text(r), ROM_DEFAULT_PATH);
            return 2;
        }
        e = assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf);
    }
    if (e != ASSETS_OK || assets_install_tables(&assets) != ASSETS_OK) {
        snprintf(why, cap, "The asset blob %s is not usable: %s", ASSET_DEFAULT_PATH, assets_error_text(e));
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    return 0;
}

/* ---------------------------------------------------------------- input */

typedef struct XIn {                     /* XInput, loaded when the program starts: no import library, no failure on a machine without it */
    DWORD packet;
    WORD buttons;
    SHORT lx, ly;
} XIn;

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, void *);
static XInputGetStateFn xinput_get;
static DWORD pad_next_probe[2];          /* a pad that is not connected is asked about once a second only: the call is slow for an empty slot */
static int pad_present[2];

static void xinput_load(void)
{
    HMODULE m = LoadLibraryA("xinput1_4.dll");

    if (m == NULL) {
        m = LoadLibraryA("xinput9_1_0.dll");
    }
    if (m != NULL) {
        xinput_get = (XInputGetStateFn)(void (*)(void))GetProcAddress(m, "XInputGetState");
    }
}

/* the layout of XINPUT_STATE: DWORD packet; XINPUT_GAMEPAD { WORD buttons; BYTE lt, rt; SHORT lx, ly, rx, ry; } */
static int pad_read(int n, XIn *x)
{
    unsigned char raw[16];
    DWORD now = GetTickCount();

    if (xinput_get == NULL || (!pad_present[n] && (LONG)(now - pad_next_probe[n]) < 0)) {
        return 0;
    }
    memset(raw, 0, sizeof raw);
    if (xinput_get((DWORD)n, raw) != 0) {
        pad_present[n] = 0;
        pad_next_probe[n] = now + 1000u;
        return 0;
    }
    pad_present[n] = 1;
    x->packet = (DWORD)raw[0] | ((DWORD)raw[1] << 8) | ((DWORD)raw[2] << 16) | ((DWORD)raw[3] << 24);
    x->buttons = (WORD)(raw[4] | (raw[5] << 8));
    x->lx = (SHORT)(raw[8] | (raw[9] << 8));
    x->ly = (SHORT)(raw[10] | (raw[11] << 8));
    return 1;
}

#define XB_UP 0x0001
#define XB_DOWN 0x0002
#define XB_LEFT 0x0004
#define XB_RIGHT 0x0008
#define XB_START 0x0010
#define XB_BACK 0x0020
#define XB_A 0x1000
#define XB_B 0x2000
#define XB_X 0x4000
#define XB_Y 0x8000
#define STICK_DEAD 16000

static void keys_now(FrontKeys *k)
{
    FrontPad kb;
    XIn x[2];
    int have[2], i;

    memset(k, 0, sizeof *k);
    kb.up = (uint8_t)(key_down[VK_UP] || key_down['W']);
    kb.down = (uint8_t)(key_down[VK_DOWN] || key_down['S']);
    kb.left = (uint8_t)(key_down[VK_LEFT] || key_down['A']);
    kb.right = (uint8_t)(key_down[VK_RIGHT] || key_down['D']);
    kb.fire = (uint8_t)(key_down[VK_CONTROL] || key_down['Z'] || key_down['X'] || key_down[VK_RETURN]);
    k->start = (uint8_t)(key_down[VK_F2] || key_down[VK_RETURN]);
    k->select = (uint8_t)key_down[VK_F3];
    k->option = (uint8_t)key_down[VK_F4];
    for (i = 0; i < 2; i++) {
        have[i] = pad_read(i, &x[i]);
        k->pad[i] = kb;                                   /* the keyboard drives both ports */
        if (have[i]) {
            WORD b = x[i].buttons;
            k->pad[i].up |= (uint8_t)((b & XB_UP) != 0 || x[i].ly > STICK_DEAD);
            k->pad[i].down |= (uint8_t)((b & XB_DOWN) != 0 || x[i].ly < -STICK_DEAD);
            k->pad[i].left |= (uint8_t)((b & XB_LEFT) != 0 || x[i].lx < -STICK_DEAD);
            k->pad[i].right |= (uint8_t)((b & XB_RIGHT) != 0 || x[i].lx > STICK_DEAD);
            k->pad[i].fire |= (uint8_t)((b & (XB_A | XB_B)) != 0);
            if (i == 0) {
                k->start |= (uint8_t)((b & XB_START) != 0);
                k->select |= (uint8_t)((b & XB_BACK) != 0);
                k->option |= (uint8_t)((b & (XB_X | XB_Y)) != 0);
            }
        }
    }
    k->pause = (uint8_t)pause_edge;
    pause_edge = 0;
}

/* ---------------------------------------------------------------- the window */

static void toggle_fullscreen(void)
{
    if (!fullscreen) {
        MONITORINFO mi;
        mi.cbSize = sizeof mi;
        saved_place.length = sizeof saved_place;
        GetWindowPlacement(hwnd, &saved_place);
        saved_style = GetWindowLong(hwnd, GWL_STYLE);
        if (GetMonitorInfo(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &mi)) {
            SetWindowLong(hwnd, GWL_STYLE, (LONG)((DWORD)saved_style & ~(DWORD)WS_OVERLAPPEDWINDOW));
            SetWindowPos(hwnd, HWND_TOP, mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top, SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
            fullscreen = 1;
            ShowCursor(FALSE);
        }
    } else {
        SetWindowLong(hwnd, GWL_STYLE, saved_style);
        SetWindowPlacement(hwnd, &saved_place);
        SetWindowPos(hwnd, NULL, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
        fullscreen = 0;
        ShowCursor(TRUE);
    }
}

/* the destination rectangle of the picture in a client area of cw x ch: the 4:3 shape of the original's picture, centred (opt.exact: the pixels as they are) */
static void dest_rect(int cw, int ch, int *x, int *y, int *w, int *h)
{
    if (opt.exact) {
        *x = *y = 0;
        *w = RENDER_W;
        *h = RENDER_H;
        return;
    }
    *h = ch;
    *w = (int)((long)ch * 4 / 3);
    if (*w > cw) {
        *w = cw;
        *h = (int)((long)cw * 3 / 4);
    }
    *x = (cw - *w) / 2;
    *y = (ch - *h) / 2;
}

static void present(void)
{
    HDC dc;
    RECT rc;
    BITMAPINFO bi;
    int x, y, w, h;

    if (hwnd == NULL) {
        return;
    }
    dc = GetDC(hwnd);
    GetClientRect(hwnd, &rc);
    dest_rect(rc.right, rc.bottom, &x, &y, &w, &h);
    if (x > 0 || y > 0) {                                     /* the bars */
        RECT r;
        HBRUSH b = (HBRUSH)GetStockObject(BLACK_BRUSH);
        SetRect(&r, 0, 0, rc.right, y);
        FillRect(dc, &r, b);
        SetRect(&r, 0, y + h, rc.right, rc.bottom);
        FillRect(dc, &r, b);
        SetRect(&r, 0, y, x, y + h);
        FillRect(dc, &r, b);
        SetRect(&r, x + w, y, rc.right, y + h);
        FillRect(dc, &r, b);
    }
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = RENDER_W;
    bi.bmiHeader.biHeight = -RENDER_H;                         /* top-down */
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    SetStretchBltMode(dc, COLORONCOLOR);                       /* no blur: the pixels of the original */
    StretchDIBits(dc, x, y, w, h, 0, 0, RENDER_W, RENDER_H, bgra, &bi, DIB_RGB_COLORS, SRCCOPY);
    ReleaseDC(hwnd, dc);
}

static LRESULT CALLBACK wnd_proc(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CLOSE:
        quit = 1;
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    case WM_KEYDOWN:
    case WM_SYSKEYDOWN: {
        unsigned vk = (unsigned)wp & 0xFFu;
        int repeat = (lp & 0x40000000) != 0;

        if (msg == WM_SYSKEYDOWN && vk == VK_RETURN) {          /* Alt+Enter */
            if (!repeat) {
                toggle_fullscreen();
            }
            return 0;
        }
        if (msg == WM_SYSKEYDOWN && vk != VK_F10 && vk != VK_MENU) {
            return DefWindowProc(h, msg, wp, lp);
        }
        if (!repeat) {
            key_down[vk] = 1;
            if (vk == VK_SPACE || vk == 'P') {                 /* a PRESS: the keyboard interrupt of the original does not repeat it */
                pause_edge = 1;
            } else if (vk == VK_ESCAPE) {
                quit = 1;
            } else if (vk == VK_F11) {
                toggle_fullscreen();
            }
        }
        return 0;
    }
    case WM_KEYUP:
    case WM_SYSKEYUP:
        key_down[(unsigned)wp & 0xFFu] = 0;
        return 0;
    case WM_KILLFOCUS:
        memset(key_down, 0, sizeof key_down);                  /* a key released while another window had the focus */
        return 0;
    case WM_ERASEBKGND:
        return 1;
    case WM_PAINT: {
        PAINTSTRUCT ps;
        BeginPaint(h, &ps);
        EndPaint(h, &ps);
        present();
        return 0;
    }
    default:
        break;
    }
    return DefWindowProc(h, msg, wp, lp);
}

static int make_window(HINSTANCE inst)
{
    WNDCLASSA wc;
    RECT r;
    DWORD style = WS_OVERLAPPEDWINDOW;
    int cw = opt.exact ? RENDER_W : 320 * opt.scale, ch = opt.exact ? RENDER_H : 240 * opt.scale;

    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = inst;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.lpszClassName = "PacManA8Port";
    if (!RegisterClassA(&wc)) {
        return 0;
    }
    SetRect(&r, 0, 0, cw, ch);
    AdjustWindowRect(&r, style, FALSE);
    hwnd = CreateWindowA(wc.lpszClassName, TITLE, style, CW_USEDEFAULT, CW_USEDEFAULT, r.right - r.left, r.bottom - r.top, NULL, NULL, inst, NULL);
    if (hwnd == NULL) {
        return 0;
    }
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    if (opt.fullscreen) {
        toggle_fullscreen();
    }
    return 1;
}

static void pump(void)
{
    MSG m;

    while (PeekMessage(&m, NULL, 0, 0, PM_REMOVE)) {
        if (m.message == WM_QUIT) {
            quit = 1;
        }
        TranslateMessage(&m);
        DispatchMessage(&m);
    }
}

/* ---------------------------------------------------------------- one frame */

static uint64_t vdig = 0xCBF29CE484222325ull, adig = 0xCBF29CE484222325ull;
static unsigned long frames_run;
static uint64_t last_hash;

static long long qpc_100ns(void)
{
    LARGE_INTEGER f, c;

    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (long long)((double)c.QuadPart * 1e7 / (double)f.QuadPart);
}

static void run_frame(void)
{
    FrontKeys k;
    FrameInput in;
    size_t got;

    keys_now(&k);
    front_frame(&front, &k, &in);
    if (writer.buf != NULL) {
        (void)replay_writer_add(&writer, &in);
    }
    last_hash = shell_frame(&shell, &in);
    render_frame(&renderer, &shell.world, colour);              /* every frame: the renderer carries the colours of the frame before */
    vdig = fnv64(vdig, colour, sizeof colour);
    got = audio_frame(&audio, &shell.world, pcm, sizeof pcm / sizeof pcm[0]);
    adig = hash_pcm(adig, pcm, got);
    if (wa != NULL && got > 0) {
        if (game_pcm != NULL && game_pcm_n + got <= GAME_PCM_MAX) {
            if (game_pcm_n == 0) {
                game_t0 = qpc_100ns();
            }
            memcpy(game_pcm + game_pcm_n, pcm, got * sizeof pcm[0]);
            game_pcm_n += got;
        }
        (void)wa_write(wa, pcm, got);
    }
    frames_run++;
}

static void make_bgra(void)
{
    size_t i;

    render_to_rgb(colour, rgb);
    for (i = 0; i < (size_t)RENDER_W * RENDER_H; i++) {
        bgra[4 * i] = rgb[3 * i + 2];
        bgra[4 * i + 1] = rgb[3 * i + 1];
        bgra[4 * i + 2] = rgb[3 * i];
        bgra[4 * i + 3] = 0;
    }
}

/* ---------------------------------------------------------------- the self test: real key messages posted to this window at set frames */

typedef struct Step {
    unsigned long frame;
    UINT msg;
    WPARAM vk;
} Step;

#define KD WM_KEYDOWN
#define KU WM_KEYUP
static const Step scenario[] = {
    {150, KD, VK_F2}, {156, KU, VK_F2},                                  /* START at the title */
    {420, KD, VK_LEFT}, {470, KU, VK_LEFT}, {470, KD, VK_UP}, {520, KU, VK_UP},
    {520, KD, VK_RIGHT}, {600, KU, VK_RIGHT}, {600, KD, VK_DOWN}, {680, KU, VK_DOWN},
    {700, KD, 'A'}, {760, KU, 'A'}, {760, KD, 'W'}, {820, KU, 'W'},
    {900, KD, VK_SPACE}, {902, KU, VK_SPACE},                            /* pause ... */
    {960, KD, VK_SPACE}, {962, KU, VK_SPACE},                            /* ... and resume */
    {1000, KD, VK_RIGHT}, {1100, KU, VK_RIGHT},
};

static void post_scenario(unsigned long frame)
{
    static size_t next;

    while (next < sizeof scenario / sizeof scenario[0] && scenario[next].frame <= frame) {
        PostMessage(hwnd, scenario[next].msg, scenario[next].vk, scenario[next].msg == KU ? (LPARAM)0xC0000001 : (LPARAM)1);
        next++;
    }
}

/* the window's pixels against the frame: the window's client area copied back out of the screen */
static long compare_window(void)
{
    HDC dc, mem;
    HBITMAP bmp, old;
    BITMAPINFO bi;
    static uint8_t got[RENDER_W * RENDER_H * 4];
    long bad = 0;
    size_t i;

    if (!opt.exact || hwnd == NULL) {
        return -1;
    }
    dc = GetDC(hwnd);
    mem = CreateCompatibleDC(dc);
    bmp = CreateCompatibleBitmap(dc, RENDER_W, RENDER_H);
    old = (HBITMAP)SelectObject(mem, bmp);
    BitBlt(mem, 0, 0, RENDER_W, RENDER_H, dc, 0, 0, SRCCOPY);
    SelectObject(mem, old);
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = RENDER_W;
    bi.bmiHeader.biHeight = -RENDER_H;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    GetDIBits(mem, bmp, 0, RENDER_H, got, &bi, DIB_RGB_COLORS);
    DeleteObject(bmp);
    DeleteDC(mem);
    ReleaseDC(hwnd, dc);
    {                                                          /* the capture, for the eye: logs/window.ppm */
        PmFile *pf = pm_fs_open("logs/window.ppm", "wb");
        if (pf != NULL) {
            pm_fs_printf(pf, "P6\n%d %d\n255\n", RENDER_W, RENDER_H);
            for (i = 0; i < (size_t)RENDER_W * RENDER_H; i++) {
                uint8_t px[3];
                px[0] = got[4 * i + 2];
                px[1] = got[4 * i + 1];
                px[2] = got[4 * i];
                pm_fs_write(pf, px, 3);
            }
            pm_fs_close(pf);
        }
    }
    for (i = 0; i < (size_t)RENDER_W * RENDER_H; i++) {
        if (got[4 * i] != bgra[4 * i] || got[4 * i + 1] != bgra[4 * i + 1] || got[4 * i + 2] != bgra[4 * i + 2]) {
            bad++;
        }
    }
    return bad;
}

/* ---------------------------------------------------------------- the main loop */

/* the sound the device really played (captured from its mix) against the sound handed to it: 10 ms blocks of loudness, the best match over a delay of 0 to 400 ms */
static void loopback_report(PmFile *rep)
{
    size_t cn = 0, gb, k, nblk;
    double crate = 0.0, best_r = -2.0, best_q = 0.0;
    long long cbase = 0;
    const float *cs;
    float *gl, *cl;
    int lag, best_lag = -1;
    size_t gsound = 0, csound = 0;

    if (wloop == NULL || game_pcm == NULL || game_pcm_n < 44100u) {
        pm_fs_printf(rep, "loopback: not measured (no capture endpoint)\n");
        return;
    }
    cs = wl_samples(wloop, &cn, &crate, &cbase);
    {                                                          /* the raw data, for the analysis tools: logs/loop_game.f32 (44,100 Hz), logs/loop_capture.f32 (the device's mix rate), logs/loop_meta.txt */
        PmFile *pf = pm_fs_open("logs/loop_game.f32", "wb");
        if (pf != NULL) {
            pm_fs_write(pf, game_pcm, game_pcm_n * sizeof(float));
            pm_fs_close(pf);
        }
        pf = pm_fs_open("logs/loop_capture.f32", "wb");
        if (pf != NULL) {
            pm_fs_write(pf, cs, cn * sizeof(float));
            pm_fs_close(pf);
        }
        pf = pm_fs_open("logs/loop_meta.txt", "wb");
        if (pf != NULL) {
            pm_fs_printf(pf, "%.1f %lld %lld\n", crate, game_t0, cbase);
            pm_fs_close(pf);
        }
    }
    {
        unsigned long st[5];
        wl_stats(wloop, st);
        pm_fs_printf(rep, "loopback: scope: %s\n", wl_scope(wloop) ? "this process only" : "the whole endpoint (other programs' sound is in it)");
        pm_fs_printf(rep, "loopback: capture packets %lu, silent %lu, discontinuities %lu, stamped before the start %lu\n", st[0], st[1], st[2], st[3]);
    }
    gb = game_pcm_n / 441u;
    nblk = gb + 60u;
    gl = (float *)calloc(nblk, sizeof(float));
    cl = (float *)calloc(nblk + 60u, sizeof(float));
    if (gl == NULL || cl == NULL) {
        free(gl);
        free(cl);
        return;
    }
    for (k = 0; k < gb; k++) {                                  /* the game's loudness per 10 ms */
        double e = 0.0;
        size_t i;
        for (i = 0; i < 441u; i++) {
            double v = (double)game_pcm[k * 441u + i];
            e += v * v;
        }
        gl[k] = (float)sqrt(e / 441.0);
        if (gl[k] > 0.005f) {
            gsound++;
        }
    }
    for (k = 0; k < nblk; k++) {                                /* the capture's loudness per 10 ms, from the time of the first sample handed over */
        double t0 = ((double)(game_t0 - cbase)) * 1e-7 + (double)k * 0.01;
        size_t i0 = t0 < 0.0 ? 0u : (size_t)(t0 * crate), n = (size_t)(crate * 0.01), i;
        double e = 0.0;
        for (i = 0; i < n && i0 + i < cn; i++) {
            double v = (double)cs[i0 + i];
            e += v * v;
        }
        cl[k] = (float)sqrt(e / (double)n);
        if ((double)cl[k] > 0.0025 * SELFTEST_GAIN) {
            csound++;
        }
    }
    for (lag = 0; lag <= 40; lag++) {
        double sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0, n = 0, r;
        for (k = 0; k < gb; k++) {
            double x = (double)gl[k], y = (double)cl[k + (size_t)lag];
            sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; n += 1.0;
        }
        r = (n * sxy - sx * sy) / sqrt(fmax((n * sxx - sx * sx) * (n * syy - sy * sy), 1e-30));
        if (r > best_r) {
            best_r = r;
            best_lag = lag * 10;
            best_q = sx > 0 ? sy / sx : 0.0;
        }
    }
    pm_fs_printf(rep, "loopback: the game handed over %.1f s, %lu blocks of 10 ms with sound; the device played %lu such blocks\n", (double)game_pcm_n / 44100.0, (unsigned long)gsound, (unsigned long)csound);
    pm_fs_printf(rep, "loopback: best match of the loudness curves: correlation %.4f at a delay of %d ms, level ratio %.4f (a volume of %.2f makes an amplitude of %.4f: the device played %.3f of what was handed over)\n", best_r, best_lag, best_q, (double)SELFTEST_VOLUME, SELFTEST_GAIN, best_q / SELFTEST_GAIN);
    free(gl);
    free(cl);
}

static void write_ppm(const char *path)
{
    PmFile *pf = pm_fs_open(path, "wb");

    if (pf != NULL) {
        pm_fs_printf(pf, "P6\n%d %d\n255\n", RENDER_W, RENDER_H);
        pm_fs_write(pf, rgb, sizeof rgb);
        pm_fs_close(pf);
    }
}

static void parse_args(int argc, char **argv)
{
    int i;

    opt.scale = 3;
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--root") == 0 && i + 1 < argc) {
            opt.root = argv[++i];
        } else if (strcmp(argv[i], "--scale") == 0 && i + 1 < argc) {
            opt.scale = atoi(argv[++i]);
            if (opt.scale < 1 || opt.scale > 8) {
                opt.scale = 3;
            }
        } else if (strcmp(argv[i], "--fullscreen") == 0) {
            opt.fullscreen = 1;
        } else if (strcmp(argv[i], "--no-audio") == 0) {
            opt.no_audio = 1;
        } else if (strcmp(argv[i], "--exact") == 0) {
            opt.exact = 1;
        } else if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) {
            opt.seed = (uint32_t)strtoul(argv[++i], NULL, 0);
            opt.have_seed = 1;
        } else if (strcmp(argv[i], "--record") == 0 && i + 1 < argc) {
            opt.record = argv[++i];
        } else if (strcmp(argv[i], "--ppm") == 0 && i + 1 < argc) {
            opt.ppm = argv[++i];
        } else if (strcmp(argv[i], "--selftest") == 0 && i + 1 < argc) {
            opt.selftest = atol(argv[++i]);
        }
    }
}

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmd, int show)
{
    char why[600];
    uint64_t t_start, t_prev, t_now, t_end = 0, worst = 0, sum = 0;
    unsigned long intervals = 0, late = 0, due_target = 0;
    PmFile *rep = NULL;
    long bad_pixels = -1;
    int ok = 1;

    (void)prev;
    (void)cmd;
    (void)show;
    SetProcessDPIAware();
    parse_args(__argc, __argv);
    if (opt.root != NULL && pm_fs_set_root(opt.root) != 0) {
        MessageBoxA(NULL, "The main folder given with --root is not usable.", TITLE, MB_OK | MB_ICONERROR);
        return 2;
    }
    if (boot(why, sizeof why) != 0) {
        MessageBoxA(NULL, why, TITLE, MB_OK | MB_ICONERROR);
        return 2;
    }
    if (!opt.have_seed) {
        opt.seed = (uint32_t)(pm_time_ns() & 0xFFFFFFFFu) | 1u;
    }
    shell_init(&shell, ram_image + 0x3000, opt.seed, 0);
    (void)shell_make_folders();
    if (opt.selftest <= 0) {
        (void)shell_highscore_load(&shell);
    }
    render_init(&renderer, ram_image);
    audio_init(&audio, AUDIO_RATE);
    front_init(&front, 0);
    xinput_load();
    if (opt.record != NULL || opt.selftest > 0) {
        replay_writer_init(&writer, record_buf, sizeof record_buf, opt.seed, 0, 0);
    }
    if (!opt.no_audio) {
        if (opt.selftest > 0) {
            game_pcm = (float *)calloc(GAME_PCM_MAX, sizeof(float));
        }
        wa = wa_open(AUDIO_RATE);
        if (wa != NULL) {
            float vv;
            int mm;
            if (wa_session_state(wa, &vv, &mm) == 0 && mm == 1) {   /* Windows keeps a mute per program (the volume mixer): a muted program is silent whatever it plays */
                (void)shell_log("the sound of this program is muted in the Windows volume mixer");
            }
            if (opt.selftest > 0) {
                (void)wa_set_volume(wa, SELFTEST_VOLUME);          /* a test does not blast the player's speakers; the measurement allows for it */
            }
        }
        if (opt.selftest > 0) {
            wloop = wl_open();
        }
    }
    if (!make_window(inst)) {
        MessageBoxA(NULL, "The window could not be made.", TITLE, MB_OK | MB_ICONERROR);
        return 2;
    }
    (void)rep;
    t_start = t_prev = pm_time_ns();
    while (!quit) {
        unsigned n = 0;

        pump();
        wl_poll(wloop);
        if (opt.selftest > 0) {
            post_scenario(frames_run);
            pump();
        }
        if (wa != NULL) {                                       /* the sound device is the clock */
            int q = wa_queued(wa);
            while (q >= 0 && q < QUEUE_TARGET_FRAMES && n < MAX_CATCH_UP && !(opt.selftest > 0 && (long)frames_run >= opt.selftest)) {
                run_frame();
                n++;
                q = wa_queued(wa);
            }
        } else {                                                /* the system timer is */
            due_target = (unsigned long)((double)(pm_time_ns() - t_start) * FRAME_HZ / 1e9);
            while (frames_run < due_target && n < MAX_CATCH_UP && !(opt.selftest > 0 && (long)frames_run >= opt.selftest)) {
                run_frame();
                n++;
            }
            if (frames_run + MAX_CATCH_UP < due_target) {       /* far behind (the window was dragged): do not race to catch up */
                t_start += (uint64_t)(((double)(due_target - frames_run) / FRAME_HZ) * 1e9);
            }
        }
        if (n > 0) {
            make_bgra();
            present();
            t_now = pm_time_ns();
            if (frames_run > (unsigned long)n) {
                uint64_t d = t_now - t_prev;
                sum += d;
                intervals++;
                if (d > worst) {
                    worst = d;
                }
                if (d > 40000000u) {                            /* a gap of more than 40 ms between pictures */
                    late++;
                }
            }
            t_prev = t_now;
        } else {
            Sleep(1);
        }
        if (opt.selftest > 0 && (long)frames_run >= opt.selftest) {
            if (bad_pixels < 0) {
                t_end = pm_time_ns();
                Sleep(400);                                     /* the device plays the last of the queue */
                wl_poll(wloop);
                pump();
                present();
                bad_pixels = compare_window();
                break;
            }
        }
    }
    if (writer.buf != NULL) {
        size_t size = 0;
        const char *path = opt.record != NULL ? opt.record : "logs/selftest.pmrp";
        ReplayError e = replay_writer_finish(&writer, &size);
        if (e == REPLAY_OK) {
            (void)shell_make_folders();
            e = replay_save(path, record_buf, size);
        }
        if (e != REPLAY_OK) {
            ok = 0;
        }
    }
    if (opt.selftest <= 0) {                                    /* a test does not touch the player's high score */
        (void)shell_highscore_save(&shell);
    }
    if (opt.ppm != NULL) {
        write_ppm(opt.ppm);
    }
    if (opt.selftest > 0) {
        rep = pm_fs_open("logs/selftest.txt", "wb");
        if (rep != NULL) {
            pm_fs_printf(rep, "frames run: %lu\n", frames_run);
            pm_fs_printf(rep, "final state hash: %016llx\n", (unsigned long long)last_hash);
            pm_fs_printf(rep, "run digest: %016llx\n", (unsigned long long)shell_digest(&shell));
            pm_fs_printf(rep, "video digest: %016llx\n", (unsigned long long)vdig);
            pm_fs_printf(rep, "audio digest: %016llx\n", (unsigned long long)adig);
            pm_fs_printf(rep, "clock: %s\n", wa != NULL ? "sound device" : "system timer");
            if (wa != NULL) {
                long hr;
                unsigned wf = wa_write_failures(wa, &hr);
                pm_fs_printf(rep, "sound device buffer: %d frames, underruns: %u, failed writes: %u (last code %ld)\n", wa_buffer_frames(wa), wa_underruns(wa), wf, hr);
            }
            pm_fs_printf(rep, "picture interval: mean %.2f ms, worst %.2f ms, over 40 ms: %lu (of %lu)\n", intervals ? (double)sum / (double)intervals / 1e6 : 0.0, (double)worst / 1e6, late, intervals);
            pm_fs_printf(rep, "elapsed: %.2f s for %lu frames (%.3f frames/s; the original runs at 59.923)\n", (double)(t_end - t_start) / 1e9, frames_run, (double)frames_run / ((double)(t_end - t_start) / 1e9));
            if (bad_pixels >= 0) {
                pm_fs_printf(rep, "window pixels differing from the frame: %ld of %d\n", bad_pixels, RENDER_W * RENDER_H);
            }
            loopback_report(rep);
            pm_fs_printf(rep, "high score: %06ld\n", shell_highscore_value(&shell));
            pm_fs_close(rep);
        }
    }
    wl_close(wloop);
    wa_close(wa);
    free(game_pcm);
    if (hwnd != NULL) {
        DestroyWindow(hwnd);
    }
    return ok ? 0 : 1;
}
