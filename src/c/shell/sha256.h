/* shell/sha256.h - SHA-256 and HMAC-SHA-256 (FIPS 180-4, RFC 2104), portable C99, for the seal of the achievements file (docs/74).  Checked against the standard test vectors in `ctest achieve_check`. */
#ifndef PM_SHA256_H
#define PM_SHA256_H

#include <stddef.h>
#include <stdint.h>

void sha256(const uint8_t *data, size_t n, uint8_t out[32]);
void hmac_sha256(const uint8_t *key, size_t keylen, const uint8_t *data, size_t n, uint8_t out[32]);

#endif
