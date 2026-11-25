/* platform/win32/win_pad.c - the PlayStation pads through the raw HID interface (docs/71); see win_pad.h. */
#include <windows.h>

#include <setupapi.h>
#include <hidsdi.h>
#include <hidpi.h>

#include <stdlib.h>
#include <string.h>

#include "win_pad.h"

#define SCAN_MS 2000u
#define KEEPALIVE_MS 100u
#define MIN_GAP_MS 16u
#define IN_MAX 1024

typedef struct Dev {
    int open;
    HANDLE h;
    PadKind kind;
    int bluetooth;
    char path[260];
    USHORT in_len, out_len, feat_len;
    OVERLAPPED rov, wov;
    uint8_t rbuf[IN_MAX];
    int rpending, wpending;
    uint8_t wbuf[IN_MAX];
    PadState st;
    int have_state;
    unsigned seq;
    int setup_sent;
    uint8_t sent[5];             /* the last strengths and colour sent */
    int have_sent;
    DWORD sent_at;
} Dev;

static Dev dev[WPAD_MAX];
static DWORD next_scan;
static void (*logfn)(const char *);
static char seen[24][260];                                   /* the paths already written to the log (a path is told about once) */
static int seen_n;

void wpad_set_log(void (*fn)(const char *line))
{
    logfn = fn;
}

static void say(const char *path, const char *fmt_what, DWORD a, DWORD b, DWORD c)
{
    char line[600];
    int i;

    for (i = 0; i < seen_n; i++) {
        if (strcmp(seen[i], path) == 0 && strcmp(fmt_what, "found") != 0) {
            return;
        }
    }
    if (seen_n < 24 && strcmp(fmt_what, "found") != 0) {
        strncpy(seen[seen_n], path, 259);
        seen_n++;
    }
    if (logfn != NULL) {
        wsprintfA(line, "pad %s: %.380s (%lu %lu %lu)", fmt_what, path, (unsigned long)a, (unsigned long)b, (unsigned long)c);
        logfn(line);
    }
}

static void dev_close(Dev *d)
{
    if (d->open) {
        if (d->h != INVALID_HANDLE_VALUE) {
            CancelIo(d->h);
            CloseHandle(d->h);
        }
        if (d->rov.hEvent != NULL) {
            CloseHandle(d->rov.hEvent);
        }
        if (d->wov.hEvent != NULL) {
            CloseHandle(d->wov.hEvent);
        }
    }
    memset(d, 0, sizeof *d);
    d->h = INVALID_HANDLE_VALUE;
}

static int start_read(Dev *d)
{
    BOOL ok;

    ResetEvent(d->rov.hEvent);
    ok = ReadFile(d->h, d->rbuf, d->in_len, NULL, &d->rov);
    if (!ok && GetLastError() != ERROR_IO_PENDING) {
        return 0;
    }
    d->rpending = 1;
    return 1;
}

/* a Bluetooth pad sends only a short report until it is asked for its calibration (feature report 5): that request switches it to the full reports */
static void bt_switch(Dev *d)
{
    uint8_t f[256];

    if (d->feat_len == 0 || d->feat_len > sizeof f) {
        return;
    }
    memset(f, 0, sizeof f);
    f[0] = 0x05;
    (void)HidD_GetFeature(d->h, f, d->feat_len);
}

static void try_open(const char *path)
{
    int i, slot = -1;
    HANDLE h;
    HIDD_ATTRIBUTES at;
    PHIDP_PREPARSED_DATA pp = NULL;
    HIDP_CAPS caps;
    PadKind kind;
    Dev *d;

    for (i = 0; i < WPAD_MAX; i++) {
        if (dev[i].open && strcmp(dev[i].path, path) == 0) {
            return;
        }
        if (!dev[i].open && slot < 0) {
            slot = i;
        }
    }
    if (slot < 0) {
        return;
    }
    h = CreateFileA(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        say(path, "cannot be opened (error)", GetLastError(), 0, 0);   /* another program has it exclusively, or it is not a device we may open: tried again at the next scan */
        return;
    }
    at.Size = sizeof at;
    if (!HidD_GetAttributes(h, &at) || (kind = padhid_kind(at.VendorID, at.ProductID)) == PAD_NONE) {
        say(path, "is not a known pad (vendor, product)", at.VendorID, at.ProductID, 0);
        CloseHandle(h);
        return;
    }
    if (!HidD_GetPreparsedData(h, &pp)) {
        say(path, "has no preparsed data (error)", GetLastError(), 0, 0);
        CloseHandle(h);
        return;
    }
    memset(&caps, 0, sizeof caps);
    if (HidP_GetCaps(pp, &caps) != HIDP_STATUS_SUCCESS || caps.InputReportByteLength < 10 || caps.InputReportByteLength > IN_MAX) {
        say(path, "has unusable report sizes (input, output)", caps.InputReportByteLength, caps.OutputReportByteLength, 0);
        HidD_FreePreparsedData(pp);
        CloseHandle(h);
        return;
    }
    HidD_FreePreparsedData(pp);
    d = &dev[slot];
    memset(d, 0, sizeof *d);
    d->open = 1;
    d->h = h;
    d->kind = kind;
    d->in_len = caps.InputReportByteLength;
    d->out_len = caps.OutputReportByteLength;
    d->feat_len = caps.FeatureReportByteLength;
    d->bluetooth = d->in_len > 64;                           /* USB: 64 bytes; Bluetooth: the long ones (DualShock 4: 547, DualSense: 78) */
    strncpy(d->path, path, sizeof d->path - 1);
    d->rov.hEvent = CreateEventA(NULL, TRUE, FALSE, NULL);
    d->wov.hEvent = CreateEventA(NULL, TRUE, TRUE, NULL);
    if (d->rov.hEvent == NULL || d->wov.hEvent == NULL) {
        dev_close(d);
        return;
    }
    if (d->bluetooth) {
        bt_switch(d);
    }
    say(path, "found", kind == PAD_DS4 ? 4u : 5u, d->in_len, d->bluetooth ? 1000u + d->out_len : d->out_len);   /* kind 4 = DualShock 4, 5 = DualSense; input length; output length (+1000: Bluetooth) */
    if (!start_read(d)) {
        say(path, "first read failed (error)", GetLastError(), 0, 0);
        dev_close(d);
    }
}

static void scan(void)
{
    GUID guid;
    HDEVINFO set;
    SP_DEVICE_INTERFACE_DATA ifd;
    DWORD i;

    HidD_GetHidGuid(&guid);
    set = SetupDiGetClassDevsA(&guid, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (set == INVALID_HANDLE_VALUE) {
        return;
    }
    ifd.cbSize = sizeof ifd;
    for (i = 0; SetupDiEnumDeviceInterfaces(set, NULL, &guid, i, &ifd); i++) {
        DWORD need = 0;
        SP_DEVICE_INTERFACE_DETAIL_DATA_A *det;

        (void)SetupDiGetDeviceInterfaceDetailA(set, &ifd, NULL, 0, &need, NULL);
        if (need < sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_A) || need > 1024) {
            continue;
        }
        det = (SP_DEVICE_INTERFACE_DETAIL_DATA_A *)malloc(need);
        if (det == NULL) {
            continue;
        }
        det->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_A);
        if (SetupDiGetDeviceInterfaceDetailA(set, &ifd, det, need, NULL, NULL)) {
            /* only the paths of Sony's devices are opened: vendor 054c is in the path, as "vid_054c" on USB and as "vid&0002054c" on Bluetooth (the number before it is the vendor id source) */
            char low[300];
            size_t k, n = strlen(det->DevicePath);

            if (n < sizeof low) {
                for (k = 0; k <= n; k++) {
                    char ch = det->DevicePath[k];
                    low[k] = (ch >= 'A' && ch <= 'Z') ? (char)(ch - 'A' + 'a') : ch;
                }
                if (strstr(low, "054c") != NULL) {
                    try_open(det->DevicePath);
                }
            }
        }
        free(det);
    }
    SetupDiDestroyDeviceInfoList(set);
}

void wpad_poll(void)
{
    DWORD now = GetTickCount();
    int i;

    if ((LONG)(now - next_scan) >= 0) {
        next_scan = now + SCAN_MS;
        scan();
    }
    for (i = 0; i < WPAD_MAX; i++) {
        Dev *d = &dev[i];
        int guard;

        if (!d->open) {
            continue;
        }
        for (guard = 0; guard < 32 && d->open && d->rpending; guard++) {   /* every report that has come; the newest counts */
            DWORD got = 0;

            if (!GetOverlappedResult(d->h, &d->rov, &got, FALSE)) {
                if (GetLastError() != ERROR_IO_INCOMPLETE) {              /* the pad is gone */
                    dev_close(d);
                }
                break;
            }
            d->rpending = 0;
            {
                PadState s;
                if (padhid_parse(d->kind, d->rbuf, got, &s)) {
                    d->st = s;
                    d->have_state = 1;
                }
            }
            if (!start_read(d)) {
                dev_close(d);
                break;
            }
        }
    }
}

int wpad_count(void)
{
    int i, n = 0;

    for (i = 0; i < WPAD_MAX; i++) {
        n += dev[i].open && dev[i].have_state;
    }
    return n;
}

int wpad_state(int idx, PadKind *kind, int *bluetooth, PadState *out)
{
    int i, n = 0;

    for (i = 0; i < WPAD_MAX; i++) {
        if (dev[i].open && dev[i].have_state) {
            if (n == idx) {
                *kind = dev[i].kind;
                *bluetooth = dev[i].bluetooth;
                *out = dev[i].st;
                return 1;
            }
            n++;
        }
    }
    return 0;
}

int wpad_feedback(uint8_t strong, uint8_t weak, uint8_t r, uint8_t g, uint8_t b)
{
    int i, written = 0;
    DWORD now = GetTickCount();
    uint8_t want[5];

    want[0] = strong;
    want[1] = weak;
    want[2] = r;
    want[3] = g;
    want[4] = b;
    for (i = 0; i < WPAD_MAX; i++) {
        Dev *d = &dev[i];
        int changed, due, busy = 0;
        size_t len;
        DWORD put = 0;

        if (!d->open) {
            continue;
        }
        if (d->wpending) {                                   /* the last write is still on its way: not stacked */
            DWORD n = 0;
            if (GetOverlappedResult(d->h, &d->wov, &n, FALSE)) {
                d->wpending = 0;
            } else if (GetLastError() == ERROR_IO_INCOMPLETE) {
                busy = 1;
            } else {
                d->wpending = 0;
            }
        }
        changed = !d->have_sent || memcmp(want, d->sent, sizeof want) != 0;
        due = (strong != 0 || weak != 0) && (LONG)(now - d->sent_at) >= (LONG)KEEPALIVE_MS;
        if (busy || !(changed || due) || (LONG)(now - d->sent_at) < (LONG)MIN_GAP_MS) {
            continue;
        }
        memset(d->wbuf, 0, sizeof d->wbuf);
        len = padhid_build_output(d->kind, d->bluetooth, d->seq++, !d->setup_sent, strong, weak, r, g, b, d->wbuf);
        if (len == 0) {
            continue;
        }
        if (d->out_len > len && d->out_len <= IN_MAX) {
            len = d->out_len;                                 /* the device wants the report as long as it says; the extra bytes are zero */
        }
        ResetEvent(d->wov.hEvent);
        if (WriteFile(d->h, d->wbuf, (DWORD)len, &put, &d->wov) || GetLastError() == ERROR_IO_PENDING) {
            d->wpending = !(put == (DWORD)len);
            d->setup_sent = 1;
            memcpy(d->sent, want, sizeof want);
            d->have_sent = 1;
            d->sent_at = now;
            written++;
        }
    }
    return written;
}

void wpad_shutdown(void)
{
    int i;

    for (i = 0; i < WPAD_MAX; i++) {
        Dev *d = &dev[i];

        if (d->open) {
            size_t len;
            DWORD put = 0;

            memset(d->wbuf, 0, sizeof d->wbuf);
            len = padhid_build_output(d->kind, d->bluetooth, d->seq++, 0, 0, 0, 0, 0, 64, d->wbuf);       /* at rest, and the dim blue of a pad that nobody is using */
            if (len > 0) {
                if (d->out_len > len && d->out_len <= IN_MAX) {
                    len = d->out_len;
                }
                if (d->wpending) {
                    (void)WaitForSingleObject(d->wov.hEvent, 50);
                }
                ResetEvent(d->wov.hEvent);
                if (WriteFile(d->h, d->wbuf, (DWORD)len, &put, &d->wov) || GetLastError() == ERROR_IO_PENDING) {
                    (void)WaitForSingleObject(d->wov.hEvent, 100);
                }
            }
            dev_close(d);
        }
    }
}
