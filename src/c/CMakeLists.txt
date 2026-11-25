# Pac-Man (Atari 8-bit) C port - owner decisions of 2026-11-18 (docs/49-owner-decisions.md):
# faithful frame-by-frame port, C99, clang and gcc, CMake, whole-state equivalence each frame.
cmake_minimum_required(VERSION 3.16)
project(pacman_a8 C)

# the version of the program: one line in the file VERSION at the top of the project (the release scripts read the same file)
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION)
  file(READ ${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION PM_VERSION_RAW)
  string(STRIP "${PM_VERSION_RAW}" PM_VERSION)
else()
  set(PM_VERSION "dev")
endif()
add_compile_definitions(PM_VERSION="${PM_VERSION}")

# without a build type asked for, the optimized one: the program does a picture every few milliseconds (docs/67, 69, 70), and an unoptimized build is too slow for it
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "build type" FORCE)
endif()

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(CMAKE_C_COMPILER_ID MATCHES "Clang|GNU")
  add_compile_options(-Wall -Wextra -Wpedantic -Wconversion -Werror)
endif()

enable_testing()

# the layers of docs/48-architecture.md section 6 are added here as they are written:
#   platform/  core/  assets/  app/  render/
add_subdirectory(platform)
add_subdirectory(core)
add_subdirectory(app)
add_subdirectory(assets)
add_subdirectory(render)
add_subdirectory(audio)
add_subdirectory(shell)
add_subdirectory(tests)
