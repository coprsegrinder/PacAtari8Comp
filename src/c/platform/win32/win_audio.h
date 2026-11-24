/* platform/win32/win_audio.h - the sound device of the Windows front end (stage J): WASAPI, shared mode, 44,100 Hz.  The game's sound is mono float; the device gets it as two equal channels, converted by
 * the system when the mix format differs (AUTOCONVERTPCM).  The device is also the CLOCK of the front end: the game runs one frame whenever the device wants about two frames more sound. */
#ifndef PM_WIN_AUDIO_H
#define PM_WIN_AUDIO_H

#include <stddef.h>

typedef struct WinAudio WinAudio;

/* open the default output device at `rate` Hz, a buffer of about 100 ms; NULL when there is none (the caller then paces by the timer) */
WinAudio *wa_open(double rate);
void wa_close(WinAudio *a);
/* the frames the device still has to play (0 when it ran dry); -1 on an error */
int wa_queued(WinAudio *a);
/* the frames that fit in the buffer now */
int wa_room(WinAudio *a);
/* append `n` mono samples (the device wants more than that: they go to both channels); returns 0 on success */
int wa_write(WinAudio *a, const float *mono, size_t n);
/* how many times the device ran dry while the game was running (a glitch) and the buffer size in frames */
unsigned wa_underruns(const WinAudio *a);
int wa_buffer_frames(const WinAudio *a);
unsigned wa_write_failures(const WinAudio *a, long *last_hr);   /* writes that did not go in, and the last error code */
int wa_set_volume(WinAudio *a, float volume);                   /* 0 on success */
int wa_session_state(WinAudio *a, float *volume, int *muted);   /* this program's volume and mute in the Windows volume mixer; 0 on success */

/* ---- the loopback measurement (stage J: sound by measurement): what the sound device really played, captured by WASAPI loopback (this program's sound only when Windows allows it, else the endpoint's whole mix) ---- */
typedef struct WinLoop WinLoop;
WinLoop *wl_open(void);                       /* NULL when the endpoint cannot be captured */
void wl_poll(WinLoop *l);                     /* take what the device has played since the last call */
void wl_close(WinLoop *l);
/* the capture as a mono float timeline: sample i is at time base + i / rate; silence is zero (no packets are delivered while the endpoint is silent) */
const float *wl_samples(const WinLoop *l, size_t *n, double *rate, long long *base_100ns);
void wl_stats(const WinLoop *l, unsigned long out[5]);   /* packets, silent packets, discontinuities, packets stamped before the start, dropped */
int wl_scope(const WinLoop *l);               /* 1: only this process's sound is captured; 0: the whole endpoint's mix */
#endif
