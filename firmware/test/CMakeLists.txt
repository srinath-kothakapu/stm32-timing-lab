# Host unit tests for the hardware-independent firmware code.
#   cmake -S firmware/test -B build/fwtest && cmake --build build/fwtest && ctest --test-dir build/fwtest
cmake_minimum_required(VERSION 3.20)
project(stm32_timing_fw_tests C)

enable_testing()

add_executable(fw_unit_tests
  test_main.c
  ../src/common/proto.c
  ../src/common/calc.c
)
target_include_directories(fw_unit_tests PRIVATE ../src/common)
target_compile_options(fw_unit_tests PRIVATE -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g)
target_link_options(fw_unit_tests PRIVATE -fsanitize=address,undefined)

add_test(NAME fw_unit_tests COMMAND fw_unit_tests)
