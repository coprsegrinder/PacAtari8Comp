# Altirra debugger commands for the high-pass test (tools/hp_test.py, OPEN-VERIFICATION.md OV-13d): injects the program of tools/mixer_test.py with 21 configurations of the sweep's channels 1, 3, 4 and AUDCTL = $84.
# Use with tools/record_tune.ps1 -Cmd altirra_hp_test.cmd -Out analysis/hp-test-recorded.wav -Trace analysis/raw-logs/hp-test.txt -Seconds 40, then  python -I tools/hp_test.py --analyze analysis/hp-test-recorded.wav analysis/raw-logs/hp-test.txt
# The ROM is never changed.  Every write to $D200-$D208 is traced (SNDW); the final burst of writes to $07FF (FLUSH lines) forces the log to be written out before Altirra is closed.
bta w d200 L9 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos
bta w 07ff L1 "FLUSH f=%d  ................................................................................................................................" @frame
bp -n a5fd "eb $0600 $78 $A9 $00 $8D $0E $D4 $8D $0E $D2 $A2 $00 $BD $00 $07 $F0 $26"
bp -n a5fd "eb $0610 $85 $FE $E8 $A0 $00 $BD $00 $07 $99 $00 $D2 $E8 $C8 $C0 $09 $D0"
bp -n a5fd "eb $0620 $F4 $AD $0B $D4 $C9 $40 $D0 $F9 $AD $0B $D4 $C9 $40 $F0 $F9 $C6"
bp -n a5fd "eb $0630 $FE $D0 $EE $4C $0B $06 $A9 $00 $A2 $08 $9D $00 $D2 $CA $10 $FA"
bp -n a5fd "eb $0640 $A2 $00 $8D $FF $07 $CA $D0 $FA $4C $48 $06"
bp -n a5fd "eb $0700 $03 $72 $A0 $00 $14 $72 $A0 $72 $A0 $00 $03 $72 $A0 $00 $10 $72"
bp -n a5fd "eb $0710 $A0 $72 $A0 $00 $14 $72 $A8 $00 $10 $00 $A0 $00 $A0 $00 $03 $72"
bp -n a5fd "eb $0720 $A0 $00 $14 $72 $A0 $72 $A0 $00 $03 $72 $A0 $00 $10 $72 $A0 $72"
bp -n a5fd "eb $0730 $A0 $00 $14 $72 $A0 $00 $10 $00 $A0 $72 $A8 $00 $03 $72 $A0 $00"
bp -n a5fd "eb $0740 $14 $72 $A0 $72 $A0 $00 $03 $72 $A0 $00 $10 $72 $A0 $72 $A0 $00"
bp -n a5fd "eb $0750 $14 $72 $A0 $00 $10 $00 $A0 $76 $A8 $00 $03 $72 $A0 $00 $14 $72"
bp -n a5fd "eb $0760 $A0 $72 $A0 $00 $03 $72 $A0 $00 $10 $72 $A0 $72 $A0 $00 $14 $72"
bp -n a5fd "eb $0770 $A0 $00 $10 $00 $A0 $72 $A8 $00 $03 $72 $A0 $00 $14 $72 $A0 $72"
bp -n a5fd "eb $0780 $A0 $00 $03 $72 $A0 $00 $10 $72 $A0 $72 $A0 $00 $14 $72 $A0 $00"
bp -n a5fd "eb $0790 $10 $00 $A0 $6E $A8 $00 $03 $72 $A0 $00 $14 $72 $A0 $72 $A0 $00"
bp -n a5fd "eb $07A0 $03 $72 $A0 $00 $10 $72 $A0 $72 $A0 $00 $14 $72 $A8 $00 $10 $00"
bp -n a5fd "eb $07B0 $A0 $6E $A0 $00 $03 $72 $A0 $00 $14 $72 $A0 $72 $A0 $00 $03 $72"
bp -n a5fd "eb $07C0 $A0 $00 $10 $72 $A0 $72 $A0 $00 $14 $78 $A8 $00 $10 $00 $A0 $6E"
bp -n a5fd "eb $07D0 $A0 $00 $00"
bp -n a5fd "r pc $a5fd+($0600-$a5fd)*(@frame>=900)"
