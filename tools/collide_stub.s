; OV-68: the SCENE STUB for the collision audit (tools/altirra_collide.cmd, written by tools/make_collide_cmd.py).
; Assembled with ca65 / ld65 to $4200 and poked into the EMULATED machine's free RAM by the harness; nothing of the game's code is changed.
; Entered instead of the frame body, at $A603 (the `jsr FrameDispatch` of the deferred vertical-blank handler), in every frame once the game is in play; it ends with `jmp $A60D` (the handler's normal exit).
;
; Each call:  1. (when a scene is staged) reads the sixteen collision registers ($D000-$D00F) = the overlaps of the scene that was on the screen since the last HITCLR, stores them in the record,
;                clears them (HITCLR), clears the 16 rows of every object of the old scene in the player-missile pages, copies the staged scene into the pages and its eight positions into HPOSP0-3, HPOSM0-3;
;             2. generates the NEXT scene at random into the staging area (a 16-bit LCG): where the objects stand (positions near each other so that they overlap often), the 16 rows of each of the five
;                objects (the missile page and the four player pages) with one of four densities of set bits.
; The record (REC, 128 bytes at $4100: the registers, then the installed scene) is printed by the harness's tracepoint at `done`.
        .setcpu "6502"

; zero-page pointers: the frame body is skipped, so the scratch pointers of the game ($3C-$3F) are free
ptr     = $3C
src     = $3E
dst     = $3C

HPOS    = $D000                 ; HPOSP0-3, HPOSM0-3 (write)
COLL    = $D000                 ; M0PF .. P3PL (read)
HITCLR  = $D01E
PMBASE  = $2300                 ; missile page; the player pages follow at $2400, $2500, $2600, $2700

; staging area (the next scene)
ST_HPOS  = $4000                ; 8 positions
ST_ROW   = $4008                ; 5 first rows: missiles, players 0-3
ST_DENS  = $400D                ; 5 density codes
ST_PAT   = $4020                ; 5 x 16 picture rows
; control and state
READY    = $4080                ; 1 = a scene is staged
BX       = $4082
BY       = $4083
SEED     = $4084                ; 16 bit
MODE     = $4086                ; bit 0: fill the maze screen with every character code (a test screen: all four playfield colours under the objects); bit 1: base x anywhere in 0-255; bit 2: the rows anywhere in the pages
VALID    = $4087                ; 1 once a scene has been installed (the registers of the first call belong to the game's own scene)
PREV_ROW = $4090                ; the rows of the installed scene (5)
COUNT    = $4098                ; scenes installed (16 bit)
TMP      = $409A
IDX      = $409B
; record
REC      = $4100                ; 16 registers
REC_SC   = $4110                ; the installed scene: 8 positions, rows (5), densities (5), then patterns at +$20
REC_VALID = $41A0
REC_COUNT = $41A1       ; 16 bit

        .org $4200
entry:
        lda READY
        bne install
        lda MODE                ; the first call: the test screen, when asked for
        and #1
        beq gen0
        jsr fillscreen
gen0:   jmp generate
install:
        ; ---- 1. read and clear the collision registers
        ldx #15
rd:     lda COLL,x
        sta REC,x
        dex
        bpl rd
        lda #0
        sta HITCLR
        ; ---- clear the old rows (the rows of the installed scene); the first time all five pages (the game's own pictures are in them)
        lda VALID
        bne rows
        ldx #0
        lda #0
        sta ptr
pg:     txa
        clc
        adc #>PMBASE
        sta ptr+1
        ldy #0
        lda #0
pgb:    sta (ptr),y
        iny
        bne pgb
        inx
        cpx #5
        bne pg
        beq nocl
rows:
        ldx #0                  ; object 0..4
clobj:  lda PREV_ROW,x
        sta ptr
        txa
        clc
        adc #>PMBASE
        sta ptr+1
        ldy #15
        lda #0
clrow:  sta (ptr),y
        dey
        bpl clrow
        inx
        cpx #5
        bne clobj
nocl:
        ; ---- copy the staged pictures into the pages
        ldx #0
cpobj:  lda ST_ROW,x
        sta ptr
        sta PREV_ROW,x
        txa
        clc
        adc #>PMBASE
        sta ptr+1
        ; source = ST_PAT + 16 * x
        txa
        asl a
        asl a
        asl a
        asl a
        clc
        adc #<ST_PAT
        sta src
        lda #>ST_PAT
        adc #0
        sta src+1
        ldy #15
cprow:  lda (src),y
        sta (ptr),y
        dey
        bpl cprow
        inx
        cpx #5
        bne cpobj
        ; ---- the eight positions
        ldx #7
hp:     lda ST_HPOS,x
        sta HPOS,x
        dex
        bpl hp
        ; ---- the record: the installed scene
        ldx #0
rs:     lda ST_HPOS,x
        sta REC_SC,x
        inx
        cpx #$10
        bne rs
        ; densities / rows are at ST_HPOS+8 .. +$11 ; patterns at +$20: copy $4000-$407F
        ldx #$10
rs2:    lda ST_HPOS,x
        sta REC_SC,x
        inx
        bpl rs2
        lda VALID
        sta REC_VALID
        lda #1
        sta VALID
        inc COUNT
        bne c1
        inc COUNT+1
c1:     lda COUNT
        sta REC_COUNT
        lda COUNT+1
        sta REC_COUNT+1
        lda #0
        sta READY
        ; ---- 2. the next scene
generate:
        lda COUNT               ; the number of scenes installed is mixed into the seed: without it the scenes repeat after 512
        eor SEED
        sta SEED
        lda COUNT+1
        eor SEED+1
        sta SEED+1
        lda MODE
        and #2
        beq narrow
        jsr rnd                 ; wide: base x anywhere
        jmp bxset
narrow: jsr rnd
        and #$3F
        clc
        adc #$58                ; base x 88 .. 151
bxset:  sta BX
        jsr rnd
        and #$7F
        clc
        adc #$38                ; base y 56 .. 183 (the objects stand in the maze rows, lines 48 to 207)
        sta BY
        ldx #7
gh:     jsr rnd
        and #$1F
        clc
        adc BX
        sec
        sbc #$10                ; base x +- 16
        sta ST_HPOS,x
        dex
        bpl gh
        ldx #4
gr:     lda MODE
        and #4
        beq nrow
        jsr rnd                 ; tall: the first row anywhere in the page, 0 .. 240 (the 16 rows stay in it)
        cmp #$F1
        bcc rowset
        and #$7F
        jmp rowset
nrow:   jsr rnd
        and #$0F
        clc
        adc BY
        sec
        sbc #$08                ; base y +- 8: first row of the object
rowset: sta ST_ROW,x
        jsr rnd
        and #$03
        sta ST_DENS,x
        dex
        bpl gr
        ; patterns
        ldx #4
po:     txa
        asl a
        asl a
        asl a
        asl a
        clc
        adc #<ST_PAT
        sta dst
        lda #>ST_PAT
        adc #0
        sta dst+1
        ldy #15
pr:     lda ST_DENS,x
        bne dens1
        lda #$FF                ; density 0: solid
        jmp pstore
dens1:  cmp #3
        bne dens2
        jsr rnd                 ; 3: about half of the bits
        jmp pstore
dens2:  cmp #2
        bne dens3
        jsr rnd                 ; 2: a quarter
        sta TMP
        jsr rnd
        and TMP
        jmp pstore
dens3:  jsr rnd                 ; 1: an eighth
        sta TMP
        jsr rnd
        and TMP
        sta TMP
        jsr rnd
        and TMP
pstore: sta (dst),y
        dey
        bpl pr
        dex
        bpl po
        lda #1
        sta READY
done:
        jmp $A60D

; ---- the test screen: the 920 cells of the maze band get the codes 13, 13 + 167, ... (mod 256): every code, about 3.6 times each
fillscreen:
        lda #0
        sta ptr
        lda #$0C
        sta ptr+1
        lda #13
        sta TMP
        ldx #3                  ; 3 pages ...
fp:     ldy #0
fy:     lda TMP
        sta (ptr),y
        clc
        adc #167
        sta TMP
        iny
        bne fy
        inc ptr+1
        dex
        bne fp
        ldy #0                  ; ... and 152 cells
fz:     lda TMP
        sta (ptr),y
        clc
        adc #167
        sta TMP
        iny
        cpy #152
        bne fz
        rts

; ---- random byte: 16 bit LCG seed := seed * 5 + 1, the high byte is returned (keeps X and Y)
rnd:
        lda SEED
        sta TMP+2
        lda SEED+1
        sta TMP+3
        asl SEED
        rol SEED+1
        asl SEED
        rol SEED+1              ; seed * 4
        clc
        lda SEED
        adc TMP+2
        sta SEED
        lda SEED+1
        adc TMP+3
        sta SEED+1              ; seed * 5
        inc SEED
        bne r1
        inc SEED+1
r1:     lda SEED+1
        eor SEED
        rts

