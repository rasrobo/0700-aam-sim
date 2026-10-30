# Technical Architecture & Upstream Inspection Findings

## 1. Overview & Repository Structure

The upstream BE 0700-AAM firmware codebase is partitioned into four major components:

| Directory | Role | Language / Framework | Upstream License |
|---|---|---|---|
| `Kick/` | Main host application UI, sequencer, sample management, and device integration | C++17, JUCE 7.0.12 | AGPL-3.0-or-later |
| `AudIO/` | DSP audio engine (Airwindows FX, synthesis, routing, sampler backend) | C++17 | AGPL-3.0-or-later |
| `ComProtocol/` | Hardware communication framing protocol (`CPktMgr`) | C++ (header + single CPP, zero external deps) | AGPL-3.0-or-later |
| `Linux/` | Buildroot board support and system image definitions for NXP i.MX8M Mini SOM (`imx8mm_var_som`) | Make / Kconfig / Buildroot | GPL-2.0 |

---

## 2. Upstream Build System & Simulator Target Analysis

### 2.1 The Existing `kickem` Target
Upstream provides an internal simulator application target under `Kick/apps/kickem` (`KT_KickEM`), gated by CMake option `KICK_SIMULATOR=ON`.

Key characteristics of `kickem`:
1. **Direct In-Memory Coupling**: Rather than speaking over the wire or emulating serial packets, `kickem` bypasses the hardware transport layer entirely. It implements an in-memory interface `sim::SimulatorIntrefaceImpl` (`Kick/apps/kickem/simulator/kick_SimulatorInterfaceImpl.h`) which directly fires JUCE-level signals (`sig::Signal`) into `Contracts::DclSignals`.
2. **Missing Out-of-the-Box Dependencies**:
   - `modules/3rdParty/juce_serialport`: Explicitly omitted from the upstream release due to licensing terms. The build fails on CMake module resolution unless a shim or stub is injected.
   - Audio Assets & Fonts: Factory sound samples and the Myriad Pro font were purged from the release.
   - Private Git Server Fallback: In `Kick/3rdParty.cmake`, CPM defaults to querying an internal git host (`MT_PLATFORM_GIT_PATH`) for `AudIO` and `ComProtocol`, rather than linking directly to the companion root folders.
3. **Heavy GUI & Host Dependency Overhead**: `kickem` requires full X11/Wayland desktop stacks, ALSA/PulseAudio development headers, and a desktop display context, making it unusable for automated, headless, or CI-based golden-file regression testing.

---

## 3. Hardware-Specific Subsystems

| Subsystem | Hardware Spec | Firmware Interface | Simulation Strategy |
|---|---|---|---|
| **Serial / Control Surface** | UART / USB-CDC at 230,400 baud, 8N1 (`/dev/ttymxc0`) | Framed packets via `CPktMgr` handled in `Controls::InputEvents` | Simulated UART over POSIX pseudo-terminal (PTY) and TCP/Unix domain socket |
| **Audio I/O** | Stereo line input & output, headphone amplifier, NXP ALSA audio | JUCE `juce_audio_devices` linked to `AudIO` graph | Configurable audio backend: Null audio sink/source for headless CI + optional host audio |
| **Pads & Buttons** | 16 velocity-sensitive RGB pads (8 banks: A–H = 128 virtual pads) + 26 function/transport buttons | `EN_PKT_TYPE_PAD` (cmd `EN_PAD_STATE`), `EN_PKT_TYPE_BUTTON`, `EN_PKT_TYPE_LED` | Full virtual control matrix with RGB state storage and velocity mapping |
| **Rotaries & Sliders** | 4 Q-Link knobs, 1 central jog wheel (CW/CCW + push), 1 capacitive touch strip | `EN_PKT_TYPE_KNOBS` (cmd 0=Rotary, 1=QLink), `EN_PKT_TYPE_SLIDER` | Delta and absolute value injection with LED bar feedback |
| **AI Camera** | OV5640 MIPI CSI-2 camera (`CONFIG_MXC_CAMERA_OV5640_MIPI_V2=y`) | V4L2 video capture pipeline | Software stub exposing synthetic gesture injection events |
| **CV / Gate** | 4 CV / Gate output jacks | `EN_PKT_TYPE_CV` (Packet type 6) | State logging, assertion tracking, and optional virtual jack monitor |
| **SD Card** | Front-panel SD card slot | Linux VFS block device / filesystem mount | Local directory folder mapping (`./sim_sdcard`) |
| **LINK** | RJ45 Ethernet port | Ableton Link network time synchronization | Network socket sync stub or disabled in headless CI |
| **Display** | 7" 800x480 RGB touchscreen | Linux frame buffer / multitouch evdev | Virtual 800x480 window (GUI mode) + virtual frame dump (headless mode) |

---

## 4. ComProtocol Wire Format Specification

The device control protocol (`ComProtocol/PktMgr`) is a lightweight binary framed message structure.

### 4.1 Packet Structure

```
+----------+----------+------------+-----------+-----------+------------+---------------------+----------+
|  Byte 0  |  Byte 1  |   Byte 2   |  Byte 3   |  Byte 4   |   Byte 5   |   Bytes 6..(6+N-1)  |  Byte 6+N|
|   'M'    |   'T'    |  PktType   |  PktDir   |  PktCmd   | Size (N+1) |    Payload Data     |   CRC8   |
|  (0x4D)  |  (0x54)  |            |           |           |            |      (N bytes)      |          |
+----------+----------+------------+-----------+-----------+------------+---------------------+----------+
```

- **Header Preamble**: 2 bytes: `'M'` (0x4D), `'T'` (0x54).
- **Packet Type** (`enumPacketType`):
  - `0x00`: `EN_PKT_TYPE_SYSTEM`
  - `0x01`: `EN_PKT_TYPE_BUTTON`
  - `0x02`: `EN_PKT_TYPE_LED`
  - `0x03`: `EN_PKT_TYPE_PAD`
  - `0x04`: `EN_PKT_TYPE_KNOBS`
  - `0x05`: `EN_PKT_TYPE_MIDI`
  - `0x06`: `EN_PKT_TYPE_CV`
  - `0x07`: `EN_PKT_TYPE_SLIDER`
- **Direction** (`enumPacketDir`):
  - `0x00`: `EN_PKT_REQUEST` (Device to Host or Host command)
  - `0x01`: `EN_PKT_RESPONSE` (Device acknowledgment or reply)
- **Command ID** (`PktCmd`): Sub-command identifier corresponding to the packet type.
- **Size Field**: `N + 1` (where `N` is the number of payload data bytes, +1 accounts for the CRC byte).
- **Payload Data**: `N` bytes of command parameters (pad index, velocity, RGB color, rotary delta, etc.).
- **CRC-8**: 1-byte checksum computed across all bytes from `'M'` through the final payload byte.

### 4.2 Checksum Algorithm (CRC-8)
- **Polynomial**: `0x31` ($x^8 + x^5 + x^4 + 1$)
- **Initial Value**: `0xFF`
- **Algorithm**:
```cpp
uint8_t crc = 0xFF;
for (char b : packetBytes) {
    crc ^= static_cast<uint8_t>(b);
    for (int j = 0; j < 8; ++j) {
        if (crc & 0x80)
            crc = (crc << 1) ^ 0x31;
        else
            crc <<= 1;
    }
}
```

---

## 5. Architectural Decision: Custom Headless & GUI Simulator

Because upstream's `kickem` does NOT communicate via the serial `ComProtocol` wire interface (it relies on in-memory JUCE signals), and because upstream cannot build out-of-the-box due to proprietary dependencies, we implement **STEP 2**:
A clean, modular C++17 virtual device harness that:
1. Emulates the real hardware protocol over PTY, Unix sockets, and TCP.
2. Manages virtual hardware state (16 pads x 8 banks with velocity, 4 Q-link knobs, jog wheel, touch strip, transport buttons, CV/gate logging, SD card directory, camera gesture events).
3. Provides both a headless scenario runner (for automated golden-file assertion testing in CI) and an interactive CLI/terminal + GUI harness.
