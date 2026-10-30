# thumpbox-sim

A desktop simulator, virtual device harness, and headless test suite for the BE 0700-AAM embedded firmware hardware communication protocol.

`thumpbox-sim` emulates the physical control surface and hardware subsystems over POSIX pseudo-terminals (`pty`), Unix domain sockets, or TCP sockets. It allows firmware and application logic to develop, test, and run automated regression suites headlessly without physical hardware attached.

---

## Features

- **Wire-Accurate Protocol Engine**: Full bidirectional encoding and decoding of the binary framed `ComProtocol` (`0x4D 0x54` header, CRC-8 polynomial `0x31`, request/response handling).
- **Virtual Control Surface Emulation**:
  - **16 RGB Pads x 8 Banks**: Velocity-sensitive trigger modeling (Banks A–H = 128 virtual pads) with full RGB state and blink tracking.
  - **Knobs & Encoders**: 4 assignable Q-link continuous controllers + central jog wheel (CW/CCW encoder + click push-button).
  - **Touch Strip**: Capacitive slider position input, touch state, and feedback LED bar levels.
  - **Transport & Navigation Controls**: Play, PlayStart, Record, Overdub, Stop, Shift, Banks, and system mode buttons.
- **Hardware Subsystem Stubs**:
  - **CV / Gate**: 4 output channels logged with timestamped state changes.
  - **AI Camera**: Virtual gesture event injection stub.
  - **SD Card**: Local filesystem folder sandbox (`./sim_sdcard`).
  - **MIDI I/O**: Virtual MIDI packet routing.
  - **Display Frame**: 800x480 virtual frame buffer and geometry state.
- **Headless JSON Scenario Runner**: Replay hardware event sequences from JSON test scripts, monitor response packets, and verify expected states deterministically in CI.
- **Interactive Terminal & GUI Harness**: Real-time interactive control mapping for manual testing.

---

## Architecture

```
+-------------------------------------------------------+
|                 Host Firmware / Client                |
|           (expects UART /dev/ttymxc0 at 230400)       |
+-------------------------------------------------------+
                           ▲
                           │ /dev/pts/X or socket
                           ▼
+-------------------------------------------------------+
|                     thumpbox-sim                      |
|                                                       |
|  +-------------------------------------------------+  |
|  |           Protocol Engine (ComProtocol)         |  |
|  |     Framing: 'M' 'T' <Type> <Dir> <Cmd> <Len>   |  |
|  |     CRC-8: Poly 0x31 (Init 0xFF)                |  |
|  +-------------------------------------------------+  |
|                          ▲                            |
|                          ▼                            |
|  +-------------------------------------------------+  |
|  |             Virtual Hardware State              |  |
|  |  * 16 RGB Pads x 8 Banks   * 4 Q-Link Knobs     |  |
|  |  * Central Jog Wheel       * Touch Strip Slider |  |
|  |  * Transport Buttons       * 4 CV/Gate Outputs  |  |
|  |  * AI Camera Gesture Stub  * SD Card Directory  |  |
|  +-------------------------------------------------+  |
|                          ▲                            |
|            ┌─────────────┴─────────────┐              |
|            ▼                           ▼              |
|  +-------------------+       +---------------------+  |
|  |  Scenario Runner  |       |   Interactive CLI   |  |
|  |  (Headless / CI)  |       |   & GUI Monitor     |  |
|  +-------------------+       +---------------------+  |
+-------------------------------------------------------+
```

---

## Requirements

- **C++17** compiler (GCC >= 9 or Clang >= 10)
- **CMake** >= 3.16
- **Make** or **Ninja**

---

## Building

```bash
mkdir -p build
cd build
cmake ..
cmake --build .
```

To run unit tests and golden-file verification:
```bash
ctest --output-on-failure
```

---

## Running

### 1. Interactive Simulator (PTY Mode)

Launch the simulator attached to a newly created pseudo-terminal:

```bash
./build/thumpbox-sim --pty
```

The simulator prints the slave PTY device path (e.g. `/dev/pts/3`). You can configure the host application or symlink `/dev/ttymxc0` to point directly to this virtual port.

### 2. Headless Scenario Runner

Execute a deterministic test scenario script:

```bash
./build/thumpbox-sim --scenario tests/scenarios/pad_and_knob_flow.json --assert-golden tests/golden/pad_and_knob_flow.golden.json
```

---

## Upstream Synchronization

Upstream source code is referenced as a git submodule in `./upstream`. To fetch or synchronize:

```bash
sh scripts/fetch_upstream.sh
```

The pinned upstream commit is recorded in `UPSTREAM_VERSION`.

---

## License & Notice

This project is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See [LICENSE](LICENSE) for the full text.

Third-party copyright notices and upstream attributions are documented in [NOTICE.md](NOTICE.md).
