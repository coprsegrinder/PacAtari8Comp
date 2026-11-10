# Altirra debugger commands: a frightened ghost that is still INSIDE the ghost house ($00 -> $80 at the power pellet, back to $00 when the time ends, $AF9A). Not seen before (docs/18, "Not covered").
# TEST AIDS (emulated RAM/PC only): Pac-Man cannot die ($A923 skipped); on every board a power pellet is eaten at a different delay after the board set-up (28 + 20*(level mod 8) frames, so that the ghosts are in
# different house states at that moment); the level-complete flag ($26) is set 1520 frames after the set-up. Level counter starts at 0 and the game advances it itself.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log F:\Ports\house.txt -Seconds 130 -Cmd altirra_house_frightened.cmd   then  python -I tools/analyze_house_frightened_log.py F:/Ports/house.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adaf "r @t1 @frame"
bp -n a82f "r @t5 (@frame-@t1); r @t6 (db($30)%8); r @t7 ((@t5>=($28+$14*@t6))&(@t5<($38+$14*@t6))); eb $32 (@t7*$0F)+(1-@t7)*db($32); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t7 (@t5=$5F0); eb $26 @t7|db($26)"
bt af8c "FRIGHT_ENDS ghost=%d state=$%02X level=%d frame=%d" x db($ce+x) db($30) @frame
bt ac7e "LEVEL_ADVANCE level=%d frame=%d" db($30) @frame
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
