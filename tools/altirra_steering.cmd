# Altirra debugger commands: frightened-mode steering, the eaten-ghost return and the house (step C11, docs/18-frightened-eaten-house.md).
# Everything in altirra_transitions.cmd (every write to GhostState, with the same TEST AIDS: game started from its start code, ghosts do not kill Pac-Man, Pac-Man moved around / onto pellets / onto ghosts,
# dots-eaten counter set to $B1/$E1/$F1 so that boards end and restart), plus:
#   STEER   every call of SteerToTarget ($B999): ghost, state, position, target, exit mask (after the no-reverse filter), and at its end ($BA16) the wanted directions and the chosen direction
#   HOUSE   every step a ghost takes inside the house ($B7F2 bobbing while it waits, $B75D walking to the door and up) and EATEN_STEP ($B6EB, an eaten ghost walking back)
# Lines: STEER ghost state x y tx ty mask dir pacx pacy frame / STEER_OUT ghost dir wv wh / HOUSE kind ghost state x y dir timer frame.
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 (@frame%$800); eb $89 db($BB83+((@frame/$80)%10)); eb $8e db($BB8D+((@frame/$500)%10)); r @t7 ((@t5>=$F0)&(@t5<$F8)); eb $32 (@t7*$0F)+(1-@t7)*db($32); r @t7 ((@t5>=$100)&(@t5<$110)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t6 ((@frame/$800)%4); r @t7 ((@t5>=$180)&(@t5<$190)); eb $8e db($8e)+@t7*(db($8a+@t6)-db($8e)); eb $89 db($89)+@t7*(db($85+@t6)-db($89))"
bp -n a82f "r @t8 (@frame%$6000); r @t9 (@t8=$3000); eb $34 db($34)+@t9*($B1-db($34)); r @t9 (@t8=$4000); eb $34 db($34)+@t9*($E1-db($34)); r @t9 (@t8=$5000); eb $34 db($34)+@t9*($F1-db($34)); r @t9 (@t8=0); eb $34 db($34)-@t9*db($34); eb $36 db($36)-@t9*db($36)"
bt a888 "ST site=A888 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt afa0 "ST site=AFA0 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b40a "ST site=B40A ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b626 "ST site=B626 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b6d0 "ST site=B6D0 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b756 "ST site=B756 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b764 "ST site=B764 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b853 "ST site=B853 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b895 "ST site=B895 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b8c7 "ST site=B8C7 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b8ed "ST site=B8ED ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt bab9 "ST site=BAB9 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt a800 "ST site=A800 ghost=0 old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" db($ce) db($34)+256*db($36) db($ad) db($ca) db($8a) db($85) db($fd) @frame
bt a886 "GHOST_EATEN ghost=%d frame=%d" x @frame
bt b3de "PELLET frame=%d" @frame
bt adaf "INIT_BOARD frame=%d" @frame
bt b999 "STEER ghost=%d state=$%02X x=%d y=%d tx=%d ty=%d mask=$%02X dir=%d pacx=%d pacy=%d frame=%d" x db($ce+x) db($8a+x) db($85+x) db($c2+x) db($c6+x) db($2a) db($8f+x) db($8e) db($89) @frame
bt ba16 "STEER_OUT ghost=%d dir=%d wv=%d wh=%d" x db($8f+x) db($d6+x) db($da+x)
bt b7f2 "HOUSE kind=bob ghost=%d state=$%02X x=%d y=%d dir=%d timer=%d frame=%d" x db($ce+x) db($8a+x) db($85+x) db($8f+x) db($ca+x) @frame
bt b75d "HOUSE kind=walk ghost=%d state=$%02X x=%d y=%d dir=%d timer=%d frame=%d" x db($ce+x) db($8a+x) db($85+x) db($8f+x) db($ca+x) @frame
bt b6eb "HOUSE kind=eaten ghost=%d state=$%02X x=%d y=%d dir=%d timer=%d frame=%d" x db($ce+x) db($8a+x) db($85+x) db($8f+x) db($ca+x) @frame
