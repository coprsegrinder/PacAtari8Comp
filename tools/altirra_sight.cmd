# Altirra debugger commands: live check of the ghost sight test (GhostSeesPacMan $BA19) against tools/sight_model.py (step C11).
# TEST AIDS (emulated RAM / PC only): start the game by jumping to its start-game code (self-clearing breakpoint 0); ghosts do not kill Pac-Man;
# Pac-Man is moved to a different junction row every 128 frames and a different junction column every 1280 frames, so ghosts line up with him often.
# (Debugger arguments are split at spaces, so the expressions contain none.)
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "eb $89 db($BB83+((@frame/$80)%10)); eb $8e db($BB8D+((@frame/$500)%10))"
# --- evidence: inputs of every same-row / same-column sight test and whether it ended in $BAB7 (chase)
bt ba26 "SIGHT_ROW ghost=%d gx=%d gy=%d gdir=%d px=%d py=%d rtc=%d" x db($8a+x) db($85+x) db($8f+x) db($8e) db($89) db($14)
bt ba6b "SIGHT_COL ghost=%d gx=%d gy=%d gdir=%d px=%d py=%d rtc=%d" x db($8a+x) db($85+x) db($8f+x) db($8e) db($89) db($14)
bt bab7 "SIGHT_YES ghost=%d" x
