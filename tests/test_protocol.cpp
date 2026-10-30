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

#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>
#include <vector>

using namespace thumpbox::protocol;

void test_crc8_calculation() {
    std::cout << "[TEST] test_crc8_calculation... ";

    // Basic CRC-8 verification
    std::vector<uint8_t> data = {'M', 'T', 0x01, 0x00, 0x00, 0x03, 0x0A, 0x01};
    uint8_t crc1 = calculate_crc8(data);
    assert(crc1 != 0);

    // Consistency check
    uint8_t crc2 = calculate_crc8(data.data(), data.size());
    assert(crc1 == crc2);

    std::cout << "PASSED\n";
}

void test_packet_serialization_and_deserialization() {
    std::cout << "[TEST] test_packet_serialization_and_deserialization... ";

    Packet original;
    original.type = PacketType::Pad;
    original.dir  = PacketDir::Request;
    original.cmd  = static_cast<uint8_t>(PadCmd::State);
    original.data = {0x03, 0x01, 100, 0x02}; // Pad 3, pressed, vel 100, Bank C

    auto bytes = serialize_packet(original);
    assert(bytes.size() == 7 + original.data.size());
    assert(bytes[0] == 'M');
    assert(bytes[1] == 'T');
    assert(bytes[2] == static_cast<uint8_t>(PacketType::Pad));
    assert(bytes[3] == static_cast<uint8_t>(PacketDir::Request));
    assert(bytes[4] == static_cast<uint8_t>(PadCmd::State));
    assert(bytes[5] == original.data.size() + 1);

    PacketParser parser;
    auto parsed = parser.parse_bytes(bytes);
    assert(parsed.size() == 1);
    assert(parsed[0] == original);

    std::cout << "PASSED\n";
}

void test_fragmented_stream_parsing() {
    std::cout << "[TEST] test_fragmented_stream_parsing... ";

    Packet pkt1;
    pkt1.type = PacketType::Button;
    pkt1.dir  = PacketDir::Request;
    pkt1.cmd  = 0;
    pkt1.data = {static_cast<uint8_t>(ButtonId::Record), 1};

    Packet pkt2;
    pkt2.type = PacketType::Knobs;
    pkt2.dir  = PacketDir::Request;
    pkt2.cmd  = static_cast<uint8_t>(KnobCmd::QLink);
    pkt2.data = {1, 1, 5, 75};

    auto b1 = serialize_packet(pkt1);
    auto b2 = serialize_packet(pkt2);

    std::vector<uint8_t> stream;
    stream.insert(stream.end(), b1.begin(), b1.end());
    stream.insert(stream.end(), b2.begin(), b2.end());

    PacketParser parser;
    std::vector<Packet> all_parsed;

    // Feed byte-by-byte to test streaming robustness
    for (uint8_t b : stream) {
        auto out = parser.parse_bytes(&b, 1);
        all_parsed.insert(all_parsed.end(), out.begin(), out.end());
    }

    assert(all_parsed.size() == 2);
    assert(all_parsed[0] == pkt1);
    assert(all_parsed[1] == pkt2);

    std::cout << "PASSED\n";
}

void test_corrupted_crc_rejection() {
    std::cout << "[TEST] test_corrupted_crc_rejection... ";

    Packet pkt;
    pkt.type = PacketType::System;
    pkt.dir  = PacketDir::Request;
    pkt.cmd  = static_cast<uint8_t>(SysCmd::CommInit);
    pkt.data = {1};

    auto bytes = serialize_packet(pkt);
    // Corrupt the CRC byte at the end
    bytes.back() ^= 0xFF;

    PacketParser parser;
    auto parsed = parser.parse_bytes(bytes);
    assert(parsed.empty());

    std::cout << "PASSED\n";
}

int main() {
    std::cout << "=== Running Protocol Tests ===\n";
    test_crc8_calculation();
    test_packet_serialization_and_deserialization();
    test_fragmented_stream_parsing();
    test_corrupted_crc_rejection();
    std::cout << "All Protocol Tests PASSED.\n";
    return 0;
}
