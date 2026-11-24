# OV-65: the outcome counters of the key loop (tools/make_keyloop_cmd.py); the counters are 16-bit words at $4300, two a branch (taken, not taken), saturating at 65535 (so that 'ever happened' survives)
bp -n a4ed "ew $4600 (dw($4600)+(dw($4600)<65535))"
bp -n a4f1 "ew $4602 (dw($4602)+(dw($4602)<65535))"
bt a5fd "KB f=%d %d %d" @frame dw($4600) dw($4602)
