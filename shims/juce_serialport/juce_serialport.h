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

/*******************************************************************************
 BEGIN_JUCE_MODULE_DECLARATION

  ID:                 juce_serialport
  vendor:             thumpbox
  version:            1.0.0
  name:               JUCE Serial Port Shim
  description:        POSIX serial port and PTY shim for thumpbox-sim
  dependencies:       juce_core

 END_JUCE_MODULE_DECLARATION
*******************************************************************************/

#pragma once

#include <juce_core/juce_core.h>

class SerialPortConfig {
public:
    enum BitParity {
        SERIALPORT_PARITY_NONE = 0,
        SERIALPORT_PARITY_ODD,
        SERIALPORT_PARITY_EVEN
    };

    enum StopBits {
        STOPBITS_1 = 0,
        STOPBITS_2
    };

    enum FlowControl {
        FLOWCONTROL_NONE = 0,
        FLOWCONTROL_HARDWARE,
        FLOWCONTROL_XONXOFF
    };

    SerialPortConfig(int baudRate = 230400,
                     int dataBits = 8,
                     BitParity parity = SERIALPORT_PARITY_NONE,
                     StopBits stopBits = STOPBITS_1,
                     FlowControl flowControl = FLOWCONTROL_NONE)
        : m_baudRate(baudRate), m_dataBits(dataBits), m_parity(parity),
          m_stopBits(stopBits), m_flowControl(flowControl) {}

    int m_baudRate;
    int m_dataBits;
    BitParity m_parity;
    StopBits m_stopBits;
    FlowControl m_flowControl;
};

class SerialPort {
public:
    using DebugCallback = std::function<void(juce::String, juce::String)>;

    SerialPort(const juce::String& portPath,
               const SerialPortConfig& config,
               DebugCallback debug = nullptr);
    ~SerialPort();

    void close();
    bool exists() const;
    int getDescriptor() const { return m_fd; }

    static juce::StringPairArray getSerialPortPaths();

private:
    int m_fd{-1};
    juce::String m_path;
};

class SerialPortInputStream : public juce::InputStream,
                              public juce::ChangeBroadcaster {
public:
    enum NotifyMode {
        NOTIFY_ALWAYS = 0,
        NOTIFY_ON_CHAR
    };

    explicit SerialPortInputStream(SerialPort* port);
    ~SerialPortInputStream() override;

    void setNotify(NotifyMode mode);
    juce::int64 getTotalLength() override;
    juce::int64 getPosition() override;
    bool setPosition(juce::int64 newPosition) override;
    int read(void* destBuffer, int maxBytesToRead) override;
    bool isExhausted() override;

private:
    SerialPort* m_port;
    NotifyMode  m_notifyMode{NOTIFY_ALWAYS};
};

class SerialPortOutputStream : public juce::OutputStream {
public:
    explicit SerialPortOutputStream(SerialPort* port);
    ~SerialPortOutputStream() override;

    void flush() override;
    bool setPosition(juce::int64 newPosition) override;
    juce::int64 getPosition() override;
    bool write(const void* dataToWrite, size_t numberOfBytes) override;

private:
    SerialPort* m_port;
};
