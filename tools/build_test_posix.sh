#!/bin/sh
# Stage 88 (compatibility): build the C port and run its tests WITHOUT CMake, with any C99 compiler on a POSIX system (here: WSL2 Ubuntu, gcc).  It repeats what src/c/CMakeLists.txt and tests/CMakeLists.txt do:
# the same sources, the same flags (-std=c99 -Wall -Wextra -Wpedantic -Wconversion -Werror), the same tests with the same expected output.  Everything is written below OUTDIR (default build/posix) in the main folder;
# the main folder's own asset blob is read, never written (the installer is run in a copy).
# Usage: sh tools/build_test_posix.sh [CC] [OUTDIR] [extra compiler flags, one word each, e.g. -O0]
# Exit code 0 when every build step and every test passed.
CC=${1:-cc}
OUT=${2:-build/posix}
shift 2 2>/dev/null
EXTRA="$*"
cd "$(dirname "$0")/.." || exit 2
ROOT=$(pwd)
S=src/c
CF="-std=c99 -Wall -Wextra -Wpedantic -Wconversion -Werror -O2 $EXTRA"
INC="-I$S/platform -I$S/core -I$S/app -I$S/assets -I$S/render -I$S/audio -I$S/shell"
FAIL=0
PASS=0
note() { printf '%s\n' "$*"; }
ok() { PASS=$((PASS + 1)); note "PASS $1"; }
bad() { FAIL=$((FAIL + 1)); note "FAIL $1"; }

rm -rf "$OUT"
mkdir -p "$OUT/obj" "$OUT/bin"
note "compiler: $($CC --version | head -n 1); flags: $CF"
note "system: $(uname -sr) $(uname -m)"

# ---- the libraries (one archive per directory of src/c, as in CMake)
for d in platform core app assets render audio shell; do
  mkdir -p "$OUT/obj/$d"
  case $d in
    shell) files="replay.c shell.c frontend.c menu.c" ;;
    assets) files="assets.c sha256.c rom_layout.c rom_install.c" ;;
    *) files=$(cd $S/$d && ls *.c | grep -v '^main.c$' | grep -v '^install_assets.c$') ;;
  esac
  objs=""
  for f in $files; do
    o="$OUT/obj/$d/${f%.c}.o"
    # shellcheck disable=SC2086
    if $CC $CF $INC -c "$S/$d/$f" -o "$o" 2> "$OUT/obj/$d/${f%.c}.log"; then objs="$objs $o"; else bad "compile $d/$f"; cat "$OUT/obj/$d/${f%.c}.log"; fi
  done
  ar rcs "$OUT/obj/libpm_$d.a" $objs
done
note "libraries built: $(ls $OUT/obj/*.a | wc -l)"
LIBS="-Wl,--start-group $OUT/obj/libpm_shell.a $OUT/obj/libpm_render.a $OUT/obj/libpm_audio.a $OUT/obj/libpm_assets.a $OUT/obj/libpm_app.a $OUT/obj/libpm_platform.a $OUT/obj/libpm_core.a -Wl,--end-group -lm"

exe() { # name, extra flags, sources...
  n=$1; fl=$2; shift 2
  # shellcheck disable=SC2086
  if $CC $CF $INC $fl "$@" $LIBS -o "$OUT/bin/$n" 2> "$OUT/bin/$n.log"; then ok "build $n"; else bad "build $n"; cat "$OUT/bin/$n.log"; fi
}
exe pacman_a8 "" $S/shell/main.c
exe install_assets "" $S/assets/install_assets.c
exe toolchain_check "" $S/tests/toolchain_check.c
exe world_check "" $S/tests/world_check.c
exe vector_runner "" $S/tests/vector_runner.c $S/tests/vector.c $S/tests/pure_functions.c $S/tests/world_functions.c
exe vector_runner_swapped "-DPM_TEST_SWAP_ENDIAN" $S/tests/vector_runner.c $S/tests/vector.c $S/tests/pure_functions.c $S/tests/world_functions.c
exe fs_sandbox "" $S/tests/fs_sandbox.c
exe platform_check "" $S/tests/platform_check.c
exe assets_check "" $S/tests/assets_check.c
exe render_check "" $S/tests/render_check.c
exe audio_check "" $S/tests/audio_check.c
exe audio_selftest "" $S/tests/audio_selftest.c
exe shell_selftest "" $S/tests/shell_selftest.c
exe frontend_check "" $S/tests/frontend_check.c
exe menu_check "" $S/tests/menu_check.c

B="$OUT/bin"
run_expect() { # name, regex, command...
  n=$1; re=$2; shift 2
  r=$("$@" 2>&1); rc=$?
  if [ -n "$re" ]; then
    if printf '%s' "$r" | grep -Eq "$re"; then ok "$n"; else bad "$n (output: $(printf '%s' "$r" | tail -n 2))"; fi
  else
    if [ $rc -eq 0 ]; then ok "$n"; else bad "$n (exit $rc: $(printf '%s' "$r" | tail -n 2))"; fi
  fi
}

# ---- the tests of src/c/tests/CMakeLists.txt, in the main folder as working directory
run_expect toolchain_check "" $B/toolchain_check
run_expect world_check "" $B/world_check
if [ -f resources/vectors/identity.vec ]; then
  run_expect vectors_identity "20 equal, 0 different" $B/vector_runner resources/vectors/identity.vec
  run_expect vectors_broken_state "0 equal, 20 different" $B/vector_runner --fn broken_identity resources/vectors/identity.vec
  run_expect vectors_broken_random "0 equal, 20 different" $B/vector_runner --fn broken_random resources/vectors/identity.vec
  run_expect vectors_byte_order_swapped "bad header|state size differs" $B/vector_runner_swapped resources/vectors/identity.vec
fi
mkdir -p "$OUT/fs_sandbox_root/main/sub"
run_expect fs_sandbox "" $B/fs_sandbox "$OUT/fs_sandbox_root"
run_expect platform_check "" $B/platform_check
run_expect assets_check "assets_check: ok, 85 entries" $B/assets_check resources/pack/assets.pmab
run_expect audio_selftest "" $B/audio_selftest
run_expect shell_selftest "shell_selftest: OK" $B/shell_selftest
run_expect frontend_check "frontend_check: OK" $B/frontend_check
run_expect menu_check "menu_check: OK" $B/menu_check

vecset() { # name, prefix, args
  n=$1; p=$2; a=$3
  set -- resources/vectors/$p*.vec
  if [ ! -f "$1" ]; then note "SKIP $n (no vector files)"; return; fi
  cnt=0
  for f in "$@"; do
    # shellcheck disable=SC2086
    if $B/vector_runner $a "$f" > "$OUT/vec.out" 2>&1; then cnt=$((cnt + 1)); else bad "$n: $f ($(tail -n 2 "$OUT/vec.out"))"; return; fi
  done
  ok "$n ($cnt sets)"
}
vecset vectors_core_ref "core_ref." ""
vecset vectors_core_ghost "core_ghost." ""
vecset vectors_core_pacman "core_pacman." ""
vecset vectors_core_score "core_score." ""
vecset vectors_core_draw "core_draw." ""
vecset vectors_core_sound "core_sound." ""
vecset vectors_core_frame "core_frame." ""
vecset vectors_core_play "core_play." ""
vecset vectors_core_play_chain "core_play." "--chain"
vecset vectors_gtia "gtia." ""
vecset vectors_gtia_world "gtia." "--via-world"
vecset vectors_run_frame "core_play." "--platform"
vecset vectors_run_frame_chain "core_play." "--platform --chain"
vecset vectors_core_app_init "core_app_init." ""
vecset vectors_core_app_board "core_app_board." ""
vecset vectors_seq_app_board "seq_core_app_board." "--chain"
vecset vectors_core_app_frame "core_app_frame." ""
vecset vectors_seq_app_frame "seq_core_app_frame." "--chain"
vecset vectors_sessions "session_" "--chain"
vecset vectors_keyloop_states "keyloop_states" ""
vecset vectors_power_on "keyloop_power_on" ""

# ---- the installer on this system: the blob it makes from the ROM must be the one made on Windows (run in a copy of the main folder's layout, so that the real blob is not touched)
if [ -f original/Pac-Man.rom ] && [ -f resources/pack/assets.pmab ]; then
  mkdir -p "$OUT/install/original" "$OUT/install/resources/pack"
  cp original/Pac-Man.rom "$OUT/install/original/Pac-Man.rom"
  ( cd "$OUT/install" && "$ROOT/$B/install_assets" ) > "$OUT/install.out" 2>&1
  if cmp -s "$OUT/install/resources/pack/assets.pmab" resources/pack/assets.pmab; then ok "assets_install: the blob made here is byte-identical to the existing one"; else bad "assets_install: the blob differs from the existing one ($(cat "$OUT/install.out"))"; fi
fi

# ---- whole games through the shell: the digests are written for comparison with the other systems
mkdir -p "$OUT/runs"
for rp in build/c85/clock.pmrp build/c85/keys.pmrp build/c85/1p.pmrp build/c85/2p.pmrp build/c86/fuzz1.pmrp build/c86/fuzz2.pmrp build/c86/fuzz3.pmrp build/c86/fuzz4.pmrp build/c86/fuzz5.pmrp build/c86/fuzz6.pmrp build/c87/bot1.pmrp build/c87/bot2.pmrp build/c87/bot3.pmrp; do
  [ -f "$rp" ] || continue
  nm=$(basename "$rp" .pmrp)
  if $B/pacman_a8 run "$rp" --video --audio --hashes "$OUT/runs/$nm.hashes" > "$OUT/runs/$nm.out" 2>&1; then ok "run $nm"; else bad "run $nm"; fi
done

note "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
