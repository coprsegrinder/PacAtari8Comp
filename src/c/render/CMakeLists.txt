# the renderer (stage 80b): the picture of the screen from the World
add_library(pm_render STATIC render.c interp.c palette.c)
target_include_directories(pm_render PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pm_render PUBLIC pm_core)
