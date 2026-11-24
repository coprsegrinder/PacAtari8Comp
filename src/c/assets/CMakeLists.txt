# the asset blob loader and the installer from the owner's cartridge image (stage 80a)
add_library(pm_assets STATIC assets.c sha256.c rom_layout.c rom_install.c)
target_include_directories(pm_assets PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pm_assets PUBLIC pm_platform)

add_executable(install_assets install_assets.c)
target_link_libraries(install_assets pm_assets)
