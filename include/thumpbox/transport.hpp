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

#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <thread>
#include <atomic>

namespace thumpbox::transport {

class ITransport {
public:
    virtual ~ITransport() = default;
    virtual bool start() = 0;
    virtual void stop() = 0;
    virtual bool send_bytes(const uint8_t* data, size_t len) = 0;
    virtual std::string get_endpoint_name() const = 0;
};

// POSIX Pseudo-terminal (PTY) Transport
class PtyTransport : public ITransport {
public:
    explicit PtyTransport(hardware::VirtualDevice& device, const std::string& symlink_path = "");
    ~PtyTransport() override;

    bool start() override;
    void stop() override;
    bool send_bytes(const uint8_t* data, size_t len) override;
    std::string get_endpoint_name() const override;

private:
    void worker_loop();

    hardware::VirtualDevice& m_device;
    std::string              m_symlink_path;
    int                      m_master_fd{-1};
    std::string              m_slave_name;
    std::atomic<bool>        m_running{false};
    std::thread              m_thread;
    protocol::PacketParser   m_parser;
};

// Unix Domain Socket / TCP Transport
class SocketTransport : public ITransport {
public:
    // If tcp_port > 0, binds to TCP 127.0.0.1:port. Otherwise binds to unix_path.
    SocketTransport(hardware::VirtualDevice& device, const std::string& unix_path, int tcp_port = 0);
    ~SocketTransport() override;

    bool start() override;
    void stop() override;
    bool send_bytes(const uint8_t* data, size_t len) override;
    std::string get_endpoint_name() const override;

private:
    void accept_loop();
    void client_loop(int client_fd);

    hardware::VirtualDevice& m_device;
    std::string              m_unix_path;
    int                      m_tcp_port{0};
    int                      m_server_fd{-1};
    std::atomic<int>         m_client_fd{-1};
    std::atomic<bool>        m_running{false};
    std::thread              m_thread;
    protocol::PacketParser   m_parser;
};

// Direct In-Memory Mock Transport for Unit and Golden Tests
class MockTransport : public ITransport {
public:
    explicit MockTransport(hardware::VirtualDevice& device);
    ~MockTransport() override;

    bool start() override;
    void stop() override;
    bool send_bytes(const uint8_t* data, size_t len) override;
    std::string get_endpoint_name() const override { return "mock://in-memory"; }

    // Host emulation helpers:
    void host_send_packet(const protocol::Packet& pkt);
    std::vector<protocol::Packet> take_packets_sent_to_host();
    const std::vector<protocol::Packet>& get_packets_sent_to_host() const;
    void clear_sent_packets();

private:
    hardware::VirtualDevice&      m_device;
    std::vector<protocol::Packet> m_packets_to_host;
    protocol::PacketParser        m_host_parser;
    std::mutex                    m_mutex;
};

} // namespace thumpbox::transport
