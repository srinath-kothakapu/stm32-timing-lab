*** Comments ***
Boots the real firmware ELFs in the Renode STM32F4 model and checks
- that the clock setup finishes and the UART protocol comes out right
- that TIM2, TIM3, GPIOA, USART2, NVIC and the PLL are configured as intended

What this does NOT cover: Renode's timer model runs at its own fixed frequency
and does not model input capture from a pin, so jitter, drift and latency can
only be measured on real boards.

Run:  renode-test firmware/sim/firmware.robot
(after building all four presets)


*** Settings ***
Library             OperatingSystem
Resource            ${RENODEKEYWORDS}

Suite Setup         Suite Setup With Platform
Suite Teardown      Teardown
Test Setup          Reset Emulation
Test Teardown       Test Teardown


*** Variables ***
${BUILD}            ${CURDIR}/../build

${TIM2}             0x40000000
${TIM3}             0x40000400
${GPIOA}            0x40020000
${USART2}           0x40004400
${NVIC_ISER0}       0xE000E100
${RCC_PLLCFGR}      0x40023804


*** Test Cases ***
F411 HSE Boots And Configures Peripherals
    Check Firmware    f411-hse    timing_f411re_hse.elf    F411RE    HSE    0x27415408

F411 HSI Boots And Configures Peripherals
    Check Firmware    f411-hsi    timing_f411re_hsi.elf    F411RE    HSI    0x27015410

F446 HSE Boots And Configures Peripherals
    Check Firmware    f446-hse    timing_f446re_hse.elf    F446RE    HSE    0x27405408

F446 HSI Boots And Configures Peripherals
    Check Firmware    f446-hsi    timing_f446re_hsi.elf    F446RE    HSI    0x27005410


*** Keywords ***
Suite Setup With Platform
    Setup
    # Use Renode's stock STM32F4 description, minus the line that downloads an SVD file
    # (register names for logging only), so the test also runs without internet access.
    ${root}=    Evaluate    [p for p in __import__('pathlib').Path(r'''${RENODEKEYWORDS}''').resolve().parents if (p / 'platforms/cpus/stm32f4.repl').exists()][0]
    ${repl}=    Get File    ${root}/platforms/cpus/stm32f4.repl
    ${repl}=    Evaluate    '\\n'.join(l for l in r'''${repl}'''.splitlines() if 'ApplySVD' not in l)
    Create File    ${TEMPDIR}/stm32f4_nosvd.repl    ${repl}
    Set Suite Variable    ${PLATFORM_FILE}    ${TEMPDIR}/stm32f4_nosvd.repl

Check Firmware
    [Arguments]    ${preset}    ${elf}    ${target}    ${clk}    ${pllcfgr}
    File Should Exist    ${BUILD}/${preset}/${elf}
    Execute Command    mach create "nucleo"
    Execute Command    machine LoadPlatformDescription @${PLATFORM_FILE}
    Execute Command    sysbus LoadELF @${BUILD}/${preset}/${elf}
    Create Terminal Tester    sysbus.usart2    timeout=20
    Start Emulation

    # protocol: header first, then status, see firmware/src/common/proto.h
    Wait For Line On Uart    ^H,1,uid=[0-9A-F]{8},target=${target},clk=${clk},ftim=84000000,ref=1000$    treatAsRegex=true
    Wait For Line On Uart    S,seq=0,drop=0,ovc=0

    # PLL: source, M, N, P, Q and the reserved/PLLR bits
    Register Should Be    ${RCC_PLLCFGR}    0xFFFFFFFF    ${pllcfgr}

    # TIM2: free running 32 bit, no prescaler, CH1 input capture on TI1, interrupt on capture
    Register Should Be    ${TIM2} + 0x00    0x1           0x1           # CR1.CEN
    Register Should Be    ${TIM2} + 0x0C    0x2           0x2           # DIER.CC1IE
    Register Should Be    ${TIM2} + 0x18    0xF3          0x01          # CCMR1: CC1S=01, IC1F=0
    Register Should Be    ${TIM2} + 0x20    0xB           0x1           # CCER: CC1E, rising edge
    Register Should Be    ${TIM2} + 0x28    0xFFFF        0             # PSC
    Register Should Be    ${TIM2} + 0x2C    0xFFFFFFFF    0xFFFFFFFF    # ARR

    # TIM3: 84 MHz / (1+1) / (41999+1) = 1000 Hz, 50 % duty, PWM mode 1
    Register Should Be    ${TIM3} + 0x28    0xFFFF        1
    Register Should Be    ${TIM3} + 0x2C    0xFFFF        41999
    Register Should Be    ${TIM3} + 0x34    0xFFFF        21000
    Register Should Be    ${TIM3} + 0x18    0x70          0x60

    # GPIOA: PA0 AF1 (TIM2_CH1), PA2 AF7 (USART2_TX), PA5 output (marker), PA6 AF2 (TIM3_CH1)
    Register Should Be    ${GPIOA} + 0x00    0x3C33        0x2422
    Register Should Be    ${GPIOA} + 0x20    0x0F000F0F    0x02000701

    # USART2: 42 MHz / 91 = 461538 Bd (460800 nominal, +0.16 %)
    Register Should Be    ${USART2} + 0x08    0xFFFF       91

    # TIM2 interrupt (IRQ 28) enabled in the NVIC
    Register Should Be    ${NVIC_ISER0}    0x10000000      0x10000000

Register Should Be
    [Arguments]    ${address}    ${mask}    ${expected}
    ${addr}=    Evaluate    ${address}
    ${raw}=    Execute Command    sysbus ReadDoubleWord ${addr}
    ${value}=    Evaluate    int("""${raw}""".strip(), 16) & ${mask}
    ${want}=    Evaluate    ${expected}
    ${hex}=    Evaluate    hex(${addr})
    Should Be Equal As Integers    ${value}    ${want}    msg=register ${hex} masked with ${mask}: got ${value}, expected ${want}
