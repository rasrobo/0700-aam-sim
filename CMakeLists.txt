cmake_minimum_required(VERSION 3.16)
project(thumpbox_sim VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Optimization and warning flags
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic -O2)
endif()

# Core static library
add_library(thumpbox_core STATIC
    src/protocol.cpp
    src/hardware.cpp
    src/transport.cpp
    src/scenario.cpp
)

target_include_directories(thumpbox_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/external
)

find_package(Threads REQUIRED)
target_link_libraries(thumpbox_core PUBLIC Threads::Threads)

# Main simulator CLI executable
add_executable(thumpbox-sim
    src/main.cpp
)
target_link_libraries(thumpbox-sim PRIVATE thumpbox_core)

# Testing
enable_testing()

add_executable(test_protocol tests/test_protocol.cpp)
target_link_libraries(test_protocol PRIVATE thumpbox_core)
add_test(NAME ProtocolTest COMMAND test_protocol)

add_executable(test_hardware tests/test_hardware.cpp)
target_link_libraries(test_hardware PRIVATE thumpbox_core)
add_test(NAME HardwareTest COMMAND test_hardware)

add_executable(test_transport tests/test_transport.cpp)
target_link_libraries(test_transport PRIVATE thumpbox_core)
add_test(NAME TransportTest COMMAND test_transport)

add_executable(test_scenario tests/test_scenario.cpp)
target_link_libraries(test_scenario PRIVATE thumpbox_core)
add_test(NAME ScenarioGoldenTest COMMAND test_scenario
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/scenarios/pad_and_knob_flow.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden/pad_and_knob_flow.golden.json"
)
