/* platform/win32/win_main.c - the Windows 11 front end of the port: a window, the keyboard and XInput pads, the sound device (stage J, docs/67).
 *   pacman_a8_play [--root DIR] [--scale N] [--fullscreen] [--no-audio] [--seed N] [--record FILE] [--ppm FILE] [--selftest FRAMES] [--menutest] [--exact]
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
#include "../../render/render.h"
#include "../../shell/frontend.h"
#include "../../shell/menu.h"
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
    int scale, fullscreen, no_audio, exact, menutest;
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
static int fullscreen;                   /* the display mode as applied to the window: 1 borderless fullscreen */
static Menu menu;                        /* the pause menu and the display settings (shell/menu.c) */
static int menu_dirty;                   /* the menu or the picture behind it must be drawn again */
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
        apply_display();
    }
    if (was_open != menu_is_open(&menu)) {
        pause_edge = 0;
        if (was_open) {
            menu_resync = 1;
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
enum { CK_SNAPSHOT, CK_FROZEN, CK_SCREEN, CK_CURSOR, CK_RUNNING, CK_MODE, CK_PICTURE, CK_QUIT };

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
static void check_picture(void)
{
    MONITORINFO mi;
    RECT cr, fr;
    DisplayRect r;
    HDC dc, mem;
    HBITMAP bmp, old;
    BITMAPINFO bi;
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
    dc = GetDC(hwnd);
    mem = CreateCompatibleDC(dc);
    bmp = CreateCompatibleBitmap(dc, cw, ch);
    old = (HBITMAP)SelectObject(mem, bmp);
    BitBlt(mem, 0, 0, cw, ch, dc, 0, 0, SRCCOPY);
    SelectObject(mem, old);
    got = (uint8_t *)malloc((size_t)cw * (size_t)ch * 4u);
    if (got == NULL) {
        DeleteObject(bmp);
        DeleteDC(mem);
        ReleaseDC(hwnd, dc);
        mt_result(0, what, "out of memory");
        return;
    }
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = cw;
    bi.bmiHeader.biHeight = -ch;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    GetDIBits(mem, bmp, 0, (UINT)ch, got, &bi, DIB_RGB_COLORS);
    DeleteObject(bmp);
    DeleteDC(mem);
    ReleaseDC(hwnd, dc);
    for (y = 0; y < ch; y++) {
        for (x = 0; x < cw; x++) {
            const uint8_t *g = got + 4 * ((size_t)y * (size_t)cw + (size_t)x);
            if (x < r.x || x >= r.x + r.w || y < r.y || y >= r.y + r.h) {
                if (g[0] != 0 || g[1] != 0 || g[2] != 0) {
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
    case CK_QUIT:
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
    if (opt.exact) {                                            /* the pixel comparison of the self test: the client area is the picture itself */
        menu_init(&menu, 0, -1, RENDER_W, RENDER_H);
    } else if (opt.scale > 0) {
        menu_init(&menu, opt.fullscreen, -1, RENDER_W * opt.scale, RENDER_H * opt.scale);
    } else {
        menu_init(&menu, opt.fullscreen, MENU_DEFAULT_RES, 0, 0);
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
    front_init(&front, 0);
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
        mt_log = pm_fs_open("logs/menutest.txt", "wb");
        mt_build();
    }
    t_start = t_prev = pm_time_ns();
    while (!quit) {
        unsigned n = 0;

        pump();
        wl_poll(wloop);
        if (opt.selftest > 0) {
            post_scenario(frames_run);
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
        const char *path = opt.record != NULL ? opt.record : (opt.menutest ? "logs/menutest.pmrp" : "logs/selftest.pmrp");
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
    wl_close(wloop);
    wa_close(wa);
    free(game_pcm);
    if (hwnd != NULL) {
        DestroyWindow(hwnd);
    }
    return ok ? 0 : 1;
}
