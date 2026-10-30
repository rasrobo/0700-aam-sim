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

using namespace thumpbox;

static std::atomic<bool> g_shutdown{false};

static void sigint_handler(int) {
    g_shutdown = true;
}

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

static void render_cli_dashboard(const hardware::VirtualDevice& dev) {
    std::cout << "\033[2J\033[H"; // Clear screen & home
    std::cout << "========================================================\n"
              << "              thumpbox-sim Virtual Device               \n"
              << "========================================================\n\n";

    // Banks & QLinks
    std::cout << "Active Bank: [" << static_cast<char>('A' + dev.get_active_bank()) << "]\n";
    std::cout << "Q-Link Knobs: ";
    for (size_t i = 0; i < hardware::NUM_QLINKS; ++i) {
        std::cout << "P" << (i + 1) << ":" << static_cast<int>(dev.get_qlink_value(i)) << "  ";
    }
    std::cout << "\nTouch Slider: " << static_cast<int>(dev.get_slider_position())
              << " (Touched: " << (dev.is_slider_touched() ? "YES" : "NO")
              << ", LED: " << static_cast<int>(dev.get_slider_led_level()) << "%)\n\n";

    // 4x4 Pad Grid for active bank
    std::cout << "Pads (Bank " << static_cast<char>('A' + dev.get_active_bank()) << "):\n";
    for (int row = 3; row >= 0; --row) {
        std::cout << "  ";
        for (int col = 0; col < 4; ++col) {
            int pad_idx = row * 4 + col;
            auto pad = dev.get_active_pad_state(pad_idx);
            if (pad.pressed) {
                std::cout << "[\033[1;32mPAD " << (pad_idx + 1) << " (V:" << static_cast<int>(pad.velocity) << ")\033[0m] ";
            } else {
                std::cout << "[ PAD " << (pad_idx + 1) << " ] ";
            }
        }
        std::cout << "\n";
    }

    std::cout << "\nTransport: "
              << "REC:" << (dev.is_button_pressed(protocol::ButtonId::Record) ? "ON " : "OFF ")
              << "PLAY:" << (dev.is_button_pressed(protocol::ButtonId::Play) ? "ON " : "OFF ")
              << "STOP:" << (dev.is_button_pressed(protocol::ButtonId::Stop) ? "ON " : "OFF ")
              << "SHIFT:" << (dev.is_button_pressed(protocol::ButtonId::Shift) ? "ON " : "OFF ")
              << "\n========================================================\n"
              << "Press Ctrl+C to exit.\n";
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

    while (!g_shutdown) {
        if (interactive) {
            render_cli_dashboard(device);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    std::cout << "\n[thumpbox-sim] Shutting down simulator...\n";
    transport->stop();
    return 0;
}
