/* assets/sha256.h - SHA-256 (FIPS 180-4), portable C99, used to recognise the cartridge image. */
#ifndef PM_ASSETS_SHA256_H
#define PM_ASSETS_SHA256_H

#include <stddef.h>
#include <stdint.h>

void pm_sha256(const uint8_t *data, size_t n, uint8_t out[32]);   /* the SHA-256 of `n` bytes into `out` */

#endif
