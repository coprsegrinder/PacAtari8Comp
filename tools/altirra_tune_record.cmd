# Altirra debugger commands for recording the start tune and what follows it (docs/21, tools/record_tune.ps1): the only input is ONE START press, injected at the CONSOL read like altirra_fullgame.cmd, late enough (title frame 900, about 15 s after the title appears) that the audio recording has started first. Nothing else is touched; nobody steers, so Pac-Man is eventually caught.
# Trace: every write to the POKEY sound registers $D200-$D208 with address, value, PC, frame and beam position vpos/hpos (SNDW; frame + beam position = the exact emulated time of the write), a short line every frame (FR; at about 100 bytes it also makes Altirra flush the log in 4 KB chunks several times a second, so the trace is complete up to the last fraction of a second), and the game events.
# Analysis: python -I tools/analyze_tail_sound.py  (aligns the trace with the recording and renders the POKEY model from the logged writes).
r @t1 0
r @t3 0
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 (@t1>=900)&(@t1<=950)"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bt a5fd "FR f=%d z19=%d z1c=%d z1e=%d z20=%d z21=%d z22=%d a3=%d lives=%d,%d t1=%d" @frame db($19) db($1c) db($1e) db($20) db($21) db($22) db($a3) db($2c) db($2d) @t1
bta w d200 L9 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos
bt a537 "NEWGAME f=%d" @frame
bt a7c8 "READY_DRAW f=%d" @frame
bt a7f5 "TUNE f=%d x=%d" @frame db($a3)
bt a800 "START_PLAY f=%d" @frame
bt a923 "DEATH_START f=%d" @frame
bt aef1 "DEATH_DONE f=%d" @frame
bt aae6 "INITBOARD_CALL f=%d" @frame
