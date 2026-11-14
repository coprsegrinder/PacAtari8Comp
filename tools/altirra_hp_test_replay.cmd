# Altirra debugger commands for the high-pass test (tools/hp_test.py, OPEN-VERIFICATION.md OV-13d): injects the program of tools/mixer_test.py with 24 configurations of the sweep's channels 1, 3, 4 and AUDCTL = $84.
# Use with tools/record_tune.ps1 -Cmd altirra_hp_test.cmd -Out analysis/hp-test-recorded.wav -Trace analysis/raw-logs/hp-test.txt -Seconds 40, then  python -I tools/hp_test.py --analyze analysis/hp-test-recorded.wav analysis/raw-logs/hp-test.txt
# The ROM is never changed.  Every write to $D200-$D208 is traced (SNDW); the final burst of writes to $07FF (FLUSH lines) forces the log to be written out before Altirra is closed.
bta w d200 L9 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos
bta w 07ff L1 "FLUSH f=%d  ................................................................................................................................" @frame
bp -n a5fd "eb $0600 $78 $A9 $00 $8D $0E $D4 $8D $0E $D2 $A2 $00 $BD $00 $07 $F0 $26"
bp -n a5fd "eb $0610 $85 $FE $E8 $A0 $00 $BD $00 $07 $99 $00 $D2 $E8 $C8 $C0 $09 $D0"
bp -n a5fd "eb $0620 $F4 $AD $0B $D4 $C9 $40 $D0 $F9 $AD $0B $D4 $C9 $40 $F0 $F9 $C6"
bp -n a5fd "eb $0630 $FE $D0 $EE $4C $0B $06 $A9 $00 $A2 $08 $9D $00 $D2 $CA $10 $FA"
bp -n a5fd "eb $0640 $A2 $00 $8D $FF $07 $CA $D0 $FA $4C $48 $06"
bp -n a5fd "eb $0700 $01 $7D $A4 $00 $00 $00 $A0 $80 $A4 $84 $01 $79 $A8 $00 $00 $7D"
bp -n a5fd "eb $0710 $A8 $7D $A8 $84 $01 $76 $A4 $00 $00 $7D $A8 $79 $A4 $84 $01 $72"
bp -n a5fd "eb $0720 $A8 $00 $00 $76 $A8 $76 $A8 $84 $01 $6F $A4 $00 $00 $76 $A8 $72"
bp -n a5fd "eb $0730 $A4 $84 $01 $6B $A8 $00 $00 $6F $A8 $6F $A8 $84 $01 $68 $A4 $00"
bp -n a5fd "eb $0740 $00 $6F $A8 $6B $A4 $84 $01 $64 $A8 $00 $00 $68 $A8 $68 $A8 $84"
bp -n a5fd "eb $0750 $01 $61 $A4 $00 $00 $68 $A8 $64 $A4 $84 $01 $5D $A8 $00 $00 $61"
bp -n a5fd "eb $0760 $A8 $61 $A8 $84 $01 $5A $A4 $00 $00 $61 $A8 $5D $A4 $84 $01 $56"
bp -n a5fd "eb $0770 $A8 $00 $00 $5A $A8 $5A $A8 $84 $01 $53 $A4 $00 $00 $5A $A8 $56"
bp -n a5fd "eb $0780 $A4 $84 $01 $4F $A8 $00 $00 $53 $A8 $53 $A8 $84 $01 $4C $A4 $00"
bp -n a5fd "eb $0790 $00 $53 $A8 $4F $A4 $84 $01 $48 $A8 $00 $00 $4C $A8 $4C $A8 $84"
bp -n a5fd "eb $07A0 $01 $45 $A4 $00 $00 $4C $A8 $48 $A4 $84 $01 $41 $A8 $00 $00 $45"
bp -n a5fd "eb $07B0 $A8 $45 $A8 $84 $01 $3E $A4 $00 $00 $45 $A8 $41 $A4 $84 $01 $3A"
bp -n a5fd "eb $07C0 $A8 $00 $00 $3E $A8 $3E $A8 $84 $01 $37 $A4 $00 $00 $3E $A8 $3A"
bp -n a5fd "eb $07D0 $A4 $84 $01 $33 $A8 $00 $00 $37 $A8 $37 $A8 $84 $01 $30 $A4 $00"
bp -n a5fd "eb $07E0 $00 $37 $A8 $33 $A4 $84 $01 $2C $A8 $00 $00 $30 $A8 $30 $A8 $84"
bp -n a5fd "eb $07F0 $00"
bp -n a5fd "r pc $a5fd+($0600-$a5fd)*(@frame>=900)"
