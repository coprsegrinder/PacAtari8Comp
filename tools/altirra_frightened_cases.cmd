# Altirra debugger commands: the frightened-ghost cases that were not provoked before - OPEN-VERIFICATION.md OV-35, docs/17, docs/18 ('Not covered').
# Three kinds of boards, in turn (board index b = 0, 1, 2, ...; kind = b mod 3, d = b div 3; the level counter is set to b mod 6 at every board set-up so that every board has a frightened time):
#  kind 0: a power pellet is eaten 60 + 36 * (d mod 16) frames after the set-up (frames 60-600: ghost 0 and the released ghosts are on their START ROUTE, state $01 -> $81), to see what a frightened start-route ghost does;
#  kind 1: a pellet at frame 700; at frames 750-789 ghosts 1 and 2 are put on ghost 0's square and Pac-Man too: TWO (three) frightened ghosts touch him in the same frame;
#  kind 2: a pellet at frame 700; at 750-755 Pac-Man is put on ghost 0 (it is eaten), then from 760 to 1399 Pac-Man stands on the DOOR SQUARE (124,100) while the eyes come back to it.
# TEST AIDS (emulated RAM/PC only, as in altirra_house_frightened.cmd): Pac-Man cannot die ($A923 skipped); the pellet is eaten by putting Pac-Man on it (x $3A, y $3C) and marking the pellets present ($32) for 16 frames; positions are written to $85-$8E; the level-complete flag ($26) is set 1520 frames after the set-up.
# Run:  powershell -File toolsun_patrol_trace.ps1 -Log analysisaw-logsrightened-cases.txt -Seconds 300 -Cmd altirra_frightened_cases.cmd      then  python -I tools/analyze_frightened_cases.py analysis/raw-logs/frightened-cases.txt
r @t0 0
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adaf "r @t0 @t0+1; r @t1 @frame; eb $30 ((@t0-1)%6); eb $31 ((@t0-1)%6)"
bp -n a82f "r @t5 (@frame-@t1); r @t6 ((@t0-1)%3); r @t4 (60+36*(((@t0-1)/3)%16)); r @t4 (@t4*(@t6=0)+700*(@t6>0))"
bp -n a82f "r @t7 ((@t5>=@t4)&(@t5<(@t4+16)))"
bp -n a82f "r @t8 ((@t6=1)&(@t5>=750)&(@t5<790))"
bp -n a82f "r @t9 ((@t6=2)&(@t5>=750)&(@t5<756))"
bp -n a82f "r @t2 ((@t6=2)&(@t5>=760)&(@t5<1400))"
bp -n a82f "eb $32 (@t7*$0F)+(1-@t7)*db($32); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89))"
bp -n a82f "eb $86 @t8*db($85)+(1-@t8)*db($86); eb $8b @t8*db($8a)+(1-@t8)*db($8b); eb $87 @t8*db($85)+(1-@t8)*db($87); eb $8c @t8*db($8a)+(1-@t8)*db($8c); eb $89 @t8*db($85)+(1-@t8)*db($89); eb $8e @t8*db($8a)+(1-@t8)*db($8e)"
bp -n a82f "eb $89 @t9*db($85)+(1-@t9)*db($89); eb $8e @t9*db($8a)+(1-@t9)*db($8e)"
bp -n a82f "eb $89 @t2*100+(1-@t2)*db($89); eb $8e @t2*124+(1-@t2)*db($8e)"
bp -n a82f "r @t3 (@t5=$5F0); eb $26 @t3|db($26)"
bt a888 "ST site=A888 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt afa0 "ST site=AFA0 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b40a "ST site=B40A ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b626 "ST site=B626 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b6d0 "ST site=B6D0 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b756 "ST site=B756 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b764 "ST site=B764 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b853 "ST site=B853 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b895 "ST site=B895 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b8c7 "ST site=B8C7 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b8ed "ST site=B8ED ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt bab9 "ST site=BAB9 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b3de "PELLET frame=%d" @frame
bt adaf "INIT_BOARD frame=%d board=%d level=%d" @frame @t0 db($30)
bt a886 "GHOST_EATEN ghost=%d eaten=%d frame=%d" x db($e9) @frame
bt af8c "FRIGHT_ENDS ghost=%d state=$%02X frame=%d" x db($ce+x) @frame
bt a5fd "FR f=%d b=%d st=%02X,%02X,%02X,%02X x=%d,%d,%d,%d y=%d,%d,%d,%d d=%d,%d,%d,%d rs=%d,%d,%d,%d p=%d,%d ge=%d e5=%d fc=%d fd=%d t5=%d" @frame @t0 db($ce) db($cf) db($d0) db($d1) db($8a) db($8b) db($8c) db($8d) db($85) db($86) db($87) db($88) db($8f) db($90) db($91) db($92) db($d2) db($d3) db($d4) db($d5) db($8e) db($89) db($e9) db($e5) db($fc) db($fd) @t5
