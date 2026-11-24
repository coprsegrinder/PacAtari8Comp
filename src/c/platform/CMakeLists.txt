# the platform layer: files (fs.c), the POKEY RANDOM model, the scripted platform for tests and the headless build; the real keyboard / pad / window / audio shell comes with stage 80
add_library(pm_platform STATIC fs.c pokey_random.c hal_scripted.c timer.c)
target_include_directories(pm_platform PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pm_platform PUBLIC pm_core)
