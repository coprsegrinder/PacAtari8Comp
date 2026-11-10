# Altirra debugger commands: force StartLevel ($1B) through 0..13 on the title menu and log the icon glyph codes the title code writes (step C11).
# TEST AID (emulated RAM only): StartLevel is set from the frame counter, one value per 64 frames; the real code at $A767-$A772 then looks up LevelIconCodes.
bp -n a767 "eb $1b ((@frame/$40)%14)"
bt a775 "TITLE_ICON startlevel=%d g1=$%02X g2=$%02X frame=%d" db($1b) db($1cc6) db($1cc7) @frame
