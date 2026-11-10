# Altirra debugger commands: unattended level sweep over levels 42-199 (zero-based counter), which had only been derived from formulas (step C11, docs/14-levels.md).
# Same TEST AIDS and evidence lines as tools/altirra_levels.cmd, but NO level jumps: the counters are set to 41 ($29; the debugger reads numbers as hex) right after the start levels ($ADFD) and each cycle of $600 frames the game's own AdvanceLevel adds 1.
# Run:  powershell -File toolsun_patrol_trace.ps1 -Log <log> -Seconds <n> -Cmd altirra_levels_42_199.cmd   then  python -I tools/analyze_levels_log.py <log>
un_patrol_trace.ps1 -Log <log> -Seconds <n> -Cmd altirra_levels_30_98.cmd   then  python -I tools/analyze_levels_log.py <log>
bp -n a504 "r pc $a537; bc 0"
bp -n adfd "eb $30 $29; eb $31 $29"
bp -n a923 "r pc $a936"
bp -n adf1 "r @t0 (@frame/$600); r @t1 (@frame/$600)"
bp -n a82f "r @t5 (@frame%$600); r @t6 (@frame/$600); r @t7 ((@t6!=@t0)&(@t6>0)); eb $26 @t7|db($26); r @t0 @t6; r @t7 ((@t5>=$200)&(@t1!=@t6)); eb ($34+db($2b)) @t7*$50+(1-@t7)*db($34+db($2b)); r @t1 (@t1+@t7*(@t6-@t1)); r @t7 ((@t5>=$240)&(@t5<$250)); eb $8e db($8e)+@t7*($7C-db($8e)); eb $89 db($89)+@t7*($84-db($89)); r @t7 ((@t5>=$280)&(@t5<$290)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89))"
bt ac7e "LEVEL_ADVANCE level_p1=%d level_p2=%d frame=%d" db($30) db($31) @frame
bt b5c4 "MOVE_DELAY ent=%d delay=%d cycle=%d level=%d" x db($b5+x) db($b0+x) db($30)
bt b3ff "FRIGHT_TIME level=%d FD=$%02X" db($30) db($fd)
bt af77 "FRIGHT_END_CHECK level=%d table=%d FC=%d FD=%d" db($30) db($672+x) db($fc) db($fd)
bt b677 "BONUS_APPEARS level=%d glyph=$%02X,$%02X" db($30) db($df3) db($df4)
bt a95a "BONUS_GLYPHS level=%d g=$%02X $%02X $%02X $%02X $%02X" db($30) db($df1) db($df2) db($df3) db($df4) db($df5)
bt a989 "BONUS_SCORE level=%d thousands=%d hundreds=%d" db($30) db($96) db($97)
bt ad0d "INDICATOR level=%d row=$%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X" db($30) db($f86) db($f87) db($f88) db($f89) db($f8a) db($f8b) db($f8c) db($f8d) db($f8e) db($f8f) db($f90) db($f91) db($f92) db($f93)
bt ae3c "RELEASE_TIMERS level=%d t1=$%02X t2=$%02X t3=$%02X frame=%d" db($30) db($cb) db($cc) db($cd) @frame
bt adaf "LEVEL_SETUP level=%d frame=%d" db($30) @frame
bt b758 "RELEASE ghost=%d state=$%02X frame=%d" x db($ce+x) @frame
bt ad0d "ITEM_COLOR level=%d zpA0=$%02X" db($30) db($a0)

