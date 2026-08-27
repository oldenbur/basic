include(FetchContent)
FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG v1.15.2
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

add_executable(hello_test hello_test.cpp)
target_link_libraries(hello_test PRIVATE intvw GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(hello_test)
