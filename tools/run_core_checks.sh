#!/bin/sh
# runs every port-form check and writes the evidence files (stage 66, OV-67; the drawing, OV-69)
cd "$(dirname "$0")/.."
python -I tools/check_core.py --write analysis/evidence-core-summary.txt > /dev/null
python -I tools/check_ghost.py --write analysis/evidence-ghost-summary.txt > /dev/null
python -I tools/check_pacman.py --write analysis/evidence-pacman-summary.txt > /dev/null
python -I tools/check_score.py --write analysis/evidence-score-summary.txt > /dev/null
python -I tools/check_sound.py --write analysis/evidence-sound-summary.txt > /dev/null
python -I tools/check_frame.py --write analysis/evidence-frame-summary.txt > /dev/null
python -I tools/check_play.py --write analysis/evidence-play-summary.txt > /dev/null
python -I tools/check_draw.py --write analysis/evidence-draw-summary.txt > /dev/null
echo done > analysis/raw-logs/core-checks.done
