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

#include "thumpbox/transport.hpp"

#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <poll.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <cstring>
#include <iostream>

namespace thumpbox::transport {

// =========================================================================
// PtyTransport
// =========================================================================

PtyTransport::PtyTransport(hardware::VirtualDevice& device, const std::string& symlink_path)
    : m_device(device), m_symlink_path(symlink_path) {}

PtyTransport::~PtyTransport() {
    stop();
}

bool PtyTransport::start() {
    m_master_fd = posix_openpt(O_RDWR | O_NOCTTY);
    if (m_master_fd < 0) {
        return false;
    }

    if (grantpt(m_master_fd) < 0 || unlockpt(m_master_fd) < 0) {
        close(m_master_fd);
        m_master_fd = -1;
        return false;
    }

    char* pts = ptsname(m_master_fd);
    if (!pts) {
        close(m_master_fd);
        m_master_fd = -1;
        return false;
    }
    m_slave_name = pts;

    // Configure raw mode on master
    struct termios tty{};
    if (tcgetattr(m_master_fd, &tty) == 0) {
        cfmakeraw(&tty);
        cfsetispeed(&tty, B230400);
        cfsetospeed(&tty, B230400);
        tcsetattr(m_master_fd, TCSANOW, &tty);
    }

    // Optionally create symlink
    if (!m_symlink_path.empty()) {
        unlink(m_symlink_path.c_str());
        if (symlink(m_slave_name.c_str(), m_symlink_path.c_str()) != 0) {
            // Non-fatal warning if symlink fails
        }
    }

    // Connect device outgoing packets to transport write
    m_device.set_packet_callback([this](const protocol::Packet& pkt) {
        auto bytes = protocol::serialize_packet(pkt);
        send_bytes(bytes.data(), bytes.size());
    });

    m_running = true;
    m_thread = std::thread(&PtyTransport::worker_loop, this);

    return true;
}

void PtyTransport::stop() {
    m_running = false;
    if (m_master_fd >= 0) {
        close(m_master_fd);
        m_master_fd = -1;
    }
    if (m_thread.joinable()) {
        m_thread.join();
    }
    if (!m_symlink_path.empty()) {
        unlink(m_symlink_path.c_str());
    }
}

bool PtyTransport::send_bytes(const uint8_t* data, size_t len) {
    if (m_master_fd < 0 || !m_running) return false;
    ssize_t written = write(m_master_fd, data, len);
    return written == static_cast<ssize_t>(len);
}

std::string PtyTransport::get_endpoint_name() const {
    return m_slave_name;
}

void PtyTransport::worker_loop() {
    uint8_t buffer[512];
    while (m_running && m_master_fd >= 0) {
        struct pollfd pfd{};
        pfd.fd = m_master_fd;
        pfd.events = POLLIN;

        int ret = poll(&pfd, 1, 50); // 50ms timeout
        if (ret > 0 && (pfd.revents & POLLIN)) {
            ssize_t bytes_read = read(m_master_fd, buffer, sizeof(buffer));
            if (bytes_read > 0) {
                auto packets = m_parser.parse_bytes(buffer, static_cast<size_t>(bytes_read));
                for (const auto& pkt : packets) {
                    m_device.receive_host_packet(pkt);
                }
            } else if (bytes_read <= 0) {
                // Client closed or error
                usleep(10000);
            }
        }
    }
}

// =========================================================================
// SocketTransport
// =========================================================================

SocketTransport::SocketTransport(hardware::VirtualDevice& device, const std::string& unix_path, int tcp_port)
    : m_device(device), m_unix_path(unix_path), m_tcp_port(tcp_port) {}

SocketTransport::~SocketTransport() {
    stop();
}

bool SocketTransport::start() {
    if (m_tcp_port > 0) {
        m_server_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (m_server_fd < 0) return false;

        int opt = 1;
        setsockopt(m_server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

        struct sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = INADDR_ANY;
        addr.sin_port = htons(m_tcp_port);

        if (bind(m_server_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
            close(m_server_fd);
            m_server_fd = -1;
            return false;
        }
    } else {
        m_server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (m_server_fd < 0) return false;

        unlink(m_unix_path.c_str());
        struct sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        std::strncpy(addr.sun_path, m_unix_path.c_str(), sizeof(addr.sun_path) - 1);

        if (bind(m_server_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
            close(m_server_fd);
            m_server_fd = -1;
            return false;
        }
    }

    if (listen(m_server_fd, 1) < 0) {
        close(m_server_fd);
        m_server_fd = -1;
        return false;
    }

    m_device.set_packet_callback([this](const protocol::Packet& pkt) {
        auto bytes = protocol::serialize_packet(pkt);
        send_bytes(bytes.data(), bytes.size());
    });

    m_running = true;
    m_thread = std::thread(&SocketTransport::accept_loop, this);

    return true;
}

void SocketTransport::stop() {
    m_running = false;
    if (m_client_fd >= 0) {
        close(m_client_fd);
        m_client_fd = -1;
    }
    if (m_server_fd >= 0) {
        close(m_server_fd);
        m_server_fd = -1;
    }
    if (m_thread.joinable()) {
        m_thread.join();
    }
    if (m_tcp_port <= 0 && !m_unix_path.empty()) {
        unlink(m_unix_path.c_str());
    }
}

bool SocketTransport::send_bytes(const uint8_t* data, size_t len) {
    int client = m_client_fd.load();
    if (client < 0 || !m_running) return false;
    ssize_t written = send(client, data, len, MSG_NOSIGNAL);
    return written == static_cast<ssize_t>(len);
}

std::string SocketTransport::get_endpoint_name() const {
    if (m_tcp_port > 0) {
        return "tcp://127.0.0.1:" + std::to_string(m_tcp_port);
    }
    return "unix://" + m_unix_path;
}

void SocketTransport::accept_loop() {
    while (m_running && m_server_fd >= 0) {
        struct pollfd pfd{};
        pfd.fd = m_server_fd;
        pfd.events = POLLIN;

        int ret = poll(&pfd, 1, 50);
        if (ret > 0 && (pfd.revents & POLLIN)) {
            int client = accept(m_server_fd, nullptr, nullptr);
            if (client >= 0) {
                m_client_fd = client;
                client_loop(client);
                close(client);
                m_client_fd = -1;
            }
        }
    }
}

void SocketTransport::client_loop(int client_fd) {
    uint8_t buffer[512];
    m_parser.reset();

    while (m_running && m_client_fd == client_fd) {
        struct pollfd pfd{};
        pfd.fd = client_fd;
        pfd.events = POLLIN;

        int ret = poll(&pfd, 1, 50);
        if (ret > 0 && (pfd.revents & POLLIN)) {
            ssize_t bytes_read = recv(client_fd, buffer, sizeof(buffer), 0);
            if (bytes_read > 0) {
                auto packets = m_parser.parse_bytes(buffer, static_cast<size_t>(bytes_read));
                for (const auto& pkt : packets) {
                    m_device.receive_host_packet(pkt);
                }
            } else {
                break; // Connection closed
            }
        }
    }
}

// =========================================================================
// MockTransport
// =========================================================================

MockTransport::MockTransport(hardware::VirtualDevice& device) : m_device(device) {
    m_device.set_packet_callback([this](const protocol::Packet& pkt) {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_packets_to_host.push_back(pkt);
    });
}

MockTransport::~MockTransport() = default;

bool MockTransport::start() { return true; }
void MockTransport::stop() {}

bool MockTransport::send_bytes(const uint8_t* data, size_t len) {
    auto packets = m_host_parser.parse_bytes(data, len);
    for (const auto& pkt : packets) {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_packets_to_host.push_back(pkt);
    }
    return true;
}

void MockTransport::host_send_packet(const protocol::Packet& pkt) {
    m_device.receive_host_packet(pkt);
}

std::vector<protocol::Packet> MockTransport::take_packets_sent_to_host() {
    std::lock_guard<std::mutex> lock(m_mutex);
    std::vector<protocol::Packet> result = std::move(m_packets_to_host);
    m_packets_to_host.clear();
    return result;
}

const std::vector<protocol::Packet>& MockTransport::get_packets_sent_to_host() const {
    return m_packets_to_host;
}

void MockTransport::clear_sent_packets() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_packets_to_host.clear();
}

} // namespace thumpbox::transport
