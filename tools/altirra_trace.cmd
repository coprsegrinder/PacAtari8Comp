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
