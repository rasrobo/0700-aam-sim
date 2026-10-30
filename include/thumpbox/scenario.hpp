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

#pragma once

#include "thumpbox/protocol.hpp"
#include "thumpbox/hardware.hpp"
#include "thumpbox/transport.hpp"

#include <string>
#include <vector>
#include <nlohmann/json.hpp>

namespace thumpbox::scenario {

struct ScenarioResult {
    bool passed{true};
    std::string scenario_name;
    std::vector<std::string> errors;
    nlohmann::json execution_trace;
};

class ScenarioRunner {
public:
    explicit ScenarioRunner(hardware::VirtualDevice& device, transport::MockTransport& transport);

    // Executes a scenario defined in JSON string or file
    ScenarioResult run_file(const std::string& json_path);
    ScenarioResult run_json(const nlohmann::json& scenario_json);

    // Compares an execution trace against a golden-file trace JSON
    static bool compare_with_golden(const nlohmann::json& actual_trace,
                                    const nlohmann::json& golden_trace,
                                    std::vector<std::string>& diffs);

    // Saves trace to file
    static bool save_golden(const std::string& path, const nlohmann::json& trace);

private:
    hardware::VirtualDevice&   m_device;
    transport::MockTransport& m_transport;

    void execute_action(const nlohmann::json& action, std::vector<std::string>& errors);
    void execute_assertion(const nlohmann::json& assertion, std::vector<std::string>& errors);
};

} // namespace thumpbox::scenario
