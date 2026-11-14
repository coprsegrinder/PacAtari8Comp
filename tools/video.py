"""Video standard of the traced machine (OPEN-VERIFICATION.md OV-42).  The default is NTSC (the Altirra 800 / OS-B setup of every earlier session);
PACMAN_VIDEO=pal in the environment switches the analyzers to the PAL timing of the same machine run with /pal:
  NTSC: 262 lines x 114 cycles, CPU 1,789,772.7 Hz (315 MHz / 88 / 2), 59.9227 frames/s
  PAL : 312 lines x 114 cycles, CPU 1,773,447.0 Hz (14,187,576 Hz / 8), 49.8607 frames/s
The cycle at which the OS leaves POKEY's initialisation mode (SKCTL := 3) is the zero of the noise generators (tools/pokey_noise.py); the PAL boot has its own, read from the trace.
"""
import os
import re

PAL = os.environ.get("PACMAN_VIDEO", "ntsc").lower() == "pal"
LINES = 312 if PAL else 262
CPU = 1773447.0 if PAL else 315e6 / 88 / 2
FRAME_CYC = LINES * 114
FRAME_HZ = CPU / FRAME_CYC
HALF_CYCLE_RATE = CPU / 28 if PAL else 63920.0

_SKCTL3 = re.compile(r"SNDW a=\$D20F v=\$03 pc=\$([0-9A-F]{4}) f=(\d+) vp=(\d+) hp=(\d+)")


def skctl_t0(trace_path):
    """Cycle of the first write of $03 to SKCTL ($D20F) in a trace that logs it (the OS's POKEY initialisation), or None."""
    with open(trace_path, errors="replace") as fh:
        for line in fh:
            m = _SKCTL3.match(line)
            if m:
                return int(m.group(2)) * FRAME_CYC + int(m.group(3)) * 114 + int(m.group(4))
    return None
