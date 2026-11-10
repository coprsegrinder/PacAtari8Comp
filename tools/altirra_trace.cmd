# Altirra debugger commands for step C11 evidence (run with tools/trace_altirra.ps1).
# One log line per hit. Formats use $ for hex.
# --- control: the game reads $A003 (start of the character-set stream) once at boot; proves read-watching works
bta r a003 L1 "CONTROL_READ_A003 value=$%02X pc=$%04X" db(@address) pc
# --- $A000-$A002: must never be read
bta r a000 L3 "READ_A000_A002 addr=$%04X value=$%02X pc=$%04X" @address db(@address) pc
# --- SmallTable_BB56 / chomp animation (reads at $B2DC) and death animation (reads at $AF26)
bt b2dc "CHOMP_OFFSET_READ ChompPhase_AB=$%02X X=$%02X" db($ab) x
bt af26 "DEATH_PLOT_READ frame_EB=$%02X X=$%02X" db($eb) x
bt af3e "STAR_SHAPE_READ frame_EB=$%02X" db($eb)
bt ae76 "DEATH_ANIM_START"
# --- ghost-eaten scores
bt b3de "POWER_PELLET_EATEN E9_before=$%02X" db($e9)
bt a886 "GHOST_EATEN E9_before_inc=$%02X" db($e9)
bt a8d3 "GHOST_SCORE_PTR_READ index*2=Y=$%02X" y
bt b423 "ADD_TO_SCORE digits=$%02X$%02X$%02X$%02X$%02X$%02X" db($94) db($95) db($96) db($97) db($98) db($99)
# --- nibble map ($0600-$07D7) evidence. NOTE: Altirra's expression language has NO accumulator variable
# (variables are pc x y s p only; a bare "a" is the hex number $A). Values are therefore read from memory after the store.
# junction table read (only when an entity stands on a lattice point): entity, row pointer, column, mask read from the table
bt b4d2 "JUNCTION ent=%d ptr=$%04X col=%d mask=$%X ypos=$%02X xpos=$%02X" db($2a) dw($3c) y db(dw($3c)+y) db($85+db($2a)) db($8a+db($2a))
# direction tables: reverse direction (power pellet; logged after the store) and the no-reverse filter at junctions (after the store)
bt b41d "GHOST_REVERSE ghost=%d old=$%X new=$%X" x y db($8f+x)
bt b4e6 "NO_REVERSE_FILTER dir=$%X result=$%X" y db($2a)
# movement delay reload per entity (4 = Pac-Man), value read back after the store
bt b5c4 "MOVE_DELAY ent=%d delay=%d cycle=%d level=%d" x db($b5+x) db($b0+x) db($30)
# frightened mode: initial countdown (zp_FD, after the store) and the end test against the per-level count
bt b3ff "FRIGHT_TIME level=%d FD=$%02X" db($30) db($fd)
bt af77 "FRIGHT_END_CHECK table=%d FC=%d FD=%d" db($672+x) db($fc) db($fd)
# routes: start routes ($0686..) and patrol routes ($06AE..)
bt b842 "START_ROUTE ghost=%d step=%d dir=$%X ypos=$%02X xpos=$%02X" x y db(dw($3c)+y) db($85+x) db($8a+x)
bt b8b2 "PATROL_ROUTE ghost=%d route=%d step=%d dir=$%X" x db($ba+x) db($be+x) db($6ae+y)
# bonus item score: the score digits at the moment AddToScore runs are already logged as ADD_TO_SCORE
# heat map: which bytes the CPU read/wrote in $0600-$07FF, dumped at the first ghost eaten and at death
hme on
bp -n a886 "hma $0600 L$0200"
bp -n ae76 "hma $0600 L$0200"
