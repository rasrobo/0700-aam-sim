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
#include "thumpbox/protocol.hpp"

#include <cassert>
#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <thread>
#include <chrono>

using namespace thumpbox;

void test_pty_transport_loopback() {
    std::cout << "[TEST] test_pty_transport_loopback... ";

    hardware::VirtualDevice device;
    transport::PtyTransport pty(device);

    assert(pty.start());
    std::string slave = pty.get_endpoint_name();
    assert(!slave.empty());

    // Open slave port as host application would
    int slave_fd = open(slave.c_str(), O_RDWR | O_NOCTTY);
    assert(slave_fd >= 0);

    // Host sends CommInit packet
    protocol::Packet init_req;
    init_req.type = protocol::PacketType::System;
    init_req.dir  = protocol::PacketDir::Request;
    init_req.cmd  = static_cast<uint8_t>(protocol::SysCmd::CommInit);
    init_req.data = {1};

    auto tx_bytes = protocol::serialize_packet(init_req);
    ssize_t written = write(slave_fd, tx_bytes.data(), tx_bytes.size());
    assert(written == static_cast<ssize_t>(tx_bytes.size()));

    // Give simulator time to process and reply
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    // Host reads response from slave port
    uint8_t rx_buffer[128];
    ssize_t bytes_read = read(slave_fd, rx_buffer, sizeof(rx_buffer));
    assert(bytes_read > 0);

    protocol::PacketParser parser;
    auto responses = parser.parse_bytes(rx_buffer, bytes_read);
    assert(!responses.empty());
    assert(responses[0].type == protocol::PacketType::System);
    assert(responses[0].dir == protocol::PacketDir::Response);
    assert(responses[0].cmd == static_cast<uint8_t>(protocol::SysCmd::CommInit));

    close(slave_fd);
    pty.stop();

    std::cout << "PASSED\n";
}

int main() {
    std::cout << "=== Running Transport Tests ===\n";
    test_pty_transport_loopback();
    std::cout << "All Transport Tests PASSED.\n";
    return 0;
}
