# 0700-aam-sim (thumpbox-sim)

A desktop simulator, virtual device harness, and headless test suite for the BE 0700-AAM embedded firmware hardware communication protocol.

`0700-aam-sim` emulates the physical control surface and hardware subsystems over POSIX pseudo-terminals (`pty`), Unix domain sockets, or TCP sockets. It allows firmware and application logic to develop, test, and run automated regression suites headlessly without physical hardware attached.

[![Watch Video Demo](https://img.youtube.com/vi/Twt-MhPzib8/hqdefault.jpg)](https://youtu.be/Twt-MhPzib8)

🎥 **[Watch the Video Documentary & Demonstration on YouTube](https://youtu.be/Twt-MhPzib8)** (Unlisted)


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

### 1. Photorealistic Webpage / GUI Hardware Simulator

Launch the hardware simulator web interface with built-in Web Audio sound synthesis, 16-step sequencer, and live ComProtocol bridge:

```bash
./build/0700-aam-sim --gui
# or
./scripts/start_gui.sh [port]
```

Open `http://localhost:8080` in your web browser.

#### GUI Hardware Features:
- **1:1 Control Surface Layout**: Anodized dark chassis, hex corner screws, recessed wells.
- **7" Multi-Touch LCD Screen (800x480)**:
  - **Main View**: Track details, quantization, pad monitor, real-time audio oscilloscope.
  - **Step Sequencer**: 16 tracks x 16 steps interactive matrix with running playhead cursor.
  - **Track Mixer**: 16 channel faders, mute/solo switches, real-time peak VU level meters.
  - **Sampler View**: Audio waveform visualizer with start/end markers and zoom.
  - **Pad Edit View**: Filter cutoff/resonance sliders, AHDSR amplitude envelope, semitone tuning.
  - **Preferences**: System diagnostics, protocol framing telemetry, golden trace export.
- **16 RGB Velocity Silicone Pads**: Banks A through H (128 pads), bank-colored backlighting (Cyan, Amber, Green, Pink, Yellow, Violet, Red, White), keyboard mapping (`Z X C V`, `A S D F`, `Q W E R`, `1 2 3 4`).
- **Touch Strip Ribbon**: Capacitive tracking fader with 16-segment glowing LED ladder.
- **4 Q-Link Rotary Encoders**: 360-degree radial LED indicator rings modulating Cutoff, Resonance, Decay, and Tuning in real time.
- **Central Data Dial (Jog Wheel)**: 90px diameter dial with tactile finger indent and push-click button.
- **Transport Control Cluster**: REC (Red LED), OVERDUB (Amber LED), STOP (White LED), PLAY (Green LED), PLAY START (Green LED).
- **Web Audio Drum Machine**: Procedural 808/909 kicks, snares, hats, claps, toms, cymbals, and tuned sub-bass synth.
- **ComProtocol WebSocket Bridge**: Sends and receives wire-accurate binary frames (`0x4D 0x54`, CRC-8 poly `0x31`) over WebSocket; seamlessly falls back to standalone browser audio when offline.

---

### 2. Interactive Simulator (PTY Mode)

Launch the simulator attached to a newly created pseudo-terminal:

```bash
./build/0700-aam-sim --pty
```

The simulator prints the slave PTY device path (e.g. `/dev/pts/3`). You can configure the host application or symlink `/dev/ttymxc0` to point directly to this virtual port.

### 3. Headless Scenario Runner

Execute a deterministic test scenario script:

```bash
./build/0700-aam-sim --scenario tests/scenarios/pad_and_knob_flow.json --assert-golden tests/golden/pad_and_knob_flow.golden.json
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
