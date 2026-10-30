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

#include <fstream>
#include <sstream>
#include <thread>
#include <cmath>

namespace thumpbox::scenario {

static protocol::ButtonId parse_button_id(const std::string& name) {
    if (name == "BankA") return protocol::ButtonId::BankA;
    if (name == "BankB") return protocol::ButtonId::BankB;
    if (name == "BankC") return protocol::ButtonId::BankC;
    if (name == "BankD") return protocol::ButtonId::BankD;
    if (name == "BankE") return protocol::ButtonId::BankE;
    if (name == "BankF") return protocol::ButtonId::BankF;
    if (name == "BankG") return protocol::ButtonId::BankG;
    if (name == "BankH") return protocol::ButtonId::BankH;
    if (name == "Record") return protocol::ButtonId::Record;
    if (name == "Overdub") return protocol::ButtonId::Overdub;
    if (name == "Stop") return protocol::ButtonId::Stop;
    if (name == "Play") return protocol::ButtonId::Play;
    if (name == "PlayStart") return protocol::ButtonId::PlayStart;
    if (name == "Shift") return protocol::ButtonId::Shift;
    if (name == "KnobEnter") return protocol::ButtonId::KnobEnter;
    if (name == "TapTempo") return protocol::ButtonId::TapTempo;
    if (name == "NoteRepeat") return protocol::ButtonId::NoteRepeat;
    if (name == "MainMode") return protocol::ButtonId::MainMode;
    if (name == "Browse") return protocol::ButtonId::Browse;
    if (name == "TrackMix") return protocol::ButtonId::TrackMix;
    if (name == "TrackMute") return protocol::ButtonId::TrackMute;
    if (name == "Link") return protocol::ButtonId::Link;
    if (name == "Erase") return protocol::ButtonId::Erase;
    return protocol::ButtonId::Invalid;
}

static hardware::GestureType parse_gesture(const std::string& name) {
    if (name == "HandUp") return hardware::GestureType::HandUp;
    if (name == "HandDown") return hardware::GestureType::HandDown;
    if (name == "SwipeLeft") return hardware::GestureType::SwipeLeft;
    if (name == "SwipeRight") return hardware::GestureType::SwipeRight;
    if (name == "Fist") return hardware::GestureType::Fist;
    if (name == "Pinch") return hardware::GestureType::Pinch;
    if (name == "Wave") return hardware::GestureType::Wave;
    return hardware::GestureType::None;
}

ScenarioRunner::ScenarioRunner(hardware::VirtualDevice& device, transport::MockTransport& transport)
    : m_device(device), m_transport(transport) {}

ScenarioResult ScenarioRunner::run_file(const std::string& json_path) {
    ScenarioResult result;
    std::ifstream file(json_path);
    if (!file.is_open()) {
        result.passed = false;
        result.errors.push_back("Failed to open scenario file: " + json_path);
        return result;
    }

    try {
        nlohmann::json root;
        file >> root;
        return run_json(root);
    } catch (const std::exception& e) {
        result.passed = false;
        result.errors.push_back(std::string("JSON parse error: ") + e.what());
        return result;
    }
}

ScenarioResult ScenarioRunner::run_json(const nlohmann::json& scenario_json) {
    ScenarioResult result;
    result.scenario_name = scenario_json.value("name", "Unnamed Scenario");
    m_transport.clear_sent_packets();

    nlohmann::json trace_packets = nlohmann::json::array();

    if (scenario_json.contains("steps") && scenario_json["steps"].is_array()) {
        for (const auto& step : scenario_json["steps"]) {
            std::string type = step.value("type", "");

            if (type == "action") {
                execute_action(step, result.errors);
            } else if (type == "assertion") {
                execute_assertion(step, result.errors);
            } else if (type == "wait") {
                int ms = step.value("ms", 10);
                std::this_thread::sleep_for(std::chrono::milliseconds(ms));
            }
        }
    }

    // Capture all packets that were emitted during execution
    const auto& emitted = m_transport.get_packets_sent_to_host();
    for (const auto& pkt : emitted) {
        nlohmann::json pj;
        pj["type"] = protocol::packet_type_to_string(pkt.type);
        pj["dir"]  = protocol::packet_dir_to_string(pkt.dir);
        pj["cmd"]  = pkt.cmd;
        pj["data"] = pkt.data;
        trace_packets.push_back(pj);
    }

    // Capture final hardware state
    nlohmann::json hw_state;
    hw_state["active_bank"] = m_device.get_active_bank();
    hw_state["slider_touched"] = m_device.is_slider_touched();
    hw_state["slider_position"] = m_device.get_slider_position();
    hw_state["slider_led_level"] = m_device.get_slider_led_level();

    nlohmann::json qlinks = nlohmann::json::array();
    for (size_t i = 0; i < hardware::NUM_QLINKS; ++i) {
        qlinks.push_back(m_device.get_qlink_value(static_cast<uint8_t>(i)));
    }
    hw_state["qlinks"] = qlinks;

    nlohmann::json cvs = nlohmann::json::array();
    for (size_t i = 0; i < hardware::NUM_CV_CHANNELS; ++i) {
        auto cv = m_device.get_cv_output(i);
        nlohmann::json c;
        c["channel"] = i;
        c["voltage"] = std::round(cv.voltage * 100.0f) / 100.0f;
        c["gate"] = cv.gate;
        cvs.push_back(c);
    }
    hw_state["cv_outputs"] = cvs;

    result.execution_trace["scenario_name"] = result.scenario_name;
    result.execution_trace["emitted_packets"] = trace_packets;
    result.execution_trace["final_state"] = hw_state;

    result.passed = result.errors.empty();
    return result;
}

void ScenarioRunner::execute_action(const nlohmann::json& action, std::vector<std::string>& errors) {
    std::string name = action.value("action", "");

    if (name == "press_pad") {
        uint8_t pad = action.value("pad", 0);
        uint8_t vel = action.value("velocity", 127);
        m_device.press_pad(pad, vel);
    } else if (name == "release_pad") {
        uint8_t pad = action.value("pad", 0);
        m_device.release_pad(pad);
    } else if (name == "select_bank") {
        uint8_t bank = action.value("bank", 0);
        m_device.select_bank(bank);
    } else if (name == "turn_qlink") {
        uint8_t knob = action.value("knob", 0);
        int8_t ticks = action.value("ticks", 1);
        m_device.turn_qlink(knob, ticks);
    } else if (name == "turn_jog") {
        int8_t ticks = action.value("ticks", 1);
        m_device.turn_jog_wheel(ticks);
    } else if (name == "press_button") {
        std::string btn_str = action.value("button", "");
        auto btn = parse_button_id(btn_str);
        if (btn != protocol::ButtonId::Invalid) {
            m_device.press_button(btn);
        } else {
            errors.push_back("Unknown button in press_button: " + btn_str);
        }
    } else if (name == "release_button") {
        std::string btn_str = action.value("button", "");
        auto btn = parse_button_id(btn_str);
        if (btn != protocol::ButtonId::Invalid) {
            m_device.release_button(btn);
        } else {
            errors.push_back("Unknown button in release_button: " + btn_str);
        }
    } else if (name == "touch_slider") {
        uint8_t pos = action.value("position", 64);
        m_device.touch_slider(pos);
    } else if (name == "release_slider") {
        m_device.release_slider();
    } else if (name == "inject_gesture") {
        std::string g_str = action.value("gesture", "");
        uint8_t conf = action.value("confidence", 100);
        m_device.inject_camera_gesture(parse_gesture(g_str), conf);
    } else if (name == "host_send_packet") {
        protocol::Packet pkt;
        std::string type_str = action.value("pkt_type", "Pad");
        if (type_str == "Pad") pkt.type = protocol::PacketType::Pad;
        else if (type_str == "Led") pkt.type = protocol::PacketType::Led;
        else if (type_str == "Slider") pkt.type = protocol::PacketType::Slider;
        else if (type_str == "Cv") pkt.type = protocol::PacketType::Cv;
        else pkt.type = protocol::PacketType::System;

        pkt.dir = protocol::PacketDir::Request;
        pkt.cmd = action.value("cmd", 0);
        if (action.contains("data") && action["data"].is_array()) {
            for (auto& d : action["data"]) {
                pkt.data.push_back(static_cast<uint8_t>(d.get<int>()));
            }
        }
        m_transport.host_send_packet(pkt);
    } else {
        errors.push_back("Unknown action: " + name);
    }
}

void ScenarioRunner::execute_assertion(const nlohmann::json& assertion, std::vector<std::string>& errors) {
    std::string assert_name = assertion.value("assert", "");

    if (assert_name == "active_bank") {
        uint8_t expected = assertion.value("expected", 0);
        if (m_device.get_active_bank() != expected) {
            errors.push_back("active_bank mismatch: expected " + std::to_string(expected) +
                             " got " + std::to_string(m_device.get_active_bank()));
        }
    } else if (assert_name == "pad_state") {
        uint8_t bank = assertion.value("bank", m_device.get_active_bank());
        uint8_t pad  = assertion.value("pad", 0);
        auto state = m_device.get_pad_state(bank, pad);

        if (assertion.contains("pressed")) {
            bool exp_pressed = assertion["pressed"];
            if (state.pressed != exp_pressed) {
                errors.push_back("pad_state pressed mismatch on bank " + std::to_string(bank) +
                                 " pad " + std::to_string(pad));
            }
        }
        if (assertion.contains("color_id")) {
            uint8_t exp_clr = assertion["color_id"];
            if (static_cast<uint8_t>(state.color) != exp_clr) {
                errors.push_back("pad_state color mismatch on bank " + std::to_string(bank) +
                                 " pad " + std::to_string(pad) + ": expected " +
                                 std::to_string(exp_clr) + " got " +
                                 std::to_string(static_cast<uint8_t>(state.color)));
            }
        }
    } else if (assert_name == "qlink_value") {
        uint8_t knob = assertion.value("knob", 0);
        uint8_t exp_val = assertion.value("expected", 0);
        if (m_device.get_qlink_value(knob) != exp_val) {
            errors.push_back("qlink_value mismatch for knob " + std::to_string(knob) +
                             ": expected " + std::to_string(exp_val) +
                             " got " + std::to_string(m_device.get_qlink_value(knob)));
        }
    } else if (assert_name == "slider_led_level") {
        uint8_t exp_level = assertion.value("expected", 0);
        if (m_device.get_slider_led_level() != exp_level) {
            errors.push_back("slider_led_level mismatch: expected " + std::to_string(exp_level) +
                             " got " + std::to_string(m_device.get_slider_led_level()));
        }
    } else if (assert_name == "cv_output") {
        size_t ch = assertion.value("channel", 0);
        auto cv = m_device.get_cv_output(ch);
        if (assertion.contains("gate")) {
            bool exp_gate = assertion["gate"];
            if (cv.gate != exp_gate) {
                errors.push_back("cv_output gate mismatch on channel " + std::to_string(ch));
            }
        }
        if (assertion.contains("voltage_approx")) {
            float exp_v = assertion["voltage_approx"];
            if (std::abs(cv.voltage - exp_v) > 0.1f) {
                errors.push_back("cv_output voltage mismatch on channel " + std::to_string(ch) +
                                 ": expected approx " + std::to_string(exp_v) +
                                 " got " + std::to_string(cv.voltage));
            }
        }
    } else {
        errors.push_back("Unknown assertion: " + assert_name);
    }
}

bool ScenarioRunner::compare_with_golden(const nlohmann::json& actual_trace,
                                        const nlohmann::json& golden_trace,
                                        std::vector<std::string>& diffs) {
    if (actual_trace == golden_trace) {
        return true;
    }

    if (actual_trace["emitted_packets"] != golden_trace["emitted_packets"]) {
        diffs.push_back("Packet sequence mismatch between actual and golden trace.");
    }
    if (actual_trace["final_state"] != golden_trace["final_state"]) {
        diffs.push_back("Final hardware state mismatch between actual and golden trace.");
    }

    return diffs.empty();
}

bool ScenarioRunner::save_golden(const std::string& path, const nlohmann::json& trace) {
    std::ofstream file(path);
    if (!file.is_open()) return false;
    file << trace.dump(2) << std::endl;
    return true;
}

} // namespace thumpbox::scenario
