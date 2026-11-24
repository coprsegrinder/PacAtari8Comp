# Altirra debugger commands: the MIRROR of altirra_player2_lives.cmd (OV-58 follow-up, stage 53 coverage): a two-player game where PLAYER 2 runs out of lives FIRST while player 1 still has lives - the path of TurnControl at $AACA-$AAD2
# (player 1 has lives, player 2 has none: the turn goes back to player 1, TurnSwitchState := 1, WaitTimer := $30), which no other harness reaches.
# TEST AIDS (emulated machine only): the game is started with zp_1A = 1 ($A504 -> $A537); at $ADFD the life counters are set to 2 (player 1) and 1 (player 2); nothing else is changed: Pac-Man stands still and the ghosts kill him by themselves.
# Run: powershell -File toolsun_patrol_trace.ps1 -Log analysisaw-logs\player1_survives.txt -Seconds 120 -Cmd altirra_player1_survives.cmd
bp -n a504 "r pc $a537; eb $1a 1; bc 0"
bp -n adfd "eb $2c 2; eb $2d 1"
bt adaf "LEVEL_SETUP level=%d frame=%d player=%d" db($30+db($2b)) @frame db($2b)
bt aa61 "SWITCH to=0 from=%d 1a=%d lives=%d,%d level=%d,%d flags=$%02X,$%02X dots=%d,%d eml=%d,%d zp43=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X frame=%d" db($2b) db($1a) db($2c) db($2d) db($30) db($31) db($32) db($33) db($34)+256*db($36) db($35)+256*db($37) db($2e) db($2f) db($43) db($44) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @frame
bt aa8b "SWITCH to=1 from=%d 1a=%d lives=%d,%d level=%d,%d flags=$%02X,$%02X dots=%d,%d eml=%d,%d zp43=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X frame=%d" db($2b) db($1a) db($2c) db($2d) db($30) db($31) db($32) db($33) db($34)+256*db($36) db($35)+256*db($37) db($2e) db($2f) db($43) db($44) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @frame
bt ad13 "LIFE_LOST player=%d lives=%d,%d frame=%d" db($2b) db($2c) db($2d) @frame
bt b487 "EXTRA_LIFE player=%d frame=%d" db($2b) @frame
bt adf1 "NEW_GAME frame=%d" @frame
bt adaf "BOARD_START cur=%d lives=%d,%d level=%d,%d flags=$%02X,$%02X dots=%d,%d eml=%d,%d zp43=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X frame=%d" db($2b) db($2c) db($2d) db($30) db($31) db($32) db($33) db($34)+256*db($36) db($35)+256*db($37) db($2e) db($2f) db($43) db($44) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @frame
bt aaef "NO_LIVES_END_OF_TURN player=%d lives=%d,%d frame=%d" db($2b) db($2c) db($2d) @frame
bt aae0 "TURN_CONTINUES player=%d lives=%d,%d frame=%d" db($2b) db($2c) db($2d) @frame
bt a82f "T cur=%d lives=%d,%d z23=%d frame=%d" db($2b) db($2c) db($2d) db($23) @frame
bt a5fd "V cur=%d lives=%d,%d z23=%d frame=%d" db($2b) db($2c) db($2d) db($23) @frame

bt aaca "P2_OUT_P1_CONTINUES f=%d lives=%d,%d switchstate=%d" @frame db($2c) db($2d) db($23)
bt aa2d "TURN_CONTROL f=%d player=%d lives=%d,%d" @frame db($2b) db($2c) db($2d)
