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

#include <cmath>
#include <algorithm>

namespace thumpbox::hardware {

VirtualDevice::VirtualDevice() {
    for (auto& pad : m_pads) {
        pad.color = protocol::PadColourId::NeutralWhite;
        pad.state = protocol::PadButtonState::StateOff;
        pad.pressed = false;
        pad.velocity = 0;
        pad.aftertouch = 0;
        pad.blinking = false;
    }
}

void VirtualDevice::send_packet_to_host(const protocol::Packet& pkt) {
    if (m_packet_cb) {
        m_packet_cb(pkt);
    }
}

void VirtualDevice::receive_host_packet(const protocol::Packet& pkt) {
    std::lock_guard<std::mutex> lock(m_mutex);

    switch (pkt.type) {
        case protocol::PacketType::System: {
            if (pkt.cmd == static_cast<uint8_t>(protocol::SysCmd::CommInit)) {
                protocol::Packet response;
                response.type = protocol::PacketType::System;
                response.dir  = protocol::PacketDir::Response;
                response.cmd  = static_cast<uint8_t>(protocol::SysCmd::CommInit);
                response.data = {1}; // 1 = EN_SYS_COMM_CONNECTED
                send_packet_to_host(response);
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::SysCmd::GetSwVersion)) {
                protocol::Packet response;
                response.type = protocol::PacketType::System;
                response.dir  = protocol::PacketDir::Response;
                response.cmd  = static_cast<uint8_t>(protocol::SysCmd::GetSwVersion);
                response.data = {1, 0, 0, 0}; // 1.0.0
                send_packet_to_host(response);
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::SysCmd::CheckCommStatus)) {
                protocol::Packet response;
                response.type = protocol::PacketType::System;
                response.dir  = protocol::PacketDir::Response;
                response.cmd  = static_cast<uint8_t>(protocol::SysCmd::CheckCommStatus);
                response.data = {0}; // 0 = EN_COMM_STATUS_SUCCESS
                send_packet_to_host(response);
            }
            break;
        }

        case protocol::PacketType::Pad: {
            if (pkt.cmd == static_cast<uint8_t>(protocol::PadCmd::SetSinglePad)) {
                if (pkt.data.size() >= 3) {
                    uint8_t pad_idx  = pkt.data[0];
                    uint8_t bank_idx = pkt.data[1];
                    uint8_t clr_id   = pkt.data[2];
                    if (pad_idx < PADS_PER_BANK && bank_idx < TOTAL_BANKS) {
                        size_t idx = bank_idx * PADS_PER_BANK + pad_idx;
                        m_pads[idx].color = static_cast<protocol::PadColourId>(clr_id);
                    }
                }
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::PadCmd::SetAllSingleColour)) {
                if (pkt.data.size() >= 2) {
                    uint8_t bank_idx = pkt.data[0];
                    uint8_t clr_id   = pkt.data[1];
                    if (bank_idx < TOTAL_BANKS) {
                        for (size_t p = 0; p < PADS_PER_BANK; ++p) {
                            m_pads[bank_idx * PADS_PER_BANK + p].color = static_cast<protocol::PadColourId>(clr_id);
                        }
                    }
                }
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::PadCmd::SetAllMultiColour)) {
                if (pkt.data.size() >= PADS_PER_BANK) {
                    for (size_t p = 0; p < PADS_PER_BANK; ++p) {
                        m_pads[m_active_bank * PADS_PER_BANK + p].color = static_cast<protocol::PadColourId>(pkt.data[p]);
                    }
                }
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::PadCmd::SetColourState)) {
                if (pkt.data.size() >= 3) {
                    uint8_t start_pad = pkt.data[0];
                    uint8_t end_pad   = pkt.data[1];
                    uint8_t state     = pkt.data[2];
                    for (uint8_t p = start_pad; p <= end_pad && p < PADS_PER_BANK; ++p) {
                        m_pads[m_active_bank * PADS_PER_BANK + p].state = static_cast<protocol::PadButtonState>(state);
                    }
                }
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::PadCmd::SetBlinking)) {
                if (pkt.data.size() >= 3) {
                    uint8_t pad_idx  = pkt.data[0];
                    uint8_t bank_idx = pkt.data[1];
                    bool    blinking = (pkt.data[2] != 0);
                    if (pad_idx < PADS_PER_BANK && bank_idx < TOTAL_BANKS) {
                        m_pads[bank_idx * PADS_PER_BANK + pad_idx].blinking = blinking;
                    }
                }
            }
            break;
        }

        case protocol::PacketType::Led: {
            if (pkt.cmd == static_cast<uint8_t>(protocol::LedCmd::SetSingleLed)) {
                if (pkt.data.size() >= 2) {
                    uint8_t btn_id = pkt.data[0];
                    bool on = (pkt.data[1] != 0);
                    if (btn_id < m_button_leds.size()) {
                        m_button_leds[btn_id] = on;
                    }
                }
            } else if (pkt.cmd == static_cast<uint8_t>(protocol::LedCmd::SetAll)) {
                if (!pkt.data.empty()) {
                    bool on = (pkt.data[0] != 0);
                    m_button_leds.fill(on);
                }
            }
            break;
        }

        case protocol::PacketType::Slider: {
            if (pkt.cmd == static_cast<uint8_t>(protocol::SliderCmd::LevelLed) ||
                pkt.cmd == static_cast<uint8_t>(protocol::SliderCmd::BarLed)) {
                if (!pkt.data.empty()) {
                    m_slider_led_level = pkt.data[0];
                }
            }
            break;
        }

        case protocol::PacketType::Cv: {
            if (pkt.data.size() >= 4) {
                size_t ch = pkt.data[0];
                if (ch < NUM_CV_CHANNELS) {
                    uint16_t raw_val = (static_cast<uint16_t>(pkt.data[1]) << 8) | pkt.data[2];
                    float voltage = (static_cast<float>(raw_val) / 65535.0f) * 10.0f;
                    bool gate = (pkt.data[3] != 0);

                    m_cv_outputs[ch].voltage = voltage;
                    m_cv_outputs[ch].gate = gate;

                    CvLogEntry entry;
                    entry.timestamp = std::chrono::steady_clock::now();
                    entry.channel = ch;
                    entry.voltage = voltage;
                    entry.gate = gate;
                    m_cv_log.push_back(entry);
                }
            }
            break;
        }

        default:
            break;
    }
}

void VirtualDevice::press_pad(uint8_t pad_index, uint8_t velocity) {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (pad_index >= PADS_PER_BANK) return;

    size_t idx = m_active_bank * PADS_PER_BANK + pad_index;
    m_pads[idx].pressed = true;
    m_pads[idx].velocity = velocity;

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Pad;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::PadCmd::State);
    pkt.data = {pad_index, 1 /*pressed*/, velocity, m_active_bank};
    send_packet_to_host(pkt);
}

void VirtualDevice::release_pad(uint8_t pad_index) {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (pad_index >= PADS_PER_BANK) return;

    size_t idx = m_active_bank * PADS_PER_BANK + pad_index;
    m_pads[idx].pressed = false;
    m_pads[idx].velocity = 0;

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Pad;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::PadCmd::State);
    pkt.data = {pad_index, 0 /*released*/, 0, m_active_bank};
    send_packet_to_host(pkt);
}

void VirtualDevice::set_pad_aftertouch(uint8_t pad_index, uint8_t pressure) {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (pad_index >= PADS_PER_BANK) return;

    size_t idx = m_active_bank * PADS_PER_BANK + pad_index;
    m_pads[idx].aftertouch = pressure;

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Pad;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::PadCmd::SetAfterTouch);
    pkt.data = {pad_index, pressure, m_active_bank};
    send_packet_to_host(pkt);
}

void VirtualDevice::select_bank(uint8_t bank_index) {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (bank_index >= TOTAL_BANKS) return;
    m_active_bank = bank_index;

    protocol::ButtonId bank_btn = static_cast<protocol::ButtonId>(static_cast<int>(protocol::ButtonId::BankA) + bank_index);
    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Button;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = 0; // EN_BTN_STATUS
    pkt.data = {static_cast<uint8_t>(bank_btn), 1};
    send_packet_to_host(pkt);
}

uint8_t VirtualDevice::get_active_bank() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_active_bank;
}

void VirtualDevice::turn_qlink(uint8_t knob_index, int8_t ticks) {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (knob_index >= NUM_QLINKS) return;

    int new_val = static_cast<int>(m_qlinks[knob_index]) + ticks;
    new_val = std::clamp(new_val, 0, 127);
    m_qlinks[knob_index] = static_cast<uint8_t>(new_val);

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Knobs;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::KnobCmd::QLink);
    uint8_t dir = (ticks >= 0) ? 1 : 0;
    uint8_t delta = static_cast<uint8_t>(std::abs(ticks));
    pkt.data = {knob_index, dir, delta, m_qlinks[knob_index]};
    send_packet_to_host(pkt);
}

void VirtualDevice::set_qlink_value(uint8_t knob_index, uint8_t value) {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (knob_index >= NUM_QLINKS) return;
    m_qlinks[knob_index] = std::min<uint8_t>(value, 127);
}

uint8_t VirtualDevice::get_qlink_value(uint8_t knob_index) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (knob_index >= NUM_QLINKS) return 0;
    return m_qlinks[knob_index];
}

void VirtualDevice::turn_jog_wheel(int8_t ticks) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_jog_position += ticks;

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Knobs;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::KnobCmd::Rotary);
    uint8_t dir = (ticks >= 0) ? 1 : 0;
    uint8_t delta = static_cast<uint8_t>(std::abs(ticks));
    pkt.data = {0 /*center knob*/, dir, delta};
    send_packet_to_host(pkt);
}

void VirtualDevice::press_jog_wheel() {
    press_button(protocol::ButtonId::KnobEnter);
}

void VirtualDevice::release_jog_wheel() {
    release_button(protocol::ButtonId::KnobEnter);
}

void VirtualDevice::touch_slider(uint8_t position) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_slider_touched = true;
    m_slider_position = std::min<uint8_t>(position, 127);

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Slider;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::SliderCmd::TouchInput);
    pkt.data = {1 /*touched*/, m_slider_position};
    send_packet_to_host(pkt);
}

void VirtualDevice::release_slider() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_slider_touched = false;

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Slider;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(protocol::SliderCmd::TouchInput);
    pkt.data = {0 /*released*/, m_slider_position};
    send_packet_to_host(pkt);
}

bool VirtualDevice::is_slider_touched() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_slider_touched;
}

uint8_t VirtualDevice::get_slider_position() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_slider_position;
}

void VirtualDevice::press_button(protocol::ButtonId btn) {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto idx = static_cast<int>(btn);
    if (idx >= 0 && idx < static_cast<int>(m_button_states.size())) {
        m_button_states[idx] = true;
    }

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Button;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = 0; // EN_BTN_STATUS
    pkt.data = {static_cast<uint8_t>(btn), 1 /*pressed*/};
    send_packet_to_host(pkt);
}

void VirtualDevice::release_button(protocol::ButtonId btn) {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto idx = static_cast<int>(btn);
    if (idx >= 0 && idx < static_cast<int>(m_button_states.size())) {
        m_button_states[idx] = false;
    }

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::Button;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = 0; // EN_BTN_STATUS
    pkt.data = {static_cast<uint8_t>(btn), 0 /*released*/};
    send_packet_to_host(pkt);
}

bool VirtualDevice::is_button_pressed(protocol::ButtonId btn) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto idx = static_cast<int>(btn);
    if (idx >= 0 && idx < static_cast<int>(m_button_states.size())) {
        return m_button_states[idx];
    }
    return false;
}

void VirtualDevice::inject_touch(int x, int y, bool down) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_last_touch.x = std::clamp(x, 0, SCREEN_WIDTH - 1);
    m_last_touch.y = std::clamp(y, 0, SCREEN_HEIGHT - 1);
    m_last_touch.down = down;
}

TouchPoint VirtualDevice::get_last_touch() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_last_touch;
}

void VirtualDevice::inject_camera_gesture(GestureType gesture, uint8_t confidence) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_last_gesture = gesture;

    protocol::Packet pkt;
    pkt.type = protocol::PacketType::System;
    pkt.dir  = protocol::PacketDir::Request;
    pkt.cmd  = 0x80; // Synthetic AI gesture event
    pkt.data = {static_cast<uint8_t>(gesture), confidence};
    send_packet_to_host(pkt);
}

GestureType VirtualDevice::get_last_gesture() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_last_gesture;
}

CvGateOutput VirtualDevice::get_cv_output(size_t channel) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (channel < NUM_CV_CHANNELS) {
        return m_cv_outputs[channel];
    }
    return {};
}

const std::vector<CvLogEntry>& VirtualDevice::get_cv_log() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_cv_log;
}

void VirtualDevice::clear_cv_log() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_cv_log.clear();
}

void VirtualDevice::set_sd_card_path(const std::string& path) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_sd_card_path = path;
}

std::string VirtualDevice::get_sd_card_path() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_sd_card_path;
}

bool VirtualDevice::is_sd_card_inserted() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_sd_card_inserted;
}

void VirtualDevice::set_sd_card_inserted(bool inserted) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_sd_card_inserted = inserted;
}

void VirtualDevice::set_audio_levels(float in_l, float in_r, float out_l, float out_r) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_audio_in_l = in_l;
    m_audio_in_r = in_r;
    m_audio_out_l = out_l;
    m_audio_out_r = out_r;
}

void VirtualDevice::get_audio_levels(float& in_l, float& in_r, float& out_l, float& out_r) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    in_l = m_audio_in_l;
    in_r = m_audio_in_r;
    out_l = m_audio_out_l;
    out_r = m_audio_out_r;
}

PadState VirtualDevice::get_pad_state(uint8_t bank, uint8_t pad) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (bank < TOTAL_BANKS && pad < PADS_PER_BANK) {
        return m_pads[bank * PADS_PER_BANK + pad];
    }
    return {};
}

PadState VirtualDevice::get_active_pad_state(uint8_t pad) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (pad < PADS_PER_BANK) {
        return m_pads[m_active_bank * PADS_PER_BANK + pad];
    }
    return {};
}

uint8_t VirtualDevice::get_slider_led_level() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_slider_led_level;
}

bool VirtualDevice::get_button_led(protocol::ButtonId btn) const {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto idx = static_cast<int>(btn);
    if (idx >= 0 && idx < static_cast<int>(m_button_leds.size())) {
        return m_button_leds[idx];
    }
    return false;
}

std::string gesture_to_string(GestureType gesture) {
    switch (gesture) {
        case GestureType::None:       return "None";
        case GestureType::HandUp:     return "HandUp";
        case GestureType::HandDown:   return "HandDown";
        case GestureType::SwipeLeft:  return "SwipeLeft";
        case GestureType::SwipeRight: return "SwipeRight";
        case GestureType::Fist:       return "Fist";
        case GestureType::Pinch:      return "Pinch";
        case GestureType::Wave:       return "Wave";
        default:                      return "Unknown";
    }
}

} // namespace thumpbox::hardware
