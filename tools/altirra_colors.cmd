# Altirra debugger commands: where the colour tables ($BBE2-$BBF1) go at run time (step C11).
# The game is started by jumping to its start-game code (self-clearing breakpoint 0); ghosts do not kill Pac-Man (test aids, emulated machine only).
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
# the loaders: LoadShadowColors (ColorsGame -> PCOLR0-3, COLOR0-3), InitDisplay2 (ColorsTitle -> COLOR0-3), start of the DLI colour values (ColorsDli -> zp $5E-$61)
bt b11e "LOAD_SHADOW_COLORS pcolr=$%02X $%02X $%02X $%02X color=$%02X $%02X $%02X $%02X" db($2c0) db($2c1) db($2c2) db($2c3) db($2c4) db($2c5) db($2c6) db($2c7)
bt a62f "INIT_DISPLAY2_COLORS color=$%02X $%02X $%02X $%02X" db($2c4) db($2c5) db($2c6) db($2c7)
# NOTE: this writes about 5 lines per frame; run it for 15-20 s only (a 40 s run produced 150 MB).
# what the hardware really gets: every write to COLPF0-3 / COLBK with its scanline (vpos) and the DLI counter zp_18
bta w d016 L5 "GTIA_COL%d=$%02X vpos=%d dli=%d" (@address-$d016) @value vpos db($18)
