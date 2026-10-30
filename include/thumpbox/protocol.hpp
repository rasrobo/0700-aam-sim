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

#include <cstdint>
#include <string>
#include <vector>
#include <optional>
#include <iosfwd>

namespace thumpbox::protocol {

constexpr uint8_t PREAMBLE_BYTE_1 = 'M'; // 0x4D
constexpr uint8_t PREAMBLE_BYTE_2 = 'T'; // 0x54
constexpr uint8_t CRC8_POLYNOMIAL = 0x31;
constexpr uint8_t CRC8_INIT = 0xFF;

enum class PacketType : uint8_t {
    System = 0x00,
    Button = 0x01,
    Led    = 0x02,
    Pad    = 0x03,
    Knobs  = 0x04,
    Midi   = 0x05,
    Cv     = 0x06,
    Slider = 0x07,
};

enum class PacketDir : uint8_t {
    Request  = 0x00,
    Response = 0x01,
};

enum class SysCmd : uint8_t {
    ResetGD         = 0x00,
    GetSwVersion    = 0x01,
    CommInit        = 0x02,
    SwUpdate        = 0x03,
    CheckCommStatus = 0x04,
    Bpm             = 0x05,
    Reconnect       = 0x06,
    Shutdown        = 0x07,
};

enum class ButtonId : int8_t {
    Invalid     = -1,
    BankA       = 0,
    BankB       = 1,
    BankC       = 2,
    BankD       = 3,
    BankE       = 4,
    BankF       = 5,
    BankG       = 6,
    BankH       = 7,
    MainMode    = 8,
    Grid        = 9,
    Browse      = 10,
    Save        = 11,
    TrackMix    = 12,
    PadMix      = 13,
    TrackMute   = 14,
    PadMute     = 15,
    NextSeq     = 16,
    Fx          = 17,
    TapTempo    = 18,
    Master      = 19,
    Copy        = 20,
    Plus        = 21,
    Menu        = 22,
    Pref        = 23,
    NoteRepeat  = 24,
    Latch       = 25,
    KnobEnter   = 26,
    Minus       = 27,
    KnobCCW     = 28,
    Back        = 29,
    KnobCW      = 30,
    Shift       = 31,
    StepSeq     = 32,
    Automation  = 33,
    Tc          = 34,
    OnOff       = 35,
    Sampler     = 36,
    Looper      = 37,
    SampleEdit  = 38,
    LinkEdit    = 39,
    ProgEdit    = 40,
    MidiControl = 41,
    Record      = 42,
    Overdub     = 43,
    Stop        = 44,
    Play        = 45,
    PlayStart   = 46,
    Link        = 47,
    FullLevel   = 48,
    HalfLevel   = 49,
    Levels16    = 50,
    Notes       = 51,
    Erase       = 52,
};

enum class ButtonState : uint8_t {
    Released    = 0,
    Pressed     = 1,
    LongPressed = 2,
    DoubleClick = 3,
};

enum class LedCmd : uint8_t {
    SetSingleLed = 0,
    BlinkSingle  = 1,
    SetAll       = 2,
};

enum class PadCmd : uint8_t {
    State              = 0,
    SetSinglePad       = 1,
    SetAllSingleColour = 2,
    SetAllMultiColour  = 3,
    Settings           = 4,
    ColorMode          = 5,
    SetColourState     = 6,
    SetAfterTouch      = 7,
    SetBlinking        = 8,
    SetStepSinglePad   = 9,
    SetStepAllPad      = 10,
};

enum class PadColourId : uint8_t {
    DarkRed      = 0,
    VividPurple  = 1,
    DarkYellow   = 2,
    LightGreen1  = 3,
    LightGreen3  = 4,
    LightGreen4  = 5,
    LightSkyBlue = 6,
    Aqua         = 7,
    Blue1        = 8,
    Pink         = 9,
    Pink1        = 10,
    Pink2        = 11,
    Red          = 12,
    Orange1      = 13,
    Orange       = 14,
    Trans        = 15,
    NeutralWhite = 16,
    NeutralGrey  = 17,
};

enum class PadButtonState : uint8_t {
    StateOff               = 0,
    StateOn                = 1,
    StateSampleAssigned    = 2,
    StateSampleNotAssigned = 3,
    StateOnBlink           = 4,
    StateOffBlink          = 5,
};

enum class KnobCmd : uint8_t {
    Rotary = 0,
    QLink  = 1,
};

enum class KnobDirection : uint8_t {
    AntiClockwise = 0,
    Clockwise     = 1,
};

enum class SliderCmd : uint8_t {
    TouchInput    = 0,
    BarLed        = 1,
    LevelLed      = 2,
    IndividualLed = 3,
};

enum class CvCmd : uint8_t {
    SetOutput = 0,
    GetOutput = 1,
};

struct Packet {
    PacketType           type{PacketType::System};
    PacketDir            dir{PacketDir::Request};
    uint8_t              cmd{0};
    std::vector<uint8_t> data;

    bool operator==(const Packet& other) const {
        return type == other.type &&
               dir  == other.dir &&
               cmd  == other.cmd &&
               data == other.data;
    }

    bool operator!=(const Packet& other) const {
        return !(*this == other);
    }
};

uint8_t calculate_crc8(const uint8_t* buffer, size_t size);
uint8_t calculate_crc8(const std::vector<uint8_t>& buffer);

std::vector<uint8_t> serialize_packet(const Packet& pkt);

class PacketParser {
public:
    PacketParser();
    void reset();

    // Feeds incoming bytes, returns complete parsed packets
    std::vector<Packet> parse_bytes(const uint8_t* bytes, size_t len);
    std::vector<Packet> parse_bytes(const std::vector<uint8_t>& bytes);

private:
    enum class State {
        Init1,
        Init2,
        Type,
        Dir,
        Id,
        Size,
        Data,
        Crc
    };

    State                m_state{State::Init1};
    PacketType           m_curType{PacketType::System};
    PacketDir            m_curDir{PacketDir::Request};
    uint8_t              m_curCmd{0};
    uint8_t              m_curFrameSize{0};
    std::vector<uint8_t> m_curData;
    std::vector<uint8_t> m_crcBuffer;
};

// Conversions for debug and logging
std::string packet_type_to_string(PacketType type);
std::string packet_dir_to_string(PacketDir dir);
std::string button_id_to_string(ButtonId id);

} // namespace thumpbox::protocol
