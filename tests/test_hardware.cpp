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

#include "thumpbox/hardware.hpp"
#include "thumpbox/transport.hpp"

#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>

using namespace thumpbox;

void test_pad_banks_and_velocity() {
    std::cout << "[TEST] test_pad_banks_and_velocity... ";

    hardware::VirtualDevice dev;
    transport::MockTransport transport(dev);

    assert(dev.get_active_bank() == 0);

    // Hit pad 5 on bank A with velocity 110
    dev.press_pad(5, 110);
    auto p5 = dev.get_active_pad_state(5);
    assert(p5.pressed == true);
    assert(p5.velocity == 110);

    auto pkts = transport.take_packets_sent_to_host();
    assert(pkts.size() == 1);
    assert(pkts[0].type == protocol::PacketType::Pad);
    assert(pkts[0].data[0] == 5);
    assert(pkts[0].data[1] == 1); // pressed
    assert(pkts[0].data[2] == 110);
    assert(pkts[0].data[3] == 0); // Bank A

    // Switch to Bank C (bank 2)
    dev.select_bank(2);
    assert(dev.get_active_bank() == 2);
    // Pad 5 on Bank C should still be unpressed
    auto p5_c = dev.get_active_pad_state(5);
    assert(p5_c.pressed == false);

    std::cout << "PASSED\n";
}

void test_knob_and_jog_rotaries() {
    std::cout << "[TEST] test_knob_and_jog_rotaries... ";

    hardware::VirtualDevice dev;
    transport::MockTransport transport(dev);

    dev.turn_qlink(0, 10);
    assert(dev.get_qlink_value(0) == 10);

    dev.turn_qlink(0, -5);
    assert(dev.get_qlink_value(0) == 5);

    auto pkts = transport.take_packets_sent_to_host();
    assert(pkts.size() == 2);
    assert(pkts[0].type == protocol::PacketType::Knobs);
    assert(pkts[0].data[0] == 0); // knob 0
    assert(pkts[0].data[1] == 1); // CW
    assert(pkts[1].data[1] == 0); // CCW

    // Test Jog wheel
    dev.turn_jog_wheel(3);
    auto jog_pkts = transport.take_packets_sent_to_host();
    assert(jog_pkts.size() == 1);
    assert(jog_pkts[0].type == protocol::PacketType::Knobs);
    assert(jog_pkts[0].cmd == static_cast<uint8_t>(protocol::KnobCmd::Rotary));

    std::cout << "PASSED\n";
}

void test_touch_strip_slider() {
    std::cout << "[TEST] test_touch_strip_slider... ";

    hardware::VirtualDevice dev;
    transport::MockTransport transport(dev);

    dev.touch_slider(95);
    assert(dev.is_slider_touched() == true);
    assert(dev.get_slider_position() == 95);

    dev.release_slider();
    assert(dev.is_slider_touched() == false);

    // Host updates slider LED level to 80%
    protocol::Packet host_pkt;
    host_pkt.type = protocol::PacketType::Slider;
    host_pkt.dir  = protocol::PacketDir::Request;
    host_pkt.cmd  = static_cast<uint8_t>(protocol::SliderCmd::LevelLed);
    host_pkt.data = {80};
    dev.receive_host_packet(host_pkt);

    assert(dev.get_slider_led_level() == 80);

    std::cout << "PASSED\n";
}

void test_cv_gate_outputs() {
    std::cout << "[TEST] test_cv_gate_outputs... ";

    hardware::VirtualDevice dev;

    // Host sends CV output for channel 1: 5.0V (DAC ~ 32768) and gate High
    protocol::Packet cv_pkt;
    cv_pkt.type = protocol::PacketType::Cv;
    cv_pkt.dir  = protocol::PacketDir::Request;
    cv_pkt.cmd  = static_cast<uint8_t>(protocol::CvCmd::SetOutput);
    cv_pkt.data = {1, 0x80, 0x00, 1}; // Ch 1, 32768 (5.0V), Gate 1
    dev.receive_host_packet(cv_pkt);

    auto cv = dev.get_cv_output(1);
    assert(cv.gate == true);
    assert(cv.voltage >= 4.9f && cv.voltage <= 5.1f);

    const auto& log = dev.get_cv_log();
    assert(log.size() == 1);
    assert(log[0].channel == 1);
    assert(log[0].gate == true);

    std::cout << "PASSED\n";
}

void test_camera_and_sd_card() {
    std::cout << "[TEST] test_camera_and_sd_card... ";

    hardware::VirtualDevice dev;
    transport::MockTransport transport(dev);

    dev.inject_camera_gesture(hardware::GestureType::SwipeRight, 95);
    assert(dev.get_last_gesture() == hardware::GestureType::SwipeRight);

    auto pkts = transport.take_packets_sent_to_host();
    assert(pkts.size() == 1);
    assert(pkts[0].data[0] == static_cast<uint8_t>(hardware::GestureType::SwipeRight));
    assert(pkts[0].data[1] == 95);

    // SD Card
    dev.set_sd_card_path("/tmp/mock_sd");
    assert(dev.get_sd_card_path() == "/tmp/mock_sd");
    assert(dev.is_sd_card_inserted() == true);

    std::cout << "PASSED\n";
}

int main() {
    std::cout << "=== Running Virtual Hardware Tests ===\n";
    test_pad_banks_and_velocity();
    test_knob_and_jog_rotaries();
    test_touch_strip_slider();
    test_cv_gate_outputs();
    test_camera_and_sd_card();
    std::cout << "All Virtual Hardware Tests PASSED.\n";
    return 0;
}
