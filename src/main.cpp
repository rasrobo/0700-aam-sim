/*
 * Copyright (c) 2026 thumpbox-sim contributors
 *
 * This file is part of thumpbox-sim.
 *
 * thumpbox-sim is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

#include "thumpbox/protocol.hpp"
#include "thumpbox/hardware.hpp"
#include "thumpbox/transport.hpp"
#include "thumpbox/scenario.hpp"

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <memory>
#include <csignal>
#include <thread>
#include <chrono>
#include <termios.h>
#include <unistd.h>

using namespace thumpbox;

static std::atomic<bool> g_shutdown{false};

static void sigint_handler(int) {
    g_shutdown = true;
}

struct TerminalRawMode {
    struct termios orig_termios{};
    bool enabled{false};

    TerminalRawMode() {
        if (isatty(STDIN_FILENO)) {
            if (tcgetattr(STDIN_FILENO, &orig_termios) == 0) {
                struct termios raw = orig_termios;
                raw.c_lflag &= ~(ECHO | ICANON);
                raw.c_cc[VMIN] = 0;
                raw.c_cc[VTIME] = 1; // 100ms read timeout
                tcsetattr(STDIN_FILENO, TCSANOW, &raw);
                enabled = true;
            }
        }
    }

    ~TerminalRawMode() {
        if (enabled) {
            tcsetattr(STDIN_FILENO, TCSANOW, &orig_termios);
        }
    }
};

static void print_usage(const char* prog) {
    std::cout << "Usage: " << prog << " [options]\n\n"
              << "Options:\n"
              << "  --pty [symlink]                 Run simulator on a virtual PTY (default)\n"
              << "  --socket <path>                 Run Unix domain socket server\n"
              << "  --tcp <port>                    Run TCP socket server (e.g. 23040)\n"
              << "  --scenario <file.json>          Execute scenario headlessly\n"
              << "  --assert-golden <golden.json>   Compare scenario execution against golden file\n"
              << "  --record-golden <output.json>   Record scenario execution to golden file\n"
              << "  --interactive                   Launch interactive terminal console\n"
              << "  --help                          Display this help message\n";
}

static void render_cli_dashboard(const hardware::VirtualDevice& dev, uint8_t active_qlink) {
    std::cout << "\033[2J\033[H"; // Clear screen & home
    std::cout << "========================================================\n"
              << "              thumpbox-sim Virtual Device               \n"
              << "========================================================\n\n";

    // Banks & QLinks
    std::cout << "Active Bank: [" << static_cast<char>('A' + dev.get_active_bank()) << "]  (Switch: Shift+A..H)\n";
    std::cout << "Q-Link Knobs (Active: P" << (active_qlink + 1) << ", Select: 7/8/9/0, Turn: [ / ]):\n  ";
    for (size_t i = 0; i < hardware::NUM_QLINKS; ++i) {
        if (i == active_qlink) {
            std::cout << "\033[1;36m*P" << (i + 1) << ":" << static_cast<int>(dev.get_qlink_value(i)) << "*\033[0m  ";
        } else {
            std::cout << " P" << (i + 1) << ":" << static_cast<int>(dev.get_qlink_value(i)) << "   ";
        }
    }
    std::cout << "\n\nTouch Slider (Touch: t / Release: y): "
              << static_cast<int>(dev.get_slider_position())
              << " (Touched: " << (dev.is_slider_touched() ? "YES" : "NO")
              << ", Feedback LED: " << static_cast<int>(dev.get_slider_led_level()) << "%)\n\n";

    // 4x4 Pad Grid for active bank
    std::cout << "Pads (Bank " << static_cast<char>('A' + dev.get_active_bank()) << " - Keys 1-4, Q-R, A-F, Z-V):\n";
    const char* key_labels[4][4] = {
        {"1", "2", "3", "4"},
        {"q", "w", "e", "r"},
        {"a", "s", "d", "f"},
        {"z", "x", "c", "v"}
    };
    for (int row = 3; row >= 0; --row) {
        std::cout << "  ";
        for (int col = 0; col < 4; ++col) {
            int pad_idx = row * 4 + col;
            auto pad = dev.get_active_pad_state(pad_idx);
            if (pad.pressed) {
                std::cout << "[\033[1;32m" << key_labels[3 - row][col] << ":P" << (pad_idx + 1) << "\033[0m] ";
            } else {
                std::cout << "[ " << key_labels[3 - row][col] << ":P" << (pad_idx + 1) << " ] ";
            }
        }
        std::cout << "\n";
    }

    std::cout << "\nJog Wheel (CCW: < / CW: > / Push: Enter) | Gesture Inject: g\n"
              << "Transport (Space: Play | R: Rec | S: Stop):\n  "
              << "REC:" << (dev.is_button_pressed(protocol::ButtonId::Record) ? "\033[1;31mON \033[0m" : "OFF ")
              << "PLAY:" << (dev.is_button_pressed(protocol::ButtonId::Play) ? "\033[1;32mON \033[0m" : "OFF ")
              << "STOP:" << (dev.is_button_pressed(protocol::ButtonId::Stop) ? "\033[1;33mON \033[0m" : "OFF ")
              << "SHIFT:" << (dev.is_button_pressed(protocol::ButtonId::Shift) ? "ON " : "OFF ")
              << "\n========================================================\n"
              << "Press Ctrl+C or 'x' while stopped to exit.\n";
}

int main(int argc, char** argv) {
    std::signal(SIGINT, sigint_handler);
    std::signal(SIGTERM, sigint_handler);

    std::string scenario_path;
    std::string assert_golden_path;
    std::string record_golden_path;
    std::string socket_path;
    std::string symlink_path;
    int tcp_port = 0;
    bool interactive = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--help") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--scenario" && i + 1 < argc) {
            scenario_path = argv[++i];
        } else if (arg == "--assert-golden" && i + 1 < argc) {
            assert_golden_path = argv[++i];
        } else if (arg == "--record-golden" && i + 1 < argc) {
            record_golden_path = argv[++i];
        } else if (arg == "--socket" && i + 1 < argc) {
            socket_path = argv[++i];
        } else if (arg == "--tcp" && i + 1 < argc) {
            tcp_port = std::stoi(argv[++i]);
        } else if (arg == "--pty") {
            if (i + 1 < argc && argv[i + 1][0] != '-') {
                symlink_path = argv[++i];
            }
        } else if (arg == "--interactive") {
            interactive = true;
        }
    }

    hardware::VirtualDevice device;

    // Headless scenario execution
    if (!scenario_path.empty()) {
        transport::MockTransport mock_transport(device);
        scenario::ScenarioRunner runner(device, mock_transport);

        std::cout << "[thumpbox-sim] Running scenario: " << scenario_path << "\n";
        auto res = runner.run_file(scenario_path);

        if (!res.passed) {
            std::cerr << "[thumpbox-sim] Scenario FAILED with " << res.errors.size() << " errors:\n";
            for (const auto& err : res.errors) {
                std::cerr << "  - " << err << "\n";
            }
            return 1;
        }

        std::cout << "[thumpbox-sim] Scenario passed: " << res.scenario_name << "\n";

        if (!record_golden_path.empty()) {
            if (scenario::ScenarioRunner::save_golden(record_golden_path, res.execution_trace)) {
                std::cout << "[thumpbox-sim] Recorded golden trace to: " << record_golden_path << "\n";
            } else {
                std::cerr << "[thumpbox-sim] Failed to write golden file: " << record_golden_path << "\n";
                return 1;
            }
        }

        if (!assert_golden_path.empty()) {
            std::ifstream gf(assert_golden_path);
            if (!gf.is_open()) {
                std::cerr << "[thumpbox-sim] Golden file not found: " << assert_golden_path << "\n";
                return 1;
            }
            nlohmann::json golden_trace;
            gf >> golden_trace;

            std::vector<std::string> diffs;
            if (!scenario::ScenarioRunner::compare_with_golden(res.execution_trace, golden_trace, diffs)) {
                std::cerr << "[thumpbox-sim] Golden-file assertion FAILED:\n";
                for (const auto& d : diffs) {
                    std::cerr << "  - " << d << "\n";
                }
                return 1;
            }
            std::cout << "[thumpbox-sim] Golden trace match SUCCESS: " << assert_golden_path << "\n";
        }

        return 0;
    }

    // Live Simulator Transport Setup
    std::unique_ptr<transport::ITransport> transport;
    if (!socket_path.empty() || tcp_port > 0) {
        transport = std::make_unique<transport::SocketTransport>(device, socket_path, tcp_port);
    } else {
        transport = std::make_unique<transport::PtyTransport>(device, symlink_path);
    }

    if (!transport->start()) {
        std::cerr << "[thumpbox-sim] Error: Failed to start transport on "
                  << transport->get_endpoint_name() << "\n";
        return 1;
    }

    std::cout << "[thumpbox-sim] Simulator listening on: " << transport->get_endpoint_name() << "\n";
    if (!symlink_path.empty()) {
        std::cout << "[thumpbox-sim] Symlink created at: " << symlink_path << "\n";
    }

    uint8_t active_qlink = 0;
    std::unique_ptr<TerminalRawMode> raw_mode;
    if (interactive) {
        raw_mode = std::make_unique<TerminalRawMode>();
    }

    uint8_t current_gesture_idx = 1;

    while (!g_shutdown) {
        if (interactive) {
            render_cli_dashboard(device, active_qlink);

            char ch = 0;
            if (read(STDIN_FILENO, &ch, 1) > 0) {
                // Pad mappings (velocity 127)
                int pad_hit = -1;
                switch (ch) {
                    // Row 4
                    case '1': pad_hit = 12; break;
                    case '2': pad_hit = 13; break;
                    case '3': pad_hit = 14; break;
                    case '4': pad_hit = 15; break;
                    // Row 3
                    case 'q': pad_hit = 8; break;
                    case 'w': pad_hit = 9; break;
                    case 'e': pad_hit = 10; break;
                    case 'r': pad_hit = 11; break;
                    // Row 2
                    case 'a': pad_hit = 4; break;
                    case 's': pad_hit = 5; break;
                    case 'd': pad_hit = 6; break;
                    case 'f': pad_hit = 7; break;
                    // Row 1
                    case 'z': pad_hit = 0; break;
                    case 'x': pad_hit = 1; break;
                    case 'c': pad_hit = 2; break;
                    case 'v': pad_hit = 3; break;

                    // Q-Link selection
                    case '7': active_qlink = 0; break;
                    case '8': active_qlink = 1; break;
                    case '9': active_qlink = 2; break;
                    case '0': active_qlink = 3; break;
                    case '[': device.turn_qlink(active_qlink, -5); break;
                    case ']': device.turn_qlink(active_qlink, +5); break;

                    // Jog wheel
                    case '<':
                    case ',': device.turn_jog_wheel(-1); break;
                    case '>':
                    case '.': device.turn_jog_wheel(+1); break;
                    case '\n':
                    case '\r':
                        device.press_jog_wheel();
                        std::this_thread::sleep_for(std::chrono::milliseconds(50));
                        device.release_jog_wheel();
                        break;

                    // Slider
                    case 't': device.touch_slider((device.get_slider_position() + 20) % 128); break;
                    case 'y': device.release_slider(); break;

                    // Transport
                    case ' ':
                        if (device.is_button_pressed(protocol::ButtonId::Play)) {
                            device.release_button(protocol::ButtonId::Play);
                        } else {
                            device.press_button(protocol::ButtonId::Play);
                        }
                        break;
                    case 'R':
                        if (device.is_button_pressed(protocol::ButtonId::Record)) {
                            device.release_button(protocol::ButtonId::Record);
                        } else {
                            device.press_button(protocol::ButtonId::Record);
                        }
                        break;
                    case 'S':
                        device.press_button(protocol::ButtonId::Stop);
                        std::this_thread::sleep_for(std::chrono::milliseconds(50));
                        device.release_button(protocol::ButtonId::Stop);
                        break;

                    // Banks A..H
                    case 'A': device.select_bank(0); break;
                    case 'B': device.select_bank(1); break;
                    case 'C': device.select_bank(2); break;
                    case 'D': device.select_bank(3); break;
                    case 'E': device.select_bank(4); break;
                    case 'F': device.select_bank(5); break;
                    case 'G': device.select_bank(6); break;
                    case 'H': device.select_bank(7); break;

                    // Gesture injection
                    case 'g': {
                        auto g = static_cast<hardware::GestureType>(current_gesture_idx);
                        device.inject_camera_gesture(g, 95);
                        current_gesture_idx = (current_gesture_idx % 7) + 1;
                        break;
                    }

                    case 3: // Ctrl+C
                        g_shutdown = true;
                        break;
                }

                if (pad_hit >= 0) {
                    device.press_pad(pad_hit, 127);
                    render_cli_dashboard(device, active_qlink);
                    std::this_thread::sleep_for(std::chrono::milliseconds(40));
                    device.release_pad(pad_hit);
                }
            }
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }

    std::cout << "\n[thumpbox-sim] Shutting down simulator...\n";
    transport->stop();
    return 0;
}
