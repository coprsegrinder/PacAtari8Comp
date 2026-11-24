/* What the port relies on from the C implementation: the 6502 arithmetic is 8-bit and wraps, so the core uses
 * uint8_t and relies on these facts; this test fails to build or run where they do not hold. C99. */
#include <limits.h>
#include <stdint.h>
#include <stdio.h>

#if CHAR_BIT != 8
#error "the port needs 8-bit bytes"
#endif

int main(void)
{
    uint8_t a = 0xFF;
    uint8_t b = (uint8_t)(a + 1u);           /* wraps to 0, as a 6502 ADC / INC does */
    uint16_t w = (uint16_t)((uint16_t)0xFFu + 1u);
    int ok = (b == 0u) && (w == 0x100u) && (sizeof(uint8_t) == 1u) && (sizeof(uint16_t) == 2u);
    ok = ok && ((uint8_t)(0u - 1u) == 0xFFu);  /* DEC from 0 */
    ok = ok && ((uint8_t)(0x80u << 1) == 0u);  /* ASL out of the byte */
#if defined(__clang__)
    printf("clang %d.%d, __STDC_VERSION__ %ld\n", __clang_major__, __clang_minor__, (long)__STDC_VERSION__);
#elif defined(__GNUC__)
    printf("gcc %d.%d, __STDC_VERSION__ %ld\n", __GNUC__, __GNUC_MINOR__, (long)__STDC_VERSION__);
#endif
    if (!ok) {
        printf("FAIL\n");
        return 1;
    }
    printf("8-bit wrap-around arithmetic: ok\n");
    return 0;
}
