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

#include "juce_serialport.h"

#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <cstdlib>

SerialPort::SerialPort(const juce::String& portPath,
                       const SerialPortConfig& config,
                       DebugCallback debug)
    : m_path(portPath) {
    juce::ignoreUnused(config);

    // Support redirecting /dev/ttymxc0 via THUMPBOX_SERIAL_PORT environment variable
    juce::String resolvedPath = m_path;
    const char* envPath = std::getenv("THUMPBOX_SERIAL_PORT");
    if (envPath != nullptr && envPath[0] != '\0') {
        resolvedPath = envPath;
    }

    m_fd = open(resolvedPath.toRawUTF8(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (m_fd >= 0) {
        struct termios tty{};
        if (tcgetattr(m_fd, &tty) == 0) {
            cfmakeraw(&tty);
            cfsetispeed(&tty, B230400);
            cfsetospeed(&tty, B230400);
            tcsetattr(m_fd, TCSANOW, &tty);
        }
        if (debug) {
            debug("SerialPort", "Opened " + resolvedPath);
        }
    } else {
        if (debug) {
            debug("SerialPort", "Failed to open " + resolvedPath);
        }
    }
}

SerialPort::~SerialPort() {
    close();
}

void SerialPort::close() {
    if (m_fd >= 0) {
        ::close(m_fd);
        m_fd = -1;
    }
}

bool SerialPort::exists() const {
    return m_fd >= 0;
}

juce::StringPairArray SerialPort::getSerialPortPaths() {
    juce::StringPairArray ports;

    const char* envPath = std::getenv("THUMPBOX_SERIAL_PORT");
    if (envPath != nullptr && envPath[0] != '\0') {
        ports.set(envPath, envPath);
        return ports;
    }

    if (juce::File("/dev/ttymxc0").exists()) {
        ports.set("/dev/ttymxc0", "/dev/ttymxc0");
    }
    if (juce::File("/tmp/thumpbox-tty").exists()) {
        ports.set("/tmp/thumpbox-tty", "/tmp/thumpbox-tty");
    }

    return ports;
}

// =========================================================================
// SerialPortInputStream
// =========================================================================

SerialPortInputStream::SerialPortInputStream(SerialPort* port)
    : m_port(port) {}

SerialPortInputStream::~SerialPortInputStream() = default;

void SerialPortInputStream::setNotify(NotifyMode mode) {
    m_notifyMode = mode;
}

juce::int64 SerialPortInputStream::getTotalLength() {
    if (!m_port || m_port->getDescriptor() < 0) return 0;
    int bytesAvailable = 0;
    if (ioctl(m_port->getDescriptor(), FIONREAD, &bytesAvailable) >= 0) {
        return bytesAvailable;
    }
    return 0;
}

juce::int64 SerialPortInputStream::getPosition() {
    return 0;
}

bool SerialPortInputStream::setPosition(juce::int64) {
    return false; // Stream device cannot seek
}

int SerialPortInputStream::read(void* destBuffer, int maxBytesToRead) {
    if (!m_port || m_port->getDescriptor() < 0 || maxBytesToRead <= 0) return 0;
    ssize_t bytesRead = ::read(m_port->getDescriptor(), destBuffer, static_cast<size_t>(maxBytesToRead));
    return (bytesRead > 0) ? static_cast<int>(bytesRead) : 0;
}

bool SerialPortInputStream::isExhausted() {
    return getTotalLength() == 0;
}

// =========================================================================
// SerialPortOutputStream
// =========================================================================

SerialPortOutputStream::SerialPortOutputStream(SerialPort* port)
    : m_port(port) {}

SerialPortOutputStream::~SerialPortOutputStream() = default;

void SerialPortOutputStream::flush() {
    if (m_port && m_port->getDescriptor() >= 0) {
        tcdrain(m_port->getDescriptor());
    }
}

bool SerialPortOutputStream::setPosition(juce::int64) {
    return false;
}

juce::int64 SerialPortOutputStream::getPosition() {
    return 0;
}

bool SerialPortOutputStream::write(const void* dataToWrite, size_t numberOfBytes) {
    if (!m_port || m_port->getDescriptor() < 0 || numberOfBytes == 0) return false;
    ssize_t written = ::write(m_port->getDescriptor(), dataToWrite, numberOfBytes);
    return written == static_cast<ssize_t>(numberOfBytes);
}
