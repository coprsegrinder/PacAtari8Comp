/* render/png.c - see png.h. */
#include "png.h"

#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------- inflate (RFC 1951): canonical Huffman codes decoded by counting, after the way zlib's puff.c does it */

#define MAXBITS 15
#define MAXLCODES 286
#define MAXDCODES 30
#define FIXLCODES 288

typedef struct Huffman {
    short count[MAXBITS + 1];
    short symbol[FIXLCODES];
} Huffman;

typedef struct Inflate {
    const uint8_t *in;
    size_t size, pos;
    uint32_t bitbuf;
    int bitcnt;
    uint8_t *out;
    size_t cap, n;
    int err;
} Inflate;

static int bits(Inflate *s, int need)
{
    long val = (long)s->bitbuf;

    while (s->bitcnt < need) {
        if (s->pos >= s->size) {
            s->err = 1;
            return 0;
        }
        val |= (long)s->in[s->pos++] << s->bitcnt;
        s->bitcnt += 8;
    }
    s->bitbuf = (uint32_t)(val >> need);
    s->bitcnt -= need;
    return (int)(val & ((1L << need) - 1));
}

static int decode(Inflate *s, const Huffman *h)
{
    int len, code = 0, first = 0, index = 0;

    for (len = 1; len <= MAXBITS; len++) {
        int count;
        code |= bits(s, 1);
        if (s->err) {
            return -1;
        }
        count = h->count[len];
        if (code - count < first) {
            return h->symbol[index + (code - first)];
        }
        index += count;
        first += count;
        first <<= 1;
        code <<= 1;
    }
    s->err = 1;
    return -1;
}

static int construct(Huffman *h, const short *length, int n)
{
    int symbol, len, left;
    short offs[MAXBITS + 1];

    for (len = 0; len <= MAXBITS; len++) {
        h->count[len] = 0;
    }
    for (symbol = 0; symbol < n; symbol++) {
        h->count[length[symbol]]++;
    }
    if (h->count[0] == n) {
        return 0;
    }
    left = 1;
    for (len = 1; len <= MAXBITS; len++) {
        left <<= 1;
        left -= h->count[len];
        if (left < 0) {
            return left;                                       /* over-subscribed */
        }
    }
    offs[1] = 0;
    for (len = 1; len < MAXBITS; len++) {
        offs[len + 1] = (short)(offs[len] + h->count[len]);
    }
    for (symbol = 0; symbol < n; symbol++) {
        if (length[symbol] != 0) {
            h->symbol[offs[length[symbol]]++] = (short)symbol;
        }
    }
    return left;
}

static int put(Inflate *s, int byte)
{
    if (s->n >= s->cap) {
        s->err = 1;
        return 0;
    }
    s->out[s->n++] = (uint8_t)byte;
    return 1;
}

static int codes(Inflate *s, const Huffman *lencode, const Huffman *distcode)
{
    static const short lens[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
    static const short lext[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
    static const short dists[30] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
    static const short dext[30] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};
    int symbol;

    do {
        symbol = decode(s, lencode);
        if (symbol < 0) {
            return -1;
        }
        if (symbol < 256) {
            if (!put(s, symbol)) {
                return -1;
            }
        } else if (symbol > 256) {
            int len, dist;
            symbol -= 257;
            if (symbol >= 29) {
                return -1;
            }
            len = lens[symbol] + bits(s, lext[symbol]);
            symbol = decode(s, distcode);
            if (symbol < 0 || symbol >= 30) {
                return -1;
            }
            dist = dists[symbol] + bits(s, dext[symbol]);
            if (s->err || (size_t)dist > s->n) {
                return -1;
            }
            while (len--) {
                if (!put(s, s->out[s->n - (size_t)dist])) {
                    return -1;
                }
            }
        }
    } while (symbol != 256);
    return 0;
}

static int fixed(Inflate *s)
{
    static Huffman lencode, distcode;
    static int built;

    if (!built) {
        short lengths[FIXLCODES];
        int symbol;
        for (symbol = 0; symbol < 144; symbol++) { lengths[symbol] = 8; }
        for (; symbol < 256; symbol++) { lengths[symbol] = 9; }
        for (; symbol < 280; symbol++) { lengths[symbol] = 7; }
        for (; symbol < FIXLCODES; symbol++) { lengths[symbol] = 8; }
        construct(&lencode, lengths, FIXLCODES);
        for (symbol = 0; symbol < MAXDCODES; symbol++) { lengths[symbol] = 5; }
        construct(&distcode, lengths, MAXDCODES);
        built = 1;
    }
    return codes(s, &lencode, &distcode);
}

static int dynamic(Inflate *s)
{
    static const short order[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};
    int nlen, ndist, ncode, index, err;
    short lengths[MAXLCODES + MAXDCODES];
    Huffman lencode, distcode;

    nlen = bits(s, 5) + 257;
    ndist = bits(s, 5) + 1;
    ncode = bits(s, 4) + 4;
    if (s->err || nlen > MAXLCODES || ndist > MAXDCODES) {
        return -1;
    }
    for (index = 0; index < ncode; index++) {
        lengths[order[index]] = (short)bits(s, 3);
    }
    for (; index < 19; index++) {
        lengths[order[index]] = 0;
    }
    err = construct(&lencode, lengths, 19);
    if (err != 0) {
        return -1;
    }
    index = 0;
    while (index < nlen + ndist) {
        int symbol = decode(s, &lencode), len, rep;
        if (symbol < 0) {
            return -1;
        }
        if (symbol < 16) {
            lengths[index++] = (short)symbol;
        } else {
            len = 0;
            if (symbol == 16) {
                if (index == 0) {
                    return -1;
                }
                len = lengths[index - 1];
                rep = 3 + bits(s, 2);
            } else if (symbol == 17) {
                rep = 3 + bits(s, 3);
            } else {
                rep = 11 + bits(s, 7);
            }
            if (s->err || index + rep > nlen + ndist) {
                return -1;
            }
            while (rep--) {
                lengths[index++] = (short)len;
            }
        }
    }
    if (lengths[256] == 0) {
        return -1;
    }
    err = construct(&lencode, lengths, nlen);
    if (err < 0 || (err > 0 && nlen - lencode.count[0] != 1)) {
        return -1;
    }
    err = construct(&distcode, lengths + nlen, ndist);
    if (err < 0 || (err > 0 && ndist - distcode.count[0] != 1)) {
        return -1;
    }
    return codes(s, &lencode, &distcode);
}

long png_inflate(const uint8_t *in, size_t size, uint8_t *out, size_t cap)
{
    Inflate s;
    int last;

    memset(&s, 0, sizeof s);
    s.in = in;
    s.size = size;
    s.out = out;
    s.cap = cap;
    do {
        int type;
        last = bits(&s, 1);
        type = bits(&s, 2);
        if (s.err) {
            return -1;
        }
        if (type == 0) {                                       /* stored */
            unsigned len, nlen;
            s.bitbuf = 0;
            s.bitcnt = 0;
            if (s.pos + 4 > s.size) {
                return -1;
            }
            len = (unsigned)s.in[s.pos] | ((unsigned)s.in[s.pos + 1] << 8);
            nlen = (unsigned)s.in[s.pos + 2] | ((unsigned)s.in[s.pos + 3] << 8);
            s.pos += 4;
            if (len != (~nlen & 0xFFFFu) || s.pos + len > s.size || s.n + len > s.cap) {
                return -1;
            }
            memcpy(s.out + s.n, s.in + s.pos, len);
            s.n += len;
            s.pos += len;
        } else if (type == 1) {
            if (fixed(&s) != 0) {
                return -1;
            }
        } else if (type == 2) {
            if (dynamic(&s) != 0) {
                return -1;
            }
        } else {
            return -1;
        }
    } while (!last);
    return s.err ? -1 : (long)s.n;
}

/* ---------------------------------------------------------------- the PNG file */

static uint32_t be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static int paeth(int a, int b, int c)
{
    int p = a + b - c, pa = abs(p - a), pb = abs(p - b), pc = abs(p - c);

    return (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
}

int png_decode_rgba(const uint8_t *data, size_t size, uint8_t **rgba, int *w, int *h)
{
    static const uint8_t sig[8] = {137, 80, 78, 71, 13, 10, 26, 10};
    size_t pos = 8, idat_n = 0, raw_n;
    uint8_t *idat = NULL, *raw = NULL, *img = NULL;
    uint8_t pal[256][3];
    int width = 0, height = 0, depth = 0, ctype = -1, interlace = 0, bpp, y, x, npal = 0, rc = 3;
    long got;

    *rgba = NULL;
    if (size < 33 || memcmp(data, sig, 8) != 0) {
        return 1;
    }
    memset(pal, 0, sizeof pal);
    idat = (uint8_t *)malloc(size);
    if (idat == NULL) {
        return 4;
    }
    while (pos + 12 <= size) {
        uint32_t len = be32(data + pos);
        const uint8_t *type = data + pos + 4, *body = data + pos + 8;
        if (pos + 12 + (size_t)len > size) {
            goto done;
        }
        if (memcmp(type, "IHDR", 4) == 0 && len >= 13) {
            width = (int)be32(body);
            height = (int)be32(body + 4);
            depth = body[8];
            ctype = body[9];
            interlace = body[12];
        } else if (memcmp(type, "PLTE", 4) == 0) {
            npal = (int)(len / 3) > 256 ? 256 : (int)(len / 3);
            memcpy(pal, body, (size_t)npal * 3);
        } else if (memcmp(type, "IDAT", 4) == 0) {
            memcpy(idat + idat_n, body, len);
            idat_n += len;
        } else if (memcmp(type, "IEND", 4) == 0) {
            break;
        }
        pos += 12 + (size_t)len;
    }
    if (width <= 0 || height <= 0 || width > 16384 || height > 16384 || ctype < 0) {
        goto done;
    }
    if (depth != 8 || interlace != 0 || !(ctype == 0 || ctype == 2 || ctype == 3 || ctype == 4 || ctype == 6)) {
        rc = 2;
        goto done;
    }
    bpp = ctype == 0 ? 1 : (ctype == 2 ? 3 : (ctype == 3 ? 1 : (ctype == 4 ? 2 : 4)));
    raw_n = (size_t)height * (1u + (size_t)width * (size_t)bpp);
    raw = (uint8_t *)malloc(raw_n);
    img = (uint8_t *)malloc((size_t)width * (size_t)height * 4u);
    if (raw == NULL || img == NULL) {
        rc = 4;
        goto done;
    }
    if (idat_n < 6) {
        goto done;
    }
    got = png_inflate(idat + 2, idat_n - 2, raw, raw_n);          /* the 2-byte zlib header, then the deflate stream */
    if (got != (long)raw_n) {
        goto done;
    }
    for (y = 0; y < height; y++) {                                 /* undo the filters, in place */
        uint8_t *row = raw + (size_t)y * (1u + (size_t)width * (size_t)bpp), ft = row[0];
        const uint8_t *up = y > 0 ? row - (1u + (size_t)width * (size_t)bpp) + 1 : NULL;
        uint8_t *cur = row + 1;
        int n = width * bpp;
        if (ft > 4) {
            goto done;
        }
        for (x = 0; x < n; x++) {
            int a = x >= bpp ? cur[x - bpp] : 0, b = up != NULL ? up[x] : 0, c = (x >= bpp && up != NULL) ? up[x - bpp] : 0, v = cur[x];
            switch (ft) {
            case 1: v += a; break;
            case 2: v += b; break;
            case 3: v += (a + b) / 2; break;
            case 4: v += paeth(a, b, c); break;
            default: break;
            }
            cur[x] = (uint8_t)v;
        }
        for (x = 0; x < width; x++) {
            const uint8_t *s = cur + x * bpp;
            uint8_t *d = img + ((size_t)y * (size_t)width + (size_t)x) * 4u;
            switch (ctype) {
            case 0: d[0] = d[1] = d[2] = s[0]; d[3] = 255; break;
            case 2: d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = 255; break;
            case 3: d[0] = pal[s[0]][0]; d[1] = pal[s[0]][1]; d[2] = pal[s[0]][2]; d[3] = 255; break;
            case 4: d[0] = d[1] = d[2] = s[0]; d[3] = s[1]; break;
            default: d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = s[3]; break;
            }
        }
    }
    (void)npal;
    *rgba = img;
    img = NULL;
    *w = width;
    *h = height;
    rc = 0;
done:
    free(idat);
    free(raw);
    free(img);
    return rc;
}
