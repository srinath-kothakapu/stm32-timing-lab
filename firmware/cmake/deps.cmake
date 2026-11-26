# Downloads the handful of CMSIS headers and ST startup files the firmware needs
# into firmware/third_party/ (git-ignored). Pinned to fixed tags.
#   ST cmsis_device_f4 v2.6.9 (Apache-2.0)
#   ARM CMSIS_5 5.9.0 core headers (Apache-2.0)

set(DEPS_DIR ${CMAKE_CURRENT_LIST_DIR}/../third_party)

set(ST_BASE "https://raw.githubusercontent.com/STMicroelectronics/cmsis_device_f4/v2.6.9")
set(ARM_BASE "https://raw.githubusercontent.com/ARM-software/CMSIS_5/5.9.0/CMSIS/Core/Include")

set(ST_FILES
  Include/stm32f4xx.h
  Include/stm32f411xe.h
  Include/stm32f446xx.h
  Include/system_stm32f4xx.h
  Source/Templates/gcc/startup_stm32f411xe.s
  Source/Templates/gcc/startup_stm32f446xx.s
  LICENSE.md
)
set(ARM_FILES
  core_cm4.h
  cmsis_version.h
  cmsis_compiler.h
  cmsis_gcc.h
  mpu_armv7.h
)

function(fetch_file url dest)
  if(NOT EXISTS ${dest})
    message(STATUS "Downloading ${url}")
    file(DOWNLOAD ${url} ${dest} STATUS st TLS_VERIFY ON)
    list(GET st 0 code)
    if(NOT code EQUAL 0)
      file(REMOVE ${dest})
      message(FATAL_ERROR "Download failed (${st}): ${url}")
    endif()
  endif()
endfunction()

foreach(f ${ST_FILES})
  fetch_file(${ST_BASE}/${f} ${DEPS_DIR}/cmsis_device_f4/${f})
endforeach()
foreach(f ${ARM_FILES})
  fetch_file(${ARM_BASE}/${f} ${DEPS_DIR}/cmsis_core/Include/${f})
endforeach()

set(CMSIS_DEVICE_INC ${DEPS_DIR}/cmsis_device_f4/Include)
set(CMSIS_CORE_INC ${DEPS_DIR}/cmsis_core/Include)
set(ST_STARTUP_DIR ${DEPS_DIR}/cmsis_device_f4/Source/Templates/gcc)
