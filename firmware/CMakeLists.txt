cmake_minimum_required(VERSION 3.20)

if(NOT CMAKE_TOOLCHAIN_FILE)
  set(CMAKE_TOOLCHAIN_FILE ${CMAKE_CURRENT_SOURCE_DIR}/cmake/arm-none-eabi.cmake)
endif()

project(stm32_timing_fw C ASM)

set(TARGET_MCU "F411RE" CACHE STRING "Target board: F411RE or F446RE")
set_property(CACHE TARGET_MCU PROPERTY STRINGS F411RE F446RE)
set(CLOCK_SRC "HSE" CACHE STRING "System clock source: HSE (ST-LINK MCO) or HSI (internal RC)")
set_property(CACHE CLOCK_SRC PROPERTY STRINGS HSE HSI)
set(REF_HZ "1000" CACHE STRING "Reference output frequency on PA6 in Hz")
set(CAPTURE_FILTER "0" CACHE STRING "TIM2 input capture filter IC1F (0..15)")

include(cmake/deps.cmake)

if(TARGET_MCU STREQUAL "F411RE")
  set(MCU_DEFS STM32F411xE TARGET_F411RE)
  set(STARTUP ${ST_STARTUP_DIR}/startup_stm32f411xe.s)
elseif(TARGET_MCU STREQUAL "F446RE")
  set(MCU_DEFS STM32F446xx TARGET_F446RE)
  set(STARTUP ${ST_STARTUP_DIR}/startup_stm32f446xx.s)
else()
  message(FATAL_ERROR "Unknown TARGET_MCU '${TARGET_MCU}'")
endif()

if(CLOCK_SRC STREQUAL "HSI")
  set(USE_HSI 1)
elseif(CLOCK_SRC STREQUAL "HSE")
  set(USE_HSI 0)
else()
  message(FATAL_ERROR "Unknown CLOCK_SRC '${CLOCK_SRC}'")
endif()

string(TOLOWER "timing_${TARGET_MCU}_${CLOCK_SRC}" APP)

add_executable(${APP}.elf
  src/main.c
  src/clock.c
  src/uart.c
  src/timing.c
  src/common/proto.c
  src/common/calc.c
  ${STARTUP}
)

target_include_directories(${APP}.elf PRIVATE src src/common ${CMSIS_DEVICE_INC} ${CMSIS_CORE_INC})
target_compile_definitions(${APP}.elf PRIVATE
  ${MCU_DEFS}
  CLOCK_USE_HSI=${USE_HSI}
  REF_HZ=${REF_HZ}u
  CAPTURE_FILTER=${CAPTURE_FILTER}u
)

set(CPU_FLAGS -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard)
target_compile_options(${APP}.elf PRIVATE
  ${CPU_FLAGS}
  $<$<COMPILE_LANGUAGE:C>:-std=c11 -Wall -Wextra -Wshadow -Wconversion -Wno-sign-conversion -Werror>
  -O2 -g3 -ffunction-sections -fdata-sections
)
target_link_options(${APP}.elf PRIVATE
  ${CPU_FLAGS}
  -T${CMAKE_CURRENT_SOURCE_DIR}/linker/stm32f4_512k_128k.ld
  --specs=nano.specs -nostartfiles
  -Wl,--gc-sections -Wl,-Map=${APP}.map -Wl,--print-memory-usage -Wl,--no-warn-rwx-segments
)

add_custom_command(TARGET ${APP}.elf POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary ${APP}.elf ${APP}.bin
  COMMAND ${CMAKE_OBJCOPY} -O ihex ${APP}.elf ${APP}.hex
  COMMAND ${CMAKE_SIZE} ${APP}.elf
  COMMENT "Creating ${APP}.bin / .hex"
)
