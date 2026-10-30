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

#include <array>
#include <vector>
#include <string>
#include <functional>
#include <mutex>
#include <chrono>

namespace thumpbox::hardware {

constexpr size_t PADS_PER_BANK = 16;
constexpr size_t TOTAL_BANKS = 8; // Banks A through H
constexpr size_t TOTAL_PADS = PADS_PER_BANK * TOTAL_BANKS; // 128 pads
constexpr size_t NUM_QLINKS = 4;
constexpr size_t NUM_CV_CHANNELS = 4;
constexpr int SCREEN_WIDTH = 800;
constexpr int SCREEN_HEIGHT = 480;

struct PadState {
    bool                     pressed{false};
    uint8_t                  velocity{0};
    protocol::PadColourId    color{protocol::PadColourId::NeutralWhite};
    protocol::PadButtonState state{protocol::PadButtonState::StateOff};
    uint8_t                  aftertouch{0};
    bool                     blinking{false};
};

struct CvGateOutput {
    float voltage{0.0f}; // 0.0V to 10.0V
    bool  gate{false};    // High/Low
};

struct CvLogEntry {
    std::chrono::steady_clock::time_point timestamp;
    size_t channel;
    float voltage;
    bool gate;
};

enum class GestureType : uint8_t {
    None = 0,
    HandUp,
    HandDown,
    SwipeLeft,
    SwipeRight,
    Fist,
    Pinch,
    Wave
};

struct TouchPoint {
    int x{0};
    int y{0};
    bool down{false};
};

class VirtualDevice {
public:
    using PacketCallback = std::function<void(const protocol::Packet&)>;

    VirtualDevice();

    void set_packet_callback(PacketCallback cb) {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_packet_cb = std::move(cb);
    }

    // Process a packet received from the host / firmware
    void receive_host_packet(const protocol::Packet& pkt);

    // ================= Virtual Hardware Inputs =================
    // Pads
    void press_pad(uint8_t pad_index, uint8_t velocity = 127); // 0..15 in active bank
    void release_pad(uint8_t pad_index);
    void set_pad_aftertouch(uint8_t pad_index, uint8_t pressure);
    void select_bank(uint8_t bank_index); // 0..7 (Bank A..H)
    uint8_t get_active_bank() const;

    // Knobs
    void turn_qlink(uint8_t knob_index, int8_t ticks); // knob 0..3 (QLink 1..4)
    void set_qlink_value(uint8_t knob_index, uint8_t value);
    uint8_t get_qlink_value(uint8_t knob_index) const;

    // Jog wheel
    void turn_jog_wheel(int8_t ticks); // positive = CW, negative = CCW
    void press_jog_wheel();
    void release_jog_wheel();

    // Touch strip (slider)
    void touch_slider(uint8_t position); // 0..127
    void release_slider();
    bool is_slider_touched() const;
    uint8_t get_slider_position() const;

    // Buttons
    void press_button(protocol::ButtonId btn);
    void release_button(protocol::ButtonId btn);
    bool is_button_pressed(protocol::ButtonId btn) const;

    // Screen
    void inject_touch(int x, int y, bool down);
    TouchPoint get_last_touch() const;

    // AI Camera
    void inject_camera_gesture(GestureType gesture, uint8_t confidence = 100);
    GestureType get_last_gesture() const;

    // CV / Gate
    CvGateOutput get_cv_output(size_t channel) const;
    const std::vector<CvLogEntry>& get_cv_log() const;
    void clear_cv_log();

    // SD Card
    void set_sd_card_path(const std::string& path);
    std::string get_sd_card_path() const;
    bool is_sd_card_inserted() const;
    void set_sd_card_inserted(bool inserted);

    // Audio meters
    void set_audio_levels(float in_l, float in_r, float out_l, float out_r);
    void get_audio_levels(float& in_l, float& in_r, float& out_l, float& out_r) const;

    // State inspection
    PadState get_pad_state(uint8_t bank, uint8_t pad) const;
    PadState get_active_pad_state(uint8_t pad) const;
    uint8_t get_slider_led_level() const;
    bool get_button_led(protocol::ButtonId btn) const;

private:
    void send_packet_to_host(const protocol::Packet& pkt);

    mutable std::mutex m_mutex;
    PacketCallback m_packet_cb;

    // Pad Matrix: 8 banks x 16 pads = 128 pads
    uint8_t m_active_bank{0};
    std::array<PadState, TOTAL_PADS> m_pads;

    // Knobs & Encoders
    std::array<uint8_t, NUM_QLINKS> m_qlinks{0, 0, 0, 0};
    int m_jog_position{0};
    bool m_jog_clicked{false};

    // Touch Slider
    bool m_slider_touched{false};
    uint8_t m_slider_position{0};
    uint8_t m_slider_led_level{0};

    // Button states & Button LEDs
    std::array<bool, 64> m_button_states{};
    std::array<bool, 64> m_button_leds{};

    // CV/Gate Outputs
    std::array<CvGateOutput, NUM_CV_CHANNELS> m_cv_outputs{};
    std::vector<CvLogEntry> m_cv_log;

    // Camera
    GestureType m_last_gesture{GestureType::None};

    // Touchscreen
    TouchPoint m_last_touch;

    // SD Card
    std::string m_sd_card_path{"./sim_sdcard"};
    bool m_sd_card_inserted{true};

    // Audio
    float m_audio_in_l{0.0f};
    float m_audio_in_r{0.0f};
    float m_audio_out_l{0.0f};
    float m_audio_out_r{0.0f};
};

std::string gesture_to_string(GestureType gesture);

} // namespace thumpbox::hardware
