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

namespace thumpbox::protocol {

uint8_t calculate_crc8(const uint8_t* buffer, size_t size) {
    uint8_t crc = CRC8_INIT;
    for (size_t i = 0; i < size; ++i) {
        crc ^= buffer[i];
        for (int j = 0; j < 8; ++j) {
            if ((crc & 0x80) != 0) {
                crc = static_cast<uint8_t>((crc << 1) ^ CRC8_POLYNOMIAL);
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

uint8_t calculate_crc8(const std::vector<uint8_t>& buffer) {
    return calculate_crc8(buffer.data(), buffer.size());
}

std::vector<uint8_t> serialize_packet(const Packet& pkt) {
    std::vector<uint8_t> buffer;
    buffer.reserve(7 + pkt.data.size());

    buffer.push_back(PREAMBLE_BYTE_1);
    buffer.push_back(PREAMBLE_BYTE_2);
    buffer.push_back(static_cast<uint8_t>(pkt.type));
    buffer.push_back(static_cast<uint8_t>(pkt.dir));
    buffer.push_back(pkt.cmd);
    // In ComProtocol, size = payload_bytes + 1 (for CRC)
    buffer.push_back(static_cast<uint8_t>(pkt.data.size() + 1));

    for (uint8_t byte : pkt.data) {
        buffer.push_back(byte);
    }

    uint8_t crc = calculate_crc8(buffer);
    buffer.push_back(crc);

    return buffer;
}

PacketParser::PacketParser() {
    reset();
}

void PacketParser::reset() {
    m_state = State::Init1;
    m_curType = PacketType::System;
    m_curDir = PacketDir::Request;
    m_curCmd = 0;
    m_curFrameSize = 0;
    m_curData.clear();
    m_crcBuffer.clear();
}

std::vector<Packet> PacketParser::parse_bytes(const uint8_t* bytes, size_t len) {
    std::vector<Packet> completed;

    for (size_t i = 0; i < len; ++i) {
        uint8_t byte = bytes[i];

        switch (m_state) {
            case State::Init1:
                if (byte == PREAMBLE_BYTE_1) {
                    m_crcBuffer.clear();
                    m_crcBuffer.push_back(byte);
                    m_state = State::Init2;
                }
                break;

            case State::Init2:
                if (byte == PREAMBLE_BYTE_2) {
                    m_crcBuffer.push_back(byte);
                    m_state = State::Type;
                } else if (byte == PREAMBLE_BYTE_1) {
                    // Handle repeated 'M'
                    m_crcBuffer.clear();
                    m_crcBuffer.push_back(byte);
                    m_state = State::Init2;
                } else {
                    reset();
                }
                break;

            case State::Type:
                m_curType = static_cast<PacketType>(byte);
                m_crcBuffer.push_back(byte);
                m_state = State::Dir;
                break;

            case State::Dir:
                m_curDir = static_cast<PacketDir>(byte);
                m_crcBuffer.push_back(byte);
                m_state = State::Id;
                break;

            case State::Id:
                m_curCmd = byte;
                m_crcBuffer.push_back(byte);
                m_state = State::Size;
                break;

            case State::Size:
                m_curFrameSize = byte;
                m_crcBuffer.push_back(byte);
                m_curData.clear();
                if (m_curFrameSize <= 1) {
                    // Frame size of 1 means 0 payload bytes + 1 CRC byte
                    m_state = State::Crc;
                } else {
                    m_curData.reserve(m_curFrameSize - 1);
                    m_state = State::Data;
                }
                break;

            case State::Data:
                m_curData.push_back(byte);
                m_crcBuffer.push_back(byte);
                if (m_curData.size() == static_cast<size_t>(m_curFrameSize - 1)) {
                    m_state = State::Crc;
                }
                break;

            case State::Crc: {
                uint8_t expected_crc = calculate_crc8(m_crcBuffer);
                if (byte == expected_crc) {
                    Packet pkt;
                    pkt.type = m_curType;
                    pkt.dir  = m_curDir;
                    pkt.cmd  = m_curCmd;
                    pkt.data = std::move(m_curData);
                    completed.push_back(std::move(pkt));
                }
                reset();
                break;
            }
        }
    }

    return completed;
}

std::vector<Packet> PacketParser::parse_bytes(const std::vector<uint8_t>& bytes) {
    return parse_bytes(bytes.data(), bytes.size());
}

std::string packet_type_to_string(PacketType type) {
    switch (type) {
        case PacketType::System: return "SYSTEM";
        case PacketType::Button: return "BUTTON";
        case PacketType::Led:    return "LED";
        case PacketType::Pad:    return "PAD";
        case PacketType::Knobs:  return "KNOBS";
        case PacketType::Midi:   return "MIDI";
        case PacketType::Cv:     return "CV";
        case PacketType::Slider: return "SLIDER";
        default:                 return "UNKNOWN";
    }
}

std::string packet_dir_to_string(PacketDir dir) {
    switch (dir) {
        case PacketDir::Request:  return "REQUEST";
        case PacketDir::Response: return "RESPONSE";
        default:                  return "UNKNOWN";
    }
}

std::string button_id_to_string(ButtonId id) {
    switch (id) {
        case ButtonId::BankA: return "BankA";
        case ButtonId::BankB: return "BankB";
        case ButtonId::BankC: return "BankC";
        case ButtonId::BankD: return "BankD";
        case ButtonId::BankE: return "BankE";
        case ButtonId::BankF: return "BankF";
        case ButtonId::BankG: return "BankG";
        case ButtonId::BankH: return "BankH";
        case ButtonId::MainMode: return "MainMode";
        case ButtonId::Grid: return "Grid";
        case ButtonId::Browse: return "Browse";
        case ButtonId::Save: return "Save";
        case ButtonId::TrackMix: return "TrackMix";
        case ButtonId::PadMix: return "PadMix";
        case ButtonId::TrackMute: return "TrackMute";
        case ButtonId::PadMute: return "PadMute";
        case ButtonId::NextSeq: return "NextSeq";
        case ButtonId::Fx: return "Fx";
        case ButtonId::TapTempo: return "TapTempo";
        case ButtonId::Master: return "Master";
        case ButtonId::Copy: return "Copy";
        case ButtonId::Plus: return "Plus";
        case ButtonId::Menu: return "Menu";
        case ButtonId::Pref: return "Pref";
        case ButtonId::NoteRepeat: return "NoteRepeat";
        case ButtonId::Latch: return "Latch";
        case ButtonId::KnobEnter: return "KnobEnter";
        case ButtonId::Minus: return "Minus";
        case ButtonId::KnobCCW: return "KnobCCW";
        case ButtonId::Back: return "Back";
        case ButtonId::KnobCW: return "KnobCW";
        case ButtonId::Shift: return "Shift";
        case ButtonId::StepSeq: return "StepSeq";
        case ButtonId::Automation: return "Automation";
        case ButtonId::Tc: return "Tc";
        case ButtonId::OnOff: return "OnOff";
        case ButtonId::Sampler: return "Sampler";
        case ButtonId::Looper: return "Looper";
        case ButtonId::SampleEdit: return "SampleEdit";
        case ButtonId::LinkEdit: return "LinkEdit";
        case ButtonId::ProgEdit: return "ProgEdit";
        case ButtonId::MidiControl: return "MidiControl";
        case ButtonId::Record: return "Record";
        case ButtonId::Overdub: return "Overdub";
        case ButtonId::Stop: return "Stop";
        case ButtonId::Play: return "Play";
        case ButtonId::PlayStart: return "PlayStart";
        case ButtonId::Link: return "Link";
        case ButtonId::FullLevel: return "FullLevel";
        case ButtonId::HalfLevel: return "HalfLevel";
        case ButtonId::Levels16: return "16Levels";
        case ButtonId::Notes: return "Notes";
        case ButtonId::Erase: return "Erase";
        default: return "UnknownButton";
    }
}

} // namespace thumpbox::protocol
