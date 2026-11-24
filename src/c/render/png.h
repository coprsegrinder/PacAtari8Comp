/* render/png.h - a small PNG reader for the lookup textures of the CRT shaders (docs/70).  Portable C99: 8-bit grey, grey + alpha, RGB, RGBA and palette images, no interlacing; the zlib stream is read
 * with an inflate of its own (no library).  Not a general PNG library: anything else is refused. */
#ifndef PM_RENDER_PNG_H
#define PM_RENDER_PNG_H

#include <stddef.h>
#include <stdint.h>

/* decodes `data` (a whole PNG file) to RGBA, 4 bytes a pixel, row 0 the top; *rgba is malloc'd (free it).  0 on success, else a non-zero code (1 not a PNG, 2 a kind not supported, 3 damaged, 4 out of memory) */
int png_decode_rgba(const uint8_t *data, size_t size, uint8_t **rgba, int *w, int *h);

/* inflates a raw deflate stream (RFC 1951) of `size` bytes into `out` (capacity `cap`); returns the bytes written, or -1 when the stream is damaged or does not fit */
long png_inflate(const uint8_t *in, size_t size, uint8_t *out, size_t cap);

#endif
