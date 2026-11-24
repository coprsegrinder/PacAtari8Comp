# the core of the game (docs/48 section 6): generated data first (stage 75a)
add_library(pm_core STATIC world.c tables.c ref.c draw.c gtia.c ghost.c house.c pacman.c score.c sound.c frame.c play.c)
target_include_directories(pm_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
