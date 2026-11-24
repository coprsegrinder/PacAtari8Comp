# the application layer: run_frame now (stage 77b); the title, the turn control, the level end, the key loop and the new game come with stages 79a-d
add_library(pm_app STATIC run_frame.c init.c intro.c board.c levelend.c turn.c dispatch.c keyloop.c newgame.c start.c app.c)
target_include_directories(pm_app PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pm_app PUBLIC pm_core pm_platform)
