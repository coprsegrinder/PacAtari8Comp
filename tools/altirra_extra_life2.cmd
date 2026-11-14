# Altirra debugger commands: the extra life in a NEW GAME after the flag was set, for player 1 and for player 2, and player 2's later thresholds (OPEN-VERIFICATION.md OV-45).  Run (fast):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\extra-life2.txt -Seconds 240 -Cmd altirra_extra_life2.cmd     then   python -I tools/analyze_extra_life2.py analysis/raw-logs/extra-life2.txt
# INPUT (as altirra_fullgame2.cmd): only what the game READS from the controller registers is injected - the STICK0 bot, CONSOL (START 6, OPTION 3, SELECT 5), STRIG1 as a fallback.  g = number of games started (@t7).
#   g=0: START at title frame 120-170.
#   g=1 (one player): Pac-Man cannot die ($A923 -> $A936).  Play frame 10 (once): player 1's score := 9,990 (the next dot makes 10,000: extra life 1).  START held at play frame 300-350: a NEW GAME during play.
#   g=2 (one player): same poke at play frame 10 (extra life 2 expected: the new game cleared the flag zp_2E).  OPTION held at play frame 300-340 -> title; SELECT (one -> two players); START.
#   g=3, g=4 (two players, Pac-Man CAN die, the bot only walks, its direction a fixed pseudo-random function of the frame number, held 32 frames, so that it keeps reaching new dots): while player 2 plays, armed every 15 frames of his play, ONE poke of player 2's score at the next score addition ($B423) after arming; stage 0 := 9,990, stage 1 := 19,990, stage 2 := 99,990 (stages repeat).
#         Expected: ONE extra life for player 2 (stage 0), none at 20,000 and 100,000.  START held at his play frame 520-570 of game 3 -> game 4 (flag zp_2F cleared by the new game -> a second extra life for player 2).
#   Nothing else is written: no sound register, no life counter, no flag.
r @t1 0
r @t2 0
r @t6 0
r @t3 0
r @t4 0
r @t5 0
r @t7 0
r @t8 0
r @t9 0
bp -n a923 "r pc $a936*(@t7<3)+$a923*(@t7>=3)"
bp -n a537 "r @t7 @t7+1; r @t9 0; r @t2 0; r @t6 0"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t8 (db($19)=0)*(db($20)=0)*(db($21)=1)*(@t8+1)"
bp -n a5fd "r @t3 ((@t7=1)&(db($19)=0)&(db($20)=0)&(@t8>=300)&(@t8<=350))*1+((@t7=2)&(db($19)=0)&(db($20)=0)&(@t8>=300)&(@t8<=340))*4+((@t7=2)&(db($19)=3)&(@t1>=100)&(@t1<=108))*2+((@t7=2)&(db($19)=3)&(@t1>=160)&(@t1<=210))*1+((@t7=3)&(db($19)=0)&(db($20)=0)&(db($2b)=1)&(@t9>=520)&(@t9<=570))*1+((@t7=0)&(@t1>=120)&(@t1<=170))*1"
bp -n a5fd "r @t4 0"
bp -n a5fd "r @t5 ((@t7=3)&(db($19)=4)&(@t1>=200)&(@t1<=260))"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1-@t4"
bp -n a4ff "eb $285 1-@t5"
bp -n a82f "eb $278 ($0E*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=0))+($07*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=1))+($0D*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=2))+($0B*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=3))"
bp -n a82f "r @t9 @t9+((@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)&(db($21)=1))"
bp -n a82f "eb $202c (1-((@t7>=1)&(@t7<=2)&(@t8=10)))*db($202c)+((@t7>=1)&(@t7<=2)&(@t8=10))*$19; eb $202d (1-((@t7>=1)&(@t7<=2)&(@t8=10)))*db($202d)+((@t7>=1)&(@t7<=2)&(@t8=10))*$19; eb $202e (1-((@t7>=1)&(@t7<=2)&(@t8=10)))*db($202e)+((@t7>=1)&(@t7<=2)&(@t8=10))*$19; eb $202f (1-((@t7>=1)&(@t7<=2)&(@t8=10)))*db($202f)+((@t7>=1)&(@t7<=2)&(@t8=10))*$10"
bp -n a82f "r @t6 @t6|((@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)&(db($21)=1)&((@t9%15)=10))"
bp -n b423 "eb $2048 (1-((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)))*db($2048)+((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0))*(($10*((@t2%3)=0))+($11*((@t2%3)=1))+($19*((@t2%3)=2))); eb $2049 (1-((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)))*db($2049)+((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0))*$19; eb $204a (1-((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)))*db($204a)+((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0))*$19; eb $204b (1-((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)))*db($204b)+((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0))*$19; eb $204c (1-((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)))*db($204c)+((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0))*$10; r @t2 @t2+((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)); r @t6 @t6*(1-((@t6>0)&(@t7>=3)&(db($2b)=1)&(db($19)=0)&(db($20)=0)))"
bt a5fd "FR f=%d g=%d z19=%d z20=%d z21=%d z1a=%d cur=%d lives=%d,%d fl=%d,%d lv=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X p8=%d p9=%d" @frame @t7 db($19) db($20) db($21) db($1a) db($2b) db($2c) db($2d) db($2e) db($2f) db($30) db($31) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @t8 @t9
bt a537 "NEWGAME f=%d g=%d" @frame @t7
bt b487 "EXTRA_LIFE f=%d g=%d cur=%d lives=%d,%d fl=%d,%d" @frame @t7 db($2b) db($2c) db($2d) db($2e) db($2f)
bt ad13 "LIFE_LOST f=%d g=%d cur=%d lives=%d,%d" @frame @t7 db($2b) db($2c) db($2d)
bt aaef "GAME_OVER_TEXT f=%d g=%d" @frame @t7
