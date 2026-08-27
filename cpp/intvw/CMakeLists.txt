cmake_minimum_required(VERSION 3.28)
project(intvw CXX)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Debug)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_SCAN_FOR_MODULES ON)

add_library(intvw)
target_sources(intvw
  PUBLIC
    FILE_SET CXX_MODULES FILES
      src/hello.cppm
)

enable_testing()
add_subdirectory(tests)
