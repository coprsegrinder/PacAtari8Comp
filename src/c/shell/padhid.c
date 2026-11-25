/* shell/padhid.c - the DualShock 4 and DualSense reports (docs/71); see padhid.h. */
#include <string.h>

#include "padhid.h"

PadKind padhid_kind(unsigned vendor, unsigned product)
{
    if (vendor != PAD_VENDOR_SONY) {
        return PAD_NONE;
    }
    if (product == PAD_PRODUCT_DS4_V1 || product == PAD_PRODUCT_DS4_V2 || product == PAD_PRODUCT_DS4_DONGLE) {
        return PAD_DS4;
    }
    if (product == PAD_PRODUCT_DUALSENSE || product == PAD_PRODUCT_DUALSENSE_EDGE) {
        return PAD_DUALSENSE;
    }
    return PAD_NONE;
}

uint32_t padhid_crc32(uint8_t seed, const uint8_t *p, size_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    size_t i;
    int k;

    for (i = 0; i <= n; i++) {
        c ^= (i == 0) ? seed : p[i - 1];
        for (k = 0; k < 8; k++) {
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
        }
    }
    return ~c;
}

static void hat(unsigned v, PadState *o)                    /* 0 up, 1 up-right, 2 right ... 7 up-left; 8 and above: none */
{
    o->up = v == 7 || v == 0 || v == 1;
    o->right = v == 1 || v == 2 || v == 3;
    o->down = v == 3 || v == 4 || v == 5;
    o->left = v == 5 || v == 6 || v == 7;
}

static int axis(uint8_t v)                                  /* 0..255, 128 in the middle, to a signed 16 bit value */
{
    return ((int)v - 128) * 256;
}

/* the fields the two pads share: the left stick, the face buttons and the hat (b0), and the other buttons as the pad lays them out */
static void common(const uint8_t *p, size_t lx, size_t b0, size_t b1, size_t b2, PadState *o)
{
    unsigned a = p[b0], b = p[b1], c = p[b2], bt = 0;

    o->lx = axis(p[lx]);
    o->ly = -axis(p[lx + 1]);                               /* the pad's y grows downwards */
    if (o->ly > 32767) {
        o->ly = 32767;
    }
    hat(a & 0x0Fu, o);
    if (a & 0x20u) { bt |= PB_CROSS; }
    if (a & 0x40u) { bt |= PB_CIRCLE; }
    if (a & 0x10u) { bt |= PB_SQUARE; }
    if (a & 0x80u) { bt |= PB_TRIANGLE; }
    if (b & 0x01u) { bt |= PB_L1; }
    if (b & 0x02u) { bt |= PB_R1; }
    if (b & 0x04u) { bt |= PB_L2; }
    if (b & 0x08u) { bt |= PB_R2; }
    if (b & 0x10u) { bt |= PB_SHARE; }                      /* Share, or Create: the same bit */
    if (b & 0x20u) { bt |= PB_OPTIONS; }
    if (b & 0x40u) { bt |= PB_L3; }
    if (b & 0x80u) { bt |= PB_R3; }
    if (c & 0x01u) { bt |= PB_PS; }
    if (c & 0x02u) { bt |= PB_TOUCH; }
    o->buttons = bt;
}

int padhid_parse(PadKind kind, const uint8_t *rep, size_t n, PadState *out)
{
    PadState s;

    if (rep == NULL || n < 1) {
        return 0;
    }
    memset(&s, 0, sizeof s);
    if (kind == PAD_DS4) {
        size_t c;
        if (rep[0] == 0x01 && n >= 8) {                     /* USB (64 bytes) and the short Bluetooth report: the same first bytes */
            c = 1;
        } else if (rep[0] == 0x11 && n >= 10) {             /* Bluetooth, full: two bytes before the same fields */
            c = 3;
        } else {
            return 0;
        }
        if (c + 6 >= n) {
            return 0;
        }
        common(rep, c, c + 4, c + 5, c + 6, &s);
    } else if (kind == PAD_DUALSENSE) {
        if (rep[0] == 0x01 && n >= 64) {                    /* USB */
            common(rep, 1, 8, 9, 10, &s);
        } else if (rep[0] == 0x01 && n >= 8) {              /* the short Bluetooth report: the two triggers are not in it */
            common(rep, 1, 5, 6, 7, &s);
        } else if (rep[0] == 0x31 && n >= 13) {             /* Bluetooth, full: one byte before the fields */
            common(rep, 2, 9, 10, 11, &s);
        } else {
            return 0;
        }
    } else {
        return 0;
    }
    *out = s;
    return 1;
}

static void put_crc(uint8_t *buf)                           /* the Bluetooth reports end in a CRC-32 of 0xA2 and the 74 bytes before it, little endian */
{
    uint32_t crc = padhid_crc32(0xA2, buf, 74);

    buf[74] = (uint8_t)(crc & 0xFFu);
    buf[75] = (uint8_t)((crc >> 8) & 0xFFu);
    buf[76] = (uint8_t)((crc >> 16) & 0xFFu);
    buf[77] = (uint8_t)((crc >> 24) & 0xFFu);
}

size_t padhid_build_output(PadKind kind, int bluetooth, unsigned seq, int setup, uint8_t strong, uint8_t weak, uint8_t r, uint8_t g, uint8_t b, uint8_t *buf)
{
    if (kind == PAD_DS4) {
        size_t c = bluetooth ? 3 : 1;
        size_t len = bluetooth ? 78 : 32;

        memset(buf, 0, len);
        if (bluetooth) {
            buf[0] = 0x11;
            buf[1] = 0xC0;                                   /* HID report with a CRC */
        } else {
            buf[0] = 0x05;
        }
        buf[c] = 0x03;                                       /* update the motors and the light bar */
        buf[c + 1] = 0x04;
        buf[c + 3] = weak;                                   /* the small motor (the "right" one) */
        buf[c + 4] = strong;                                 /* the big motor (the "left" one) */
        buf[c + 5] = r;
        buf[c + 6] = g;
        buf[c + 7] = b;
        if (bluetooth) {
            put_crc(buf);
        }
        return len;
    }
    if (kind == PAD_DUALSENSE) {
        size_t c = bluetooth ? 3 : 1;
        size_t len = bluetooth ? 78 : 63;

        memset(buf, 0, len);
        if (bluetooth) {
            buf[0] = 0x31;
            buf[1] = (uint8_t)((seq & 0x0Fu) << 4);
            buf[2] = 0x10;
        } else {
            buf[0] = 0x02;
        }
        buf[c] = 0x03;                                       /* valid_flag0: compatible vibration, haptics select */
        buf[c + 1] = 0x04;                                   /* valid_flag1: light bar control */
        buf[c + 2] = weak;                                   /* motor right */
        buf[c + 3] = strong;                                 /* motor left */
        buf[c + 38] = (uint8_t)(0x04u | (setup ? 0x02u : 0u)); /* valid_flag2: vibration 2, and the light bar set-up when asked */
        buf[c + 41] = setup ? 2 : 0;                         /* light bar set-up: the start-up light out */
        buf[c + 44] = r;
        buf[c + 45] = g;
        buf[c + 46] = b;
        if (bluetooth) {
            put_crc(buf);
        }
        return len;
    }
    return 0;
}
