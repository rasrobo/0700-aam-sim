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

#include "thumpbox/scenario.hpp"

#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>
#include <fstream>

using namespace thumpbox;

int main(int argc, char** argv) {
    std::cout << "=== Running Scenario & Golden-File Tests ===\n";

    std::string scenario_file = "tests/scenarios/pad_and_knob_flow.json";
    std::string golden_file   = "tests/golden/pad_and_knob_flow.golden.json";

    if (argc > 1) {
        scenario_file = argv[1];
    }
    if (argc > 2) {
        golden_file = argv[2];
    }

    hardware::VirtualDevice device;
    transport::MockTransport transport(device);
    scenario::ScenarioRunner runner(device, transport);

    auto result = runner.run_file(scenario_file);
    if (!result.passed) {
        std::cerr << "Scenario run failed with errors:\n";
        for (const auto& err : result.errors) {
            std::cerr << "  - " << err << "\n";
        }
        return 1;
    }

    // Check against golden file
    std::ifstream gf(golden_file);
    if (!gf.is_open()) {
        std::cerr << "Failed to open golden file: " << golden_file << "\n";
        return 1;
    }

    nlohmann::json golden_trace;
    gf >> golden_trace;

    std::vector<std::string> diffs;
    if (!scenario::ScenarioRunner::compare_with_golden(result.execution_trace, golden_trace, diffs)) {
        std::cerr << "Golden comparison failed with diffs:\n";
        for (const auto& d : diffs) {
            std::cerr << "  - " << d << "\n";
        }
        return 1;
    }

    std::cout << "Scenario and Golden Match: SUCCESS\n";
    return 0;
}
