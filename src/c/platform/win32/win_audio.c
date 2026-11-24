/* platform/win32/win_audio.c - see win_audio.h. */
#define INITGUID
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>

#include <stdlib.h>

#include "win_audio.h"

struct WinAudio {
    IMMDeviceEnumerator *en;
    IMMDevice *dev;
    IAudioClient *client;
    IAudioRenderClient *render;
    UINT32 buffer_frames;
    unsigned underruns, write_fail;
    long last_hr;
    int started;
    int com;
};

static void release(WinAudio *a)
{
    if (a->render != NULL) {
        IAudioRenderClient_Release(a->render);
    }
    if (a->client != NULL) {
        IAudioClient_Release(a->client);
    }
    if (a->dev != NULL) {
        IMMDevice_Release(a->dev);
    }
    if (a->en != NULL) {
        IMMDeviceEnumerator_Release(a->en);
    }
    if (a->com) {
        CoUninitialize();
    }
    free(a);
}

WinAudio *wa_open(double rate)
{
    WinAudio *a = (WinAudio *)calloc(1, sizeof *a);
    WAVEFORMATEX fmt;
    HRESULT hr;

    if (a == NULL) {
        return NULL;
    }
    hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    a->com = SUCCEEDED(hr);
    hr = CoCreateInstance(&CLSID_MMDeviceEnumerator, NULL, CLSCTX_ALL, &IID_IMMDeviceEnumerator, (void **)&a->en);
    if (FAILED(hr)) {
        release(a);
        return NULL;
    }
    hr = IMMDeviceEnumerator_GetDefaultAudioEndpoint(a->en, eRender, eConsole, &a->dev);
    if (FAILED(hr)) {
        release(a);
        return NULL;
    }
    hr = IMMDevice_Activate(a->dev, &IID_IAudioClient, CLSCTX_ALL, NULL, (void **)&a->client);
    if (FAILED(hr)) {
        release(a);
        return NULL;
    }
    ZeroMemory(&fmt, sizeof fmt);
    fmt.wFormatTag = WAVE_FORMAT_IEEE_FLOAT;
    fmt.nChannels = 2;
    fmt.nSamplesPerSec = (DWORD)(rate + 0.5);
    fmt.wBitsPerSample = 32;
    fmt.nBlockAlign = (WORD)(fmt.nChannels * fmt.wBitsPerSample / 8);
    fmt.nAvgBytesPerSec = fmt.nSamplesPerSec * fmt.nBlockAlign;
    fmt.cbSize = 0;
    hr = IAudioClient_Initialize(a->client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY, 1000000, 0, &fmt, NULL);   /* 100 ms in 100 ns units */
    if (FAILED(hr)) {
        release(a);
        return NULL;
    }
    hr = IAudioClient_GetBufferSize(a->client, &a->buffer_frames);
    if (FAILED(hr)) {
        release(a);
        return NULL;
    }
    hr = IAudioClient_GetService(a->client, &IID_IAudioRenderClient, (void **)&a->render);
    if (FAILED(hr)) {
        release(a);
        return NULL;
    }
    return a;
}

void wa_close(WinAudio *a)
{
    if (a == NULL) {
        return;
    }
    if (a->started) {
        IAudioClient_Stop(a->client);
    }
    release(a);
}

int wa_queued(WinAudio *a)
{
    UINT32 pad = 0;

    if (FAILED(IAudioClient_GetCurrentPadding(a->client, &pad))) {
        return -1;
    }
    return (int)pad;
}

int wa_room(WinAudio *a)
{
    int q = wa_queued(a);

    return q < 0 ? -1 : (int)a->buffer_frames - q;
}

int wa_write(WinAudio *a, const float *mono, size_t n)
{
    BYTE *buf = NULL;
    float *out;
    size_t i;
    int q = wa_queued(a);

    if (q < 0 || n > (size_t)((int)a->buffer_frames - q)) {
        a->write_fail++;
        a->last_hr = 1;
        return -1;
    }
    if (a->started && q == 0) {                              /* the device played everything and waited for us */
        a->underruns++;
    }
    {
        HRESULT g = IAudioRenderClient_GetBuffer(a->render, (UINT32)n, &buf);
        if (FAILED(g)) {
            a->write_fail++;
            a->last_hr = (long)g;
            return -1;
        }
    }
    out = (float *)buf;
    for (i = 0; i < n; i++) {
        out[2 * i] = mono[i];
        out[2 * i + 1] = mono[i];
    }
    if (FAILED(IAudioRenderClient_ReleaseBuffer(a->render, (UINT32)n, 0))) {
        return -1;
    }
    if (!a->started) {                                       /* start once there is sound in the buffer: no gap at the beginning */
        if (SUCCEEDED(IAudioClient_Start(a->client))) {
            a->started = 1;
        }
    }
    return 0;
}

unsigned wa_underruns(const WinAudio *a)
{
    return a->underruns;
}

int wa_buffer_frames(const WinAudio *a)
{
    return (int)a->buffer_frames;
}


/* ---------------------------------------------------------------- loopback capture */

struct WinLoop {
    IMMDeviceEnumerator *en;
    IMMDevice *dev;
    IAudioClient *client;
    IAudioCaptureClient *cap;
    WAVEFORMATEX *fmt;
    int is_float, channels;
    double rate;
    long long base;
    float *buf;
    size_t cap_samples, n;
    int com;
    unsigned long pkts, silent, discont, early, dropped;
    int scope;                    /* 1: this process only (the capture holds nothing but the game's sound), 0: the whole endpoint mix (other programs' sound is in it too) */
};

#define LOOP_SECONDS 40

static long long qpc_100ns(void)
{
    LARGE_INTEGER f, c;

    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (long long)((double)c.QuadPart * 1e7 / (double)f.QuadPart);
}

void wl_close(WinLoop *l)
{
    if (l == NULL) {
        return;
    }
    if (l->client != NULL) {
        IAudioClient_Stop(l->client);
    }
    if (l->cap != NULL) {
        IAudioCaptureClient_Release(l->cap);
    }
    if (l->client != NULL) {
        IAudioClient_Release(l->client);
    }
    if (l->dev != NULL) {
        IMMDevice_Release(l->dev);
    }
    if (l->en != NULL) {
        IMMDeviceEnumerator_Release(l->en);
    }
    if (l->fmt != NULL) {
        CoTaskMemFree(l->fmt);
    }
    if (l->com) {
        CoUninitialize();
    }
    free(l->buf);
    free(l);
}


/* ---- activation of a loopback client for this process only (Windows 10 2004 and later): the capture then holds the game's own sound and nothing else ---- */
typedef struct ActParams {
    DWORD activation_type;               /* 1 = process loopback */
    DWORD target_pid;
    DWORD mode;                          /* 0 = include the target process and its children */
} ActParams;

typedef struct ActHandler {
    IActivateAudioInterfaceCompletionHandlerVtbl *lpVtbl;
    LONG refs;
    HANDLE done;
} ActHandler;

static const GUID IID_AgileObject_ = {0x94ea2b94, 0xe9cc, 0x49e0, {0xc0, 0xff, 0xee, 0x64, 0xca, 0x8f, 0x5b, 0x90}};

static HRESULT STDMETHODCALLTYPE ah_qi(IActivateAudioInterfaceCompletionHandler *This, REFIID riid, void **out)
{
    if (IsEqualIID(riid, &IID_IUnknown) || IsEqualIID(riid, &IID_IActivateAudioInterfaceCompletionHandler) || IsEqualIID(riid, &IID_AgileObject_)) {
        *out = This;
        InterlockedIncrement(&((ActHandler *)This)->refs);
        return S_OK;
    }
    *out = NULL;
    return E_NOINTERFACE;
}

static ULONG STDMETHODCALLTYPE ah_addref(IActivateAudioInterfaceCompletionHandler *This)
{
    return (ULONG)InterlockedIncrement(&((ActHandler *)This)->refs);
}

static ULONG STDMETHODCALLTYPE ah_release(IActivateAudioInterfaceCompletionHandler *This)
{
    ActHandler *h = (ActHandler *)This;
    LONG r = InterlockedDecrement(&h->refs);

    if (r == 0) {                                                          /* the system may still hold the handler after the activation call returned: it is freed by the last release */
        CloseHandle(h->done);
        free(h);
    }
    return (ULONG)r;
}

static HRESULT STDMETHODCALLTYPE ah_done(IActivateAudioInterfaceCompletionHandler *This, IActivateAudioInterfaceAsyncOperation *op)
{
    (void)op;
    SetEvent(((ActHandler *)This)->done);
    return S_OK;
}

static IActivateAudioInterfaceCompletionHandlerVtbl ah_vtbl = {ah_qi, ah_addref, ah_release, ah_done};

static IAudioClient *activate_process_loopback(void)
{
    ActParams p;
    PROPVARIANT pv;
    ActHandler *h = (ActHandler *)calloc(1, sizeof *h);
    IActivateAudioInterfaceAsyncOperation *op = NULL;
    IAudioClient *client = NULL;
    HRESULT hr, res = E_FAIL;
    IUnknown *unk = NULL;

    p.activation_type = 1;
    p.target_pid = GetCurrentProcessId();
    p.mode = 0;
    ZeroMemory(&pv, sizeof pv);
    pv.vt = VT_BLOB;
    pv.blob.cbSize = (ULONG)sizeof p;
    pv.blob.pBlobData = (BYTE *)&p;
    if (h == NULL) {
        return NULL;
    }
    h->lpVtbl = &ah_vtbl;
    h->refs = 1;                                                           /* ours */
    h->done = CreateEventA(NULL, TRUE, FALSE, NULL);
    if (h->done == NULL) {
        free(h);
        return NULL;
    }
    hr = ActivateAudioInterfaceAsync(L"VAD\\Process_Loopback", &IID_IAudioClient, &pv, (IActivateAudioInterfaceCompletionHandler *)h, &op);
    if (SUCCEEDED(hr) && WaitForSingleObject(h->done, 5000) == WAIT_OBJECT_0) {
        hr = IActivateAudioInterfaceAsyncOperation_GetActivateResult(op, &res, &unk);
        if (SUCCEEDED(hr) && SUCCEEDED(res) && unk != NULL) {
            IUnknown_QueryInterface(unk, &IID_IAudioClient, (void **)&client);
            IUnknown_Release(unk);
        }
    }
    if (op != NULL) {
        IActivateAudioInterfaceAsyncOperation_Release(op);
    }
    ah_release((IActivateAudioInterfaceCompletionHandler *)h);            /* ours; the system's reference ends it */
    return client;
}

WinLoop *wl_open(void)
{
    WinLoop *l = (WinLoop *)calloc(1, sizeof *l);
    HRESULT hr = E_FAIL;
    WORD tag;
    WAVEFORMATEX pfmt;

    if (l == NULL) {
        return NULL;
    }
    l->com = SUCCEEDED(CoInitializeEx(NULL, COINIT_MULTITHREADED));
    l->client = activate_process_loopback();
    if (l->client != NULL) {                                  /* this process only: float, two channels, 44,100 Hz, the game's own format */
        ZeroMemory(&pfmt, sizeof pfmt);
        pfmt.wFormatTag = WAVE_FORMAT_IEEE_FLOAT;
        pfmt.nChannels = 2;
        pfmt.nSamplesPerSec = 44100;
        pfmt.wBitsPerSample = 32;
        pfmt.nBlockAlign = 8;
        pfmt.nAvgBytesPerSec = 44100 * 8;
        l->fmt = (WAVEFORMATEX *)CoTaskMemAlloc(sizeof pfmt);
        if (l->fmt == NULL) {
            wl_close(l);
            return NULL;
        }
        *l->fmt = pfmt;
        l->scope = 1;
        l->channels = 2;
        l->rate = 44100.0;
        l->is_float = 1;
        hr = S_OK;
    } else {                                                  /* the whole endpoint: other programs' sound is in the capture */
        hr = CoCreateInstance(&CLSID_MMDeviceEnumerator, NULL, CLSCTX_ALL, &IID_IMMDeviceEnumerator, (void **)&l->en);
        if (SUCCEEDED(hr)) {
            hr = IMMDeviceEnumerator_GetDefaultAudioEndpoint(l->en, eRender, eConsole, &l->dev);
        }
        if (SUCCEEDED(hr)) {
            hr = IMMDevice_Activate(l->dev, &IID_IAudioClient, CLSCTX_ALL, NULL, (void **)&l->client);
        }
        if (SUCCEEDED(hr)) {
            hr = IAudioClient_GetMixFormat(l->client, &l->fmt);
        }
        if (FAILED(hr)) {
            wl_close(l);
            return NULL;
        }
        tag = l->fmt->wFormatTag;
        if (tag == WAVE_FORMAT_EXTENSIBLE) {
            const WAVEFORMATEXTENSIBLE *x = (const WAVEFORMATEXTENSIBLE *)l->fmt;
            tag = (WORD)x->SubFormat.Data1;                   /* 3 = float, 1 = PCM */
        }
        l->channels = l->fmt->nChannels;
        l->rate = (double)l->fmt->nSamplesPerSec;
        l->is_float = tag == WAVE_FORMAT_IEEE_FLOAT && l->fmt->wBitsPerSample == 32;
        if (!(l->is_float || (tag == WAVE_FORMAT_PCM && l->fmt->wBitsPerSample == 16)) || l->channels < 1) {
            wl_close(l);
            return NULL;
        }
    }
    hr = IAudioClient_Initialize(l->client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK | (l->scope ? AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM : 0), 1000000, 0, l->fmt, NULL);
    if (SUCCEEDED(hr)) {
        hr = IAudioClient_GetService(l->client, &IID_IAudioCaptureClient, (void **)&l->cap);
    }
    if (FAILED(hr)) {
        wl_close(l);
        return NULL;
    }
    l->cap_samples = (size_t)(l->rate * LOOP_SECONDS);
    l->buf = (float *)calloc(l->cap_samples, sizeof(float));
    if (l->buf == NULL) {
        wl_close(l);
        return NULL;
    }
    l->base = qpc_100ns();
    if (FAILED(IAudioClient_Start(l->client))) {
        wl_close(l);
        return NULL;
    }
    return l;
}

void wl_poll(WinLoop *l)
{
    UINT32 packet = 0;

    if (l == NULL) {
        return;
    }
    while (SUCCEEDED(IAudioCaptureClient_GetNextPacketSize(l->cap, &packet)) && packet > 0) {
        BYTE *data = NULL;
        UINT32 frames = 0;
        DWORD flags = 0;
        UINT64 dev_pos = 0, qpc = 0;
        size_t i, start;
        int c;

        if (FAILED(IAudioCaptureClient_GetBuffer(l->cap, &data, &frames, &flags, &dev_pos, &qpc))) {
            return;
        }
        l->pkts++;
        if (flags & AUDCLNT_BUFFERFLAGS_SILENT) {
            l->silent++;
        }
        if (flags & AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY) {
            l->discont++;
        }
        if ((long long)qpc < l->base) {
            l->early++;
        }
        start = (size_t)(((double)((long long)qpc - l->base)) * 1e-7 * l->rate + 0.5);
        for (i = 0; i < frames && start + i < l->cap_samples; i++) {
            float v = 0.0f;
            if (!(flags & AUDCLNT_BUFFERFLAGS_SILENT) && (long long)qpc >= l->base) {
                for (c = 0; c < l->channels; c++) {
                    v += l->is_float ? ((const float *)data)[i * (size_t)l->channels + (size_t)c] : (float)((const short *)data)[i * (size_t)l->channels + (size_t)c] / 32768.0f;
                }
                v /= (float)l->channels;
            }
            l->buf[start + i] = v;
            if (start + i + 1 > l->n) {
                l->n = start + i + 1;
            }
        }
        IAudioCaptureClient_ReleaseBuffer(l->cap, frames);
    }
}

const float *wl_samples(const WinLoop *l, size_t *n, double *rate, long long *base_100ns)
{
    *n = l->n;
    *rate = l->rate;
    *base_100ns = l->base;
    return l->buf;
}

void wl_stats(const WinLoop *l, unsigned long out[5])
{
    out[0] = l->pkts;
    out[1] = l->silent;
    out[2] = l->discont;
    out[3] = l->early;
    out[4] = l->dropped;
}

unsigned wa_write_failures(const WinAudio *a, long *last_hr)
{
    *last_hr = a->last_hr;
    return a->write_fail;
}

int wl_scope(const WinLoop *l)
{
    return l->scope;
}

/* the volume and the mute of this program's sound in the Windows volume mixer (per program, kept by Windows): a muted program is silent whatever it plays */
int wa_session_state(WinAudio *a, float *volume, int *muted)
{
    ISimpleAudioVolume *sv = NULL;
    BOOL m = FALSE;

    *volume = -1.0f;
    *muted = -1;
    if (FAILED(IAudioClient_GetService(a->client, &IID_ISimpleAudioVolume, (void **)&sv))) {
        return -1;
    }
    ISimpleAudioVolume_GetMasterVolume(sv, volume);
    ISimpleAudioVolume_GetMute(sv, &m);
    *muted = m ? 1 : 0;
    ISimpleAudioVolume_Release(sv);
    return 0;
}

/* set this stream's volume (0 to 1): the self test plays quietly */
int wa_set_volume(WinAudio *a, float volume)
{
    ISimpleAudioVolume *sv = NULL;
    HRESULT hr;

    if (FAILED(IAudioClient_GetService(a->client, &IID_ISimpleAudioVolume, (void **)&sv))) {
        return -1;
    }
    hr = ISimpleAudioVolume_SetMasterVolume(sv, volume, NULL);
    ISimpleAudioVolume_Release(sv);
    return FAILED(hr) ? -1 : 0;
}
