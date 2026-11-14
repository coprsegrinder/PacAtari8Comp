# Altirra debugger commands: a game PLAYED BY A PERSON, traced for ALL SOUND (OPEN-VERIFICATION.md OV-19). NOTHING is injected or changed: no bot, no START value, no pokes, no PC move, no invulnerability
# (the game can end by itself); the trace is passive. You press the keys in Altirra's window: F2 = START, F3 = SELECT, F4 = OPTION, arrows = joystick 1, Left Ctrl = fire.
# To get the audio as well, run it through the recorder (the recording runs at normal speed; the Altirra window must have the focus for the keys):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\record_tune.ps1 -Cmd altirra_sound_natural.cmd -Trace analysis/raw-logs/sound-natural.txt -Out analysis/sound-natural-recorded.wav -Seconds 360
# then   python -I tools/analyze_sound_events.py analysis/raw-logs/sound-natural.txt   python -I tools/analyze_tail_sound.py analysis/sound-natural-recorded.wav analysis/raw-logs/sound-natural.txt
#   python -I tools/analyze_full_waveform.py analysis/sound-natural-recorded.wav analysis/raw-logs/sound-natural.txt
# Played to cover what the aided sessions could not show by steering: eat a power pellet, eat a ghost, eat the fruit/bonus item (BONUS_APPEAR then BONUS_EATEN at $A93D), lose a life, get the game over.
# Trace: every write to $D200-$D20F with value, PC, frame and beam position (SNDW), a short line per frame (FR, also makes the log flush), and the game events.
r @t1 0
r @t2 0
r @t3 0
r @t4 0
r @t5 0
r @t7 0
r @t8 0
r @t9 0
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a800 "r @t2 @frame"
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
