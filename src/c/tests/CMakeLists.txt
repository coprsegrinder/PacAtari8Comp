# stage 75a, 75b: the toolchain facts, the generated World and tables, the vector runner, the file sandbox, the portability scan.
# The tests run with the repository folder (the main folder of the tools) as their working directory.
get_filename_component(PM_MAIN_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../.. ABSOLUTE)

add_executable(toolchain_check toolchain_check.c)
add_test(NAME toolchain_check COMMAND toolchain_check)

add_executable(world_check world_check.c)
target_link_libraries(world_check pm_assets pm_core pm_platform)
add_test(NAME world_check COMMAND world_check WORKING_DIRECTORY ${PM_MAIN_DIR})
set_tests_properties(world_check PROPERTIES FIXTURES_REQUIRED asset_blob)   # the tables are installed from the blob (stage 80a)

# the vector runner, and a build of it with the opposite byte-order assumption (it must not accept the files)
add_executable(vector_runner vector_runner.c vector.c pure_functions.c world_functions.c)
target_link_libraries(vector_runner pm_assets pm_app pm_core pm_platform)
add_executable(vector_runner_swapped vector_runner.c vector.c pure_functions.c world_functions.c)
target_compile_definitions(vector_runner_swapped PRIVATE PM_TEST_SWAP_ENDIAN)
target_link_libraries(vector_runner_swapped pm_assets pm_app pm_core pm_platform)

find_program(PM_PYTHON NAMES python python3)
if(PM_PYTHON)
  add_test(NAME vectors_make_identity COMMAND ${PM_PYTHON} -I tools/make_vectors.py --identity WORKING_DIRECTORY ${PM_MAIN_DIR})
  set_tests_properties(vectors_make_identity PROPERTIES FIXTURES_SETUP identity_vectors)

  add_test(NAME vectors_identity COMMAND vector_runner resources/vectors/identity.vec WORKING_DIRECTORY ${PM_MAIN_DIR})
  set_tests_properties(vectors_identity PROPERTIES FIXTURES_REQUIRED "identity_vectors;asset_blob" PASS_REGULAR_EXPRESSION "20 equal, 0 different")

  # negative controls: a function with one byte wrong, and one that reads a RANDOM value it should not, are caught on every call
  add_test(NAME vectors_broken_state COMMAND vector_runner --fn broken_identity resources/vectors/identity.vec WORKING_DIRECTORY ${PM_MAIN_DIR})
  set_tests_properties(vectors_broken_state PROPERTIES FIXTURES_REQUIRED "identity_vectors;asset_blob" PASS_REGULAR_EXPRESSION "0 equal, 20 different")
  add_test(NAME vectors_broken_random COMMAND vector_runner --fn broken_random resources/vectors/identity.vec WORKING_DIRECTORY ${PM_MAIN_DIR})
  set_tests_properties(vectors_broken_random PROPERTIES FIXTURES_REQUIRED "identity_vectors;asset_blob" PASS_REGULAR_EXPRESSION "0 equal, 20 different")

  # byte order: the reader assumes little-endian by its code, not by the machine; a reader built with the opposite assumption rejects the file
  add_test(NAME vectors_byte_order_swapped COMMAND vector_runner_swapped resources/vectors/identity.vec WORKING_DIRECTORY ${PM_MAIN_DIR})
  set_tests_properties(vectors_byte_order_swapped PROPERTIES FIXTURES_REQUIRED "identity_vectors;asset_blob" PASS_REGULAR_EXPRESSION "bad header|state size differs")
endif()

# the file sandbox: the main folder of this test is <build>/fs_sandbox_root/main, with a folder `sub` in it
file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/fs_sandbox_root/main/sub)
add_executable(fs_sandbox fs_sandbox.c)
target_link_libraries(fs_sandbox pm_platform)
add_test(NAME fs_sandbox COMMAND fs_sandbox ${CMAKE_CURRENT_BINARY_DIR}/fs_sandbox_root)

# the portability scan, and its self test (the scan must fail on bad files)
add_test(NAME portability_scan COMMAND ${CMAKE_COMMAND} -DSRC=${CMAKE_CURRENT_SOURCE_DIR}/.. -P ${CMAKE_CURRENT_SOURCE_DIR}/portability_scan.cmake)
add_test(NAME portability_scan_selftest COMMAND ${CMAKE_COMMAND} -DSCAN=${CMAKE_CURRENT_SOURCE_DIR}/portability_scan.cmake -DWORK=${CMAKE_CURRENT_BINARY_DIR}/scan_selftest -P ${CMAKE_CURRENT_SOURCE_DIR}/portability_scan_selftest.cmake)

# stage 76: the recorded vector sets of the real functions, run by prefix (a derived data folder: when it is not there the test is skipped, not passed)
function(pm_vector_test name prefix)
  set(extra "")
  if(ARGC GREATER 2)
    set(extra "-DRUNNER_ARGS=${ARGV2}")
  endif()
  add_test(NAME ${name} COMMAND ${CMAKE_COMMAND} -DRUNNER=$<TARGET_FILE:vector_runner> ${extra} -DDIR=${PM_MAIN_DIR}/resources/vectors -DPREFIX=${prefix} -DCWD=${PM_MAIN_DIR} -P ${CMAKE_CURRENT_SOURCE_DIR}/run_vector_sets.cmake WORKING_DIRECTORY ${PM_MAIN_DIR})
  set_tests_properties(${name} PROPERTIES SKIP_REGULAR_EXPRESSION "no vector files" FIXTURES_REQUIRED asset_blob)
endfunction()
pm_vector_test(vectors_core_ref "core_ref.")
pm_vector_test(vectors_core_ghost "core_ghost.")
pm_vector_test(vectors_core_pacman "core_pacman.")
pm_vector_test(vectors_core_score "core_score.")
pm_vector_test(vectors_core_draw "core_draw.")
pm_vector_test(vectors_core_sound "core_sound.")
pm_vector_test(vectors_core_frame "core_frame.")
pm_vector_test(vectors_core_play "core_play.")
pm_vector_test(vectors_core_play_chain "core_play." "--chain")
pm_vector_test(vectors_gtia "gtia.")
pm_vector_test(vectors_gtia_world "gtia." "--via-world")

# stage 77b: the platform layer (the POKEY RANDOM model, the scripted platform) and run_frame on a platform that replays the recorded inputs, also in chain mode
add_executable(platform_check platform_check.c)
target_link_libraries(platform_check pm_assets pm_app pm_core pm_platform)
add_test(NAME platform_check COMMAND platform_check WORKING_DIRECTORY ${PM_MAIN_DIR})
set_tests_properties(platform_check PROPERTIES FIXTURES_REQUIRED asset_blob)
pm_vector_test(vectors_run_frame "core_play." "--platform")
pm_vector_test(vectors_run_frame_chain "core_play." "--platform --chain")
pm_vector_test(vectors_core_app_init "core_app_init.")
pm_vector_test(vectors_core_app_board "core_app_board.")
pm_vector_test(vectors_seq_app_board "seq_core_app_board." "--chain")
pm_vector_test(vectors_core_app_frame "core_app_frame.")
pm_vector_test(vectors_seq_app_frame "seq_core_app_frame." "--chain")
pm_vector_test(vectors_sessions "session_" "--chain")
pm_vector_test(vectors_keyloop_states "keyloop_states")
pm_vector_test(vectors_power_on "keyloop_power_on")

# stage 80a: the asset blob loader and the installer; the blob (resources/pack/assets.pmab) is derived from the owner's ROM by install_assets and is not committed
add_executable(assets_check assets_check.c)
target_link_libraries(assets_check pm_assets pm_app pm_core pm_platform)
# the installer makes the blob from the owner's ROM (original/Pac-Man.rom, not committed); without the ROM the tests are skipped, not passed
add_test(NAME assets_install COMMAND install_assets WORKING_DIRECTORY ${PM_MAIN_DIR})
set_tests_properties(assets_install PROPERTIES FIXTURES_SETUP asset_blob SKIP_REGULAR_EXPRESSION "cannot be opened" PASS_REGULAR_EXPRESSION "install_assets: ok")
add_test(NAME assets_check COMMAND assets_check resources/pack/assets.pmab WORKING_DIRECTORY ${PM_MAIN_DIR})
set_tests_properties(assets_check PROPERTIES FIXTURES_REQUIRED asset_blob PASS_REGULAR_EXPRESSION "assets_check: ok, 85 entries")

# stage 80b: the renderer; render_check draws the frame of a memory image (tests/test_render.py compares it with the real captures)
add_executable(render_check render_check.c)
target_link_libraries(render_check pm_render pm_assets pm_core pm_platform)

# stage 80c: the POKEY model; audio_check renders timed register writes to PCM (tests/test_audio.py compares it with the Python model and with Altirra's recordings)
add_executable(audio_check audio_check.c)
target_link_libraries(audio_check pm_audio pm_platform pm_core)
add_executable(audio_selftest audio_selftest.c)
target_link_libraries(audio_selftest pm_audio pm_core)
add_test(NAME audio_selftest COMMAND audio_selftest WORKING_DIRECTORY ${PM_MAIN_DIR})

# stage 80d: the shell; its self test needs the asset blob and writes only below build/
add_executable(shell_selftest shell_selftest.c)
target_link_libraries(shell_selftest pm_shell pm_assets pm_app pm_core pm_platform)
add_test(NAME shell_selftest COMMAND shell_selftest WORKING_DIRECTORY ${PM_MAIN_DIR})
set_tests_properties(shell_selftest PROPERTIES FIXTURES_REQUIRED asset_blob PASS_REGULAR_EXPRESSION "shell_selftest: OK")

# stage 94: the named constants of the original (core/constants.h, generated) compile with every other header and have the values of the chapters
add_executable(constants_check constants_check.c)
add_test(NAME constants_check COMMAND constants_check)
set_tests_properties(constants_check PROPERTIES PASS_REGULAR_EXPRESSION "constants_check: OK \\(51 constants\\)")

# stage 97: the installer makes the folders it writes into (a clean checkout has no resources/): into a path that does not exist yet
add_test(NAME assets_install_nested_clean COMMAND ${CMAKE_COMMAND} -E remove_directory ${PM_MAIN_DIR}/build/installer-nested)
set_tests_properties(assets_install_nested_clean PROPERTIES FIXTURES_SETUP nested_clean)
add_test(NAME assets_install_nested COMMAND install_assets original/Pac-Man.rom build/installer-nested/a/b/assets.pmab WORKING_DIRECTORY ${PM_MAIN_DIR})
set_tests_properties(assets_install_nested PROPERTIES FIXTURES_REQUIRED nested_clean SKIP_REGULAR_EXPRESSION "cannot be opened" PASS_REGULAR_EXPRESSION "install_assets: ok")
