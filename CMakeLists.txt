cmake_minimum_required(VERSION 3.16)
project(0700_aam_sim VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Optimization and warning flags
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic -O2)
endif()

# Core static library
add_library(aam_sim_core STATIC
    src/protocol.cpp
    src/hardware.cpp
    src/transport.cpp
    src/scenario.cpp
)

target_include_directories(aam_sim_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/external
)

find_package(Threads REQUIRED)
target_link_libraries(aam_sim_core PUBLIC Threads::Threads)

# Main simulator CLI executable
add_executable(0700-aam-sim
    src/main.cpp
)
target_link_libraries(0700-aam-sim PRIVATE aam_sim_core)

# Compatibility alias for thumpbox-sim
add_custom_target(thumpbox-sim ALL
    COMMAND ${CMAKE_COMMAND} -E create_symlink 0700-aam-sim thumpbox-sim
    DEPENDS 0700-aam-sim
)

# Testing
enable_testing()

add_executable(test_protocol tests/test_protocol.cpp)
target_link_libraries(test_protocol PRIVATE aam_sim_core)
add_test(NAME ProtocolTest COMMAND test_protocol)

add_executable(test_hardware tests/test_hardware.cpp)
target_link_libraries(test_hardware PRIVATE aam_sim_core)
add_test(NAME HardwareTest COMMAND test_hardware)

add_executable(test_transport tests/test_transport.cpp)
target_link_libraries(test_transport PRIVATE aam_sim_core)
add_test(NAME TransportTest COMMAND test_transport)

add_executable(test_scenario tests/test_scenario.cpp)
target_link_libraries(test_scenario PRIVATE aam_sim_core)
add_test(NAME ScenarioGoldenTest COMMAND test_scenario
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/scenarios/pad_and_knob_flow.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden/pad_and_knob_flow.golden.json"
)
