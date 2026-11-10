# Altirra debugger commands: unattended patrol-route coverage test (step C11, nibble map).
# TEST AID (changes the emulated PC only, never the ROM): a ghost touching Pac-Man (non-frightened) does not kill him
# (PC skips the death branch at $A923), so the run needs no input. Route choice stays the game's own (RANDOM).
# (Writing the A register from a breakpoint does not take effect in Altirra, so routes cannot be forced; run long instead.)
# start the game without a key press: the first time the main loop polls CONSOL ($A504) jump to the start-game code ($A537), then
# delete this breakpoint (it is breakpoint 0, the first command of the file) so the busy poll loop is not slowed down
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
# Second test aids, used by run_patrol_trace.ps1 -Complete (default off): (a) a ghost that sees Pac-Man does not switch to chase
# (PC skips $BAB7-$BABD), (b) when the patrol phase of route 3, 12 or 15 begins its timer is refilled to $FF so a whole loop can be seen.
# (Debugger arguments are split at spaces, so the expression below has none.)
#COMPLETE bp -n bab7 "r pc $babf"
#COMPLETE bp -n b897 "eb ($ca+x) db($ca+x)+((db($ba+x)=3)|(db($ba+x)=12)|(db($ba+x)=15))*($ff-db($ca+x))"
# --- evidence
bt b871 "ROUTE_SELECT ghost=%d route=%d target_x=$%02X target_y=$%02X timer=$%02X" x db($ba+x) db($c2+x) db($c6+x) db($ca+x)
bt b855 "STATE ghost=%d new=$%02X why=to_patrol_travel timer=$%02X" x db($ce+x) db($ca+x)
bt b897 "STATE ghost=%d new=$%02X why=target_reached_patrol_starts" x db($ce+x)
bt b8c9 "STATE ghost=%d new=$%02X why=head_for_corner" x db($ce+x)
bt b8ef "STATE ghost=%d new=$%02X why=chase_or_B8ED" x db($ce+x)
bt b6d2 "STATE ghost=%d new=$%02X why=B6D0" x db($ce+x)
bt a88a "STATE ghost=%d new=$%02X why=eaten" x db($ce+x)
bt babb "STATE ghost=%d new=$%02X why=BAB9" x db($ce+x)
bt b628 "STATE ghost=%d new=$%02X why=B626" x db($ce+x)
bt b766 "STATE ghost=%d new=$%02X why=B764" x db($ce+x)
bt b8e8 "CORNER_REACHED ghost=%d" x
bt b8b6 "PATROL_WRAP ghost=%d route=%d" x db($ba+x)
bt b8b2 "PATROL_ROUTE ghost=%d route=%d step=%d dir=$%X ypos=$%02X xpos=$%02X" x db($ba+x) db($be+x) db($6ae+y) db($85+x) db($8a+x)
bt b4d2 "JUNCTION ent=%d ptr=$%04X col=%d mask=$%X ypos=$%02X xpos=$%02X" db($2a) dw($3c) y db(dw($3c)+y) db($85+db($2a)) db($8a+db($2a))
bt b842 "START_ROUTE ghost=%d step=%d dir=$%X" x y db(dw($3c)+y)
