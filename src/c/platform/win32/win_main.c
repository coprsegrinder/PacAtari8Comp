/* platform/win32/win_main.c - the Windows 11 front end of the port: a window, the keyboard and XInput pads, the sound device (stage J, docs/67).
 *   pacman_a8_play [--root DIR] [--fps N|native|uncapped] [--no-audio] [--seed N] [--record FILE] [--ppm FILE]   (the game always starts in borderless fullscreen, at the monitor's resolution and refresh rate)
 *   [--crt off|guest|zfast|aperture]   (the CRT shader of the Graphics Options at the start)
 *   test options: [--windowed [--scale N]] [--trace FILE] [--selftest FRAMES] [--menutest] [--startuptest] [--exact]
 * It is the interactive twin of the headless shell: the same Shell, the same renderer, the same sound model, driven by the player instead of a replay.  What it adds is only what a machine does around the game:
 *   - keyboard / pad -> FrontKeys -> FrameInput (shell/frontend.c, portable and tested), one per frame;
 *   - the frame clock: the sound device's buffer (the game runs a frame whenever the device has less than two frames of sound queued), or the system timer when there is no device (--no-audio);
 *   - the picture: the renderer's 384 x 240 pixels (1.6 : 1) at a whole-number scale when that fills the area well, else as large as fits, nearest pixel, centred, black around it, never stretched (shell/menu.c display_fit);
 *   - the pause menu (ESC) and the graphics options (display mode, resolution): while a menu is open no game frame runs (shell/menu.c; docs/68);
 *   - the high score under save/, the replay of the game under --record (a recorded game replays headlessly to the same digests: the proof that this front end adds nothing to the game).
 * Keys: arrows / WASD stick, Ctrl / Z / X / Enter fire (Enter also START), F1 help, F2 START, F3 SELECT, F4 OPTION, Space / P pause, Alt+Enter or F11 full screen, Esc the pause menu.  Pads (XInput): D-pad or left stick,
 * A / B fire, Start = START, Back = SELECT, X / Y = OPTION; pad 2 is player 2; the keyboard drives both ports (hot-seat play on one keyboard).
 * --selftest FRAMES: plays a built-in scenario by posting real key messages to its own window, runs FRAMES frames, writes logs/selftest.txt (the digests, the timing, the sound device's underruns, a comparison of
 * the window's pixels with the frame) and quits.  --exact makes the window client exactly 384 x 240 pixels with no stretching (the pixel comparison needs it).
 * --menutest: drives the pause menu and the graphics options by real key messages (ESC, arrows, Enter, F11, Alt+Enter), checks that the game is frozen while a menu is open, and that every display mode and
 * resolution gives the layout of display_fit and the picture the window really shows (logs/menutest.txt). */
#include <windows.h>

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../assets/assets.h"
#include "../../assets/rom_install.h"
#include "../../audio/audio.h"
#include "../../render/interp.h"
#include "../../render/render.h"
#include "../../shell/frontend.h"
#include "../../shell/menu.h"
#include "../../shell/replay.h"
#include "../../shell/shell.h"
#include "../fs.h"
#include "../timer.h"
#include "win_audio.h"
#include "win_gl.h"

#define AUDIO_RATE 44100.0
#define FRAME_HZ 59.9227                 /* NTSC: 1,789,772.5 Hz / 29,868 cycles a frame */
#define QUEUE_TARGET_FRAMES 1500         /* the device keeps about two game frames of sound queued */
#define MAX_CATCH_UP 4
#define SELFTEST_VOLUME 0.3f             /* the self test plays at a low volume (the capture is of the sound after it) */
#define SELFTEST_GAIN ((double)SELFTEST_VOLUME * (double)SELFTEST_VOLUME)   /* Windows volume scalars are an audio taper: the amplitude is the square of the scalar */
#define RECORD_CAP (1u << 23)
#define TITLE "Pac-Man (Atari 8-bit) - C port"

typedef struct Options {
    int scale, fullscreen, no_audio, exact, menutest, windowed, startuptest, crttest, offtest;
    const char *fps, *trace, *crt;
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
static Audio audio;                      /* the chip model at the output rate: the digests of the game are made from it (as in the headless shell) */
static AudioHq audio_hq;                 /* the same chip at four times the rate, low-passed: what the speaker plays (no tone above 22 kHz folded down into the hearing range, docs/22) */
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
static int fullscreen;                   /* the display mode as applied to the window: 1 borderless fullscreen */
static Menu menu;                        /* the pause menu and the display settings (shell/menu.c) */
static int menu_dirty;                   /* the menu or the picture behind it must be drawn again */
static LONG saved_style;
static void detect_monitor_hz(void);

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

/* the display mode and the size of the window, from the settings of the menu (menu.fullscreen, menu.res): borderless fullscreen covers the monitor; windowed makes a window whose client area is the selected
 * resolution (as much of it as the monitor's work area has room for), centred on the monitor.  Nothing of the game is touched, so a change is immediate and the game goes on where it was. */
static void apply_display(void)
{
    MONITORINFO mi;
    RECT r;
    DWORD style;
    int cw, ch, fw, fh, workw, workh;

    mi.cbSize = sizeof mi;
    if (hwnd == NULL || !GetMonitorInfo(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &mi)) {
        return;
    }
    detect_monitor_hz();
    if (IsZoomed(hwnd) || IsIconic(hwnd)) {                     /* a maximized or minimized window is made a normal one first: the size and place below are of the normal window */
        ShowWindow(hwnd, SW_RESTORE);
    }
    if (menu.fullscreen) {
        SetWindowLong(hwnd, GWL_STYLE, (LONG)(WS_POPUP | WS_VISIBLE));
        SetWindowPos(hwnd, HWND_TOP, mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top,
                     SWP_NOOWNERZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW);
        if (!fullscreen) {
            ShowCursor(FALSE);
        }
        fullscreen = 1;
    } else {
        style = WS_OVERLAPPEDWINDOW | WS_VISIBLE;
        menu_size(&menu, &cw, &ch);
        SetRect(&r, 0, 0, cw, ch);
        AdjustWindowRect(&r, style, FALSE);
        fw = (r.right - r.left) - cw;
        fh = (r.bottom - r.top) - ch;
        workw = mi.rcWork.right - mi.rcWork.left;
        workh = mi.rcWork.bottom - mi.rcWork.top;
        if (cw + fw > workw) {
            cw = workw - fw;
        }
        if (ch + fh > workh) {
            ch = workh - fh;
        }
        SetWindowLong(hwnd, GWL_STYLE, (LONG)style);
        SetWindowPos(hwnd, HWND_NOTOPMOST, mi.rcWork.left + (workw - (cw + fw)) / 2, mi.rcWork.top + (workh - (ch + fh)) / 2, cw + fw, ch + fh,
                     SWP_NOOWNERZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW);
        if (fullscreen) {
            ShowCursor(TRUE);
        }
        fullscreen = 0;
    }
    saved_style = GetWindowLong(hwnd, GWL_STYLE);
    InvalidateRect(hwnd, NULL, FALSE);
    menu_dirty = 1;
    if (crt_gl_is_open()) {
        RECT crc;
        GetClientRect(hwnd, &crc);
        crt_gl_resize(crc.right, crc.bottom);
    }
}

/* F11 and Alt+Enter: the other display mode, at the resolution selected */
static void toggle_fullscreen(void)
{
    menu.fullscreen = !menu.fullscreen;
    apply_display();
}

/* the picture in a client area of cw x ch (opt.exact: the pixels as they are).  In a window the picture may use the whole client area; in borderless fullscreen it may use the centred area of the
 * selected resolution (a monitor smaller than the resolution gives the monitor): display_fit makes it a whole-number scale when that uses the area well, else the largest that fits, always 1.6 : 1 */
static void layout(int cw, int ch, DisplayRect *r)
{
    int aw = cw, ah = ch;

    if (opt.exact) {
        memset(r, 0, sizeof *r);
        r->w = RENDER_W;
        r->h = RENDER_H;
        r->scale_num = r->scale_den = r->integer = 1;
        return;
    }
    if (fullscreen) {
        menu_size(&menu, &aw, &ah);
    }
    display_fit(cw, ch, aw, ah, r);
}

/* ---------------------------------------------------------------- the FPS option: in-between pictures (docs/69) */

#define CRT_SUB 8                         /* with a CRT shader the in-between picture is made 8 times as wide and brought back to 384: an eighth of a game pixel across */
#define RING 32                          /* the game frames kept for the in-between pictures (the moves of an object are looked for up to 20 frames back) */
#define SAMPLES_PER_FRAME (AUDIO_RATE / FRAME_HZ)
#define PICTURE_AHEAD 0.6                /* the picture is of the game time the sound device is at plus this many frames.  The native picture is the newest game frame, which is 1.3 frames ahead of the sound on average: the further a picture is behind it, the later it shows what a key did.  An in-between picture needs the game a frame ahead of it to know where an object is going, so it cannot be as new: 0.6 puts it 0.7 frames (11 ms) behind the native one on average, 0 to 1.6 (measured: docs/69).  0 would be 21 ms behind, 1.0 only 5 ms but with an uneven game time */
static InterpFrame *ring;                /* the last RING game frames, with their layers */
static unsigned long ring_id[RING];
static int ring_ok[RING];
static InterpOut iout;                   /* the picture made for the window */
static int iout_have;                    /* iout is what the window shows */
static const uint8_t *shown_colour;      /* the colours of the nearest game frame to the picture shown (the menu is drawn over it); NULL: the last frame */
static double audio_written;             /* samples handed to the sound device */
static double tau_a;                     /* the game time (in frames) of the picture to show, as of tau_t0 */
static uint64_t tau_t0;
#define PROD_N 256
static uint64_t prod_ns[PROD_N];       /* when each of the last frames of the game was made (the picture's game time is made from these) */
static int tau_valid;
static int tau_grid_hz;                  /* when the pictures are made on the refreshes of the monitor: its rate; the game time then advances by whole refreshes (0: by the clock) */
static uint64_t next_tick_ns;
static PmFile *trace_file;                /* --trace FILE: every picture made, with the game time and where the objects are drawn (for the analysis of the motion) */
static unsigned long still_last = ~0ul;   /* the game frame the picture shows when there are fewer pictures a second than the game makes: a picture is made when this changes */
static unsigned long tick_count, blit_count;    /* pictures made at a tick, and pictures that differed from the one before (the FPS test counts them) */
typedef HRESULT(WINAPI *DwmFlushFn)(void);
static DwmFlushFn dwm_flush;
static int bars_x = -1, bars_y = -1, bars_w = -1, bars_h = -1, bars_cw = -1, bars_ch = -1;

static int interp_wanted(void)
{
    return ring != NULL && !opt.exact && menu_fps(&menu) != MENU_FPS_NATIVE;
}

static int mon_w, mon_h;                 /* the size of the monitor the window is on, in pixels */

/* the size and refresh rate of a monitor (its current mode); 0 when Windows does not say */
static void monitor_mode(HMONITOR hm, int *w, int *h, int *hz)
{
    MONITORINFOEXA mi;
    DEVMODEA dm;

    *w = *h = *hz = 0;
    memset(&mi, 0, sizeof mi);
    mi.cbSize = sizeof mi;
    if (hm == NULL || !GetMonitorInfoA(hm, (MONITORINFO *)&mi)) {
        return;
    }
    *w = (int)(mi.rcMonitor.right - mi.rcMonitor.left);
    *h = (int)(mi.rcMonitor.bottom - mi.rcMonitor.top);
    memset(&dm, 0, sizeof dm);
    dm.dmSize = sizeof dm;
    if (EnumDisplaySettingsA(mi.szDevice, ENUM_CURRENT_SETTINGS, &dm)) {
        if (dm.dmDisplayFrequency > 1) {
            *hz = (int)dm.dmDisplayFrequency;
        }
        if (dm.dmPelsWidth > 0 && dm.dmPelsHeight > 0) {
            *w = (int)dm.dmPelsWidth;
            *h = (int)dm.dmPelsHeight;
        }
    }
}

static void detect_monitor_hz(void)
{
    int w, h, hz;

    if (hwnd == NULL) {
        return;
    }
    monitor_mode(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &w, &h, &hz);
    if (hz > 0) {
        menu.monitor_hz = hz;
    }
    if (w > 0) {
        mon_w = w;
        mon_h = h;
    }
}

/* the window gets the picture of iout: all of it, or the rectangles of d; the black around it is drawn when the layout changed */
static int plain_gl;                     /* the OpenGL window is shown and draws the plain picture when no shader is chosen (set below, with the chains) */
static int plain_present(const uint32_t *src, int w, int h, const InterpDirty *d);

static void present_interp(const InterpDirty *d)
{
    HDC dc;
    RECT rc;
    BITMAPINFO bi;
    DisplayRect pr;
    int i, full;

    if (hwnd == NULL || iout.work == NULL) {
        return;
    }
    GetClientRect(hwnd, &rc);
    layout(rc.right, rc.bottom, &pr);
    if (pr.w != iout.ow || pr.h != iout.oh) {                 /* the window changed size since the picture was made: the next picture is made at the new size */
        return;
    }
    if (plain_gl) {
        (void)plain_present((const uint32_t *)iout.work, iout.ow, iout.oh, d);
        return;
    }
    dc = GetDC(hwnd);
    full = d == NULL || d->full;
    if (pr.x != bars_x || pr.y != bars_y || pr.w != bars_w || pr.h != bars_h || rc.right != bars_cw || rc.bottom != bars_ch) {
        HBRUSH b = (HBRUSH)GetStockObject(BLACK_BRUSH);
        RECT r;
        SetRect(&r, 0, 0, rc.right, pr.y);
        FillRect(dc, &r, b);
        SetRect(&r, 0, pr.y + pr.h, rc.right, rc.bottom);
        FillRect(dc, &r, b);
        SetRect(&r, 0, pr.y, pr.x, pr.y + pr.h);
        FillRect(dc, &r, b);
        SetRect(&r, pr.x + pr.w, pr.y, rc.right, pr.y + pr.h);
        FillRect(dc, &r, b);
        bars_x = pr.x;
        bars_y = pr.y;
        bars_w = pr.w;
        bars_h = pr.h;
        bars_cw = rc.right;
        bars_ch = rc.bottom;
        full = 1;
    }
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = iout.ow;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    if (full) {
        bi.bmiHeader.biHeight = -iout.oh;
        StretchDIBits(dc, pr.x, pr.y, iout.ow, iout.oh, 0, 0, iout.ow, iout.oh, iout.work, &bi, DIB_RGB_COLORS, SRCCOPY);
    } else {
        for (i = 0; i < d->n; i++) {                           /* only what moved: each rectangle holds an object's old and new place */
            int x0 = d->r[i][0], y0 = d->r[i][1], w = d->r[i][2] - d->r[i][0], h = d->r[i][3] - d->r[i][1];
            if (w <= 0 || h <= 0) {
                continue;
            }
            bi.bmiHeader.biHeight = -h;
            StretchDIBits(dc, pr.x + x0, pr.y + y0, w, h, x0, 0, w, h, iout.work + (size_t)y0 * (size_t)iout.ow, &bi, DIB_RGB_COLORS, SRCCOPY);
        }
    }
    ReleaseDC(hwnd, dc);
}

/* ---------------------------------------------------------------- the CRT shader: the picture of the game (384 x 240) goes through a chain of OpenGL passes into the child window (docs/70) */

static CrtChain *crt_cache[4];          /* the chains of the three shaders, loaded once and kept: choosing a shader again is instant (loading and compiling takes about a second) */
static CrtChain *crt_chain;              /* the chain of the shader chosen, or NULL when it is off */
static int crt_active;                   /* the OpenGL child window is the one that shows the picture */
static unsigned crt_frames;              /* pictures through the chain (the shaders' frame counter) */
static uint32_t crt_last[RENDER_W * RENDER_H];   /* the last picture given to the chain: what a repaint of the window shows again */
static int crt_have_last;
static int crt_gl_w, crt_gl_h;
static int crt_errors;                   /* pictures the chain failed to make (the test looks) */
static int crt_shot_req;                 /* a test asks for the pixels of the next picture */
static uint8_t *crt_shot;
static int crt_shot_w, crt_shot_h;
static double swap_ema_ms = -1.0;        /* how long the swap of the OpenGL window takes while it waits for the monitor (-1: not known yet); a swap that does not wait (a window, not fullscreen) is no clock, and the timer paces the pictures then */
static int crt_want_interval;            /* how the swap of the OpenGL window waits: 0 not at all, n for every n-th refresh of the monitor (the pictures are then paced by it) */
static double interp_ms;                 /* how long the last in-between picture took to make (the trace shows it) */
static double crt_ms_render, crt_ms_swap;   /* how long the last picture took to give to OpenGL, and to swap (the trace shows them) */
static char crt_why[2000];                /* why the shaders are not available, for the log */

static CrtChain *plain_chain;            /* the picture as it is (src/shaders/plain.slangp): the OpenGL window is the one that shows the picture all the time when it can, so that choosing a shader or Off only changes what is drawn into it (no window is shown or hidden, the screen does not go black) */
static uint64_t crt_choice_ns;           /* when the shader was chosen: the first picture through it is timed from here (the log says how long the choice took to show) */
static void crt_render_last(void)
{
    RECT rc;
    DisplayRect pr;
    char err[300];
    uint64_t t_start_ns = pm_time_ns(), t_mid;

    if (!crt_active || crt_chain == NULL || !crt_have_last || hwnd == NULL) {
        return;
    }
    GetClientRect(hwnd, &rc);
    if (rc.right != crt_gl_w || rc.bottom != crt_gl_h) {
        crt_gl_resize(rc.right, rc.bottom);
        crt_gl_w = rc.right;
        crt_gl_h = rc.bottom;
    }
    layout(rc.right, rc.bottom, &pr);
    if (pr.w < 1 || pr.h < 1) {
        return;
    }
    err[0] = '\0';
    if (crt_chain_render(crt_chain, crt_last, RENDER_W, RENDER_H, pr.x, pr.y, pr.w, pr.h, crt_frames++, err, sizeof err) != 0) {
        if (crt_errors++ == 0) {
            char line[360];
            snprintf(line, sizeof line, "CRT shader: %s", err);
            (void)shell_log(line);
        }
        return;
    }
    if (crt_shot_req) {
        free(crt_shot);
        crt_shot = (uint8_t *)malloc((size_t)pr.w * (size_t)pr.h * 4u);
        if (crt_shot != NULL && crt_gl_readback(crt_shot, pr.w, pr.h) == 0) {
            crt_shot_w = pr.w;
            crt_shot_h = pr.h;
        } else {
            crt_shot_w = crt_shot_h = 0;
        }
        crt_shot_req = 0;
    }
    t_mid = pm_time_ns();
    crt_gl_interval(crt_want_interval);
    crt_gl_swap();
    crt_ms_render = (double)(t_mid - t_start_ns) / 1e6;
    crt_ms_swap = (double)(pm_time_ns() - t_mid) / 1e6;
    if (crt_want_interval > 0) {
        swap_ema_ms = swap_ema_ms < 0.0 ? crt_ms_swap : 0.9 * swap_ema_ms + 0.1 * crt_ms_swap;
    }
    if (crt_choice_ns != 0) {
        char line[160];
        snprintf(line, sizeof line, "CRT shader: first picture %.0f ms after the choice (draw %.1f ms, swap %.1f ms)", (double)(pm_time_ns() - crt_choice_ns) / 1e6, crt_ms_render, crt_ms_swap);
        (void)shell_log(line);
        crt_choice_ns = 0;
    }
}

/* the plain picture (w x h, BGRA, the part of the window `pr`) through the plain chain into the OpenGL window; 1 when it was drawn */
static int plain_present(const uint32_t *src, int w, int h, const InterpDirty *d)
{
    RECT rc;
    DisplayRect pr;
    char err[200];

    if (!plain_gl || plain_chain == NULL || hwnd == NULL || src == NULL) {
        return 0;
    }
    GetClientRect(hwnd, &rc);
    if (rc.right != crt_gl_w || rc.bottom != crt_gl_h) {
        crt_gl_resize(rc.right, rc.bottom);
        crt_gl_w = rc.right;
        crt_gl_h = rc.bottom;
    }
    layout(rc.right, rc.bottom, &pr);
    {
        uint64_t up0 = pm_time_ns();
        if (d != NULL && !d->full) {                              /* only the places of the picture that changed go to the graphics card (the whole picture is 13 MB at 2304 x 1440) */
            crt_gl_dirty(d->r, d->n);
        } else {
            crt_gl_dirty(NULL, -1);
        }
        if (pr.w < 1 || pr.h < 1 || crt_chain_render(plain_chain, src, w, h, pr.x, pr.y, pr.w, pr.h, 0u, err, sizeof err) != 0) {
            return 0;
        }
        crt_ms_render = (double)(pm_time_ns() - up0) / 1e6;
    }
    {
        uint64_t sw0 = pm_time_ns();
        crt_gl_interval(crt_want_interval);
        crt_gl_swap();
        crt_ms_swap = (double)(pm_time_ns() - sw0) / 1e6;
        if (crt_want_interval > 0) {
            swap_ema_ms = swap_ema_ms < 0.0 ? crt_ms_swap : 0.9 * swap_ema_ms + 0.1 * crt_ms_swap;
        }
    }
    return 1;
}

/* the chosen shader on (or off): the chain is made, the OpenGL window shown; when the machine cannot, the choice goes back to off and says so in the menu and the log */
static void crt_apply(void)
{
    char err[1600];

    crt_choice_ns = pm_time_ns();
    crt_chain = NULL;
    crt_active = 0;
    crt_have_last = 0;
    iout_have = 0;
    menu_dirty = 1;
    if (menu.crt == 0) {
        if (!plain_gl) {
            crt_gl_show(0);
        }
        if (hwnd != NULL) {
            InvalidateRect(hwnd, NULL, FALSE);                          /* not erased to black: the next picture covers it */
        }
        return;
    }
    if (!crt_gl_is_open() && crt_gl_open(hwnd, err, sizeof err) != 0) {
        snprintf(crt_why, sizeof crt_why, "the CRT shaders are not available: %.1500s", err);
        (void)shell_log(crt_why);
        menu.crt = 0;
        menu.crt_unavailable = 1;
        return;
    }
    if (crt_cache[menu.crt] == NULL) {
        crt_cache[menu.crt] = crt_chain_load(menu_crt_files[menu.crt], err, sizeof err);
    }
    crt_chain = crt_cache[menu.crt];
    if (crt_chain == NULL) {
        snprintf(crt_why, sizeof crt_why, "the CRT shader %s is not available: %.1500s", menu_crt_names[menu.crt], err);
        (void)shell_log(crt_why);
        menu.crt = 0;
        menu.crt_unavailable = 1;
        crt_gl_show(plain_gl);
        return;
    }
    menu.crt_unavailable = 0;
    crt_errors = 0;
    {
        RECT rc;
        GetClientRect(hwnd, &rc);
        crt_gl_resize(rc.right, rc.bottom);
        crt_gl_w = rc.right;
        crt_gl_h = rc.bottom;
    }
    crt_gl_show(1);
    crt_active = 1;
}

static void present(void)
{
    HDC dc;
    RECT rc;
    BITMAPINFO bi;
    DisplayRect pr;
    int x, y, w, h;

    if (hwnd == NULL) {
        return;
    }
    if (crt_active) {                                                   /* the CRT shader makes the picture, in the OpenGL window */
        crt_want_interval = 0;
        crt_render_last();
        return;
    }
    if (iout_have && !menu_is_open(&menu) && interp_wanted()) {         /* the picture of the FPS option is what the window shows */
        present_interp(NULL);
        return;
    }
    if (plain_gl) {
        crt_want_interval = 0;
        (void)plain_present((const uint32_t *)bgra, RENDER_W, RENDER_H, NULL);
        return;
    }
    dc = GetDC(hwnd);
    GetClientRect(hwnd, &rc);
    layout(rc.right, rc.bottom, &pr);
    x = pr.x;
    y = pr.y;
    w = pr.w;
    h = pr.h;
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

/* ---------------------------------------------------------------- the menu */

static int menu_resync;                  /* the menu was closed: the timer clock must not try to make up the time spent in it */

static void menu_event(MenuKey k)
{
    int was_open = menu_is_open(&menu);

    menu_key(&menu, k);
    if (menu.quit) {
        quit = 1;
    }
    if (menu.changed) {
        menu.changed = 0;
        swap_ema_ms = -1.0;                                   /* window or fullscreen: whether the swap waits is found out again */
        apply_display();
    }
    if (menu.crt_changed) {                                   /* the CRT shader */
        menu.crt_changed = 0;
        crt_apply();
        still_last = ~0ul;
    }
    if (menu.fps_changed) {                                   /* the FPS: the next pictures are made the new way, from the game time the sound is at */
        menu.fps_changed = 0;
        still_last = ~0ul;
        next_tick_ns = 0;
        tau_valid = 0;
        iout_have = 0;
        shown_colour = NULL;
    }
    if (was_open != menu_is_open(&menu)) {
        pause_edge = 0;
        if (was_open) {
            menu_resync = 1;
            still_last = ~0ul;
            tau_valid = 0;
            next_tick_ns = 0;
        }
    }
    menu_dirty = 1;
}

static int menu_key_of(unsigned vk, MenuKey *k)
{
    switch (vk) {
    case VK_UP: case 'W': *k = MK_UP; return 1;
    case VK_DOWN: case 'S': *k = MK_DOWN; return 1;
    case VK_LEFT: case 'A': *k = MK_LEFT; return 1;
    case VK_RIGHT: case 'D': *k = MK_RIGHT; return 1;
    case VK_RETURN: case VK_SPACE: *k = MK_SELECT; return 1;
    case VK_ESCAPE: *k = MK_BACK; return 1;
    default: return 0;
    }
}

/* the pad drives the menu too: D-pad or left stick move, A selects, B goes back; Start + Back together open it (a pad has no Esc) */
static void pad_menu_poll(void)
{
    static unsigned prev;
    XIn x;
    unsigned m = 0, e;

    if (pad_read(0, &x)) {
        WORD b = x.buttons;
        m |= (unsigned)((b & XB_UP) != 0 || x.ly > STICK_DEAD) << 0;
        m |= (unsigned)((b & XB_DOWN) != 0 || x.ly < -STICK_DEAD) << 1;
        m |= (unsigned)((b & XB_LEFT) != 0 || x.lx < -STICK_DEAD) << 2;
        m |= (unsigned)((b & XB_RIGHT) != 0 || x.lx > STICK_DEAD) << 3;
        m |= (unsigned)((b & XB_A) != 0) << 4;
        m |= (unsigned)((b & XB_B) != 0) << 5;
        m |= (unsigned)((b & XB_START) != 0) << 6;
        m |= (unsigned)((b & XB_BACK) != 0) << 7;
    }
    e = m & ~prev;
    prev = m;
    if (menu_is_open(&menu)) {
        if (e & 1u) { menu_event(MK_UP); }
        if (e & 2u) { menu_event(MK_DOWN); }
        if (e & 4u) { menu_event(MK_LEFT); }
        if (e & 8u) { menu_event(MK_RIGHT); }
        if (e & 16u) { menu_event(MK_SELECT); }
        if (e & 32u) { menu_event(MK_BACK); }
    } else if ((m & 0xC0u) == 0xC0u && (e & 0xC0u) != 0) {
        menu_event(MK_BACK);
    }
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
        if (vk == VK_F11) {
            if (!repeat) {
                toggle_fullscreen();
            }
            return 0;
        }
        if (vk == VK_F1) {                                        /* the help, from anywhere: a pause, like the menu */
            if (!repeat) {
                menu_event(MK_HELP);
            }
            return 0;
        }
        if (menu_is_open(&menu) || vk == VK_ESCAPE) {             /* ESC opens the menu; while it is open the keys are its keys, not the game's */
            MenuKey mk;
            if (menu_key_of(vk, &mk) && (!repeat || (mk != MK_BACK && mk != MK_SELECT))) {
                menu_event(mk);
            }
            return 0;
        }
        if (!repeat) {
            key_down[vk] = 1;
            if (vk == VK_SPACE || vk == 'P') {                 /* a PRESS: the keyboard interrupt of the original does not repeat it */
                pause_edge = 1;
            }
        }
        return 0;
    }
    case WM_SYSCOMMAND:
        if ((wp & 0xFFF0u) == SC_MINIMIZE) {                      /* who minimises the window? (it happens in long test runs, and was never found: this says what was in front) */
            char title[120] = "", line[320];
            HWND fg = GetForegroundWindow();
            DWORD pid = 0;
            if (fg != NULL) {
                GetWindowTextA(fg, title, sizeof title);
                GetWindowThreadProcessId(fg, &pid);
            }
            snprintf(line, sizeof line, "the window was told to minimise (SC_MINIMIZE); in front: \"%s\" (process %lu), this is %lu", title, (unsigned long)pid, (unsigned long)GetCurrentProcessId());
            (void)shell_log(line);
        }
        break;
    case WM_SIZE:
        if (crt_gl_is_open()) {
            crt_gl_resize(LOWORD(lp), HIWORD(lp));              /* the OpenGL window of the CRT shaders is as large as the client area */
        }
        break;
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
    int cw, ch;

    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = inst;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.lpszClassName = "PacManA8Port";
    if (!RegisterClassA(&wc)) {
        return 0;
    }
    menu_size(&menu, &cw, &ch);
    SetRect(&r, 0, 0, cw, ch);
    AdjustWindowRect(&r, style, FALSE);
    hwnd = CreateWindowA(wc.lpszClassName, TITLE, style, CW_USEDEFAULT, CW_USEDEFAULT, r.right - r.left, r.bottom - r.top, NULL, NULL, inst, NULL);
    if (hwnd == NULL) {
        return 0;
    }
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    apply_display();                                          /* the size and place of the window, and borderless fullscreen when asked for */
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
    if (interp_wanted()) {                                      /* every frame: the renderer carries the colours of the frame before; the layers are kept for the in-between pictures */
        size_t slot = (size_t)(frames_run % RING), prev = (size_t)((frames_run + RING - 1) % RING);
        InterpFrame *f = &ring[slot];
        render_frame_layers(&renderer, &shell.world, f->colour, &f->layers);
        interp_prepare(f);
        memcpy(colour, f->colour, sizeof colour);
        ring_ok[slot] = 1;
        ring_id[slot] = frames_run;
        interp_follow(f, (frames_run > 0 && ring_ok[prev] && ring_id[prev] == frames_run - 1) ? &ring[prev] : NULL);
    } else {
        render_frame(&renderer, &shell.world, colour);
    }
    vdig = fnv64(vdig, colour, sizeof colour);
    {
        uint8_t wreg[WRITE_CLOCK_MAX], wval[WRITE_CLOCK_MAX];
        unsigned wn = audio_world_writes(&shell.world, wreg, wval);
        got = audio_frame(&audio, &shell.world, pcm, sizeof pcm / sizeof pcm[0]);
        adig = hash_pcm(adig, pcm, got);
        got = audio_hq_frame(&audio_hq, wreg, wval, wn, pcm, sizeof pcm / sizeof pcm[0]);          /* what the speaker gets */
    }
    if (wa != NULL && got > 0) {
        if (game_pcm != NULL && game_pcm_n + got <= GAME_PCM_MAX) {
            if (game_pcm_n == 0) {
                game_t0 = qpc_100ns();
            }
            memcpy(game_pcm + game_pcm_n, pcm, got * sizeof pcm[0]);
            game_pcm_n += got;
        }
        (void)wa_write(wa, pcm, got);
        audio_written += (double)got;
    }
    prod_ns[frames_run % PROD_N] = pm_time_ns();
    frames_run++;
}

/* ---------------------------------------------------------------- one picture of the FPS option */

static const InterpFrame *ring_get_ctx(void *ctx, unsigned long id)
{
    size_t s = (size_t)(id % RING);

    (void)ctx;
    return (ring_ok[s] && ring_id[s] == id) ? &ring[s] : NULL;
}

static const InterpFrame *ring_get(unsigned long id)
{
    return ring_get_ctx(NULL, id);
}

/* which game time (in frames) the picture of this moment shows: the frame the sound device is playing, so that picture and sound are one; the model runs on the clock at exactly the game's rate and is
 * pulled to the device's position slowly (the device's queue is read in steps), so the speed of the game is the original's whatever the display does */
static double game_time(uint64_t now, uint64_t t_start_ns)
{
    double pred, dt, target, cmin = 1e30, err, up, down;
    unsigned long j, lo, newest;
    static uint64_t ref_ns;

    if (wa == NULL || frames_run == 0) {
        return (double)(now - t_start_ns) * FRAME_HZ / 1e9;
    }
    if (ref_ns == 0) {
        ref_ns = now;
    }
    /* The game time of the picture is a clock that runs at exactly the game's rate and is never ahead of the game: frame j was made at the time prod_ns[j], and the picture must not be at frame j before it
     * is made, and needs the frame after it as well to see where the objects go: so tau(prod_ns[j]) <= j - 1 for every frame j of the last 2.5 s.  The latest frame made, relative to that clock, fixes where the
     * clock is (the sound device's queue, which was read before, is read in steps and has a noise as large as the margin: the pictures then stood still at the newest frame for up to a second, the pauses of Pac-Man).
     * The frames are made as the device needs them, so on average the picture stays with the sound; it is a frame or two behind the newest frame made, as the in-between pictures need. */
    newest = frames_run - 1u;
    lo = newest > 150u ? newest - 150u : 0u;
    for (j = lo; j <= newest; j++) {
        double v = (double)j - FRAME_HZ * (double)((int64_t)(prod_ns[j % PROD_N] - ref_ns)) / 1e9;
        if (v < cmin) {
            cmin = v;
        }
    }
    target = FRAME_HZ * (double)((int64_t)(now - ref_ns)) / 1e9 + cmin - 1.0;
    if (!tau_valid) {
        tau_a = target;
        tau_t0 = now;
        tau_valid = 1;
        return tau_a;
    }
    dt = (double)(now - tau_t0) / 1e9;
    if (tau_grid_hz > 0) {                                      /* pictures on the monitor's refreshes: the game time goes by whole refreshes, so that a picture that came a fraction of a millisecond early or late does not change how many pictures a game frame lasts (the mouth of Pac-Man flaps evenly) */
        double per = 1.0 / (double)tau_grid_hz;
        double whole = floor(dt / per + 0.5);
        if (whole < 1.0) {
            return tau_a + dt * FRAME_HZ;
        }
        dt = whole * per;
        tau_t0 += (uint64_t)(dt * 1e9);
    } else {
        tau_t0 = now;
    }
    pred = tau_a + dt * FRAME_HZ;
    err = target - pred;
    up = 0.01 * FRAME_HZ * dt;                                  /* the clock may run 1 % fast to come forward, 10 % slow to go back: never a jump, and never ahead of the game for long */
    down = 0.10 * FRAME_HZ * dt;
    if (err > 0.0 && err < 0.8) {                               /* behind the limit by less than 0.8 frame: leave the clock alone, so that the pictures keep their place among the refreshes (a frame lasts the same number of pictures every time) */
        err = 0.0;
    } else if (err > up) {
        err = up;
    } else if (err < -down) {
        err = -down;
    }
    tau_a = pred + err;
    return tau_a;
}

/* waits for the next picture time (or not), makes the picture of this moment and shows it; returns 1 when it made one */
static int interp_step(uint64_t t_start_ns)
{
    const int target = menu_fps(&menu);
    uint64_t now = pm_time_ns();
    InterpDirty d;
    RECT rc;
    DisplayRect pr;
    double tau, still_tau = 0.0;
    int grid_next = 0;
    long A;
    int changed;
    const int still = target > 0 && target < 55;                 /* fewer pictures a second than the game makes (30): every n-th game frame, as the game made it */

    if (still) {
        /* Not a picture made between two frames: that would make the objects glide through a game that is shown at half its pictures, and the playfield, the animation and the sound would not go with them.  The
         * game frames are shown as they are, every second one for 30 (the one the picture time is at, or the one before it), a picture made as soon as that frame changes (no clock of its own to drift against
         * the game's) and no sooner. */
        int step = (int)floor(FRAME_HZ / (double)target + 0.5);
        double t0 = game_time(now, t_start_ns);
        unsigned long a = t0 < 0.0 ? 0u : (unsigned long)floor(t0), newest0 = frames_run > 0 ? frames_run - 1u : 0u, id;
        int want_w, want_h;

        if (a > newest0) {
            a = newest0;
        }
        id = (a / (unsigned long)step) * (unsigned long)step;
        GetClientRect(hwnd, &rc);
        layout(rc.right, rc.bottom, &pr);
        want_w = crt_active ? RENDER_W * CRT_SUB : pr.w;
        want_h = crt_active ? RENDER_H : pr.h;
        if (id == still_last && iout.base_valid && iout.ow == want_w && iout.oh == want_h && (!crt_active || crt_have_last)) {
            Sleep(1);
            return 0;
        }
        still_last = id;
        still_tau = (double)id;
    }
    iout.still = still;
    iout.blend = 1;                                             /* the pictures between two game frames are mixtures of them where they differ (C-154) */
    if (still) {
        /* no clock: see above */
    } else if (target == MENU_FPS_UNCAPPED) {
        /* as many pictures as there are: one whenever the picture is not the one before */
    } else if ((crt_active || plain_gl) && (swap_ema_ms < 0.0 || swap_ema_ms > 300.0 / (double)target) && target >= 55 && menu.monitor_hz >= target && ((menu.monitor_hz + target / 2) / target) * target >= menu.monitor_hz - 1 && ((menu.monitor_hz + target / 2) / target) * target <= menu.monitor_hz + 1) {
        /* with a CRT shader the OpenGL swap waits for every n-th refresh of the monitor and so is the clock itself: the picture is drawn, the swap returns when it is on its way to the screen (not for the rates below 55: a swap that long would keep the game and the sound waiting) */
        crt_want_interval = (menu.monitor_hz + target / 2) / target;
        grid_next = menu.monitor_hz;
    } else if (dwm_flush != NULL && target >= 30 && menu.monitor_hz >= target && ((menu.monitor_hz + target / 2) / target) * target >= menu.monitor_hz - 1 && ((menu.monitor_hz + target / 2) / target) * target <= menu.monitor_hz + 1) {
        /* the monitor's refresh is the tick when the rate fits it (180 on 180 Hz, 60 or 90 on 180 Hz, 60 on 59.94): every n-th refresh, so that no picture is shown a refresh too long or too short */
        static uint64_t last_flush;
        static int flushed;
        int every = (menu.monitor_hz + target / 2) / target;
        grid_next = menu.monitor_hz;
        (void)dwm_flush();                                      /* one refresh a call, so that the game and the sound are looked after between the refreshes of a slow rate */
        now = pm_time_ns();
        if (now - last_flush < (uint64_t)(0.4e9 / (double)menu.monitor_hz)) {   /* DwmFlush came back at once (the window is minimised or covered): do not spin */
            Sleep(2);
            now = pm_time_ns();
        }
        last_flush = now;
        if (++flushed < every) {
            return 0;
        }
        flushed = 0;
    } else {
        uint64_t period = (uint64_t)(1e9 / (double)target);
        if (next_tick_ns == 0) {
            next_tick_ns = now;
        }
        if (now < next_tick_ns) {
            if (next_tick_ns - now > 1500000u) {
                Sleep(1);
            } else {
                YieldProcessor();
            }
            return 0;
        }
        next_tick_ns += period;
        if (now > next_tick_ns + 3 * period) {                  /* far behind (the window was dragged): start again from now */
            next_tick_ns = now + period;
        }
    }
    if (!((crt_active || plain_gl) && crt_want_interval > 0 && target >= 55 && menu.monitor_hz >= target)) {
        crt_want_interval = 0;                                  /* a rate the monitor's refresh does not fit (or no shader): the swap does not wait */
    }
    tau_grid_hz = grid_next;
    tau = still ? still_tau : game_time(now, t_start_ns);
    if (tau < 0.0) {
        tau = 0.0;
    }
    {
        unsigned long newest = frames_run > 0 ? frames_run - 1u : 0u;
        const InterpFrame *nf;

        if (tau > (double)newest) {                              /* the game is not that far yet */
            tau = (double)newest;
        }
        A = (long)floor(tau);
        if (ring_get((unsigned long)A) == NULL) {                /* the frame is not there (just after the FPS was changed): the newest there is */
            if (ring_get(newest) == NULL) {
                Sleep(1);
                return 0;
            }
            tau = (double)newest;
        }
        GetClientRect(hwnd, &rc);
        layout(rc.right, rc.bottom, &pr);
        if (pr.w < 1 || pr.h < 1 || interp_out_size(&iout, crt_active ? RENDER_W * CRT_SUB : pr.w, crt_active ? RENDER_H : pr.h) != 0) {          /* a CRT shader works on the picture as the Atari made it, 384 x 240: made 8 times as wide here, and averaged back */
            Sleep(1);
            return 0;
        }
        {
            uint64_t ir0 = pm_time_ns();
            interp_render(&iout, ring_get_ctx, NULL, tau, newest, &d);
            interp_ms = (double)(pm_time_ns() - ir0) / 1e6;
        }
        nf = ring_get((unsigned long)iout.base_id);
        shown_colour = nf != NULL ? nf->colour : NULL;
        if (trace_file != NULL && nf != NULL) {
            int k;
            pm_fs_printf(trace_file, "%.3f %.4f %lu %lu", (double)now / 1e6, tau, newest, (unsigned long)iout.base_id);
            for (k = 0; k < INTERP_OBJECTS; k++) {
                pm_fs_printf(trace_file, " %.3f %.3f %.3f %.3f", nf->obj[k].present ? (nf->obj[k].x0 + nf->obj[k].x1) / 2.0 + iout.last_offx[k] / 1024.0 : -1.0, nf->obj[k].present ? (nf->obj[k].y0 + nf->obj[k].y1) / 2.0 + iout.last_offy[k] / 1024.0 : -1.0, nf->obj[k].present ? (nf->obj[k].x0 + nf->obj[k].x1) / 2.0 : -1.0, nf->obj[k].present ? (nf->obj[k].y0 + nf->obj[k].y1) / 2.0 : -1.0);
            }
            {                                                   /* a hash of the picture around Pac-Man as it was composed (the stretches of unchanged picture the eye sees as pauses) */
                unsigned long hh = 2166136261u;
                int hx, hy, ccx = (nf->obj[4].x0 + nf->obj[4].x1) / 2, ccy = (nf->obj[4].y0 + nf->obj[4].y1) / 2;
                for (hy = ccy - 10; hy < ccy + 10; hy++) {
                    for (hx = ccx - 14; hx < ccx + 14; hx++) {
                        if (hx >= 0 && hx < RENDER_W && hy >= 0 && hy < RENDER_H) {
                            int wx = (int)(((long)hx * 2 + 1) * iout.ow / (2L * RENDER_W)), wy = (int)(((long)hy * 2 + 1) * iout.oh / (2L * RENDER_H));
                            hh = (hh ^ iout.work[(size_t)wy * (size_t)iout.ow + (size_t)wx]) * 16777619u;
                        }
                    }
                }
                pm_fs_printf(trace_file, " %lu", hh & 0xFFFFFFFFu);
            }
            pm_fs_printf(trace_file, " %.3f %.3f %.3f\n", interp_ms, crt_ms_render, crt_ms_swap);
        }
    }
    iout_have = 1;
    changed = d.full || d.n > 0;
    tick_count++;
    if (crt_active) {
        if (changed || target != MENU_FPS_UNCAPPED) {
            if (changed || !crt_have_last) {
                interp_box_x(iout.work, RENDER_W * CRT_SUB, RENDER_H, CRT_SUB, crt_last);
            }
            crt_have_last = 1;
            crt_render_last();
            blit_count += changed ? 1u : 0u;
        } else {
            tick_count--;
            Sleep(1);
        }
    } else if (changed) {
        present_interp(&d);
        blit_count++;
    } else if (target == MENU_FPS_UNCAPPED) {
        tick_count--;
        Sleep(1);                                               /* nothing new to show: do not spin */
    }
    return 1;
}

static void make_bgra(void)
{
    size_t i;

    render_to_rgb(shown_colour != NULL ? shown_colour : colour, rgb);
    for (i = 0; i < (size_t)RENDER_W * RENDER_H; i++) {
        bgra[4 * i] = rgb[3 * i + 2];
        bgra[4 * i + 1] = rgb[3 * i + 1];
        bgra[4 * i + 2] = rgb[3 * i];
        bgra[4 * i + 3] = 0;
    }
    if (crt_active) {                                                  /* the CRT shader takes this picture (the menu is drawn over it first, so it goes through the shader too) */
        memcpy(crt_last, bgra, sizeof crt_last);
        crt_have_last = 1;
    }
}


/* the menu is drawn into the 384 x 240 picture itself (so it scales with the picture): the frame darkened, a panel, the text in the OS font (the glyphs of the renderer's character set at $E000; the menu's
 * text is upper case: the OS font has screen codes 0-63 for the ASCII $20-$5F) */
static void put_px(int x, int y, unsigned r, unsigned g, unsigned b)
{
    if (x >= 0 && x < RENDER_W && y >= 0 && y < RENDER_H) {
        uint8_t *p = bgra + 4 * ((size_t)y * RENDER_W + (size_t)x);
        p[0] = (uint8_t)b;
        p[1] = (uint8_t)g;
        p[2] = (uint8_t)r;
    }
}

static void put_text(int x, int y, const char *t, unsigned r, unsigned g, unsigned b)
{
    for (; *t != '\0'; t++, x += 8) {
        unsigned c = (unsigned char)*t;
        int row, bit;

        if (c < 0x20u || c > 0x5Fu) {
            continue;
        }
        for (row = 0; row < 8; row++) {
            uint8_t bits = ram_image[0xE000 + (c - 0x20u) * 8u + (unsigned)row];
            for (bit = 0; bit < 8; bit++) {
                if ((bits >> (7 - bit)) & 1) {
                    put_px(x + bit, y + row, r, g, b);
                }
            }
        }
    }
}

static void draw_menu(void)
{
    MenuLine l[MENU_MAX_LINES];
    int n = menu_lines(&menu, l), i, widest = 0, bx, by, bw, bh;
    size_t k;

    if (n == 0) {
        return;
    }
    for (k = 0; k < (size_t)RENDER_W * RENDER_H; k++) {
        bgra[4 * k] = (uint8_t)(bgra[4 * k] >> 2);
        bgra[4 * k + 1] = (uint8_t)(bgra[4 * k + 1] >> 2);
        bgra[4 * k + 2] = (uint8_t)(bgra[4 * k + 2] >> 2);
    }
    for (i = 0; i < n; i++) {
        int len = (int)strlen(l[i].text);
        if (len > widest) {
            widest = len;
        }
    }
    bw = widest * 8 + 40;
    bh = n * 14 + 20;
    bx = (RENDER_W - bw) / 2;
    by = (RENDER_H - bh) / 2;
    for (i = by; i < by + bh; i++) {
        int j;
        for (j = bx; j < bx + bw; j++) {
            int edge = i == by || i == by + bh - 1 || j == bx || j == bx + bw - 1;
            if (edge) {
                put_px(j, i, 230, 230, 230);
            } else {
                put_px(j, i, 0, 0, 0);
            }
        }
    }
    for (i = 0; i < n; i++) {
        int len = (int)strlen(l[i].text), tx = bx + (bw - len * 8) / 2, ty = by + 10 + i * 14;

        if (l[i].heading) {
            put_text(tx, ty, l[i].text, 255, 210, 60);
        } else if (l[i].selected) {
            put_text(tx, ty, l[i].text, 255, 255, 255);
            put_text(bx + 8, ty, ">", 255, 210, 60);
        } else if (l[i].item) {
            put_text(tx, ty, l[i].text, 150, 150, 150);
        } else {
            put_text(tx, ty, l[i].text, 110, 110, 110);
        }
    }
}

/* the picture behind the menu (or the game's own) drawn to the window */
static void show_frame(void)
{
    make_bgra();
    if (menu_is_open(&menu)) {
        draw_menu();
    }
    if (crt_active) {
        memcpy(crt_last, bgra, sizeof crt_last);
        crt_have_last = 1;
    }
    present();
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

/* ---------------------------------------------------------------- the menu test: real key messages, then what the window really shows */

enum { OP_KEY, OP_SYSKEY, OP_WAIT, OP_FRAMES, OP_CHECK };
enum { CK_SNAPSHOT, CK_FROZEN, CK_SCREEN, CK_CURSOR, CK_RUNNING, CK_MODE, CK_PICTURE, CK_QUIT, CK_FPS_BEGIN, CK_FPS_END, CK_STARTUP, CK_CRT_REQ, CK_CRT, CK_CRT_SET, CK_DUMP };

typedef struct Op {
    int kind, a, b;
} Op;

static Op mt_ops[1200];
static int mt_n, mt_i;
static DWORD mt_until;
static PmFile *mt_log;
static int mt_pass, mt_fail;
static unsigned long mt_f0;
static uint64_t mt_h0;
static unsigned long mt_ticks0, mt_blits0, mt_frames0;     /* the counters at the start of an FPS measurement */
static uint64_t mt_t0;
static double mt_cpu0;                                   /* the CPU time of the process (s) at the start of an FPS measurement */

static double process_cpu_seconds(void)
{
    FILETIME c, e, k, u;

    if (!GetProcessTimes(GetCurrentProcess(), &c, &e, &k, &u)) {
        return 0.0;
    }
    return ((double)(((unsigned long long)k.dwHighDateTime << 32) | k.dwLowDateTime) + (double)(((unsigned long long)u.dwHighDateTime << 32) | u.dwLowDateTime)) / 1e7;
}

static void mt_add(int kind, int a, int b)
{
    if (mt_n < (int)(sizeof mt_ops / sizeof mt_ops[0])) {
        mt_ops[mt_n].kind = kind;
        mt_ops[mt_n].a = a;
        mt_ops[mt_n].b = b;
        mt_n++;
    }
}

static void mt_key(int vk)
{
    mt_add(OP_KEY, vk, 0);
    mt_add(OP_WAIT, 80, 0);
}

static void mt_result(int ok, const char *what, const char *fmt, ...)
{
    char buf[500];
    va_list ap;

    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (ok) {
        mt_pass++;
    } else {
        mt_fail++;
    }
    if (mt_log != NULL) {
        pm_fs_printf(mt_log, "%s  %s: %s\n", ok ? "PASS" : "FAIL", what, buf);
    }
}

static void mt_build(void)
{
    int pass, i;

    if (opt.offtest) {                                  /* in borderless fullscreen, as the player has it: a shader on, then off: the window shows the plain picture again */
        mt_add(OP_FRAMES, 300, 0);
        mt_add(OP_CHECK, CK_CRT_SET, 2);
        mt_add(OP_WAIT, 1500, 0);
        mt_key(VK_ESCAPE); mt_key(VK_DOWN); mt_key(VK_RETURN);
        mt_key(VK_DOWN); mt_key(VK_DOWN); mt_key(VK_DOWN);
        mt_add(OP_WAIT, 600, 0);
        mt_add(OP_CHECK, CK_DUMP, 2);
        mt_key(VK_RIGHT); mt_add(OP_WAIT, 600, 0); mt_add(OP_CHECK, CK_DUMP, 3);
        mt_key(VK_RIGHT); mt_add(OP_WAIT, 600, 0); mt_add(OP_CHECK, CK_DUMP, 0);     /* the last shader, then round to Off */
        mt_key(VK_RIGHT); mt_add(OP_WAIT, 600, 0); mt_add(OP_CHECK, CK_DUMP, 1);
        mt_key(VK_LEFT); mt_add(OP_WAIT, 600, 0); mt_add(OP_CHECK, CK_DUMP, 0);      /* and back to Off with Left */
        mt_key(VK_LEFT); mt_add(OP_WAIT, 600, 0); mt_add(OP_CHECK, CK_DUMP, 3);
        mt_key(VK_RIGHT); mt_add(OP_WAIT, 600, 0); mt_add(OP_CHECK, CK_DUMP, 0);
        mt_key(VK_ESCAPE); mt_key(VK_ESCAPE);
        mt_add(OP_WAIT, 500, 0);
        mt_add(OP_CHECK, CK_CRT_REQ, 0);
        mt_add(OP_WAIT, 300, 0);
        mt_add(OP_CHECK, CK_CRT, 0);
        mt_add(OP_CHECK, CK_CRT_SET, 0);
        mt_add(OP_WAIT, 1500, 0);
        mt_add(OP_CHECK, CK_CRT, 0);
        mt_add(OP_CHECK, CK_CRT_SET, 1);
        mt_add(OP_WAIT, 1500, 0);
        mt_add(OP_CHECK, CK_CRT_REQ, 0);
        mt_add(OP_WAIT, 300, 0);
        mt_add(OP_CHECK, CK_CRT, 1);
        mt_add(OP_CHECK, CK_CRT_SET, 0);
        mt_add(OP_WAIT, 1500, 0);
        mt_add(OP_CHECK, CK_CRT, 0);
        mt_add(OP_CHECK, CK_QUIT, 1);
        return;
    }
    if (opt.startuptest) {                              /* the game as the player starts it: nothing set */
        mt_add(OP_WAIT, 1500, 0);
        mt_add(OP_CHECK, CK_STARTUP, 0);
        mt_add(OP_CHECK, CK_QUIT, 1);
        return;
    }

    mt_add(OP_FRAMES, 640, 0);                         /* the game is running (START at 150, then the stick) */
    mt_add(OP_KEY, VK_F1, 0);                          /* F1 in the game: the help, a pause */
    mt_add(OP_WAIT, 100, 0);
    mt_add(OP_CHECK, CK_SNAPSHOT, 0);
    mt_add(OP_WAIT, 500, 0);
    mt_add(OP_CHECK, CK_FROZEN, 0);
    mt_add(OP_CHECK, CK_SCREEN, MENU_HELP);
    mt_key(VK_UP);                                     /* a game key does nothing in the help */
    mt_add(OP_CHECK, CK_SCREEN, MENU_HELP);
    mt_key(VK_F1);                                     /* F1 again: back to the game */
    mt_add(OP_CHECK, CK_SCREEN, MENU_CLOSED);
    mt_add(OP_WAIT, 400, 0);
    mt_add(OP_CHECK, CK_RUNNING, 0);
    mt_add(OP_KEY, VK_ESCAPE, 0);                      /* ESC opens the menu */
    mt_add(OP_WAIT, 100, 0);
    mt_add(OP_CHECK, CK_SNAPSHOT, 0);
    mt_add(OP_WAIT, 700, 0);
    mt_add(OP_CHECK, CK_FROZEN, 0);                    /* 700 ms of the menu: not one frame, not one bit of the game's state */
    mt_add(OP_CHECK, CK_SCREEN, MENU_MAIN);
    mt_add(OP_CHECK, CK_CURSOR, 0);
    mt_key(VK_F1);                                     /* F1 in the pause menu: the help; ESC closes it and the menu is as it was */
    mt_add(OP_CHECK, CK_SCREEN, MENU_HELP);
    mt_key(VK_ESCAPE);
    mt_add(OP_CHECK, CK_SCREEN, MENU_MAIN);
    mt_add(OP_CHECK, CK_CURSOR, 0);
    mt_key(VK_ESCAPE);                                 /* ESC in the main menu resumes */
    mt_add(OP_CHECK, CK_SCREEN, MENU_CLOSED);
    mt_add(OP_WAIT, 500, 0);
    mt_add(OP_CHECK, CK_RUNNING, 0);
    mt_key(VK_ESCAPE);                                 /* and again: the main menu's items */
    mt_add(OP_WAIT, 100, 0);
    mt_add(OP_CHECK, CK_SNAPSHOT, 0);
    mt_key(VK_UP);
    mt_add(OP_CHECK, CK_CURSOR, 2);
    mt_key(VK_DOWN);
    mt_add(OP_CHECK, CK_CURSOR, 0);
    mt_key(VK_DOWN);
    mt_add(OP_CHECK, CK_CURSOR, 1);
    mt_key(VK_RETURN);                                 /* Graphics Options */
    mt_add(OP_CHECK, CK_SCREEN, MENU_GRAPHICS);
    mt_key(VK_ESCAPE);                                 /* ESC: back to the main menu, on Graphics Options */
    mt_add(OP_CHECK, CK_SCREEN, MENU_MAIN);
    mt_add(OP_CHECK, CK_CURSOR, 1);
    mt_key(VK_RETURN);
    mt_add(OP_CHECK, CK_SCREEN, MENU_GRAPHICS);
    mt_add(OP_CHECK, CK_MODE, 0);
    mt_add(OP_WAIT, 200, 0);
    mt_add(OP_CHECK, CK_PICTURE, 0);                   /* the window as it starts */
    for (pass = 0; pass < 2; pass++) {
        if (pass == 1) {
            mt_key(VK_RIGHT);                          /* Display Mode: Borderless Fullscreen, at once */
            mt_add(OP_WAIT, 300, 0);
            mt_add(OP_CHECK, CK_MODE, 1);
            mt_add(OP_CHECK, CK_PICTURE, 0);
        }
        mt_key(VK_DOWN);
        for (i = 0; i < menu_resolution_count; i++) {  /* every resolution of the list, in this display mode */
            mt_key(VK_RIGHT);
            mt_add(OP_WAIT, 220, 0);
            mt_add(OP_CHECK, CK_PICTURE, 0);
        }
        mt_key(VK_UP);
    }
    mt_add(OP_KEY, VK_F11, 0);                         /* F11 and Alt+Enter, from fullscreen and back */
    mt_add(OP_WAIT, 350, 0);
    mt_add(OP_CHECK, CK_MODE, 0);
    mt_add(OP_CHECK, CK_PICTURE, 0);
    mt_add(OP_SYSKEY, VK_RETURN, 0);
    mt_add(OP_WAIT, 350, 0);
    mt_add(OP_CHECK, CK_MODE, 1);
    mt_add(OP_CHECK, CK_PICTURE, 0);
    mt_add(OP_KEY, VK_F11, 0);
    mt_add(OP_WAIT, 350, 0);
    mt_add(OP_CHECK, CK_MODE, 0);
    mt_add(OP_CHECK, CK_PICTURE, 0);
    mt_add(OP_CHECK, CK_FROZEN, 0);                    /* all of that with the game frozen */
    mt_key(VK_DOWN);                                   /* the FPS: every choice in turn, each measured for two seconds in the running game */
    mt_key(VK_DOWN);
    mt_add(OP_CHECK, CK_CURSOR, 2);
    for (i = 1; i <= menu_fps_count; i++) {
        mt_key(VK_RIGHT);
        mt_add(OP_CHECK, CK_FPS_BEGIN, 0);             /* (the counters are read again after the settling time) */
        mt_key(VK_ESCAPE);
        mt_key(VK_ESCAPE);                             /* the game runs again */
        mt_add(OP_WAIT, 500, 0);
        mt_add(OP_CHECK, CK_FPS_BEGIN, 1);
        mt_add(OP_WAIT, 2000, 0);
        mt_add(OP_CHECK, CK_FPS_END, i % menu_fps_count);
        mt_key(VK_ESCAPE);                             /* back to the FPS item of the graphics options */
        mt_key(VK_DOWN);
        mt_key(VK_RETURN);
        mt_key(VK_DOWN);
        mt_key(VK_DOWN);
    }
    mt_key(VK_UP);
    mt_key(VK_UP);
    mt_add(OP_CHECK, CK_CURSOR, 0);
    mt_key(VK_DOWN);                                   /* the CRT shader: each of the three, in the running game, its picture read back from the OpenGL window */
    mt_key(VK_DOWN);
    mt_key(VK_DOWN);
    mt_add(OP_CHECK, CK_CURSOR, 3);
    for (i = 1; i <= 4; i++) {
        mt_key(VK_RIGHT);                              /* 1, 2, 3, then 0 again: off */
        mt_add(OP_WAIT, 4000, 0);                      /* the passes are compiled when it is chosen */
        mt_key(VK_ESCAPE);
        mt_key(VK_ESCAPE);
        mt_add(OP_WAIT, 900, 0);
        mt_add(OP_CHECK, CK_CRT_REQ, 0);
        mt_add(OP_WAIT, 300, 0);
        mt_add(OP_CHECK, CK_CRT, i % 4);
        mt_key(VK_ESCAPE);
        mt_key(VK_DOWN);
        mt_key(VK_RETURN);
        mt_key(VK_DOWN);
        mt_key(VK_DOWN);
        mt_key(VK_DOWN);
    }
    mt_key(VK_UP);
    mt_key(VK_UP);
    mt_key(VK_UP);
    mt_add(OP_CHECK, CK_CURSOR, 0);
    mt_key(VK_ESCAPE);
    mt_add(OP_CHECK, CK_SCREEN, MENU_MAIN);
    mt_key(VK_UP);
    mt_add(OP_CHECK, CK_CURSOR, 0);
    mt_key(VK_RETURN);                                 /* Resume Game */
    mt_add(OP_CHECK, CK_SCREEN, MENU_CLOSED);
    mt_add(OP_WAIT, 600, 0);
    mt_add(OP_CHECK, CK_RUNNING, 0);
    mt_key(VK_ESCAPE);                                 /* Quit Game */
    mt_key(VK_UP);
    mt_add(OP_CHECK, CK_CURSOR, 2);
    mt_key(VK_RETURN);
    mt_add(OP_CHECK, CK_QUIT, 0);
}

static void check_mode(int want)
{
    MONITORINFO mi;
    RECT wr, cr;
    LONG style = GetWindowLong(hwnd, GWL_STYLE);

    mi.cbSize = sizeof mi;
    GetMonitorInfo(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &mi);
    GetWindowRect(hwnd, &wr);
    GetClientRect(hwnd, &cr);
    if (want) {
        int ok = menu.fullscreen == 1 && fullscreen == 1 && !(style & WS_CAPTION) && wr.left == mi.rcMonitor.left && wr.top == mi.rcMonitor.top && wr.right == mi.rcMonitor.right &&
                 wr.bottom == mi.rcMonitor.bottom && cr.right == mi.rcMonitor.right - mi.rcMonitor.left && cr.bottom == mi.rcMonitor.bottom - mi.rcMonitor.top;
        mt_result(ok, "mode borderless fullscreen", "window %ldx%ld at %ld,%ld, monitor %ldx%ld, no frame: %s", wr.right - wr.left, wr.bottom - wr.top, wr.left, wr.top,
                  mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top, (style & WS_CAPTION) ? "frame present" : "yes");
    } else {
        int ok = menu.fullscreen == 0 && fullscreen == 0 && (style & WS_CAPTION) == WS_CAPTION && wr.left >= mi.rcWork.left && wr.top >= mi.rcWork.top && wr.right <= mi.rcWork.right &&
                 wr.bottom <= mi.rcWork.bottom;
        mt_result(ok, "mode windowed", "window %ldx%ld at %ld,%ld, client %ldx%ld, frame: %s", wr.right - wr.left, wr.bottom - wr.top, wr.left, wr.top, cr.right, cr.bottom,
                  (style & WS_CAPTION) == WS_CAPTION ? "yes" : "no");
    }
}

/* what the window shows, copied back out of the screen, against what the layout says it should show */
static int capture_client(uint8_t **out, int *cw, int *ch);

static void check_picture(void)
{
    MONITORINFO mi;
    RECT cr, fr;
    DisplayRect r;
    uint8_t *got;
    int cw, ch, rw, rh, ex_w, ex_h, x, y, ok, size_ok;
    long outside = 0, exact_bad = 0, nn_bad = 0, inside = 0;
    char what[64];
    LONG style = GetWindowLong(hwnd, GWL_STYLE);

    mi.cbSize = sizeof mi;
    GetMonitorInfo(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &mi);
    GetClientRect(hwnd, &cr);
    cw = cr.right;
    ch = cr.bottom;
    menu_size(&menu, &rw, &rh);
    if (menu.fullscreen) {                                    /* the client area is the monitor, the picture may use the selected resolution (at most the monitor) */
        ex_w = mi.rcMonitor.right - mi.rcMonitor.left;
        ex_h = mi.rcMonitor.bottom - mi.rcMonitor.top;
    } else {                                                  /* the client area is the selected resolution, or what the work area has room for */
        SetRect(&fr, 0, 0, rw, rh);
        AdjustWindowRect(&fr, (DWORD)style, FALSE);
        ex_w = rw;
        ex_h = rh;
        if (ex_w + (fr.right - fr.left - rw) > mi.rcWork.right - mi.rcWork.left) {
            ex_w = mi.rcWork.right - mi.rcWork.left - (fr.right - fr.left - rw);
        }
        if (ex_h + (fr.bottom - fr.top - rh) > mi.rcWork.bottom - mi.rcWork.top) {
            ex_h = mi.rcWork.bottom - mi.rcWork.top - (fr.bottom - fr.top - rh);
        }
    }
    size_ok = cw == ex_w && ch == ex_h;
    layout(cw, ch, &r);
    snprintf(what, sizeof what, "%s %dx%d%s", menu.fullscreen ? "fullscreen" : "windowed", rw, rh, menu.res >= 0 ? "" : " (window)");
    {                                                           /* what the window shows as Windows composes it (the OpenGL window is the one that shows the picture) */
        int gw = 0, gh = 0;
        got = NULL;
        if (capture_client(&got, &gw, &gh) != 0 || gw != cw || gh != ch) {
            free(got);
            mt_result(0, what, "the window's pixels could not be read");
            return;
        }
    }
    for (y = 0; y < ch; y++) {
        for (x = 0; x < cw; x++) {
            const uint8_t *g = got + 4 * ((size_t)y * (size_t)cw + (size_t)x);
            if (x >= cw - 420 && y < 280) {
                inside += (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) ? 1 : 0;
                continue;                                      /* (the graphics driver's own notice in the top right corner is not the program's) */
            }
            if (x < r.x || x >= r.x + r.w || y < r.y || y >= r.y + r.h) {
                if ((g[0] != 0 || g[1] != 0 || g[2] != 0)) {
                    outside++;
                }
            } else {
                int sx = (int)(((long)(2 * (x - r.x) + 1) * RENDER_W) / (2L * r.w)), sy = (int)(((long)(2 * (y - r.y) + 1) * RENDER_H) / (2L * r.h));
                const uint8_t *e = bgra + 4 * ((size_t)sy * RENDER_W + (size_t)sx);

                inside++;
                if (g[0] != e[0] || g[1] != e[1] || g[2] != e[2]) {
                    int dx, dy, hit = 0;
                    exact_bad++;
                    for (dy = -1; dy <= 1 && !hit; dy++) {          /* a nearest-pixel stretch may differ from the centre rule by one source pixel at an edge; a blend matches none */
                        for (dx = -1; dx <= 1 && !hit; dx++) {
                            int tx = sx + dx, ty = sy + dy;
                            if (tx >= 0 && tx < RENDER_W && ty >= 0 && ty < RENDER_H) {
                                const uint8_t *n = bgra + 4 * ((size_t)ty * RENDER_W + (size_t)tx);
                                hit = g[0] == n[0] && g[1] == n[1] && g[2] == n[2];
                            }
                        }
                    }
                    if (!hit) {
                        nn_bad++;
                    }
                }
            }
        }
    }
    free(got);
    {
        long aspect = (long)r.w * RENDER_H - (long)r.h * RENDER_W;
        int aspect_ok = aspect <= RENDER_W && aspect >= -RENDER_W;                     /* 1.6 : 1 to within a pixel */
        int centred = (2 * r.x + r.w - cw) >= -1 && (2 * r.x + r.w - cw) <= 1 && (2 * r.y + r.h - ch) >= -1 && (2 * r.y + r.h - ch) <= 1;
        int fits = r.w <= cw && r.h <= ch;
        ok = size_ok && aspect_ok && centred && fits && outside == 0 && nn_bad == 0 && (!r.integer || exact_bad == 0) && inside == (long)r.w * r.h;
        mt_result(ok, what, "client %dx%d (expected %dx%d), picture %dx%d at %d,%d, scale %s%ld.%02ld, aspect %s, centred %s, outside the picture %ld pixels not black, inside %ld of %ld differ from the centre rule, %ld blended",
                  cw, ch, ex_w, ex_h, r.w, r.h, r.x, r.y, r.integer ? "whole " : "fitted ", (long)r.w * 100 / RENDER_W / 100, (long)r.w * 100 / RENDER_W % 100, aspect_ok ? "1.6:1" : "WRONG",
                  centred ? "yes" : "NO", outside, exact_bad, inside, nn_bad);
    }
}

static void dump_bgra(const char *path)
{
    PmFile *pf = pm_fs_open(path, "wb");
    size_t i;

    if (pf != NULL) {
        pm_fs_printf(pf, "P6\n%d %d\n255\n", RENDER_W, RENDER_H);
        for (i = 0; i < (size_t)RENDER_W * RENDER_H; i++) {
            uint8_t px[3];
            px[0] = bgra[4 * i + 2];
            px[1] = bgra[4 * i + 1];
            px[2] = bgra[4 * i];
            pm_fs_write(pf, px, 3);
        }
        pm_fs_close(pf);
    }
}

/* what this program's own window shows, as Windows composes it (children included: the OpenGL window of a CRT shader too): BGRA, client area; malloc'd.  Only this window is asked for, nothing of the desktop */
static int capture_client(uint8_t **out, int *cw, int *ch)
{
    RECT rc;
    HDC dc, mem;
    HBITMAP bmp, old;
    BITMAPINFO bi;
    uint8_t *buf;

    GetClientRect(hwnd, &rc);
    *cw = rc.right;
    *ch = rc.bottom;
    if (rc.right < 1 || rc.bottom < 1) {
        return 1;
    }
    dc = GetDC(hwnd);
    mem = CreateCompatibleDC(dc);
    bmp = CreateCompatibleBitmap(dc, rc.right, rc.bottom);
    old = (HBITMAP)SelectObject(mem, bmp);
    PrintWindow(hwnd, mem, 3u);                                /* PW_CLIENTONLY | PW_RENDERFULLCONTENT */
    SelectObject(mem, old);
    buf = (uint8_t *)malloc((size_t)rc.right * (size_t)rc.bottom * 4u);
    if (buf == NULL) {
        DeleteObject(bmp);
        DeleteDC(mem);
        ReleaseDC(hwnd, dc);
        return 1;
    }
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = rc.right;
    bi.bmiHeader.biHeight = -rc.bottom;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    GetDIBits(mem, bmp, 0, (UINT)rc.bottom, buf, &bi, DIB_RGB_COLORS);
    DeleteObject(bmp);
    DeleteDC(mem);
    ReleaseDC(hwnd, dc);
    *out = buf;
    return 0;
}

static void mt_check(int id, int arg)
{
    switch (id) {
    case CK_SNAPSHOT:
        mt_f0 = frames_run;
        mt_h0 = shell_state_hash(&shell);
        mt_result(menu_is_open(&menu), "snapshot", "frames run %lu, state hash %016llx, menu %s", mt_f0, (unsigned long long)mt_h0, menu_is_open(&menu) ? "open" : "closed");
        break;
    case CK_FROZEN: {
        uint64_t h = shell_state_hash(&shell);
        mt_result(menu_is_open(&menu) && frames_run == mt_f0 && h == mt_h0, "game frozen", "frames run %lu (was %lu), state hash %016llx (was %016llx)", frames_run, mt_f0, (unsigned long long)h, (unsigned long long)mt_h0);
        break;
    }
    case CK_SCREEN:
        mt_result(menu.screen == arg, "menu screen", "screen %d, expected %d", menu.screen, arg);
        if (arg == MENU_MAIN || arg == MENU_GRAPHICS || arg == MENU_HELP) {   /* the picture of the menu, for the eye (the first time each screen is shown) */
            static int shot[4];
            if (!shot[arg]) {
                shot[arg] = 1;
                dump_bgra(arg == MENU_MAIN ? "logs/menu_main.ppm" : (arg == MENU_HELP ? "logs/menu_help.ppm" : "logs/menu_graphics.ppm"));
            }
        }
        break;
    case CK_CURSOR:
        mt_result(menu.cursor == arg, "menu cursor", "item %d, expected %d", menu.cursor, arg);
        break;
    case CK_RUNNING:
        mt_result(!menu_is_open(&menu) && frames_run > mt_f0 + 10 && shell_state_hash(&shell) != mt_h0, "game running again", "frames run %lu (was %lu)", frames_run, mt_f0);
        break;
    case CK_MODE:
        check_mode(arg);
        break;
    case CK_PICTURE:
        check_picture();
        break;
    case CK_FPS_BEGIN:
        if (arg == 1) {
            mt_ticks0 = tick_count;
            mt_blits0 = blit_count;
            mt_frames0 = frames_run;
            mt_t0 = pm_time_ns();
            mt_cpu0 = process_cpu_seconds();
        }
        break;
    case CK_FPS_END: {
        double dt = (double)(pm_time_ns() - mt_t0) / 1e9;
        double game = (double)(frames_run - mt_frames0) / dt;
        double ticks = (double)(tick_count - mt_ticks0) / dt;
        double blits = (double)(blit_count - mt_blits0) / dt;
        double cpu = (process_cpu_seconds() - mt_cpu0) / dt * 100.0;
        int v = menu_fps(&menu), idx = menu.fps, ok;
        char what[64];

        snprintf(what, sizeof what, "fps choice %d (%d)", idx, v);
        if (IsIconic(hwnd)) {                                                    /* a test needs its window on the screen: something minimised it (not this program): note it and bring it back */
            if (mt_log != NULL) {
                pm_fs_printf(mt_log, "NOTE  the window was minimised during choice %d (by something else); restored\n", idx);
            }
            ShowWindow(hwnd, SW_RESTORE);
        }
        ok = fabs(game - FRAME_HZ) / FRAME_HZ <= 0.02;                           /* the game runs at its own rate whatever is shown */
        if (v == MENU_FPS_NATIVE) {
            ok = ok && ticks >= 25.0 && !iout_have;
            mt_result(ok, what, "native: the game %.2f frames/s (the original runs at 59.92), %.1f pictures/s, no in-between pictures; CPU %.0f %% of one core", game, ticks, cpu);
        } else if (v == MENU_FPS_UNCAPPED) {
            ok = ok && blits >= 120.0 && iout_have;
            mt_result(ok, what, "uncapped: the game %.2f frames/s, %.1f different pictures/s; CPU %.0f %% of one core", game, blits, cpu);
        } else {
            ok = ok && fabs(ticks - (double)v) / (double)v <= 0.06 && iout_have;
            mt_result(ok, what, "%d: the game %.2f frames/s, %.1f pictures/s, %.1f of them different from the one before; CPU %.0f %% of one core", v, game, ticks, blits, cpu);
        }
        break;
    }
    case CK_CRT_REQ:
        crt_shot_req = 1;
        break;
    case CK_DUMP: {                                    /* the item as the player sees it: with the keys, the shader item steps through every choice and its line says which one */
        MenuLine ml[MENU_MAX_LINES];
        int ln, nl2, found = 0;
        nl2 = menu_lines(&menu, ml);
        for (ln = 0; ln < nl2; ln++) {
            if (ml[ln].item && strstr(ml[ln].text, menu_crt_names[arg]) != NULL && strstr(ml[ln].text, "CRT SHADER") != NULL) {
                found = 1;
            }
        }
        mt_result(menu.crt == arg && found && crt_active == (arg != 0), "crt item by keys", "choice %d (%s): the menu line says so, the shader is %s", arg, menu_crt_names[arg], crt_active ? "on" : "off");
        break;
    }
    case CK_CRT_SET:                                   /* chosen as the menu does it */
        menu.crt = arg;
        crt_apply();
        break;
    case CK_CRT: {
        char what[64];
        long x, y, lit = 0, n;
        double diff = 0.0;

        snprintf(what, sizeof what, "crt shader %d (%s)", arg, menu_crt_names[arg]);
        if (arg == 0) {                                                /* none: what the window really shows is the plain picture (the pictures of the FPS option, drawn by GDI), not a left-over of the shader */
            uint8_t *cap = NULL;
            int cw = 0, chh = 0, ok0;
            long same = 0, total = 0;
            ok0 = menu.crt == 0 && !crt_active && crt_chain == NULL;
            if (ok0 && iout.work != NULL && capture_client(&cap, &cw, &chh) == 0) {
                DisplayRect dr;
                layout(cw, chh, &dr);
                if (dr.w == iout.ow && dr.h == iout.oh) {
                    for (y = 0; y < dr.h; y += 5) {
                        for (x = 0; x < dr.w; x += 5) {
                            const uint8_t *g = cap + 4 * ((size_t)(dr.y + y) * (size_t)cw + (size_t)(dr.x + x));
                            const uint8_t *e = (const uint8_t *)(iout.work + (size_t)y * (size_t)iout.ow + (size_t)x);
                            total++;
                            same += g[0] == e[0] && g[1] == e[1] && g[2] == e[2];
                        }
                    }
                }
                free(cap);
            }
            mt_result(ok0 && total > 1000 && same * 100 >= total * 99, what, "none: no shader chain, and the window's own pixels (read back through Windows; the OpenGL window draws them, through the plain shader) are the plain picture: %ld of %ld sampled pixels equal", same, total);
            break;
        }
        if (crt_shot == NULL || crt_shot_w < 1 || !crt_active || crt_chain == NULL) {
            mt_result(0, what, "no picture from the chain (active %d, %s)", crt_active, crt_why[0] != '\0' ? crt_why : "no reason logged");
            break;
        }
        n = (long)crt_shot_w * crt_shot_h;
        for (y = 0; y < crt_shot_h; y++) {
            for (x = 0; x < crt_shot_w; x++) {
                const uint8_t *g = crt_shot + 4 * ((size_t)y * (size_t)crt_shot_w + (size_t)x);
                const uint8_t *pl = (const uint8_t *)crt_last + 4 * ((size_t)(y * RENDER_H / crt_shot_h) * RENDER_W + (size_t)(x * RENDER_W / crt_shot_w));   /* plain: the picture stretched by nearest pixel (BGRA) */
                lit += (g[0] + g[1] + g[2]) / 3 > 12;
                diff += (double)(abs(g[0] - pl[2]) + abs(g[1] - pl[1]) + abs(g[2] - pl[0])) / 3.0;
            }
        }
        diff /= (double)n;
        mt_result(menu.crt == arg && crt_errors == 0 && lit * 100 > n * 3/2 && diff > 2.0, what, "%dx%d picture from the chain (%d passes): %.1f %% of the pixels lit, %.1f of 255 different from the plain picture, %d failed pictures",
                  crt_shot_w, crt_shot_h, crt_chain_passes(crt_chain), 100.0 * (double)lit / (double)n, diff, crt_errors);
        break;
    }
    case CK_STARTUP: {
        int mw, mh, mhz;
        MONITORINFO mi;
        RECT wr;
        int want_res, want_fps;
        LONG style = GetWindowLong(hwnd, GWL_STYLE);

        mi.cbSize = sizeof mi;
        GetMonitorInfo(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &mi);
        GetWindowRect(hwnd, &wr);
        monitor_mode(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &mw, &mh, &mhz);
        want_res = menu_res_nearest(mw, mh);
        want_fps = menu_fps_nearest(mhz);
        mt_result(menu.fullscreen == 1 && fullscreen == 1 && !(style & WS_CAPTION) && wr.left == mi.rcMonitor.left && wr.top == mi.rcMonitor.top && wr.right == mi.rcMonitor.right && wr.bottom == mi.rcMonitor.bottom,
                  "starts in borderless fullscreen", "window %ldx%ld at %ld,%ld, monitor %dx%d, no frame: %s", wr.right - wr.left, wr.bottom - wr.top, wr.left, wr.top, mw, mh, (style & WS_CAPTION) ? "NO" : "yes");
        mt_result(menu.res == want_res && menu.res >= 0, "starts at the monitor's resolution", "monitor %dx%d; the list entry chosen is %dx%d (%s), the nearest is %dx%d", mw, mh, menu_resolutions[menu.res < 0 ? 0 : menu.res].w, menu_resolutions[menu.res < 0 ? 0 : menu.res].h,
                  menu.res >= 0 && menu_resolutions[menu.res].w == mw && menu_resolutions[menu.res].h == mh ? "exactly the monitor's" : "the nearest", menu_resolutions[want_res].w, menu_resolutions[want_res].h);
        mt_result(menu.fps == want_fps && menu_fps(&menu) == menu_fps_values[want_fps] && menu.monitor_hz == mhz, "starts at the monitor's refresh rate", "monitor %d Hz; the FPS chosen is %d (%s)", mhz, menu_fps(&menu),
                  menu_fps(&menu) == mhz ? "exactly the monitor's" : "the nearest");
        mt_result(frames_run > 30 && interp_wanted() == (menu_fps(&menu) != MENU_FPS_NATIVE), "the game is running", "%lu frames in 1.5 s", frames_run);
        break;
    }
    case CK_QUIT:
        if (arg == 1) {
            quit = 1;
            break;
        }
        mt_result(menu.quit == 1 && quit == 1, "quit game", "the menu set quit=%d, the program quit=%d", menu.quit, quit);
        break;
    default:
        break;
    }
}

static void menutest_step(void)
{
    DWORD now = GetTickCount();
    const Op *o;

    if (mt_i >= mt_n || (LONG)(now - mt_until) < 0) {
        return;
    }
    if (IsIconic(hwnd)) {                                        /* the window was minimised by something outside the program (it happens in long runs): the test needs it on the screen */
        if (mt_log != NULL) {
            pm_fs_printf(mt_log, "NOTE  the window was minimised before step %d (by something else); restored\n", mt_i);
        }
        ShowWindow(hwnd, SW_RESTORE);
        mt_until = now + 400u;
        return;
    }
    o = &mt_ops[mt_i++];
    switch (o->kind) {
    case OP_FRAMES:
        if (frames_run < (unsigned long)o->a) {
            mt_i--;
        }
        break;
    case OP_WAIT:
        mt_until = now + (DWORD)o->a;
        break;
    case OP_KEY:
        PostMessage(hwnd, WM_KEYDOWN, (WPARAM)o->a, (LPARAM)1);
        PostMessage(hwnd, WM_KEYUP, (WPARAM)o->a, (LPARAM)0xC0000001);
        break;
    case OP_SYSKEY:
        PostMessage(hwnd, WM_SYSKEYDOWN, (WPARAM)o->a, (LPARAM)0x20000001);
        PostMessage(hwnd, WM_SYSKEYUP, (WPARAM)o->a, (LPARAM)0xE0000001);
        break;
    default:
        mt_check(o->a, o->b);
        break;
    }
}

/* ---------------------------------------------------------------- the CRT shaders: a test that runs each preset on a frame of the game and writes the picture (logs/crt_*.ppm) */

static const char *const crt_presets[3][2] = {
    {"crt-guest-advanced-ntsc", "third-party/crt-shaders/crt/crt-guest-advanced-ntsc.slangp"},
    {"zfast-crt-composite", "third-party/crt-shaders/crt/zfast-crt-composite.slangp"},
    {"crt-aperture", "third-party/crt-shaders/crt/crt-aperture.slangp"},
};

static void crt_write_ppm(const char *path, const uint8_t *rgba, int w, int h)
{
    PmFile *pf = pm_fs_open(path, "wb");
    int i;

    if (pf != NULL) {
        pm_fs_printf(pf, "P6\n%d %d\n255\n", w, h);
        for (i = 0; i < w * h; i++) {
            pm_fs_write(pf, rgba + 4 * (size_t)i, 3);
        }
        pm_fs_close(pf);
    }
}

static void crt_test_run(void)
{
    char err[2000];
    RECT rc;
    DisplayRect pr;
    int k, f;
    uint8_t *img;
    PmFile *log = pm_fs_open("logs/crttest.txt", "wb");
    int pass = 0, fail = 0;

    GetClientRect(hwnd, &rc);
    layout(rc.right, rc.bottom, &pr);
    if (log == NULL) {
        return;
    }
    pm_fs_printf(log, "client %ldx%ld, picture %dx%d at %d,%d\n", rc.right, rc.bottom, pr.w, pr.h, pr.x, pr.y);
    if (crt_gl_open(hwnd, err, sizeof err) != 0) {
        pm_fs_printf(log, "FAIL  OpenGL: %s\n", err);
        pm_fs_close(log);
        return;
    }
    crt_gl_resize(rc.right, rc.bottom);
    pm_fs_printf(log, "PASS  OpenGL: %s\n", crt_gl_renderer());
    img = (uint8_t *)malloc((size_t)pr.w * (size_t)pr.h * 4u);
    make_bgra();
    for (k = 0; k < 3 && img != NULL; k++) {
        CrtChain *c;
        long lit = 0, i;
        double sum = 0.0;
        char path[80];
        uint64_t t_load = pm_time_ns();

        c = crt_chain_load(crt_presets[k][1], err, sizeof err);
        t_load = pm_time_ns() - t_load;
        if (c == NULL) {
            pm_fs_printf(log, "FAIL  %s: %s\n", crt_presets[k][0], err);
            fail++;
            continue;
        }
        err[0] = '\0';
        for (f = 0; f < 6; f++) {                                       /* a few pictures, so that the passes that look at the one before have something */
            if (crt_chain_render(c, (const uint32_t *)bgra, RENDER_W, RENDER_H, pr.x, pr.y, pr.w, pr.h, (unsigned)f, err, sizeof err) != 0) {
                break;
            }
        }
        if (err[0] != '\0') {
            pm_fs_printf(log, "FAIL  %s: render: %s\n", crt_presets[k][0], err);
            fail++;
            crt_chain_free(c);
            continue;
        }
        crt_gl_readback(img, pr.w, pr.h);
        for (i = 0; i < (long)pr.w * pr.h; i++) {
            double l = (img[4 * i] + img[4 * i + 1] + img[4 * i + 2]) / 3.0;
            sum += l;
            lit += l > 12.0;
        }
        snprintf(path, sizeof path, "logs/crt_%s.ppm", crt_presets[k][0]);
        crt_write_ppm(path, img, pr.w, pr.h);
        pm_fs_printf(log, "%s  %s: %d passes compiled in %.0f ms, picture %dx%d, mean brightness %.1f, %.1f %% of the pixels lit\n", (lit > (long)pr.w * pr.h / 20) ? "PASS" : "FAIL", crt_presets[k][0], crt_chain_passes(c), (double)t_load / 1e6, pr.w, pr.h, sum / ((double)pr.w * pr.h),
                     100.0 * (double)lit / ((double)pr.w * pr.h));
        if (lit > (long)pr.w * pr.h / 20) {
            pass++;
        } else {
            fail++;
        }
        crt_chain_free(c);
    }
    free(img);
    pm_fs_printf(log, "RESULT: %d passed, %d failed\n", pass, fail);
    pm_fs_close(log);
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

    opt.scale = 0;                                              /* 0: the 1280 x 720 window of the resolution list (the picture at 3 x) */
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--root") == 0 && i + 1 < argc) {
            opt.root = argv[++i];
        } else if (strcmp(argv[i], "--scale") == 0 && i + 1 < argc) {
            opt.scale = atoi(argv[++i]);
            if (opt.scale < 1 || opt.scale > 8) {
                opt.scale = 0;
            }
        } else if (strcmp(argv[i], "--fullscreen") == 0) {
            opt.fullscreen = 1;
        } else if (strcmp(argv[i], "--no-audio") == 0) {
            opt.no_audio = 1;
        } else if (strcmp(argv[i], "--trace") == 0 && i + 1 < argc) {
            opt.trace = argv[++i];
        } else if (strcmp(argv[i], "--windowed") == 0) {
            opt.windowed = 1;
        } else if (strcmp(argv[i], "--fps") == 0 && i + 1 < argc) {
            opt.fps = argv[++i];
        } else if (strcmp(argv[i], "--crt") == 0 && i + 1 < argc) {
            opt.crt = argv[++i];
        } else if (strcmp(argv[i], "--crttest") == 0) {
            opt.crttest = 1;
        } else if (strcmp(argv[i], "--offtest") == 0) {
            opt.offtest = 1;
            opt.menutest = 1;
        } else if (strcmp(argv[i], "--startuptest") == 0) {
            opt.startuptest = 1;
            opt.menutest = 1;
        } else if (strcmp(argv[i], "--menutest") == 0) {
            opt.menutest = 1;
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
    {
        int mw, mh, mhz;
        monitor_mode(MonitorFromPoint((POINT){0, 0}, MONITOR_DEFAULTTOPRIMARY), &mw, &mh, &mhz);
        if (opt.exact) {                                        /* the pixel comparison of the self test: the client area is the picture itself */
            menu_init(&menu, 0, -1, RENDER_W, RENDER_H);
        } else if (opt.scale > 0 && opt.windowed) {             /* a window size asked for on the command line (with --windowed) */
            menu_init(&menu, 0, -1, RENDER_W * opt.scale, RENDER_H * opt.scale);
        } else {
            menu_init(&menu, !opt.windowed, MENU_DEFAULT_RES, 0, 0);
            if (!opt.windowed && mw > 0) {                      /* the game starts in borderless fullscreen with the resolution of the list that is the monitor's, or the nearest to it */
                menu.res = menu_res_nearest(mw, mh);
            }
        }
        menu.monitor_hz = mhz;
        menu.fps = menu_fps_nearest(mhz);                       /* and the FPS that is its refresh rate, or the nearest number */
        if (opt.fps != NULL) {                                  /* a test or a wish on the command line */
            if (strcmp(opt.fps, "native") == 0) {
                menu.fps = 0;
            } else if (strcmp(opt.fps, "uncapped") == 0) {
                menu.fps = menu_fps_count - 1;
            } else if (atoi(opt.fps) > 0) {
                menu.fps = menu_fps_nearest(atoi(opt.fps));
            }
        }
    }
    if (opt.root == NULL) {
        /* Started by a double click, the current folder is the program's own.
         * Look for the main folder (the one holding original/Pac-Man.rom) in the
         * current folder, then in the program's folder and each folder above it. */
        static char found[MAX_PATH + 64];
        char dir[MAX_PATH];
        char probe[MAX_PATH + 64];
        int pass;

        for (pass = 0; pass < 2 && opt.root == NULL; pass++) {
            DWORD n = pass == 0 ? GetCurrentDirectoryA(MAX_PATH, dir) : GetModuleFileNameA(NULL, dir, MAX_PATH);
            if (n == 0 || n >= MAX_PATH) {
                continue;
            }
            for (;;) {
                char *cut;
                DWORD attr;

                snprintf(probe, sizeof probe, "%s\\original\\Pac-Man.rom", dir);
                attr = GetFileAttributesA(probe);
                if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
                    snprintf(found, sizeof found, "%s", dir);
                    opt.root = found;
                    break;
                }
                cut = strrchr(dir, '\\');
                if (cut == NULL || cut == dir) {
                    break;
                }
                *cut = '\0';
            }
        }
    }
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
    if (opt.selftest <= 0 && !opt.menutest) {
        (void)shell_highscore_load(&shell);
    }
    render_init(&renderer, ram_image);
    audio_init(&audio, AUDIO_RATE);
    audio_hq_init(&audio_hq, AUDIO_RATE);
    front_init(&front, 0);
    ring = (InterpFrame *)malloc((size_t)RING * sizeof(InterpFrame));
    (void)interp_out_init(&iout);
    {                                                           /* the timer resolution (Sleep) and the monitor's refresh (DwmFlush), loaded so that the program needs neither library to start */
        HMODULE m = LoadLibraryA("winmm.dll");
        if (m != NULL) {
            typedef UINT(WINAPI * TimeBeginFn)(UINT);
            TimeBeginFn tb = (TimeBeginFn)(void (*)(void))GetProcAddress(m, "timeBeginPeriod");
            if (tb != NULL) {
                (void)tb(1);
            }
        }
        m = LoadLibraryA("dwmapi.dll");
        if (m != NULL) {
            dwm_flush = (DwmFlushFn)(void (*)(void))GetProcAddress(m, "DwmFlush");
        }
    }
    xinput_load();
    if (opt.record != NULL || opt.selftest > 0 || opt.menutest) {
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
            if (opt.selftest > 0 || opt.menutest) {
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
    if (opt.menutest) {
        mt_log = pm_fs_open(opt.startuptest ? "logs/startuptest.txt" : (opt.offtest ? "logs/offtest.txt" : "logs/menutest.txt"), "wb");
        mt_build();
    }
    if (opt.crt != NULL && !opt.crttest) {
        menu.crt = strcmp(opt.crt, "guest") == 0 ? 1 : (strcmp(opt.crt, "zfast") == 0 ? 2 : (strcmp(opt.crt, "aperture") == 0 ? 3 : 0));
        if (menu.crt != 0) {
            crt_apply();
        }
    }
    if (opt.trace != NULL) {
        trace_file = pm_fs_open(opt.trace, "wb");
    }
    if (!opt.crttest) {                                         /* the three shaders are loaded and compiled now, before the game runs, so that choosing one in the menu does not stop the picture for a second */
        char werr[400];
        if (crt_gl_is_open() || crt_gl_open(hwnd, werr, sizeof werr) == 0) {
            int ci;
            uint64_t w0 = pm_time_ns();
            for (ci = 1; ci < 4; ci++) {
                if (crt_cache[ci] == NULL) {
                    RECT wrc;
                    DisplayRect wpr;
                    crt_cache[ci] = crt_chain_load(menu_crt_files[ci], werr, sizeof werr);
                    GetClientRect(hwnd, &wrc);
                    layout(wrc.right, wrc.bottom, &wpr);
                    crt_gl_resize(wrc.right, wrc.bottom);
                    if (crt_cache[ci] != NULL && wpr.w > 0 && wpr.h > 0) {      /* one picture through it: the driver compiles at the first use, and the sizes of its buffers are made */
                        (void)crt_chain_render(crt_cache[ci], crt_last, RENDER_W, RENDER_H, wpr.x, wpr.y, wpr.w, wpr.h, 0u, werr, sizeof werr);
                    }
                }
            }
            if (plain_chain == NULL) {
                plain_chain = crt_chain_load("src/shaders/plain.slangp", werr, sizeof werr);
            }
            plain_gl = plain_chain != NULL && !opt.exact;
            if (plain_chain == NULL) {
                (void)shell_log(werr);
            }
            crt_gl_show(plain_gl);                              /* shown from now on: the screen does not go black when a shader is chosen */
            { char ln[96]; snprintf(ln, sizeof ln, "CRT shaders loaded in %.0f ms", (double)(pm_time_ns() - w0) / 1e6); (void)shell_log(ln); }
        }
    }
    t_start = t_prev = pm_time_ns();
    while (!quit) {
        if (opt.crttest && frames_run >= 700u) {                  /* the CRT shaders on a frame of the game */
            crt_test_run();
            break;
        }
        unsigned n = 0;

        pump();
        wl_poll(wloop);
        if (opt.selftest > 0) {
            post_scenario(frames_run);
            pump();
        } else if (opt.crttest) {
            post_scenario(frames_run);                               /* START, then the stick: a frame of play */
            pump();
        } else if (opt.menutest) {
            post_scenario(frames_run < 639 ? frames_run : 639);     /* the game is played up to the frame the menu test opens the menu at */
            menutest_step();
            pump();
        }
        pad_menu_poll();
        if (menu_is_open(&menu)) {                              /* a pause: no frame of the game, no sound written; the picture behind the menu stays */
            if (menu_dirty) {
                show_frame();
                menu_dirty = 0;
            }
            Sleep(8);
            continue;
        }
        if (menu_dirty) {
            show_frame();
            menu_dirty = 0;
        }
        if (menu_resync) {                                      /* the timer clock goes on from the frame the game is at, not from the wall clock of before the menu */
            menu_resync = 0;
            t_start = pm_time_ns() - (uint64_t)((double)frames_run / FRAME_HZ * 1e9);
            if (interp_wanted()) {
                t_start += (uint64_t)(2.0 / FRAME_HZ * 1e9);          /* the pictures are of the time two frames before the frames made */
            }
        }
        if (wa != NULL) {                                       /* the sound device is the clock */
            int q = wa_queued(wa);
            while (q >= 0 && q < QUEUE_TARGET_FRAMES && n < MAX_CATCH_UP && !(opt.selftest > 0 && (long)frames_run >= opt.selftest)) {
                run_frame();
                n++;
                q = wa_queued(wa);
            }
        } else {                                                /* the system timer is */
            due_target = (unsigned long)((double)(pm_time_ns() - t_start) * FRAME_HZ / 1e9) + (interp_wanted() ? 2u : 0u);
            while (frames_run < due_target && n < MAX_CATCH_UP && !(opt.selftest > 0 && (long)frames_run >= opt.selftest)) {
                run_frame();
                n++;
            }
            if (frames_run + MAX_CATCH_UP < due_target) {       /* far behind (the window was dragged): do not race to catch up */
                t_start += (uint64_t)(((double)(due_target - frames_run) / FRAME_HZ) * 1e9);
            }
        }
        if (interp_wanted()) {
            (void)interp_step(t_start);
        } else if (n > 0) {
            make_bgra();
            shown_colour = NULL;
            iout_have = 0;
            present();
            tick_count++;
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
        const char *path = opt.record != NULL ? opt.record : (opt.startuptest ? "logs/startuptest.pmrp" : (opt.offtest ? "logs/offtest.pmrp" : (opt.menutest ? "logs/menutest.pmrp" : "logs/selftest.pmrp")));
        ReplayError e = replay_writer_finish(&writer, &size);
        if (e == REPLAY_OK) {
            (void)shell_make_folders();
            e = replay_save(path, record_buf, size);
        }
        if (e != REPLAY_OK) {
            ok = 0;
        }
    }
    if (opt.selftest <= 0 && !opt.menutest) {                   /* a test does not touch the player's high score */
        (void)shell_highscore_save(&shell);
    }
    if (opt.ppm != NULL) {
        write_ppm(opt.ppm);
    }
    while (opt.menutest && mt_i < mt_n && quit) {              /* the checks after the last key: Quit Game ended the loop before the script's last step ran */
        if (mt_ops[mt_i].kind == OP_CHECK) {
            mt_check(mt_ops[mt_i].a, mt_ops[mt_i].b);
        }
        mt_i++;
    }
    if (mt_log != NULL) {
        pm_fs_printf(mt_log, "frames run: %lu\n", frames_run);
        pm_fs_printf(mt_log, "final state hash: %016llx\n", (unsigned long long)last_hash);
        pm_fs_printf(mt_log, "run digest: %016llx\n", (unsigned long long)shell_digest(&shell));
        pm_fs_printf(mt_log, "video digest: %016llx\n", (unsigned long long)vdig);
        pm_fs_printf(mt_log, "audio digest: %016llx\n", (unsigned long long)adig);
        pm_fs_printf(mt_log, "script finished: %s (%d of %d steps)\n", mt_i >= mt_n ? "yes" : "NO", mt_i, mt_n);
        pm_fs_printf(mt_log, "RESULT: %d passed, %d failed\n", mt_pass, mt_fail);
        pm_fs_close(mt_log);
        if (mt_fail != 0 || mt_i < mt_n) {
            ok = 0;
        }
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
    if (trace_file != NULL) {
        pm_fs_close(trace_file);
    }
    {
        int ci;
        for (ci = 0; ci < 4; ci++) {
            if (crt_cache[ci] != NULL) {
                crt_chain_free(crt_cache[ci]);
                crt_cache[ci] = NULL;
            }
        }
        crt_chain = NULL;
        if (plain_chain != NULL) {
            crt_chain_free(plain_chain);
            plain_chain = NULL;
        }
    }
    crt_gl_close();
    free(crt_shot);
    wl_close(wloop);
    wa_close(wa);
    free(game_pcm);
    if (hwnd != NULL) {
        DestroyWindow(hwnd);
    }
    return ok ? 0 : 1;
}
