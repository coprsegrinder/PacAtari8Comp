/* shell/padhid.h - the reports of the PlayStation pads (DualShock 4 and DualSense), as bytes: how to read what the pad sends and how to build what it is told (rumble, light bar).  Portable C99, no system
 * call: platform/win32/win_pad.c finds the devices and moves the bytes; `ctest padhid_check` checks the byte layouts against reports written out by hand from the layouts the public drivers use (Linux
 * hid-sony / hid-playstation, DS4Windows) (docs/71).  NOT yet checked against a real pad (OV-81).
 *   input : USB report 0x01 (64 bytes), Bluetooth report 0x11 (DualShock 4) or 0x31 (DualSense) once the pad is switched to its full reports, and the short Bluetooth report 0x01 a pad sends before that;
 *   output: USB report 0x05 (DualShock 4, 32 bytes) or 0x02 (DualSense, 63 bytes); Bluetooth 0x11 / 0x31, 78 bytes, closed by a CRC-32 over the seed byte 0xA2 and the first 74 bytes. */
#ifndef PM_SHELL_PADHID_H
#define PM_SHELL_PADHID_H

#include <stddef.h>
#include <stdint.h>

#define PAD_VENDOR_SONY 0x054C
#define PAD_PRODUCT_DS4_V1 0x05C4
#define PAD_PRODUCT_DS4_V2 0x09CC
#define PAD_PRODUCT_DS4_DONGLE 0x0BA0
#define PAD_PRODUCT_DUALSENSE 0x0CE6
#define PAD_PRODUCT_DUALSENSE_EDGE 0x0DF2

typedef enum PadKind { PAD_NONE = 0, PAD_DS4 = 1, PAD_DUALSENSE = 2 } PadKind;

/* the buttons of PadState.buttons */
#define PB_CROSS 0x0001u
#define PB_CIRCLE 0x0002u
#define PB_SQUARE 0x0004u
#define PB_TRIANGLE 0x0008u
#define PB_L1 0x0010u
#define PB_R1 0x0020u
#define PB_L2 0x0040u
#define PB_R2 0x0080u
#define PB_SHARE 0x0100u         /* Share (DualShock 4) or Create (DualSense) */
#define PB_OPTIONS 0x0200u
#define PB_L3 0x0400u
#define PB_R3 0x0800u
#define PB_PS 0x1000u
#define PB_TOUCH 0x2000u

typedef struct PadState {
    int up, down, left, right;   /* the direction cross */
    int lx, ly;                  /* the left stick, -32768..32767, up and right positive (as XInput) */
    unsigned buttons;            /* PB_* */
} PadState;

/* the kind of pad a USB vendor / product pair is (PAD_NONE for anything else) */
PadKind padhid_kind(unsigned vendor, unsigned product);

/* reads one input report as the pad sent it (the report id is its first byte); 1 when it is a report this knows (and fills *out), else 0 and *out is not touched */
int padhid_parse(PadKind kind, const uint8_t *rep, size_t n, PadState *out);

/* the output report for these motor strengths (strong: the big, low-pitched motor; weak: the small, high one) and light bar colour; `bluetooth` selects the framing, `seq` counts the Bluetooth reports,
 * `setup` (DualSense) also asks the pad to put out its own start-up light so the colour is the only light.  buf holds at least PADHID_OUT_MAX bytes; returns the report's length (0 for PAD_NONE) */
#define PADHID_OUT_MAX 78
size_t padhid_build_output(PadKind kind, int bluetooth, unsigned seq, int setup, uint8_t strong, uint8_t weak, uint8_t r, uint8_t g, uint8_t b, uint8_t *buf);

/* CRC-32 (the usual one: polynomial 0xEDB88320, start and end 0xFFFFFFFF) of `seed` followed by p[0..n) */
uint32_t padhid_crc32(uint8_t seed, const uint8_t *p, size_t n);

#endif
