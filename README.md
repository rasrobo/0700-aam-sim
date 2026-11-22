# 0700-aam-sim (thumpbox-sim)

A desktop simulator, virtual device harness, and headless test suite for the BE 0700-AAM embedded firmware hardware communication protocol.

`0700-aam-sim` emulates the physical control surface and hardware subsystems over POSIX pseudo-terminals (`pty`), Unix domain sockets, or TCP sockets. It allows firmware and application logic to develop, test, and run automated regression suites headlessly without physical hardware attached.

[![Watch 4K GUI Simulator Demo](https://img.youtube.com/vi/wuoW0KpWg2U/hqdefault.jpg)](https://youtu.be/wuoW0KpWg2U)

🎛️ **[Live Interactive Web Simulator](https://rasrobo.github.io/0700-aam-sim/)** (Zero Install — Run in Browser)  
🎥 **[Watch 4K GUI Walkthrough & 1:1 Hardware Parity Demo](https://youtu.be/wuoW0KpWg2U)** (4K Ultra HD • 1:1 Button Parity • CC-BY 4.0 Open Source Music • Unlisted)  
📺 **[Watch Terminal Architecture & CI Pipeline Documentary](https://youtu.be/Twt-MhPzib8)** (1080p • Unlisted)


---

## Web simulator: device-true performance behaviour (2026-11-22)

The web app (`web/`) mirrors how the physical 0700-AAM is actually played, so
time spent in the sim transfers to the hardware:

- **Pads play their labelled sounds.** The chassis markup lists pads top-row
  first (13-16, 9-12, 5-8, 1-4); pad listeners are now bound by the pad's
  `data-pad` number, not DOM position. (Before this fix, clicking the pad
  labelled 9 triggered pad 5's sound.)
- **16 LEVEL = keygroup performance.** Strike a melodic or bass pad, then press
  **16 LEVEL**: that pad becomes the keygroup source (mirroring the upstream
  firmware's KeygroupSampler, one sample across a pitch range) and all 16 pads
  play it chromatically, with the source's root note on Pad 5. The LCD readout
  names the source pad and the note each pad strike plays. Press 16 LEVEL
  again to return to one-shot pads. Sequencer playback is never pitched.
- **REC / OVERDUB record into the loop.** While the pattern plays with Record
  or Overdub lit, pad strikes are written into the pattern at the current
  step — exactly how a loop is built on the device. Keygroup strikes record
  their pitch (`patternNotes`), and the sequencer loops them back at that
  pitch. CLEAR wipes notes as well as hits.

Verified headlessly (Puppeteer + analyser tap + pitch analysis): keygroup
strikes from a C#4 source read back as A3 / C#4 / E4 / F#4, and an overdubbed
E4 replays from the loop exactly one bar later, on pitch.

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

## Sound design notes (learned the hard way, 2026-11-22)

- **One-shot blips are drum sounds, not instruments.** The original pitched
  samples were 0.5 s dry blips; pitched across two octaves by the keygroup
  they made every song sound broken. Pitched pads now use warm sustained
  voices (scripts/make_warm_kit.py): fundamental-forward harmonics, a real
  ADSR with sustain, vibrato + detune, ~3 s long so a note pitched up an
  octave still rings. Keygroup sources must be *longer* than you think —
  pitching down stretches them, pitching up eats them.
- **Balance the kit in the manifest, not in the performance.** The old bass
  samples sat ~18 dB under the melody and were effectively silent.
  `samples/manifest.json` now carries per-sample `mix` gains (melody 0.5,
  hooks 0.45, bass 0.6) so layered loops sum to a musical level.
- **A master limiter is not optional once loops layer.** Chords + bass +
  arpeggio ringing together summed to 240k clipped samples in one 20 s
  performance. The engine now runs a gentle brickwall compressor on the
  master bus (audio.js); the same render peaks clean.
- **Vibrato and detune read as "warpy strings" — piano fixed it.** The warm
  synth kit (vibrato ~18 cents peak-to-peak, pitch-tracked after the fact,
  plus a detuned second saw) sounded seasick, and sustained pads piled up
  under half-second chord changes. The kit is now piano (scripts/
  make_piano_kit.py): additive partials with inharmonicity, per-partial
  decays, hammer tick — pitch dead steady, notes decay naturally, and
  renders peak at 0.62 with lower manifest gains. Nothing is full blast;
  the limiter only catches peaks (threshold -6 dB).
