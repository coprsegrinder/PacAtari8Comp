# Altirra debugger commands: a game played by a BOT, with NO aids, traced for ALL SOUND (OPEN-VERIFICATION.md OV-46).  Same trace as altirra_sound_natural.cmd, same analyzers, but the keys come from the schedule below.
# NOTHING in the game is written: no pokes, no invulnerability, no PC move, no life refill.  Only the values the game READS from the controller registers are injected (as altirra_fullgame2.cmd): STICK0 (a bot whose direction is a fixed pseudo-random function
# of the frame number, held 32 frames) and CONSOL (START 6, SELECT 5, OPTION 3).  The game is killed by the ghosts, loses its lives and ends by itself.  g = number of games started (@t7), t1 = frames of the title/countdown state (z19 >= 3).
#   g=0: START at title frame 120-170  -> game 1: ONE player, start level 0, played to its game over, countdown, title (state 4).
#   g=1: at the title: OPTION x7 (start level steps 0,1,2,4,6,8,10,12), SELECT (one -> two players), START -> game 2: TWO players, high start level, to the game over of both.
#   g=2: at the title: OPTION x5 (wraps to a lower start level), SELECT (two -> one player), START -> game 3: one player, to its game over.  The start level and player count actually reached are in the FR lines (sl, lives).
# Run (needs real time and the Altirra window need not have the focus; the recording uses a private settings copy):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools
ecord_tune.ps1 -Cmd altirra_sound_bot.cmd -Trace analysis/raw-logs/sound-bot.txt -Out analysis/sound-bot-recorded.wav -Seconds 780
# then  python -I tools/analyze_sound_events.py analysis/raw-logs/sound-bot.txt   python -I tools/analyze_tail_sound.py analysis/sound-bot-recorded.wav analysis/raw-logs/sound-bot.txt   python -I tools/analyze_full_waveform.py analysis/sound-bot-recorded.wav analysis/raw-logs/sound-bot.txt
r @t1 0
r @t3 0
r @t4 0
r @t5 0
r @t7 0
r @t8 0
bp -n a537 "r @t7 @t7+1"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 ((@t7=0)&(@t1>=120)&(@t1<=170))*1+((@t7=1)&(db($19)>=3)&(@t1>=60)&(@t1<=327)&(((@t1-60)%40)<8))*4+((@t7=1)&(db($19)>=3)&(@t1>=400)&(@t1<=408))*2+((@t7=1)&(db($19)>=3)&(@t1>=480)&(@t1<=530))*1+((@t7=2)&(db($19)>=3)&(@t1>=60)&(@t1<=247)&(((@t1-60)%40)<8))*4+((@t7=2)&(db($19)>=3)&(@t1>=300)&(@t1<=308))*2+((@t7=2)&(db($19)>=3)&(@t1>=380)&(@t1<=430))*1"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1"
bp -n a4ff "eb $285 1"
bp -n a82f "eb $278 ($0E*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=0))+($07*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=1))+($0D*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=2))+($0B*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=3))"
bt a923 "DEATH_START f=%d" @frame
bt aaef "GAME_OVER_TEXT f=%d" @frame
bt a5fd "FR f=%d z19=%d z20=%d z21=%d lives=%d,%d lv=%d fc=%d fd=%d f2=%d e5=%d f7=%d f4=%d s1=%02X%02X%02X%02X%02X%02X d34=%d d36=%d sl=%d p=%d cyc=%d t1=%d" @frame db($19) db($20) db($21) db($2c) db($2d) db($30) db($fc) db($fd) db($f2) db($e5) db($f7) db($f4) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($34) db($36) db($1b) @t7 @t8 @t1
bta w d200 L16 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos
bt a537 "NEWGAME f=%d" @frame
bt a7c8 "READY_DRAW f=%d" @frame
bt a7f5 "TUNE f=%d x=%d" @frame db($a3)
bt a800 "START_PLAY f=%d" @frame
bt b3de "PELLET f=%d" @frame
bt a886 "GHOST_EATEN f=%d x=%d" @frame x
bt a93d "BONUS_EATEN f=%d" @frame
bt b660 "BONUS_APPEAR f=%d" @frame
bt b487 "EXTRA_LIFE f=%d" @frame
bt ac75 "LEVEL_ADV f=%d" @frame
bt adaf "INIT_BOARD f=%d" @frame
bt aef1 "DEATH_DONE f=%d" @frame
