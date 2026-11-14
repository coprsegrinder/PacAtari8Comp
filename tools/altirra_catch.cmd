# Altirra debugger commands: who catches Pac-Man while the frightened phase is running? (docs/14-levels.md, board 71 observation; docs/18)
# Level counter 70 (the first endless-frightened level) is poked right after the start levels ($ADFD). Aids as in altirra_transitions.cmd (emulated RAM/PC only): Pac-Man cannot die ($A923 skipped),
# every 2048 frames the power-pellet flags are refilled and Pac-Man is moved onto a power pellet (frightened) and later onto ghost (cycle mod 4), which eats it. No dot-count pokes.
# Extra evidence line CAUGHT at $A923 (reached only for a ghost that is not eaten and has bit 7 clear): the four ghost states, the phase FC, FD, frame. Run:
#   powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\catch.txt -Seconds 150 -Cmd altirra_catch.cmd   then  python -I tools/analyze_catch_log.py analysis/raw-logs/catch.txt
bp -n a504 "r pc $a537; bc 0"
bp -n adfd "eb $30 $46; eb $31 $46"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 (@frame%$800); eb $89 db($BB83+((@frame/$80)%10)); eb $8e db($BB8D+((@frame/$500)%10)); r @t7 ((@t5>=$F0)&(@t5<$F8)); eb $32 (@t7*$0F)+(1-@t7)*db($32); r @t7 ((@t5>=$100)&(@t5<$110)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t6 ((@frame/$800)%4); r @t7 ((@t5>=$180)&(@t5<$190)); eb $8e db($8e)+@t7*(db($8a+@t6)-db($8e)); eb $89 db($89)+@t7*(db($85+@t6)-db($89))"
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
bt a800 "ST site=A800 ghost=0 old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" db($ce) db($34)+256*db($36) db($ad) db($ca) db($8a) db($85) db($fd) @frame
bt a886 "GHOST_EATEN ghost=%d frame=%d" x @frame
bt b3de "PELLET frame=%d" @frame
bt adaf "INIT_BOARD frame=%d" @frame
bt a923 "CAUGHT ghost=%d g0=$%02X g1=$%02X g2=$%02X g3=$%02X FC=%d FD=%d pacx=%d pacy=%d frame=%d" x db($ce) db($cf) db($d0) db($d1) db($fc) db($fd) db($8e) db($89) @frame
bt af77 "PHASE FC=%d table=%d frame=%d" db($fc) db($672+db($30)) @frame
