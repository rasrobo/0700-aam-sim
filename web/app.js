/**
 * 0700-AAM Sovereign Desktop Hardware Simulator Controller
 * Coordinates skeuomorphic hardware controls, Web Audio synth engine,
 * interactive 7" LCD touchscreen views, 16-step sequencer, and ComProtocol WebSocket bridge.
 */

document.addEventListener("DOMContentLoaded", () => {
    // --- State Matrix ---
    const state = {
        currentBank: 0, // 0 = Bank A ... 7 = Bank H
        shiftActive: false,
        fullLevel: false,
        tcOn: true,
        lastStruckPad: 0,
        currentSeq: 0,
        sixteenLevel: false,
        // 16 LEVEL keygroup: the last pitched pad struck becomes the keygroup
        // source; while 16 LEVEL is on, the 16 pads play that one sample
        // chromatically (pad 5 = the sample's root note, ascending).
        lastPad: 11,
        keygroupPad: 11,
        activeView: "main",

        // Transport
        isPlaying: false,
        isRecording: false,
        isOverdubbing: false,
        bpm: 120.0,
        currentStep: 0,
        totalSteps: 16,

        // Q-Links (0.0 to 1.0)
        qlinks: [0.65, 0.25, 0.50, 0.50],

        // Master & Rec Gain (0.0 to 1.0)
        masterGain: 0.55,
        recGain: 0.70,

        // Touch Slider (0.0 to 1.0)
        touchValue: 0.5,

        // Jog Wheel
        jogAngle: 0,

        // Bank Colors
        bankColors: [
            "#00d2ff", // Bank A (Cyan)
            "#ff9900", // Bank B (Amber)
            "#00ff66", // Bank C (Green)
            "#ff00aa", // Bank D (Pink)
            "#ffee00", // Bank E (Yellow)
            "#9933ff", // Bank F (Purple)
            "#ff3344", // Bank G (Red)
            "#ffffff"  // Bank H (White)
        ],

        // 16 instruments x 16 steps pattern matrix
        pattern: Array.from({ length: 16 }, () => new Array(16).fill(false)),
        // Pitched notes recorded into the loop by keygroup overdub strikes:
        // patternNotes[track][step] = array of MIDI notes (a chord can land
        // on one step), or null for a plain unpitched hit.
        patternNotes: Array.from({ length: 16 }, () => new Array(16).fill(null)),

        // Mixer states (16 channels)
        mixer: Array.from({ length: 16 }, () => ({
            volume: 0.85,
            pan: 0.0,
            mute: false,
            solo: false,
            vuLevel: 0.0
        }))
    };

    // Default demo song: "When the Saints Go Marching In" (public
    // domain) — the opening phrase as a one-bar loop, so the machine
    // plays a tune everyone knows the moment you press PLAY.
    // (Replaced 2026-11-23: the old factory groove hammered a pitched
    // D4 sample on all 16 steps as a "shaker" and stabbed unrelated
    // bass pitches — noise, not a song.)
    // Drums (marching): kick on beats 1 and 3, snare on 2 and 4,
    // closed hat on every eighth note.
    [0, 8].forEach(s => state.pattern[0][s] = true);
    [4, 12].forEach(s => state.pattern[1][s] = true);
    [0, 2, 4, 6, 8, 10, 12, 14].forEach(s => state.pattern[2][s] = true);
    // Voicing rule (2026-11-24, the anti-warp rule): a keygroup note
    // is a playback-rate shift from the sample's root, and big shifts
    // sound warped — the old demo ran the melody on mel_d4 (root 62)
    // at +5/+9/+10/+12 semitones. So every demo note sits on the
    // track whose root is closest to it, keeping shifts within a few
    // semitones — the same reason the song renders use a soundfont
    // (a real sample near every pitch) instead of one stretched one.
    // Bass: G2 on track 12 (bass_fs1, root 42, +1), D3 on track 14
    // (bass_gs1, root 44, +6) — patternNotes carry the pitches,
    // exactly as an overdub capture would have written them.
    state.pattern[12][0] = true;  state.patternNotes[12][0] = [43];   // G2
    state.pattern[12][8] = true;  state.patternNotes[12][8] = [43];   // G2
    state.pattern[14][12] = true; state.patternNotes[14][12] = [50];  // D3
    // Melody on track 6 (hook_gs4, root 68): G4 B4 C5 D5 at
    // -1/+3/+4/+6 semitones — "Oh when the saints..."
    [[0, 67], [4, 71], [8, 72], [12, 74]].forEach(([s, n]) => {
        state.pattern[6][s] = true;
        state.patternNotes[6][s] = [n];
    });

    // --- Instantiate Audio Engine ---
    const audio = new AudioEngine();

    // Bundled samples load on the first gesture (an AudioContext cannot decode before one).
    // Until they are ready every pad keeps its synthesised voice, so nothing breaks if the
    // samples folder is absent.
    window.__audio = audio;   // exposed for testing the sampler from the console
    window.__simState = state; // exposed for headless tests of the control surface
    const kickSampler = () => { audio.loadSamples("samples/"); };
    window.addEventListener("pointerdown", kickSampler, { once: true });
    window.addEventListener("keydown", kickSampler, { once: true });

    // --- WebSocket ComProtocol Client ---
    let ws = null;
    let wsConnected = false;

    function connectWebSocket() {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const host = window.location.hostname || "localhost";
        const wsUrl = `${proto}//${host}:8080/ws`;

        const indicator = document.getElementById("ws-indicator");
        const statusText = document.getElementById("ws-text");

        try {
            ws = new WebSocket(wsUrl);
            ws.binaryType = "arraybuffer";

            ws.onopen = () => {
                wsConnected = true;
                indicator.querySelector(".dot").className = "dot active";
                statusText.innerText = "COM PROTOCOL ACTIVE (:8080)";
                console.log("[WebSocket] Connected to 0700-AAM simulator harness");
            };

            ws.onclose = () => {
                wsConnected = false;
                indicator.querySelector(".dot").className = "dot disconnected";
                statusText.innerText = "STANDALONE (DISCONNECTED)";
            };

            ws.onerror = () => {
                wsConnected = false;
                indicator.querySelector(".dot").className = "dot disconnected";
                statusText.innerText = "STANDALONE (DISCONNECTED)";
            };

            ws.onmessage = (evt) => {
                if (evt.data instanceof ArrayBuffer) {
                    const bytes = new Uint8Array(evt.data);
                    const packet = ComProtocol.decodePacket(bytes);
                    if (packet) handleIncomingPacket(packet);
                }
            };
        } catch (e) {
            console.warn("[WebSocket] Standalone mode active:", e);
        }
    }

    function sendHwPacket(cmd, payload = []) {
        if (ws && wsConnected && ws.readyState === WebSocket.OPEN) {
            const bytes = ComProtocol.encodePacket(cmd, payload, 0x01, 0x01);
            ws.send(bytes.buffer);
        }
    }

    function handleIncomingPacket(packet) {
        const { cmd, payload } = packet;
        const C = ComProtocol.CommandId;

        if (cmd >= C.PAD_1 && cmd <= C.PAD_16) {
            const padIdx = cmd - C.PAD_1;
            const isDown = payload.length > 0 && payload[0] === 0x01;
            const vel = payload.length > 1 ? payload[1] : 127;
            if (isDown) triggerPadStrike(padIdx, vel, false);
        } else if (cmd === C.SET_PAD_COLOR) {
            // Update pad color from firmware
            if (payload.length >= 4) {
                const padIdx = payload[0];
                const r = payload[1], g = payload[2], b = payload[3];
                const padEl = document.querySelector(`.pad[data-pad="${padIdx + 1}"]`);
                if (padEl) padEl.style.setProperty("--pad-glow-color", `rgb(${r},${g},${b})`);
            }
        }
    }

    // --- Pad Matrix & Strike Handling ---
    // The chassis markup lists pads top-row first (13-16, 9-12, 5-8, 1-4), so
    // DOM order is NOT pad order. Sort by the data-pad number: on the real
    // device, the pad labelled 9 is pad 9 and plays pad 9's sound.
    const padElements = Array.from(document.querySelectorAll(".pad"))
        .sort((a, b) => parseInt(a.dataset.pad) - parseInt(b.dataset.pad));

    function updatePadColors() {
        const color = state.bankColors[state.currentBank % state.bankColors.length];
        document.documentElement.style.setProperty("--pad-glow-color", color);

        const bankLetters = ["A", "B", "C", "D", "E", "F", "G", "H"];
        const curLetter = bankLetters[state.currentBank];
        const bankDisplay = document.getElementById("main-active-bank");
        if (bankDisplay) {
            const startPad = state.currentBank * 16 + 1;
            const endPad = startPad + 15;
            bankDisplay.innerText = `BANK ${curLetter} (Pads ${startPad}-${endPad})`;
        }
    }

    const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
    const noteName = (midi) => `${NOTE_NAMES[midi % 12]}${Math.floor(midi / 12) - 1}`;
    // Pads whose bundled sample has a root note (see samples/manifest.json).
    const PITCHED_PADS = new Set([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
    const keygroupRoot = () => {
        const roots = audio.sampleNotes || {};
        return roots[state.keygroupPad];
    };

    function triggerPadStrike(padIndex, velocity = 127, sendPacket = true, fromSequencer = false) {
        audio.ensureContext();
        if (!fromSequencer) state.lastStruckPad = padIndex;
        if (!fromSequencer) lcdFollowPad(padIndex);

        let effectiveVel = velocity;
        if (state.fullLevel) effectiveVel = 127;

        // Visual flash on physical pad
        const padEl = padElements[padIndex];
        if (padEl) {
            padEl.classList.add("hit");
            setTimeout(() => padEl.classList.remove("hit"), 120);
        }

        // Visual flash on LCD mini-pad monitor
        const miniPads = document.querySelectorAll(".mini-pad");
        if (miniPads[padIndex]) {
            miniPads[padIndex].classList.add("active");
            setTimeout(() => miniPads[padIndex].classList.remove("active"), 120);
        }

        // Trigger Audio Synthesis
        const instNameTag = document.getElementById("stepseq-inst-name");
        const root = keygroupRoot();
        let keygroupNote = null;
        if (!fromSequencer && state.sixteenLevel && root != null && audio.samplesReady) {
            // 16 LEVEL keygroup performance: every pad plays the keygroup
            // source sample at a chromatic pitch, pad 5 (index 4) = root.
            const midiNote = root + (padIndex - 4);
            keygroupNote = midiNote;
            const velNorm = Math.max(0.1, Math.min(1.0, effectiveVel / 127.0));
            audio.schedulePitch(state.keygroupPad, midiNote, null, velNorm);
            if (instNameTag) {
                instNameTag.innerText = `16 LEVEL Pad ${state.keygroupPad + 1} keygroup: ${noteName(midiNote)}`;
            }
        } else {
            audio.triggerPad(padIndex, effectiveVel);
            if (PITCHED_PADS.has(padIndex)) state.lastPad = padIndex;

            // Update active instrument in Step Sequencer view
            // (user strikes only — sequencer playback must not keep
            // rewriting the Step Sequencer's TRACK box)
            if (!fromSequencer && instNameTag && audio.instruments[padIndex]) {
                instNameTag.innerText = `Pad ${padIndex + 1}: ${audio.instruments[padIndex].name}`;
            }
        }

        // REC / OVERDUB: on the device, striking pads while the loop plays
        // with Record or Overdub lit writes those hits into the pattern, and
        // they loop back. Keygroup strikes write their pitch too, so a melody
        // played once over the loop is captured and repeats.
        if (!fromSequencer && state.isPlaying && (state.isRecording || state.isOverdubbing)) {
            let step = state.currentStep;
            if (!state.tcOn && state._stepDurMs) {
                // TC off: no timing correction — the strike belongs to
                // whichever step boundary it is closest to in time.
                const phase = performance.now() - (state._stepStartAt || 0);
                if (phase > state._stepDurMs / 2) step = (step + 1) % state.totalSteps;
            }
            const track = keygroupNote != null ? state.keygroupPad : padIndex;
            state.pattern[track][step] = true;
            if (keygroupNote != null) {
                if (!Array.isArray(state.patternNotes[track][step])) {
                    state.patternNotes[track][step] = [];
                }
                if (!state.patternNotes[track][step].includes(keygroupNote)) {
                    state.patternNotes[track][step].push(keygroupNote);
                }
            } else {
                state.patternNotes[track][step] = null;
            }
            const btn = document.querySelector(`.step-btn[data-track="${track}"][data-step="${step}"]`);
            if (btn) btn.classList.add("active");
        }

        // Send ComProtocol packet
        if (sendPacket) {
            sendHwPacket(ComProtocol.CommandId.PAD_1 + padIndex, [0x01, effectiveVel]);
        }
    }

    padElements.forEach((padEl, idx) => {
        // Mouse Down / Touch Start
        const onDown = (e) => {
            e.preventDefault();
            // Calculate velocity based on click position inside pad
            const rect = padEl.getBoundingClientRect();
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            const relY = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
            // Lower on the pad = higher velocity
            const vel = Math.round(60 + relY * 67);
            triggerPadStrike(idx, vel, true);
        };

        const onUp = (e) => {
            e.preventDefault();
            sendHwPacket(ComProtocol.CommandId.PAD_1 + idx, [0x00, 0x00]);
        };

        padEl.addEventListener("mousedown", onDown);
        padEl.addEventListener("mouseup", onUp);
        padEl.addEventListener("touchstart", onDown, { passive: false });
        padEl.addEventListener("touchend", onUp, { passive: false });
    });

    // --- Touch Strip Ribbon ---
    const touchStrip = document.getElementById("touch-strip");
    const touchThumb = document.getElementById("touch-thumb");
    const touchLedLadder = document.getElementById("touch-led-ladder");

    // Generate 16 LED segments
    for (let i = 0; i < 16; i++) {
        const seg = document.createElement("div");
        seg.className = "strip-led-seg";
        touchLedLadder.appendChild(seg);
    }
    const ledSegments = Array.from(touchLedLadder.children);

    function setTouchStrip(norm) {
        state.touchValue = Math.max(0.0, Math.min(1.0, norm));
        touchThumb.style.left = `${state.touchValue * 100}%`;

        // Update LEDs
        const activeCount = Math.round(state.touchValue * 16);
        ledSegments.forEach((seg, i) => {
            seg.classList.toggle("lit", i < activeCount);
        });

        // Modulate Pitch / Filter Cutoff via Touch
        const pitchBend = (state.touchValue - 0.5) * 4; // -2 to +2 semitones
        audio.params.tuning = pitchBend;

        sendHwPacket(ComProtocol.CommandId.TOUCH_SLIDER, [Math.round(state.touchValue * 127)]);
    }

    let isTouchingStrip = false;
    touchStrip.addEventListener("mousedown", (e) => {
        isTouchingStrip = true;
        const rect = touchStrip.getBoundingClientRect();
        setTouchStrip((e.clientX - rect.left) / rect.width);
    });
    window.addEventListener("mousemove", (e) => {
        if (!isTouchingStrip) return;
        const rect = touchStrip.getBoundingClientRect();
        setTouchStrip((e.clientX - rect.left) / rect.width);
    });
    window.addEventListener("mouseup", () => {
        if (isTouchingStrip) {
            isTouchingStrip = false;
            // Return to center
            setTouchStrip(0.5);
        }
    });

    // --- Master & Rec Gain Knobs ---
    function setupRotaryKnob(elId, onValChange) {
        const knob = document.getElementById(elId);
        if (!knob) return;
        const ind = knob.querySelector(".knob-indicator");
        let startY = 0;
        let startVal = parseFloat(knob.dataset.val) || 75;

        const updateKnob = (val) => {
            val = Math.max(0, Math.min(100, val));
            knob.dataset.val = val;
            const deg = -135 + (val / 100) * 270;
            ind.style.transform = `rotate(${deg}deg)`;
            onValChange(val / 100.0);
        };

        updateKnob(startVal);

        knob.addEventListener("mousedown", (e) => {
            startY = e.clientY;
            startVal = parseFloat(knob.dataset.val) || 75;

            const onMove = (ev) => {
                const dy = startY - ev.clientY;
                updateKnob(startVal + dy * 0.75);
            };

            const onEnd = () => {
                window.removeEventListener("mousemove", onMove);
                window.removeEventListener("mouseup", onEnd);
            };

            window.addEventListener("mousemove", onMove);
            window.addEventListener("mouseup", onEnd);
        });
    }

    setupRotaryKnob("knob-master", (val) => {
        state.masterGain = val;
        audio.setMasterVolume(val);
    });

    setupRotaryKnob("knob-rec", (val) => {
        state.recGain = val;
    });

    // --- Output strip (below the device): volume slider + live meter.
    // The meter reads the engine's own analyser, which sits AFTER the
    // master limiter — so it shows exactly what reaches the speakers,
    // red zone included. Default master is 0.55 (normalised 2026-11-24:
    // at the old 0.85 the demo loop ran hot, RMS ~0.12 with everything
    // stacked; 0.55 measures peak ~0.39 / RMS ~0.07 with headroom for
    // pad bursts). The on-device MASTER knob and this slider drive the
    // same gain and stay in sync.
    const outSlider = document.getElementById("output-volume");
    const outMeter = document.getElementById("output-meter");
    const outDb = document.getElementById("output-db");
    const knobMasterEl = document.getElementById("knob-master");
    let outDragging = false;
    if (outSlider) {
        outSlider.addEventListener("pointerdown", () => { outDragging = true; });
        window.addEventListener("pointerup", () => { outDragging = false; });
        outSlider.addEventListener("input", () => {
            const v = parseFloat(outSlider.value) / 100.0;
            state.masterGain = v;
            audio.setMasterVolume(v);
            if (knobMasterEl) {
                knobMasterEl.dataset.val = Math.round(v * 100);
                const ind = knobMasterEl.querySelector(".knob-indicator");
                if (ind) ind.style.transform = `rotate(${-135 + v * 270}deg)`;
            }
        });
    }
    if (outMeter) {
        const mctx = outMeter.getContext("2d");
        const mdata = new Float32Array(512);
        let peakHold = 0, peakAge = 0;
        const drawMeter = () => {
            requestAnimationFrame(drawMeter);
            const W = outMeter.width, H = outMeter.height;
            mctx.fillStyle = "#0b0e14";
            mctx.fillRect(0, 0, W, H);
            let peak = 0;
            if (audio.analyser) {
                audio.analyser.getFloatTimeDomainData(mdata);
                for (let i = 0; i < mdata.length; i++) {
                    const a = Math.abs(mdata[i]);
                    if (a > peak) peak = a;
                }
            }
            if (peak >= peakHold) { peakHold = peak; peakAge = 0; }
            else if (++peakAge > 45) { peakHold = Math.max(0, peakHold - 0.008); peakAge = 30; }
            const frac = Math.min(1, peak);
            const grad = mctx.createLinearGradient(0, 0, W, 0);
            grad.addColorStop(0, "#37d67a");
            grad.addColorStop(0.62, "#37d67a");
            grad.addColorStop(0.78, "#f5c542");
            grad.addColorStop(0.92, "#e5484d");
            grad.addColorStop(1, "#e5484d");
            mctx.fillStyle = grad;
            mctx.fillRect(0, 0, W * frac, H);
            mctx.fillStyle = "rgba(255,255,255,0.85)";
            mctx.fillRect(Math.max(0, W * Math.min(1, peakHold) - 2), 0, 2, H);
            if (outDb) {
                outDb.textContent = peakHold > 0.001
                    ? `${(20 * Math.log10(peakHold)).toFixed(1)} dB`
                    : "-inf dB";
            }
            if (outSlider && !outDragging) {
                const sv = Math.round(state.masterGain * 100);
                if (parseFloat(outSlider.value) !== sv) outSlider.value = sv;
            }
        };
        drawMeter();
    }

    // --- 4 Q-Link Rotary Encoders with 360 Radial LED Rings ---
    const qlinkReadouts = [
        document.getElementById("readout-q1"),
        document.getElementById("readout-q2"),
        document.getElementById("readout-q3"),
        document.getElementById("readout-q4")
    ];

    function updateQlink(idx, normVal) {
        state.qlinks[idx] = Math.max(0.0, Math.min(1.0, normVal));
        const qModule = document.querySelector(`.qlink-module[data-qlink="${idx + 1}"]`);
        if (!qModule) return;

        // Rotate knob indicator
        const line = qModule.querySelector(".knob-line");
        const deg = -135 + state.qlinks[idx] * 270;
        line.style.transform = `rotate(${deg}deg)`;

        // SVG Radial Ring offset (circumference = 2 * PI * 42 ≈ 264)
        const ringVal = qModule.querySelector(".ring-val");
        const totalLen = 264;
        const offset = totalLen - (state.qlinks[idx] * totalLen * 0.75);
        ringVal.style.strokeDashoffset = offset;

        // Apply audio parameter modulation
        if (idx === 0) {
            audio.setFilterCutoff(state.qlinks[0]);
            qlinkReadouts[0].innerText = `${(audio.params.cutoff / 1000).toFixed(1)} kHz`;
        } else if (idx === 1) {
            audio.setResonance(state.qlinks[1]);
            qlinkReadouts[1].innerText = `${audio.params.resonance.toFixed(1)} Q`;
        } else if (idx === 2) {
            audio.setDecay(state.qlinks[2]);
            qlinkReadouts[2].innerText = `${audio.params.decay.toFixed(1)}x`;
        } else if (idx === 3) {
            audio.setTuning(state.qlinks[3]);
            qlinkReadouts[3].innerText = `${audio.params.tuning > 0 ? "+" : ""}${audio.params.tuning} st`;
        }

        sendHwPacket(ComProtocol.CommandId.QLINK_1 + idx, [Math.round(state.qlinks[idx] * 127)]);
    }

    document.querySelectorAll(".qlink-rotary").forEach((rotary, idx) => {
        let startY = 0;
        let startVal = state.qlinks[idx];

        rotary.addEventListener("mousedown", (e) => {
            startY = e.clientY;
            startVal = state.qlinks[idx];

            const onMove = (ev) => {
                const dy = startY - ev.clientY;
                updateQlink(idx, startVal + dy * 0.008);
            };

            const onEnd = () => {
                window.removeEventListener("mousemove", onMove);
                window.removeEventListener("mouseup", onEnd);
            };

            window.addEventListener("mousemove", onMove);
            window.addEventListener("mouseup", onEnd);
        });

        // Mouse wheel modulation
        rotary.addEventListener("wheel", (e) => {
            e.preventDefault();
            const step = e.deltaY < 0 ? 0.04 : -0.04;
            updateQlink(idx, state.qlinks[idx] + step);
        }, { passive: false });
    });

    // Initialize all 4 Q-Links
    for (let i = 0; i < 4; i++) updateQlink(i, state.qlinks[i]);

    // --- Central Jog Wheel (Data Dial) ---
    const jogWheel = document.getElementById("jog-wheel");
    const jogCenterBtn = document.getElementById("jog-center-btn");

    function rotateJogWheel(deltaDegrees) {
        state.jogAngle = (state.jogAngle + deltaDegrees) % 360;
        jogWheel.style.transform = `rotate(${state.jogAngle}deg)`;

        // Adjust active parameter or BPM
        const bpmStep = deltaDegrees > 0 ? 0.5 : -0.5;
        state.bpm = Math.max(40.0, Math.min(280.0, state.bpm + bpmStep));
        document.getElementById("lcd-bpm").innerText = `${state.bpm.toFixed(1)} BPM`;

        const cmd = deltaDegrees > 0 ? ComProtocol.CommandId.JOG_CW : ComProtocol.CommandId.JOG_CCW;
        sendHwPacket(cmd, [Math.abs(Math.round(deltaDegrees))]);
    }

    jogWheel.addEventListener("wheel", (e) => {
        e.preventDefault();
        rotateJogWheel(e.deltaY < 0 ? 15 : -15);
    }, { passive: false });

    jogCenterBtn.addEventListener("click", () => {
        sendHwPacket(ComProtocol.CommandId.JOG_CLICK, [0x01]);
        jogCenterBtn.style.background = "#00d2ff";
        setTimeout(() => jogCenterBtn.style.background = "", 150);
    });

    // Plus, Minus & D-Pad Cursor Buttons
    document.getElementById("btn-plus").addEventListener("click", () => rotateJogWheel(15));
    document.getElementById("btn-minus").addEventListener("click", () => rotateJogWheel(-15));
    const btnCurUp = document.getElementById("btn-cursor-up");
    const btnCurDown = document.getElementById("btn-cursor-down");
    const btnCurLeft = document.getElementById("btn-cursor-left");
    const btnCurRight = document.getElementById("btn-cursor-right");
    if (btnCurUp) btnCurUp.addEventListener("click", () => rotateJogWheel(15));
    if (btnCurDown) btnCurDown.addEventListener("click", () => rotateJogWheel(-15));
    if (btnCurLeft) btnCurLeft.addEventListener("click", () => rotateJogWheel(-15));
    if (btnCurRight) btnCurRight.addEventListener("click", () => rotateJogWheel(15));

    // --- Bank Selection Buttons (A, B, C, D / E, F, G, H with Shift) ---
    const bankButtons = [
        document.getElementById("btn-bank-a"),
        document.getElementById("btn-bank-b"),
        document.getElementById("btn-bank-c"),
        document.getElementById("btn-bank-d")
    ];

    function selectBank(bankIndex) {
        state.currentBank = bankIndex;
        bankButtons.forEach((btn, idx) => {
            const isSelected = (state.currentBank % 4) === idx;
            btn.classList.toggle("active", isSelected);
            const led = btn.querySelector(".bank-led");
            if (led) led.classList.toggle("active", isSelected);
        });

        updatePadColors();
        sendHwPacket(ComProtocol.CommandId.BANK_A + (state.currentBank % 8));
    }

    bankButtons.forEach((btn, idx) => {
        btn.addEventListener("click", () => {
            const targetBank = state.shiftActive ? idx + 4 : idx;
            selectBank(targetBank);
        });
    });

    // --- Shift Button ---
    const shiftBtn = document.getElementById("btn-shift");
    shiftBtn.addEventListener("click", () => {
        state.shiftActive = !state.shiftActive;
        shiftBtn.classList.toggle("active", state.shiftActive);
        sendHwPacket(ComProtocol.CommandId.SHIFT, [state.shiftActive ? 0x01 : 0x00]);
    });

    // --- Pad Mode Buttons: Full Level & 16 Level ---
    const btnFullLevel = document.getElementById("btn-full-level");
    const btn16Level = document.getElementById("btn-16-level");

    btnFullLevel.addEventListener("click", () => {
        state.fullLevel = !state.fullLevel;
        btnFullLevel.classList.toggle("active", state.fullLevel);
        sendHwPacket(ComProtocol.CommandId.FULL_LEVEL, [state.fullLevel ? 0x01 : 0x00]);
    });

    btn16Level.addEventListener("click", () => {
        state.sixteenLevel = !state.sixteenLevel;
        btn16Level.classList.toggle("active", state.sixteenLevel);
        if (state.sixteenLevel) {
            // The last pitched pad struck becomes the keygroup source, as on
            // the hardware: hit a melodic/bass pad, then press 16 LEVEL and
            // the pads become that sound played across chromatic pitches.
            if (PITCHED_PADS.has(state.lastPad)) state.keygroupPad = state.lastPad;
            const instNameTag = document.getElementById("stepseq-inst-name");
            const root = keygroupRoot();
            if (instNameTag) {
                instNameTag.innerText = root != null
                    ? `16 LEVEL: Pad ${state.keygroupPad + 1} keygroup (root ${noteName(root)} on Pad 5)`
                    : `16 LEVEL: Pad ${state.keygroupPad + 1} keygroup (samples loading...)`;
            }
        }
        sendHwPacket(ComProtocol.CommandId.LEVEL_16, [state.sixteenLevel ? 0x01 : 0x00]);
    });

    // --- Previously dead hardware buttons, wired to real functions
    // (button audit 2026-11-24: these had labels and protocol ids but
    // no handlers at all). Each one now does the job its label claims,
    // against the sim's real state.
    const refreshStepGrid = () => {
        document.querySelectorAll(".step-btn").forEach(btn => {
            const t = parseInt(btn.dataset.track), st = parseInt(btn.dataset.step);
            btn.classList.toggle("active", !!state.pattern[t][st]);
        });
    };
    const flashBtn = (el) => {
        if (!el) return;
        el.classList.add("active");
        setTimeout(() => el.classList.remove("active"), 220);
    };
    const clonePattern = () => JSON.parse(JSON.stringify({
        pattern: state.pattern, patternNotes: state.patternNotes }));
    const applyPattern = (data) => {
        state.pattern = data.pattern;
        state.patternNotes = data.patternNotes;
        refreshStepGrid();
        refreshLcd();
    };

    // TC ON/OFF: timing correction for captured strikes (see the
    // capture block in triggerPadStrike).
    const btnTc = document.getElementById("btn-tc");
    btnTc.classList.add("active"); // TC defaults on
    btnTc.addEventListener("click", () => {
        state.tcOn = !state.tcOn;
        btnTc.classList.toggle("active", state.tcOn);
        const val = document.getElementById("main-tc-val");
        if (val) val.innerText = state.tcOn ? "1/16 Standard" : "Off (nearest step)";
        sendHwPacket(ComProtocol.CommandId.TC, [state.tcOn ? 0x01 : 0x00]);
    });

    // TRACK MUTE / PAD MUTE: mute the last struck pad's track. The
    // sequencer already honours state.mixer[track].mute.
    const btnTrackMute = document.getElementById("btn-track-mute");
    btnTrackMute.addEventListener("click", () => {
        const track = state.lastStruckPad;
        state.mixer[track].mute = !state.mixer[track].mute;
        btnTrackMute.classList.toggle("active", state.mixer[track].mute);
        const strip = document.querySelectorAll("#mixer-strips .mixer-strip")[track];
        const mb = strip ? strip.querySelector(".strip-btn.mute") : null;
        if (mb) mb.classList.toggle("active", state.mixer[track].mute);
        sendHwPacket(ComProtocol.CommandId.TRACK_MUTE, [track, state.mixer[track].mute ? 0x01 : 0x00]);
    });

    // ERASE / CLEAR: erase the last struck pad's row; with SHIFT held,
    // erase the whole pattern.
    const btnErase = document.getElementById("btn-erase");
    btnErase.addEventListener("click", () => {
        if (state.shiftActive) {
            for (let t = 0; t < 16; t++) {
                state.pattern[t].fill(false);
                state.patternNotes[t].fill(null);
            }
        } else {
            const t = state.lastStruckPad;
            state.pattern[t].fill(false);
            state.patternNotes[t].fill(null);
        }
        refreshStepGrid();
        refreshLcd();
        flashBtn(btnErase);
        sendHwPacket(ComProtocol.CommandId.ERASE, [state.lastStruckPad]);
    });

    // COPY / PASTE: plain press copies the whole pattern; SHIFT+press
    // pastes it back (the device's one button, two jobs).
    let patternClipboard = null;
    const btnCopy = document.getElementById("btn-copy");
    btnCopy.addEventListener("click", () => {
        if (state.shiftActive && patternClipboard) {
            applyPattern(JSON.parse(JSON.stringify(patternClipboard)));
        } else {
            patternClipboard = clonePattern();
        }
        flashBtn(btnCopy);
        sendHwPacket(ComProtocol.CommandId.COPY, [state.shiftActive ? 0x01 : 0x00]);
    });

    // NOTE REPEAT / LATCH: while on, the last struck pad retriggers
    // every step (16ths at the current bpm) until switched off.
    let noteRepeatTimer = null;
    const btnNoteRepeat = document.getElementById("btn-note-repeat");
    const stopNoteRepeat = () => {
        if (noteRepeatTimer) { clearTimeout(noteRepeatTimer); noteRepeatTimer = null; }
    };
    btnNoteRepeat.addEventListener("click", () => {
        state.noteRepeatOn = !state.noteRepeatOn;
        btnNoteRepeat.classList.toggle("active", state.noteRepeatOn);
        stopNoteRepeat();
        if (state.noteRepeatOn) {
            const tick = () => {
                if (!state.noteRepeatOn) return;
                triggerPadStrike(state.lastStruckPad, 110, false);
                noteRepeatTimer = setTimeout(tick, (60000 / state.bpm) / 4);
            };
            tick();
        }
        sendHwPacket(ComProtocol.CommandId.NOTE_REPEAT, [state.noteRepeatOn ? 0x01 : 0x00]);
    });

    // NEXT SEQ / FX: four sequence slots in memory. Leaving a slot
    // saves it; entering a fresh slot starts from an empty pattern.
    const seqSlots = [null, null, null, null];
    const btnNextSeq = document.getElementById("btn-next-seq");
    btnNextSeq.addEventListener("click", () => {
        seqSlots[state.currentSeq] = { ...clonePattern(), bpm: state.bpm };
        state.currentSeq = (state.currentSeq + 1) % 4;
        const slot = seqSlots[state.currentSeq];
        if (slot) {
            applyPattern(JSON.parse(JSON.stringify(slot)));
            state.bpm = slot.bpm;
        } else {
            applyPattern({ pattern: Array.from({ length: 16 }, () => new Array(16).fill(false)),
                           patternNotes: Array.from({ length: 16 }, () => new Array(16).fill(null)) });
        }
        const label = document.getElementById("main-seq-name");
        if (label) label.innerText = `Seq 0${state.currentSeq + 1}` + (state.currentSeq === 0 ? " - Main Groove" : " - User");
        flashBtn(btnNextSeq);
        sendHwPacket(ComProtocol.CommandId.NEXT_SEQ, [state.currentSeq]);
        refreshLcd();
    });

    // BACK / UNDO button: back to the main screen.
    document.getElementById("btn-back").addEventListener("click", () => switchView("main"));

    // EXPORT GOLDEN JSON TRACE: download the live state as JSON.
    const btnGolden = document.getElementById("btn-download-golden");
    if (btnGolden) btnGolden.addEventListener("click", () => {
        const trace = { device: "0700-AAM sim", exportedAt: new Date().toISOString(),
            bpm: state.bpm, currentBank: state.currentBank, currentSeq: state.currentSeq,
            pattern: state.pattern, patternNotes: state.patternNotes,
            mixer: state.mixer.map(ch => ({ volume: ch.volume, mute: ch.mute })) };
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" }));
        a.download = "0700-aam-golden-trace.json";
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    });

    // Sample edit: REV / NORM / CROP operate on the last struck pad's
    // actual sample buffer, so the next hit plays the edit.
    const editSample = (el, fn) => {
        if (!el) return;
        el.addEventListener("click", () => {
            const name = audio.samplePads && audio.samplePads[state.lastStruckPad];
            const buf = name && audio.samples && audio.samples[name];
            if (!buf || !audio.ctx) return;
            audio.samples[name] = fn(buf);
            flashBtn(el);
        });
    };
    editSample(document.getElementById("btn-sample-rev"), (buf) => {
        const out = audio.ctx.createBuffer(buf.numberOfChannels, buf.length, buf.sampleRate);
        for (let c = 0; c < buf.numberOfChannels; c++) {
            const d = buf.getChannelData(c).slice();
            d.reverse();
            out.copyToChannel(d, c);
        }
        return out;
    });
    editSample(document.getElementById("btn-sample-norm"), (buf) => {
        let peak = 0;
        for (let c = 0; c < buf.numberOfChannels; c++)
            for (const v of buf.getChannelData(c)) peak = Math.max(peak, Math.abs(v));
        if (!peak) return buf;
        const g = 0.89 / peak;
        const out = audio.ctx.createBuffer(buf.numberOfChannels, buf.length, buf.sampleRate);
        for (let c = 0; c < buf.numberOfChannels; c++) {
            const d = buf.getChannelData(c).slice();
            for (let i = 0; i < d.length; i++) d[i] *= g;
            out.copyToChannel(d, c);
        }
        return out;
    });
    editSample(document.getElementById("btn-sample-crop"), (buf) => {
        const TH = 0.002, PAD = 256;
        let first = buf.length, last = 0;
        for (let c = 0; c < buf.numberOfChannels; c++) {
            const d = buf.getChannelData(c);
            for (let i = 0; i < d.length; i++) if (Math.abs(d[i]) > TH) { if (i < first) first = i; if (i > last) last = i; }
        }
        if (last <= first) return buf;
        first = Math.max(0, first - PAD);
        last = Math.min(buf.length - 1, last + PAD);
        const out = audio.ctx.createBuffer(buf.numberOfChannels, last - first + 1, buf.sampleRate);
        for (let c = 0; c < buf.numberOfChannels; c++)
            out.copyToChannel(buf.getChannelData(c).subarray(first, last + 1), c);
        return out;
    });

    // BROWSE / SAVE: pattern slots in localStorage, in a modal like
    // the keymap's. Save stores the current pattern under a name;
    // Load brings one back onto the machine.
    const browseModal = document.getElementById("modal-browse");
    const browseList = document.getElementById("browse-list");
    const LS_KEY = "aam-pattern-slots-v1";
    const loadSlots = () => { try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; } };
    const storeSlots = (slots) => localStorage.setItem(LS_KEY, JSON.stringify(slots));
    const renderBrowseList = () => {
        const slots = loadSlots();
        browseList.innerHTML = slots.length ? "" : "<p>No saved patterns yet. Name one above and press Save.</p>";
        slots.forEach((slot, i) => {
            const row = document.createElement("div");
            row.className = "browse-row";
            const nm = document.createElement("span");
            nm.textContent = `${slot.name} (${slot.bpm} BPM)`;
            const load = document.createElement("button");
            load.textContent = "Load";
            load.addEventListener("click", () => {
                applyPattern(JSON.parse(JSON.stringify(slot.data)));
                state.bpm = slot.bpm;
                browseModal.classList.add("hidden");
            });
            const del = document.createElement("button");
            del.textContent = "Delete";
            del.addEventListener("click", () => {
                const s2 = loadSlots(); s2.splice(i, 1); storeSlots(s2); renderBrowseList();
            });
            row.append(nm, load, del);
            browseList.appendChild(row);
        });
    };
    document.getElementById("btn-browse").addEventListener("click", () => {
        renderBrowseList();
        browseModal.classList.remove("hidden");
        sendHwPacket(ComProtocol.CommandId.BROWSE, [0x01]);
    });
    document.getElementById("browse-close").addEventListener("click", () => browseModal.classList.add("hidden"));
    document.getElementById("browse-save").addEventListener("click", () => {
        const nameEl = document.getElementById("browse-name");
        const name = (nameEl.value || "").trim() || `Pattern ${loadSlots().length + 1}`;
        const slots = loadSlots();
        slots.push({ name, bpm: state.bpm, data: clonePattern() });
        storeSlots(slots);
        nameEl.value = "";
        renderBrowseList();
    });

    // --- Tap Tempo Engine ---
    const tapTimes = [];
    const tapBtn = document.getElementById("btn-tap-tempo");
    tapBtn.addEventListener("click", () => {
        const now = performance.now();
        tapTimes.push(now);
        if (tapTimes.length > 4) tapTimes.shift();

        if (tapTimes.length >= 2) {
            let totalDiff = 0;
            for (let i = 1; i < tapTimes.length; i++) {
                totalDiff += (tapTimes[i] - tapTimes[i - 1]);
            }
            const avgDiff = totalDiff / (tapTimes.length - 1);
            const calculatedBpm = Math.round(60000 / avgDiff * 10) / 10;
            if (calculatedBpm >= 40 && calculatedBpm <= 280) {
                state.bpm = calculatedBpm;
                document.getElementById("lcd-bpm").innerText = `${state.bpm.toFixed(1)} BPM`;
            }
        }

        tapBtn.classList.add("pressed");
        setTimeout(() => tapBtn.classList.remove("pressed"), 100);
        sendHwPacket(ComProtocol.CommandId.TAP_TEMPO);
    });

    // --- Transport Controls (Rec, Overdub, Stop, Play, Play Start) ---
    const btnRec = document.getElementById("btn-rec");
    const btnOverdub = document.getElementById("btn-overdub");
    const btnStop = document.getElementById("btn-stop");
    const btnPlay = document.getElementById("btn-play");
    const btnPlayStart = document.getElementById("btn-play-start");

    function setTransportState(playing, recording = false, overdubbing = false) {
        state.isPlaying = playing;
        state.isRecording = recording;
        state.isOverdubbing = overdubbing;

        btnPlay.classList.toggle("active", state.isPlaying);
        btnPlayStart.classList.toggle("active", state.isPlaying);
        btnStop.classList.toggle("active", !state.isPlaying);
        btnRec.classList.toggle("active", state.isRecording);
        btnOverdub.classList.toggle("active", state.isOverdubbing);

        // Topbar play control mirrors the transport (firmware AppTopbar).
        const tbPlay = document.getElementById("tb-play");
        if (tbPlay) {
            tbPlay.textContent = state.isPlaying ? "❚❚ PLAYING" : "▶ PLAY";
            tbPlay.classList.toggle("active", state.isPlaying);
        }

        if (state.isPlaying) {
            audio.ensureContext();
            startSequencerClock();
        } else {
            stopSequencerClock();
        }
    }

    btnPlay.addEventListener("click", () => {
        setTransportState(true, state.isRecording, state.isOverdubbing);
        sendHwPacket(ComProtocol.CommandId.PLAY);
    });

    btnPlayStart.addEventListener("click", () => {
        state.currentStep = 0;
        setTransportState(true, state.isRecording, state.isOverdubbing);
        sendHwPacket(ComProtocol.CommandId.PLAY_START);
    });

    btnStop.addEventListener("click", () => {
        setTransportState(false, false, false);
        sendHwPacket(ComProtocol.CommandId.STOP);
    });

    btnRec.addEventListener("click", () => {
        setTransportState(state.isPlaying, !state.isRecording, false);
        sendHwPacket(ComProtocol.CommandId.REC);
    });

    btnOverdub.addEventListener("click", () => {
        setTransportState(state.isPlaying, false, !state.isOverdubbing);
        sendHwPacket(ComProtocol.CommandId.OVERDUB);
    });

    // --- 16-Step Sequencer Engine ---
    let seqInterval = null;

    function startSequencerClock() {
        stopSequencerClock();
        const stepTimeMs = (60000 / state.bpm) / 4; // 16th notes

        seqInterval = setInterval(() => {
            const step = state.currentStep;
            state._stepStartAt = performance.now();
            state._stepDurMs = stepTimeMs;

            // Trigger active pattern steps
            for (let track = 0; track < 16; track++) {
                if (state.pattern[track][step]) {
                    const ch = state.mixer[track];
                    if (!ch.mute) {
                        const pitched = state.patternNotes[track][step];
                        if (pitched != null && audio.samplesReady &&
                            audio.sampleNotes && audio.sampleNotes[track] != null) {
                            // Keygroup notes recorded by overdub: loop them
                            // back at their recorded pitches (chords too).
                            const notes = Array.isArray(pitched) ? pitched : [pitched];
                            notes.forEach(n => audio.schedulePitch(track, n, null, 110 / 127.0));
                            const padEl = padElements[track];
                            if (padEl) {
                                padEl.classList.add("hit");
                                setTimeout(() => padEl.classList.remove("hit"), 120);
                            }
                        } else {
                            triggerPadStrike(track, 110, false, true);
                        }
                        ch.vuLevel = 0.95;
                    }
                }
            }

            // Update LCD step sequencer cursor
            updateStepCursor(step);

            // Update the statusbar playhead readout (BAR : BEAT : TICK,
            // per the firmware's Locate control) + grid playhead + the
            // "now" lines. Defined in the LCD-to-spec section below.
            lcdPlayhead(step);

            // Advance step
            state.currentStep = (state.currentStep + 1) % state.totalSteps;
        }, stepTimeMs);
    }

    function stopSequencerClock() {
        if (seqInterval) {
            clearInterval(seqInterval);
            seqInterval = null;
        }
        updateStepCursor(-1);
        lcdPlayhead(-1);
    }

    function updateStepCursor(currentStep) {
        document.querySelectorAll(".step-btn").forEach(btn => {
            const s = parseInt(btn.dataset.step);
            btn.classList.toggle("current-step", s === currentStep);
        });
    }

    // --- LCD View Tabs & Screen Navigation ---
    const lcdTabs = document.querySelectorAll(".lcd-tab");
    const viewPanels = document.querySelectorAll(".view-panel");

    function switchView(viewId) {
        state.activeView = viewId;
        lcdTabs.forEach(tab => tab.classList.toggle("active", tab.dataset.view === viewId));
        viewPanels.forEach(panel => panel.classList.toggle("active", panel.id === `view-${viewId}`));
        lcdOnView(viewId);
    }

    lcdTabs.forEach(tab => {
        tab.addEventListener("click", () => switchView(tab.dataset.view));
    });

    // Hardware Nav Button Mappings to Screen
    document.getElementById("btn-main").addEventListener("click", () => switchView("main"));
    document.getElementById("btn-step-seq").addEventListener("click", () => switchView("stepseq"));
    document.getElementById("btn-track-mix").addEventListener("click", () => switchView("mixer"));
    document.getElementById("btn-sampler").addEventListener("click", () => switchView("sampler"));
    document.getElementById("btn-sample-edit").addEventListener("click", () => switchView("sampler"));
    document.getElementById("btn-program-edit").addEventListener("click", () => switchView("padedit"));
    document.getElementById("btn-menu").addEventListener("click", () => switchView("menu"));

    // ============================================================
    // LCD presentation, rebuilt to the real 0700-AAM firmware's
    // spec — Music Tribe's open-source Kick app (modules/kick_ui):
    //  * AppTopbar: nav left, project name centre, play/browse/
    //    settings right; tempo is NOT in the chrome (it is a
    //    per-sequence value, shown in Main Mode's Sequence list).
    //  * AppStatusbar: playhead progress line on top, STP
    //    (selected sequence/track/program) left, info box centre,
    //    BAR : BEAT : TICK right (Locate::getBarBeatTickInfo
    //    format: bar : 2-digit beat : 3-digit tick, 960 ppq).
    //  * Main Mode (AppMainmode): Sequence / Track / Program tabs
    //    over lists — no pattern view, no oscilloscope.
    //  * Grid View (AppGrid): piano roll for the selected track —
    //    note-name ruler, note blocks, white playhead line +
    //    triangle, velocity parameter lane underneath.
    //  * Step Sequencer (StepSequencer): ONE track — a note area
    //    with a velocity bar (gradient #FF2A00 -> #FFB608) over a
    //    numbered step button; beat columns shaded differently.
    //  * The oscilloscope is gone from the LCD: in the firmware a
    //    waveform appears only in the Sample Editor and Looper.
    // ============================================================
    let viewTrack = 0; // track shown by Grid View + Step Sequencer
    const PROG_NAMES = ["kick", "snare", "hat_closed", "clap",
        "hook_fs4", "hook_e4", "hook_gs4", "mel_b3", "mel_cs4",
        "mel_d4", "mel_e4", "mel_fs4", "bass_fs1", "bass_e1",
        "bass_gs1", "stab_fsm"]; // samples/manifest.json pad map
    const PROG_ROOTS = { 4: 66, 5: 64, 6: 68, 7: 59, 8: 61, 9: 62,
        10: 64, 11: 66, 12: 42, 13: 40, 14: 44, 15: 54 };
    const progName = (t) => (audio.samplePads && audio.samplePads[t]) || PROG_NAMES[t];
    const progRoot = (t) => (audio.sampleNotes && audio.sampleNotes[t] != null)
        ? audio.sampleNotes[t] : PROG_ROOTS[t];
    const pad2 = (n) => String(n).padStart(2, "0");
    const trackLabel = (t) => `${pad2(t + 1)} · ${audio.instruments[t].name}`;
    const seqName = (i) => `Seq 0${i + 1}` + (i === 0 ? " - Main Groove" : " - User");
    const VIEW_TITLES = { main: "Main Mode", menu: "Menu", grid: "Grid View",
        stepseq: "Step Sequencer", mixer: "Track Mixer", sampler: "Sample Editor",
        padedit: "Program Edit", prefs: "Settings" };

    function setInfo(text) {
        const el = document.getElementById("sb-info");
        if (el) el.textContent = text;
    }

    function renderSTP() {
        const trk = document.getElementById("sb-track-name");
        if (trk) trk.textContent = trackLabel(viewTrack);
        const prg = document.getElementById("sb-prog-name");
        if (prg) prg.textContent = progName(viewTrack);
    }

    // --- Main Mode: Sequence list (columns per AppSequenceComponent:
    // name, bpm, bars, start, end, transpose, loop, global) ---
    function renderSeqRows() {
        const wrap = document.getElementById("mm-seq-rows");
        if (!wrap) return;
        wrap.innerHTML = "";
        for (let i = 0; i < 4; i++) {
            const row = document.createElement("div");
            row.className = "mm-row seq-cols" + (i === state.currentSeq ? " selected" : "");
            const slot = seqSlots[i];
            const bpmCell = i === state.currentSeq
                ? `<span id="lcd-bpm">${state.bpm.toFixed(1)} BPM</span>`
                : `<span>${slot && slot.bpm != null ? slot.bpm.toFixed(1) + " BPM" : "—"}</span>`;
            row.innerHTML = `<span class="mm-name">${seqName(i)}</span>${bpmCell}` +
                `<span>1</span><span>1</span><span>1</span><span>0</span><span>ON</span>` +
                `<span>${i === state.currentSeq ? "ON" : "—"}</span>`;
            row.addEventListener("click", () => selectSequence(i));
            wrap.appendChild(row);
        }
    }

    // Same slot semantics as the NEXT SEQ hardware button: leaving a
    // slot saves it; entering a fresh slot starts empty.
    function selectSequence(i) {
        if (i === state.currentSeq) return;
        seqSlots[state.currentSeq] = { ...clonePattern(), bpm: state.bpm };
        state.currentSeq = i;
        const slot = seqSlots[state.currentSeq];
        if (slot) {
            applyPattern(JSON.parse(JSON.stringify(slot)));
            state.bpm = slot.bpm;
        } else {
            applyPattern({ pattern: Array.from({ length: 16 }, () => new Array(16).fill(false)),
                           patternNotes: Array.from({ length: 16 }, () => new Array(16).fill(null)) });
        }
        const label = document.getElementById("main-seq-name");
        if (label) label.innerText = seqName(i);
        sendHwPacket(ComProtocol.CommandId.NEXT_SEQ, [state.currentSeq]);
        refreshLcd();
    }

    // --- Main Mode: Track list (name, program, length, transpose,
    // mute, solo — mute/solo wired to the mixer state) ---
    function renderTrackRows() {
        const wrap = document.getElementById("mm-track-rows");
        if (!wrap) return;
        wrap.innerHTML = "";
        audio.instruments.forEach((instr, t) => {
            const row = document.createElement("div");
            row.className = "mm-row track-cols" + (t === viewTrack ? " selected" : "");
            row.innerHTML = `<span>${pad2(t + 1)}</span><span class="mm-name">${instr.name}</span>` +
                `<span>${progName(t)}</span><span>16</span><span>0</span>`;
            const mBtn = document.createElement("button");
            mBtn.className = "mm-ms" + (state.mixer[t].mute ? " on-mute" : "");
            mBtn.textContent = "M";
            mBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                state.mixer[t].mute = !state.mixer[t].mute;
                const strip = document.querySelectorAll("#mixer-strips .mixer-strip")[t];
                const mb = strip ? strip.querySelector(".strip-btn.mute") : null;
                if (mb) mb.classList.toggle("active", state.mixer[t].mute);
                renderTrackRows();
            });
            const sBtn = document.createElement("button");
            sBtn.className = "mm-ms" + (state.mixer[t].solo ? " on-solo" : "");
            sBtn.textContent = "S";
            sBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                state.mixer[t].solo = !state.mixer[t].solo;
                const strip = document.querySelectorAll("#mixer-strips .mixer-strip")[t];
                const sb = strip ? strip.querySelector(".strip-btn.solo") : null;
                if (sb) sb.classList.toggle("active", state.mixer[t].solo);
                renderTrackRows();
            });
            row.appendChild(mBtn);
            row.appendChild(sBtn);
            row.addEventListener("click", () => {
                viewTrack = t;
                renderSTP(); renderTrackRows(); renderGrid(); renderStepSeq();
            });
            wrap.appendChild(row);
        });
    }

    // --- Main Mode: Program list (kit programs; types per the
    // firmware's create-program dialog: DRUM / KEY ...) ---
    function renderProgRows() {
        const wrap = document.getElementById("mm-prog-rows");
        if (!wrap) return;
        wrap.innerHTML = "";
        for (let t = 0; t < 16; t++) {
            const row = document.createElement("div");
            row.className = "mm-row prog-cols";
            const root = progRoot(t);
            row.innerHTML = `<span>${pad2(t + 1)}</span><span class="mm-name">${progName(t)}</span>` +
                `<span>${t < 4 ? "DRUM" : "KEY"}</span><span>${root != null ? noteName(root) : "—"}</span>`;
            wrap.appendChild(row);
        }
    }

    // --- Grid View: piano roll for the selected track ---
    function trackPitches(t) {
        const set = new Set();
        for (let s = 0; s < 16; s++) {
            const ns = state.patternNotes[t][s];
            if (state.pattern[t][s] && ns) ns.forEach(n => set.add(n));
        }
        return [...set].sort((a, b) => b - a);
    }

    function renderGrid() {
        const nameEl = document.getElementById("grid-track-name");
        if (nameEl) nameEl.textContent = `TRK ${pad2(viewTrack + 1)} · ${audio.instruments[viewTrack].name.toUpperCase()}`;
        const rowsEl = document.getElementById("grid-rows");
        if (!rowsEl) return;
        rowsEl.innerHTML = "";
        const t = viewTrack;
        const pitches = trackPitches(t);
        const hasUnpitched = state.pattern[t].some((on, s) => on && !(state.patternNotes[t][s] && state.patternNotes[t][s].length));
        const mkRow = (label, note) => { // note === null: unpitched-hit row
            const row = document.createElement("div");
            row.className = "grid-row";
            const ruler = document.createElement("div");
            ruler.className = "grid-ruler";
            ruler.textContent = label;
            row.appendChild(ruler);
            const cells = document.createElement("div");
            cells.className = "grid-cells";
            for (let s = 0; s < 16; s++) {
                const cell = document.createElement("div");
                cell.className = "grid-cell" + (s % 4 === 0 ? " beat" : "");
                const ns = state.patternNotes[t][s];
                const has = !!state.pattern[t][s] && (note === null
                    ? !(ns && ns.length)
                    : !!(ns && ns.includes(note)));
                if (has) {
                    const block = document.createElement("div");
                    block.className = "grid-block";
                    if (note !== null) block.textContent = noteName(note);
                    cell.appendChild(block);
                }
                cell.addEventListener("click", () => {
                    if (note === null) {
                        state.pattern[t][s] = !state.pattern[t][s];
                        if (!state.pattern[t][s]) state.patternNotes[t][s] = null;
                        if (state.pattern[t][s]) audio.triggerPad(t, 100);
                    } else {
                        const cur = state.pattern[t][s] && state.patternNotes[t][s]
                            ? [...state.patternNotes[t][s]] : [];
                        const at = cur.indexOf(note);
                        if (at >= 0) {
                            cur.splice(at, 1);
                            if (cur.length) state.patternNotes[t][s] = cur;
                            else { state.pattern[t][s] = false; state.patternNotes[t][s] = null; }
                        } else {
                            cur.push(note);
                            state.pattern[t][s] = true;
                            state.patternNotes[t][s] = cur.sort((a, b) => a - b);
                            audio.triggerPad(t, 100);
                        }
                    }
                    renderGrid(); renderStepSeq(); refreshStepGrid();
                });
                cells.appendChild(cell);
            }
            row.appendChild(cells);
            rowsEl.appendChild(row);
        };
        pitches.forEach(n => mkRow(noteName(n), n));
        if (hasUnpitched || pitches.length === 0) {
            mkRow(pitches.length === 0 ? audio.instruments[t].name : "HIT", null);
        }
        if (pitches.length === 0 && !hasUnpitched) {
            const empty = document.createElement("div");
            empty.className = "grid-empty";
            empty.textContent = "No notes in this track — click a cell to add a hit, or strike the pad with REC / OVERDUB.";
            rowsEl.appendChild(empty);
        }
        // Velocity parameter lane (pattern steps play at velocity 110).
        const lane = document.getElementById("grid-lane-bars");
        if (lane) {
            lane.innerHTML = "";
            for (let s = 0; s < 16; s++) {
                const bar = document.createElement("div");
                bar.className = "lane-bar";
                bar.style.height = state.pattern[t][s] ? `${(110 / 127) * 100}%` : "0%";
                lane.appendChild(bar);
            }
        }
    }

    // --- Step Sequencer: one track, velocity bars over step buttons ---
    function renderStepSeq() {
        const grid = document.getElementById("stepseq-grid");
        if (!grid) return;
        grid.innerHTML = "";
        const t = viewTrack;
        for (let s = 0; s < 16; s++) {
            const col = document.createElement("div");
            col.className = "ss-col";
            const area = document.createElement("div");
            area.className = "ss-note-area " + (s % 4 === 0 ? "on-beat" : "off-beat");
            if (state.pattern[t][s]) {
                const bar = document.createElement("div");
                bar.className = "ss-vel-bar";
                bar.style.height = `${(110 / 127) * 100}%`;
                area.appendChild(bar);
                const ns = state.patternNotes[t][s];
                if (ns && ns.length) {
                    const lab = document.createElement("div");
                    lab.className = "ss-note-label";
                    lab.textContent = [...ns].sort((a, b) => a - b).map(noteName).join(" ");
                    area.appendChild(lab);
                }
            }
            const btn = document.createElement("div");
            btn.className = "step-btn" + (s % 4 === 0 ? " group-beat" : "");
            btn.dataset.track = t;
            btn.dataset.step = s;
            btn.textContent = s + 1;
            if (state.pattern[t][s]) btn.classList.add("active");
            const toggle = () => {
                state.pattern[t][s] = !state.pattern[t][s];
                // Clearing a step clears its notes too — otherwise the
                // old pitches sound again if the step is reactivated.
                if (!state.pattern[t][s]) state.patternNotes[t][s] = null;
                if (state.pattern[t][s]) audio.triggerPad(t, 100);
                renderStepSeq(); renderGrid();
                if (state.isPlaying) lcdPlayhead(state.currentStep);
            };
            btn.addEventListener("click", toggle);
            area.addEventListener("click", toggle);
            col.appendChild(area);
            col.appendChild(btn);
            grid.appendChild(col);
        }
    }

    function refreshLcd() {
        renderSTP(); renderSeqRows(); renderTrackRows();
        renderProgRows(); renderGrid(); renderStepSeq();
    }

    function lcdOnView(viewId) {
        setInfo(VIEW_TITLES[viewId] || "");
        refreshLcd();
    }

    // A user pad strike selects that pad's track on the LCD
    // (the sim's lastStruckPad semantics, made visible).
    function lcdFollowPad(padIndex) {
        viewTrack = padIndex;
        renderSTP(); renderGrid(); renderStepSeq(); renderTrackRows();
    }

    // Playhead readout, driven by the sequencer clock (not a free
    // animation). step < 0 = stopped.
    function lcdPlayhead(step) {
        const bbt = document.getElementById("sb-bbt-val");
        const fill = document.getElementById("sb-progress-fill");
        const ph = document.getElementById("grid-playhead");
        if (step < 0) {
            if (fill) fill.style.width = "0%";
            if (ph) ph.style.display = "none";
            const gn = document.getElementById("grid-now");
            if (gn) gn.textContent = "STEP -- · —";
            const sn = document.getElementById("ss-now");
            if (sn) sn.textContent = "STEP -- · —";
            if (!state.isPlaying) setInfo(VIEW_TITLES[state.activeView] || "");
            return;
        }
        const beat = Math.floor(step / 4) + 1;
        const tick = (step % 4) * 240; // 960 ppq, 4 steps per beat
        if (bbt) bbt.textContent = `1 : ${pad2(beat)} : ${String(tick).padStart(3, "0")}`;
        if (fill) fill.style.width = `${((step + 1) / state.totalSteps) * 100}%`;
        if (ph) {
            ph.style.display = "block";
            // Offset past the note-name ruler column (64px, --ruler-w).
            ph.style.left = `calc(64px + (100% - 64px) * ${step / 16})`;
            ph.style.width = `calc((100% - 64px) / 16)`;
        }
        // "Now" text: everything sounding on this step, and the
        // selected track's own line for the Grid / Step Seq views.
        const sounding = [];
        let trackNow = "—";
        for (let t = 0; t < 16; t++) {
            if (!state.pattern[t][step] || state.mixer[t].mute) continue;
            const ns = state.patternNotes[t][step];
            const txt = ns && ns.length
                ? [...ns].sort((a, b) => a - b).map(noteName).join(" ")
                : audio.instruments[t].name;
            sounding.push(txt);
            if (t === viewTrack) trackNow = txt;
        }
        setInfo(sounding.length ? sounding.join(" · ") : "—");
        const nowText = `STEP ${pad2(step + 1)} · ${trackNow}`;
        const gn = document.getElementById("grid-now");
        if (gn) gn.textContent = nowText;
        const sn = document.getElementById("ss-now");
        if (sn) sn.textContent = nowText;
    }

    // --- LCD wiring: topbar, menu, tabs, track selectors ---
    document.getElementById("tb-play").addEventListener("click", () => {
        setTransportState(!state.isPlaying, state.isRecording, state.isOverdubbing);
    });
    document.getElementById("tb-browse").addEventListener("click", () => {
        document.getElementById("btn-browse").click();
    });
    const menuBrowse = document.getElementById("menu-browse");
    if (menuBrowse) menuBrowse.addEventListener("click", () => {
        document.getElementById("btn-browse").click();
    });
    document.querySelectorAll("[data-nav]").forEach(el => {
        el.addEventListener("click", () => switchView(el.dataset.nav));
    });
    document.querySelectorAll(".mm-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".mm-tab").forEach(x => x.classList.toggle("active", x === tab));
            ["seq", "track", "program"].forEach(k => {
                const pane = document.getElementById(`mm-pane-${k}`);
                if (pane) pane.classList.toggle("hidden", k !== tab.dataset.mmtab);
            });
        });
    });
    const mmDel = document.getElementById("mm-del-seq");
    if (mmDel) mmDel.addEventListener("click", () => {
        seqSlots[state.currentSeq] = null;
        applyPattern({ pattern: Array.from({ length: 16 }, () => new Array(16).fill(false)),
                       patternNotes: Array.from({ length: 16 }, () => new Array(16).fill(null)) });
        setInfo(`Sequence cleared — ${seqName(state.currentSeq)}`);
    });
    const cycleTrack = (d) => {
        viewTrack = (viewTrack + 16 + d) % 16;
        const tag = document.getElementById("stepseq-inst-name");
        if (tag) tag.innerText = `Pad ${viewTrack + 1}: ${audio.instruments[viewTrack].name}`;
        renderSTP(); renderGrid(); renderStepSeq(); renderTrackRows();
    };
    document.getElementById("grid-track-prev").addEventListener("click", () => cycleTrack(-1));
    document.getElementById("grid-track-next").addEventListener("click", () => cycleTrack(1));
    document.getElementById("ss-track-prev").addEventListener("click", () => cycleTrack(-1));
    document.getElementById("ss-track-next").addEventListener("click", () => cycleTrack(1));

    refreshLcd();

    // Step Sequencer Toolbar Actions
    document.getElementById("btn-clear-seq").addEventListener("click", () => {
        for (let t = 0; t < 16; t++) {
            for (let s = 0; s < 16; s++) {
                state.pattern[t][s] = false;
                state.patternNotes[t][s] = null;
            }
        }
        document.querySelectorAll(".step-btn").forEach(btn => btn.classList.remove("active"));
        refreshLcd();
    });

    document.getElementById("btn-random-seq").addEventListener("click", () => {
        for (let t = 0; t < 16; t++) {
            for (let s = 0; s < 16; s++) {
                const prob = t === 0 ? 0.35 : (t === 2 ? 0.65 : 0.15);
                state.pattern[t][s] = Math.random() < prob;
            }
        }
        document.querySelectorAll(".step-btn").forEach(btn => {
            const t = parseInt(btn.dataset.track);
            const s = parseInt(btn.dataset.step);
            btn.classList.toggle("active", state.pattern[t][s]);
        });
        refreshLcd();
    });

    // --- Build 16-Channel Mixer in Mixer View ---
    const mixerStripsContainer = document.getElementById("mixer-strips");
    if (mixerStripsContainer) {
        audio.instruments.forEach((instr, idx) => {
            const strip = document.createElement("div");
            strip.className = "mixer-strip";

            strip.innerHTML = `
                <div class="mixer-strip-title">P${idx + 1}</div>
                <div class="vu-meter-bar"><div class="vu-fill" id="vu-${idx}"></div></div>
                <div class="fader-track">
                    <input type="range" class="fader-slider" min="0" max="100" value="85" orient="vertical">
                </div>
                <div class="strip-mute-solo">
                    <button class="strip-btn mute" id="mute-${idx}">M</button>
                    <button class="strip-btn solo" id="solo-${idx}">S</button>
                </div>
            `;

            const fader = strip.querySelector(".fader-slider");
            fader.addEventListener("input", (e) => {
                state.mixer[idx].volume = parseFloat(e.target.value) / 100.0;
            });

            const muteBtn = strip.querySelector(".strip-btn.mute");
            muteBtn.addEventListener("click", () => {
                state.mixer[idx].mute = !state.mixer[idx].mute;
                muteBtn.classList.toggle("active", state.mixer[idx].mute);
            });

            const soloBtn = strip.querySelector(".strip-btn.solo");
            soloBtn.addEventListener("click", () => {
                state.mixer[idx].solo = !state.mixer[idx].solo;
                soloBtn.classList.toggle("active", state.mixer[idx].solo);
            });

            mixerStripsContainer.appendChild(strip);
        });
    }

    // --- Mixer VU decay loop ---
    // (The old main-view oscilloscope is removed: in the real
    // firmware no screen shows a scope — a waveform appears only
    // in the Sample Editor and the Looper.)
    function renderMeters() {
        requestAnimationFrame(renderMeters);

        // Update Mixer VU Fills
        for (let i = 0; i < 16; i++) {
            const ch = state.mixer[i];
            ch.vuLevel = Math.max(0, ch.vuLevel - 0.04);
            const vuEl = document.getElementById(`vu-${i}`);
            if (vuEl) vuEl.style.height = `${ch.vuLevel * 100}%`;
        }
    }
    renderMeters();

    // --- Sampler Waveform Drawing ---
    const samplerCanvas = document.getElementById("sampler-canvas");
    if (samplerCanvas) {
        const sCtx = samplerCanvas.getContext("2d");
        sCtx.fillStyle = "#151515";
        sCtx.fillRect(0, 0, samplerCanvas.width, samplerCanvas.height);

        // Draw synthetic drum waveform sample (firmware WAVEFORM_1 blue)
        sCtx.strokeStyle = "#00aaee";
        sCtx.lineWidth = 2;
        sCtx.beginPath();
        const midY = samplerCanvas.height / 2;
        sCtx.moveTo(0, midY);

        for (let x = 0; x < samplerCanvas.width; x++) {
            const progress = x / samplerCanvas.width;
            const env = Math.exp(-progress * 5.0);
            const freq = 60 - progress * 40;
            const wave = Math.sin(progress * freq * Math.PI * 2) * env;
            sCtx.lineTo(x, midY + wave * (midY - 15));
        }
        sCtx.stroke();
    }

    // --- Keyboard Shortcut Bindings ---
    const keyToPad = {
        "z": 0, "x": 1, "c": 2, "v": 3,
        "a": 4, "s": 5, "d": 6, "f": 7,
        "q": 8, "w": 9, "e": 10, "r": 11,
        "1": 12, "2": 13, "3": 14, "4": 15
    };

    window.addEventListener("keydown", (e) => {
        // Ignore if user is inside an input field
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

        const key = e.key.toLowerCase();

        // 16 Pads
        if (keyToPad[key] !== undefined) {
            triggerPadStrike(keyToPad[key], 120, true);
            return;
        }

        // Space = Play / Stop
        if (e.code === "Space") {
            e.preventDefault();
            setTransportState(!state.isPlaying);
            return;
        }

        // Banks (Capital letters)
        if (e.key === "A") selectBank(0);
        else if (e.key === "B") selectBank(1);
        else if (e.key === "C") selectBank(2);
        else if (e.key === "D") selectBank(3);

        // Jog Wheel: [ / Left / Down = CCW, ] / Right / Up = CW, Enter = Click
        if (e.key === "[" || e.key === "ArrowDown" || e.key === "ArrowLeft") { e.preventDefault(); rotateJogWheel(-15); }
        else if (e.key === "]" || e.key === "ArrowUp" || e.key === "ArrowRight") { e.preventDefault(); rotateJogWheel(15); }
        else if (e.key === "Enter") jogCenterBtn.click();
        else if (e.key === "-" || e.key === "_") { e.preventDefault(); document.getElementById("btn-minus").click(); }
        else if (e.key === "+" || e.key === "=") { e.preventDefault(); document.getElementById("btn-plus").click(); }
        else if (e.key === "Backspace") { e.preventDefault(); document.getElementById("btn-back").click(); }

        // Touch Strip: T
        if (key === "t") setTouchStrip(Math.random());
    });

    // --- Key Map Modal & Fullscreen ---
    const keyMapModal = document.getElementById("modal-keymap");
    document.getElementById("btn-toggle-keys").addEventListener("click", () => {
        keyMapModal.classList.toggle("hidden");
    });
    document.getElementById("modal-close").addEventListener("click", () => {
        keyMapModal.classList.add("hidden");
    });

    document.getElementById("btn-fullscreen").addEventListener("click", () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    });

    document.getElementById("btn-reconnect-ws").addEventListener("click", () => {
        connectWebSocket();
    });

    // --- Initialize ---
    selectBank(0);
    connectWebSocket();

    // --- Learner panel (LoopProof): check my result / export / start
    // links. Lives below the device with the output strip; the
    // hardware face is untouched. Reference states ship in
    // references.js (generated by tools/gen_references.py from the
    // v5 capture pattern.json files).
    //
    // State formats:
    //  * Export format (the download): the full snapshot —
    //    {format:"loopproof-state", version:1, song, bpm,
    //     pattern: 16x16 bool, patternNotes: 16x16 (note array|null)}.
    //  * Link format (the #s= hash): compact —
    //    base64url(UTF-8 JSON {v:1, bpm, cells:{"track,step":[notes]}})
    //    where [] means an unpitched hit and absent means empty.
    //    lpDecode accepts both formats.
    const LP_TRACK_LABELS = ["Kick", "Snare", "Closed hat", "Clap",
        "Hook F#4", "Hook E4", "Hook G#4", "Melodic B3", "Melodic C#4",
        "Melodic D4", "Melodic E4", "Melodic F#4", "Bass F#1", "Bass E1",
        "Bass G#1", "Stab"];
    const lpRefs = window.LOOPPROOF_REFERENCES || null;
    const lpSnapshot = () => JSON.parse(JSON.stringify({
        bpm: state.bpm, pattern: state.pattern,
        patternNotes: state.patternNotes }));
    const lpApply = (snap) => {
        state.bpm = snap.bpm;
        applyPattern(JSON.parse(JSON.stringify({
            pattern: snap.pattern, patternNotes: snap.patternNotes })));
        const lcd = document.getElementById("lcd-bpm");
        if (lcd) lcd.innerText = `${state.bpm.toFixed(1)} BPM`;
    };
    const lpEncode = (snap) => {
        const cells = {};
        for (let t = 0; t < 16; t++) for (let s = 0; s < 16; s++) {
            if (snap.pattern[t][s]) {
                const ns = snap.patternNotes[t][s];
                cells[`${t},${s}`] = ns ? [...ns].sort((a, b) => a - b) : [];
            }
        }
        const json = JSON.stringify({ v: 1, bpm: Math.round(snap.bpm * 10) / 10, cells });
        const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(json)));
        return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    };
    const lpDecode = (str) => {
        const b64 = str.replace(/-/g, "+").replace(/_/g, "/");
        const json = new TextDecoder().decode(
            Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
        const data = JSON.parse(json);
        if (data.pattern && data.patternNotes) {  // full export format
            return { bpm: data.bpm ?? 120, pattern: data.pattern,
                     patternNotes: data.patternNotes };
        }
        const snap = { bpm: data.bpm ?? 120,
            pattern: Array.from({ length: 16 }, () => new Array(16).fill(false)),
            patternNotes: Array.from({ length: 16 }, () => new Array(16).fill(null)) };
        for (const [key, ns] of Object.entries(data.cells || {})) {
            const [t, s] = key.split(",").map(Number);
            snap.pattern[t][s] = true;
            snap.patternNotes[t][s] = ns && ns.length ? [...ns] : null;
        }
        return snap;
    };
    const lpCellText = (snap, t, s) => {
        if (!snap.pattern[t][s]) return "nothing";
        const ns = snap.patternNotes[t][s];
        if (!ns || !ns.length) return "a hit (no pitch)";
        return [...ns].sort((a, b) => a - b).map(noteName).join("–");
    };
    const lpDiff = (mine, ref) => {
        const diffs = [];
        let match = 0;
        for (let t = 0; t < 16; t++) for (let s = 0; s < 16; s++) {
            const a = mine.pattern[t][s], b = ref.pattern[t][s];
            const an = a && mine.patternNotes[t][s] ? [...mine.patternNotes[t][s]].sort((x, y) => x - y) : [];
            const bn = b && ref.patternNotes[t][s] ? [...ref.patternNotes[t][s]].sort((x, y) => x - y) : [];
            if (a === b && JSON.stringify(an) === JSON.stringify(bn)) { match++; continue; }
            diffs.push({ track: t, step: s, mine: lpCellText(mine, t, s),
                         ref: lpCellText(ref, t, s) });
        }
        return { match, total: 256, diffs };
    };
    const lpSongSel = document.getElementById("lp-song");
    const lpResult = document.getElementById("lp-result");
    const lpStarts = document.getElementById("lp-starts");
    const lpTrackLabel = (slug, t) => {
        const role = lpRefs && lpRefs[slug] && lpRefs[slug].roles
            ? lpRefs[slug].roles[String(t)] : null;
        return `track ${t + 1} (${role || LP_TRACK_LABELS[t]})`;
    };
    const lpRenderStarts = () => {
        if (!lpRefs || !lpStarts || !lpSongSel) return;
        const song = lpRefs[lpSongSel.value];
        lpStarts.innerHTML = "";
        const mk = (label, snap) => {
            const a = document.createElement("a");
            a.href = "#s=" + lpEncode(snap);
            a.textContent = label;
            lpStarts.appendChild(a);
        };
        for (const st of song.starts) mk(st.label, st.state);
        mk("Finished loop (the goal)", song.reference);
    };
    const lpRunCheck = () => {
        if (!lpRefs || !lpSongSel || !lpResult) return null;
        const slug = lpSongSel.value;
        const song = lpRefs[slug];
        const mine = lpSnapshot();
        const res = lpDiff(mine, song.reference);
        lpResult.innerHTML = "";
        const verdict = document.createElement("div");
        verdict.className = "lp-verdict " + (res.diffs.length ? "bad" : "ok");
        verdict.textContent = res.diffs.length
            ? `${res.match}/${res.total} steps match — ${res.diffs.length} difference${res.diffs.length === 1 ? "" : "s"} to fix:`
            : `✓ ${res.match}/${res.total} steps match — this is the reference state. Proven.`;
        lpResult.appendChild(verdict);
        if (Math.abs(mine.bpm - song.reference.bpm) > 1) {
            const tempo = document.createElement("div");
            tempo.textContent = `Tempo check: the reference runs at ${song.reference.bpm} BPM; yours is set to ${Math.round(mine.bpm * 10) / 10} BPM.`;
            lpResult.appendChild(tempo);
        }
        if (res.diffs.length) {
            const ul = document.createElement("ul");
            for (const d of res.diffs.slice(0, 60)) {
                const li = document.createElement("li");
                li.textContent = d.mine === "nothing"
                    ? `Step ${d.step + 1} · ${lpTrackLabel(slug, d.track)} — missing: the reference has ${d.ref}, your loop has nothing there.`
                    : d.ref === "nothing"
                        ? `Step ${d.step + 1} · ${lpTrackLabel(slug, d.track)} — extra: your loop has ${d.mine}, the reference has nothing there.`
                        : `Step ${d.step + 1} · ${lpTrackLabel(slug, d.track)} — notes differ: the reference has ${d.ref}, your loop has ${d.mine}.`;
                ul.appendChild(li);
            }
            if (res.diffs.length > 60) {
                const li = document.createElement("li");
                li.textContent = `…and ${res.diffs.length - 60} more.`;
                ul.appendChild(li);
            }
            lpResult.appendChild(ul);
        }
        return res;
    };
    const lpApplyHash = () => {
        if (!location.hash.startsWith("#s=")) return false;
        try {
            lpApply(lpDecode(location.hash.slice(3)));
            if (lpResult) {
                lpResult.innerHTML = "";
                const note = document.createElement("div");
                note.className = "lp-verdict ok";
                note.textContent = "Loaded a start state from the link — build from here, then check your result.";
                lpResult.appendChild(note);
            }
            return true;
        } catch (e) { return false; }
    };
    if (lpRefs && lpSongSel) {
        for (const [slug, song] of Object.entries(lpRefs)) {
            const opt = document.createElement("option");
            opt.value = slug;
            opt.textContent = song.title;
            lpSongSel.appendChild(opt);
        }
        lpSongSel.addEventListener("change", lpRenderStarts);
        lpRenderStarts();
        document.getElementById("lp-check").addEventListener("click", lpRunCheck);
        document.getElementById("lp-export").addEventListener("click", () => {
            const slug = lpSongSel.value;
            const data = { format: "loopproof-state", version: 1, song: slug,
                exportedFrom: "0700-AAM simulator (LoopProof learner panel)",
                ...lpSnapshot() };
            const blob = new Blob([JSON.stringify(data, null, 1)],
                { type: "application/json" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `loopproof-state-${slug}.json`;
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 4000);
        });
        document.getElementById("lp-copylink").addEventListener("click", async (ev) => {
            const url = location.origin + location.pathname + "#s=" + lpEncode(lpSnapshot());
            try { await navigator.clipboard.writeText(url); }
            catch (e) { window.prompt("Copy this link:", url); }
            const btn = ev.currentTarget;
            const old = btn.textContent;
            btn.textContent = "Link copied ✓";
            setTimeout(() => { btn.textContent = old; }, 1600);
        });
        window.addEventListener("hashchange", lpApplyHash);
        lpApplyHash();
    } else {
        const panel = document.getElementById("learner-panel");
        if (panel) panel.style.display = "none";
    }
    window.__loopproof = { snapshot: lpSnapshot, apply: lpApply,
        encode: lpEncode, decode: lpDecode, diff: lpDiff, check: lpRunCheck };

    // ============================================================
    // Guide layer — page-level learning overlays. Neither feature
    // is part of the hardware face or the LCD: both float above the
    // page, never block or delay a press, and the sim stays live
    // underneath them.
    //   1) Hover help: a themed tooltip explains every control.
    //   2) "Get to know the device": a guided tour that spotlights
    //      one control at a time with a dialog card.
    // ============================================================

    // --- 1) Hover help ------------------------------------------
    // One short sentence per control, in the device's own terms.
    const GUIDE_HELP_BY_ID = {
        // Transport
        "btn-play": "PLAY — starts the 16-step loop playing.",
        "btn-play-start": "PLAY START — restarts the loop from step 1 and plays.",
        "btn-stop": "STOP — stops playback and any recording.",
        "btn-rec": "REC — arms recording: with the loop playing, every strike is written into the loop at the step that's playing. REC captures the first pass.",
        "btn-overdub": "OVERDUB — layers new strikes into the playing loop without erasing what's already there. Chords over drums, bass over chords: this is how layers are added.",
        // Tempo & timing
        "btn-tap-tempo": "TAP TEMPO — tap steadily to set the tempo; the display shows the BPM your taps settle on.",
        "btn-tc": "TC (Timing Correct) — on, strikes are written into the step that's playing; off, into the nearest step.",
        // Pads & levels
        "btn-full-level": "FULL LEVEL — on, every pad strike plays at full velocity; off, velocity follows where on the pad you hit (lower = harder).",
        "btn-16-level": "16 LEVEL — keygroups: strike a melodic pad, press 16 LEVEL, and all 16 pads play that one sound at 16 pitches (pad 5 plays its root note).",
        "btn-erase": "ERASE — clears the last struck pad's row from the pattern.",
        // Banks
        "btn-bank-a": "BANK A — the pads play bank A. Hold SHIFT for bank E.",
        "btn-bank-b": "BANK B — the pads play bank B. Hold SHIFT for bank F.",
        "btn-bank-c": "BANK C — the pads play bank C. Hold SHIFT for bank G.",
        "btn-bank-d": "BANK D — the pads play bank D. Hold SHIFT for bank H.",
        // Mode / view buttons
        "btn-main": "MAIN — switches the screen to Main Mode: sequences, tracks and programs in lists.",
        "btn-step-seq": "STEP SEQ — the step sequencer: click steps on and off to program the selected track's rhythm.",
        "btn-track-mix": "TRACK MIX — the Track Mixer: a fader, mute and solo for every track.",
        "btn-sampler": "SAMPLER — the Sample Editor: the last struck sound's waveform, ready to edit.",
        "btn-sample-edit": "SAMPLE EDIT — the Sample Editor: reverse, normalize or trim the last struck sound.",
        "btn-program-edit": "PROG EDIT — Program Edit: shape the selected sound — filter, envelope, tuning, velocity.",
        "btn-menu": "MENU — the mode menu on the screen: every view the device offers.",
        "btn-browse": "BROWSE — the pattern slots: save the current pattern under a name, or load one back. Slots live in this browser.",
        "btn-track-mute": "TRACK MUTE — mutes the last struck pad's track; press again to unmute.",
        "btn-next-seq": "NEXT SEQ — moves to the next of the four sequence slots; each slot keeps its own pattern.",
        // Jog cluster
        "btn-note-repeat": "NOTE REPEAT — while on, the last struck pad re-triggers in time until you switch it off.",
        "btn-back": "BACK — returns the screen to Main Mode.",
        "btn-copy": "COPY — copies the current pattern. SHIFT + COPY pastes it back.",
        "btn-plus": "+ — nudges the selected value up (the jog wheel's step button).",
        "btn-minus": "− — nudges the selected value down (the jog wheel's step button).",
        "btn-shift": "SHIFT — hold to reach the buttons' second labels: banks E–H, SAVE, PASTE and more.",
        "jog-wheel": "The data wheel — drag it, scroll over it, or use − / + to change the selected value.",
        "jog-center-btn": "ENTER — the jog wheel's push button: confirms the current selection.",
        // Knobs, Q-Links, touch strip
        "knob-master": "MASTER — the master volume knob. It and the OUTPUT strip below the device drive the same level.",
        "knob-rec": "REC GAIN — how hot the sampler records incoming audio.",
        "qlink-1": "Q1 CUTOFF — the filter cutoff for the selected sound. Drag up or down.",
        "qlink-2": "Q2 RESONANCE — the filter resonance (the peak at the cutoff) for the selected sound.",
        "qlink-3": "Q3 DECAY — how long the selected sound rings after a strike.",
        "qlink-4": "Q4 TUNING — the selected sound's tuning, in semitones.",
        "touch-strip": "TOUCH STRIP — drag along it to bend the pitch of what plays.",
        // LCD top bar & in-screen controls
        "tb-play": "PLAY on the screen's top bar — starts and stops the loop, same as the PLAY button.",
        "tb-browse": "BROWSE on the screen's top bar — the pattern slots, same as the BROWSE button.",
        "mm-del-seq": "DELETE — clears the selected sequence's pattern.",
        "menu-browse": "File Browser — save and load patterns in this browser's slots.",
        "grid-track-prev": "Previous track — show the track above in the Grid.",
        "grid-track-next": "Next track — show the track below in the Grid.",
        "ss-track-prev": "Previous track — program the track above in the step sequencer.",
        "ss-track-next": "Next track — program the track below in the step sequencer.",
        "btn-clear-seq": "CLEAR — wipes the pattern in the step sequencer.",
        "btn-random-seq": "RANDOMIZE — deals a random pattern in the step sequencer. Undo it with CLEAR and your own clicks.",
        "btn-sample-rev": "REVERSE — plays the sample backwards (edits the last struck sound).",
        "btn-sample-norm": "NORMALIZE — raises the sample to full level without clipping.",
        "btn-sample-crop": "TRIM — crops the sample to its sounding part.",
        "param-cutoff": "Cutoff Frequency — where the filter starts closing; lower is darker.",
        "param-res": "Resonance (Q) — how much the filter emphasises its cutoff point.",
        "param-atk": "Attack Time — how quickly the sound reaches full level after a strike.",
        "param-decay": "Decay Multiplier — stretches or shortens how long the sound rings.",
        "param-tune": "Semitone Tune — shifts the sound's pitch in semitones.",
        "param-vel-sens": "Velocity Sensitivity — how much your strike strength changes the volume.",
        "btn-reconnect-ws": "RECONNECT WEBSOCKET — re-links the harness to a hardware bridge, if one is running.",
        "btn-download-golden": "EXPORT GOLDEN JSON TRACE — downloads a trace of the hardware-protocol traffic for debugging.",
        // Page chrome
        "btn-sales-video": "Watch the 4K showcase and hardware walkthrough on YouTube.",
        "btn-toggle-keys": "KEY MAP — the keyboard shortcuts that play this device from a computer keyboard.",
        "btn-fullscreen": "EXPAND — toggles fullscreen.",
        "modal-close": "Close this panel.",
        // Output strip & learner panel
        "output-volume": "OUTPUT — the master volume slider. It and the MASTER knob drive the same level; the meter shows the live output.",
        "lp-song": "The tutorial song you're following — its reference state is what Check compares against.",
        "lp-check": "Check my result — compares your loop, step by step, against the tutorial's reference state.",
        "lp-export": "Export my state — downloads your current loop as a file you can keep or share.",
        "lp-copylink": "Copy link to my state — a link that reloads the simulator with your loop loaded.",
        "btn-guided-tour": "A short guided tour: the machine's main controls, one at a time, in the order you'd use them.",
        // Browse modal
        "browse-close": "Close the pattern browser.",
        "browse-name": "Name for the pattern you're about to save.",
        "browse-save": "Save the current pattern into a slot in this browser.",
    };

    // Help for generated / class-based controls (pads, step buttons,
    // LCD tabs, mixer parts, browse rows…). Checked in order.
    const GUIDE_HELP_RULES = [
        [(el) => el.closest(".pad"), (el) => {
            const pad = el.closest(".pad");
            const name = (pad.querySelector(".pad-name") || {}).textContent || "sound";
            return `Pad ${pad.dataset.pad} — ${name.trim()}: strike to play it. Lower on the pad = harder hit. While the loop plays with REC or OVERDUB lit, the strike is captured into the loop at the current step.`;
        }],
        [(el) => el.closest(".step-btn"), (el) => {
            const b = el.closest(".step-btn");
            return `Step ${Number(b.dataset.step) + 1} — click to toggle this step on or off for the track shown. Lit steps sound in the loop.`;
        }],
        [(el) => el.closest(".ss-note-area"), (el) => {
            const col = el.closest(".ss-col");
            const b = col && col.querySelector(".step-btn");
            const s = b ? `Step ${Number(b.dataset.step) + 1}'s` : "This step's";
            return `${s} note area — the bar shows the step's velocity. Click to toggle the step.`;
        }],
        [(el) => el.closest(".grid-cell"), () =>
            "A cell in the Grid piano roll — click to add or clear a note for the selected track at this step. Amber blocks are notes in the loop."],
        [(el) => el.closest(".fader-slider"), () =>
            "Track fader — drag to set this track's volume in the mix."],
        [(el) => el.closest(".strip-btn.mute"), () =>
            "M — mute this track in the mixer."],
        [(el) => el.closest(".strip-btn.solo"), () =>
            "S — solo this track: hear it on its own."],
        [(el) => el.closest(".mm-ms"), (el) =>
            (el.closest(".mm-ms").textContent || "").trim().startsWith("S")
                ? "S — solo this track: hear it on its own."
                : "M — mute this track."],
        [(el) => el.closest(".mm-tab"), (el) => ({
            seq: "Sequence — the four sequence slots and their settings; click a row to select a sequence.",
            track: "Track — the 16 tracks with their programs, lengths, mute and solo.",
            program: "Program — the sounds loaded across the 16 pads.",
        })[el.closest(".mm-tab").dataset.mmtab] || "A Main Mode list."],
        [(el) => el.closest(".lcd-tab"), (el) => ({
            menu: "MENU — the mode menu: every screen the device offers.",
            main: "MAIN — Main Mode: sequences, tracks and programs in lists.",
            grid: "GRID — the piano roll: the selected track's notes as blocks, with the playhead sweeping. Click cells to edit.",
            stepseq: "STEP SEQ — the step sequencer for the selected track.",
            prefs: "SETTINGS — device information and harness details.",
        })[el.closest(".lcd-tab").dataset.view] || "Switches the screen."],
        [(el) => el.closest(".menu-item"), (el) => {
            const it = el.closest(".menu-item");
            if (it.id === "menu-browse") return GUIDE_HELP_BY_ID["menu-browse"];
            return ({
                main: "Main Mode — sequences, tracks and programs in lists.",
                grid: "Grid View — the piano roll for the selected track.",
                stepseq: "Step Sequencer — click steps on and off, one track at a time.",
                mixer: "Track Mixer — a fader, mute and solo for every track.",
                sampler: "Sample Editor — the selected sound's waveform and edits.",
                padedit: "Program Edit — shape the selected sound: filter, envelope, tuning.",
                prefs: "Settings — device information and harness details.",
            })[it.dataset.nav] || "Opens this screen.";
        }],
        [(el) => el.closest(".mh-back"), () => "Back to Main Mode."],
        [(el) => el.closest(".mh-arrow"), () => "Previous / next track."],
        [(el) => el.closest(".browse-row button"), (el) =>
            (el.closest("button").textContent || "").trim() === "Load"
                ? "Load this saved pattern into the machine."
                : "Delete this saved pattern slot."],
        [(el) => el.closest("#lp-starts a"), () =>
            "Loads the loop as it stands at the start of this tutorial step — build from here."],
        [(el) => el.closest(".mm-row"), () => "Click to select this row."],
    ];

    const guideHelpFor = (el) => {
        if (!el || el.nodeType !== 1) return null;
        for (const [match, text] of GUIDE_HELP_RULES) {
            try { if (match(el)) return text(el); } catch (e) { /* keep looking */ }
        }
        for (let n = el; n && n !== document.body; n = n.parentElement) {
            if (!n.id) continue;
            if (GUIDE_HELP_BY_ID[n.id]) return GUIDE_HELP_BY_ID[n.id];
            if (/^mute-\d+$/.test(n.id)) return "M — mute this track in the mixer.";
            if (/^solo-\d+$/.test(n.id)) return "S — solo this track: hear it on its own.";
        }
        return null;
    };

    const tooltip = document.getElementById("hw-tooltip");
    let tipTarget = null, tipTimer = null, tipPendingHost = null, tipStashedTitles = [];
    let tourOpen = false; // the tour suppresses tooltips while it runs

    const stashTitles = (fromEl) => {
        tipStashedTitles = [];
        for (let n = fromEl; n && n !== document.documentElement; n = n.parentElement) {
            if (n.hasAttribute && n.hasAttribute("title")) {
                tipStashedTitles.push([n, n.getAttribute("title")]);
                n.removeAttribute("title");
            }
        }
    };
    const restoreTitles = () => {
        for (const [n, v] of tipStashedTitles) n.setAttribute("title", v);
        tipStashedTitles = [];
    };
    const hideTooltip = () => {
        if (tipTimer) { clearTimeout(tipTimer); tipTimer = null; }
        tipPendingHost = null;
        if (tooltip) tooltip.classList.add("hidden");
        tipTarget = null;
        restoreTitles();
    };
    const placeTooltip = (x, y, anchorRect) => {
        const pad = 8, tw = tooltip.offsetWidth, th = tooltip.offsetHeight;
        let left, top;
        if (anchorRect) { // keyboard focus / touch: anchor to the control
            left = anchorRect.left + anchorRect.width / 2 - tw / 2;
            top = anchorRect.bottom + 10;
            if (top + th > window.innerHeight - pad) top = anchorRect.top - th - 10;
        } else {          // mouse: follow the pointer
            left = x + 16; top = y + 18;
            if (left + tw > window.innerWidth - pad) left = x - tw - 12;
            if (top + th > window.innerHeight - pad) top = y - th - 12;
        }
        tooltip.style.left = Math.max(pad, Math.min(left, window.innerWidth - tw - pad)) + "px";
        tooltip.style.top = Math.max(pad, Math.min(top, window.innerHeight - th - pad)) + "px";
    };
    const showTooltip = (target, text, x, y, anchorRect) => {
        if (!tooltip || tourOpen) return;
        tipTarget = target;
        tooltip.textContent = text;
        tooltip.classList.remove("hidden");
        placeTooltip(x || 0, y || 0, anchorRect);
    };
    if (tooltip) {
        document.addEventListener("mouseover", (e) => {
            if (tourOpen) return;
            const text = guideHelpFor(e.target);
            const host = text ? (e.target.closest(".pad,button,[id],input,select,a,.step-btn,.grid-cell,.fader-slider") || e.target) : null;
            if (!text) {
                if (tipTimer) { clearTimeout(tipTimer); tipTimer = null; tipPendingHost = null; }
                if (tipTarget) hideTooltip();
                return;
            }
            if (tipTarget === host && !tooltip.classList.contains("hidden")) {
                placeTooltip(e.clientX, e.clientY, null);
                return;
            }
            if (tipPendingHost === host && tipTimer) return; // already counting down for this control
            if (tipTimer) clearTimeout(tipTimer);
            tipPendingHost = host;
            const delay = tooltip.classList.contains("hidden") ? 300 : 60;
            tipTimer = setTimeout(() => {
                tipPendingHost = null;
                stashTitles(e.target);
                showTooltip(host, text, e.clientX, e.clientY, null);
            }, delay);
        });
        document.addEventListener("mousemove", (e) => {
            if (tipTarget && !tooltip.classList.contains("hidden"))
                placeTooltip(e.clientX, e.clientY, null);
        });
        document.addEventListener("mouseout", (e) => {
            if (!e.relatedTarget) { hideTooltip(); return; }
            if (tipTarget && e.target && !tipTarget.contains(e.relatedTarget)
                     && !guideHelpFor(e.relatedTarget)) hideTooltip();
        });
        // A press must never wait for — or be covered by — a tooltip.
        let lastPointerDownAt = 0;
        document.addEventListener("pointerdown", () => {
            lastPointerDownAt = Date.now();
            hideTooltip();
        }, true);
        document.addEventListener("scroll", hideTooltip, { capture: true, passive: true });
        document.addEventListener("focusin", (e) => {
            if (tourOpen) return;
            // Focus that arrives because of a pointer press is not
            // keyboard focus — the press already dismissed the tip.
            if (Date.now() - lastPointerDownAt < 600) return;
            const text = guideHelpFor(e.target);
            if (!text) return;
            if (tipTimer) clearTimeout(tipTimer);
            stashTitles(e.target);
            showTooltip(e.target, text, 0, 0, e.target.getBoundingClientRect());
        });
        document.addEventListener("focusout", hideTooltip);
        // Touch: press-and-hold (~0.55 s, without moving) shows the help;
        // a normal tap or strike is untouched — the press itself has
        // already happened by the time the tooltip appears.
        let touchTimer = null, touchStart = null;
        document.addEventListener("pointerdown", (e) => {
            if (e.pointerType !== "touch") return;
            touchStart = { x: e.clientX, y: e.clientY, el: e.target };
            touchTimer = setTimeout(() => {
                const text = touchStart && guideHelpFor(touchStart.el);
                if (text && !tourOpen) {
                    stashTitles(touchStart.el);
                    showTooltip(touchStart.el, text, 0, 0, touchStart.el.getBoundingClientRect());
                    setTimeout(() => { if (tipTarget === touchStart.el) hideTooltip(); }, 2400);
                }
            }, 550);
        });
        const cancelTouch = () => { if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; } };
        document.addEventListener("pointerup", cancelTouch);
        document.addEventListener("pointercancel", cancelTouch);
        document.addEventListener("pointermove", (e) => {
            if (touchStart && Math.hypot(e.clientX - touchStart.x, e.clientY - touchStart.y) > 12) cancelTouch();
        }, { passive: true });
    }

    // --- 2) "Get to know the device" guided tour -----------------
    const TOUR_STEPS = [
        { sel: "#btn-play", title: "Start with PLAY",
          body: "This is the heartbeat of the machine. PLAY starts the 16-step loop; STOP halts it. A starter groove is already loaded — press PLAY now and hear it go round." },
        { sel: "#btn-tap-tempo", title: "Tap the tempo",
          body: "No typing numbers: TAP TEMPO takes the speed from your taps. Four steady taps and the loop follows your feel — the BPM you've tapped shows on the screen." },
        { sel: "#btn-step-seq", title: "Program the beats",
          body: "STEP SEQ opens the step sequencer. Press it and look at the screen: sixteen steps for one track — click steps on to place hits, off to remove them. That's how a rhythm gets written." },
        { sel: "#pad-matrix", title: "The pads",
          body: "Sixteen pads: drums on the lower rows, bass notes up top. Strike one — where and how hard you hit sets its volume. While the loop plays, these strikes can be captured into it." },
        { sel: "#btn-16-level", title: "16 LEVEL — one sound, sixteen notes",
          body: "Strike a melodic pad, then press 16 LEVEL: all sixteen pads become that one sound at sixteen pitches — a little keyboard. Melodies and basslines are played in this way." },
        { sel: "#btn-rec", title: "REC — capture the first pass",
          body: "REC arms recording. With the loop playing and REC lit, everything you strike is written into the loop at the step that's playing. Use REC to lay down the first layer." },
        { sel: "#btn-overdub", title: "OVERDUB — add layers on top",
          body: "OVERDUB is REC's layering twin: the loop keeps what it already has and adds your new strikes over it. Chords over drums, bass over chords, melody last — that is the whole looping method." },
        { sel: ".lcd-tab[data-view=\"grid\"]", title: "GRID — watch it build",
          body: "The GRID tab turns the screen into a piano roll for one track: captured notes appear as amber blocks. Press it while a loop plays and watch each layer land; the ◀ ▶ arrows change track." },
        { sel: ".lcd-tab[data-view=\"main\"]", title: "MAIN — home base",
          body: "MAIN is the home screen: sequences, tracks and programs in lists. The strip at the bottom of the screen always names the sequence, track and program in play." },
        { sel: "#btn-browse", title: "BROWSE — keep what you make",
          body: "Made a loop you like? BROWSE opens the pattern slots: save the current pattern under a name and load it back whenever you return. Slots live in this browser, on this device." },
        { sel: "#output-strip", title: "OUTPUT — your volume",
          body: "Under the device sits the output strip: the master volume and a live meter for everything the machine plays. That's the tour — now press PLAY and build a loop of your own." },
    ];
    const tourSpot = document.getElementById("tour-spot");
    const tourCard = document.getElementById("tour-card");
    const tourCount = document.getElementById("tour-count");
    const tourTitle = document.getElementById("tour-title");
    const tourBody = document.getElementById("tour-body");
    const tourBack = document.getElementById("tour-back");
    const tourNext = document.getElementById("tour-next");
    const tourEndBtn = document.getElementById("tour-end");
    const tourStartBtn = document.getElementById("btn-guided-tour");
    let tourIdx = -1, tourRaf = 0;

    const tourTarget = () => {
        const step = TOUR_STEPS[tourIdx];
        return step ? document.querySelector(step.sel) : null;
    };
    const positionTour = () => {
        if (!tourOpen) return;
        const t = tourTarget();
        if (t) {
            const r = t.getBoundingClientRect();
            const p = 6;
            tourSpot.style.left = (r.left - p) + "px";
            tourSpot.style.top = (r.top - p) + "px";
            tourSpot.style.width = (r.width + p * 2) + "px";
            tourSpot.style.height = (r.height + p * 2) + "px";
            // Card: below the target if it fits, above if not, and
            // docked to the bottom on short screens.
            const cw = tourCard.offsetWidth, ch = tourCard.offsetHeight;
            let top;
            if (r.bottom + ch + 18 <= window.innerHeight) top = r.bottom + 14;
            else if (r.top - ch - 18 >= 0) top = r.top - ch - 14;
            else top = window.innerHeight - ch - 12;
            let left = r.left + r.width / 2 - cw / 2;
            left = Math.max(12, Math.min(left, window.innerWidth - cw - 12));
            tourCard.style.left = left + "px";
            tourCard.style.top = Math.max(8, top) + "px";
        }
        tourRaf = requestAnimationFrame(positionTour);
    };
    const showTourStep = (i) => {
        tourIdx = Math.max(0, Math.min(i, TOUR_STEPS.length - 1));
        const step = TOUR_STEPS[tourIdx];
        tourCount.textContent = `${tourIdx + 1} of ${TOUR_STEPS.length}`;
        tourTitle.textContent = step.title;
        tourBody.textContent = step.body;
        tourBack.disabled = tourIdx === 0;
        tourNext.textContent = tourIdx === TOUR_STEPS.length - 1 ? "Finish" : "Next";
        const t = tourTarget();
        if (t) t.scrollIntoView({ block: "center", behavior: "smooth" });
    };
    const startTour = () => {
        if (!tourSpot || !tourCard) return;
        hideTooltip();
        tourOpen = true;
        tourSpot.classList.remove("hidden");
        tourCard.classList.remove("hidden");
        showTourStep(0);
        cancelAnimationFrame(tourRaf);
        tourRaf = requestAnimationFrame(positionTour);
        tourNext.focus();
    };
    const endTour = () => {
        tourOpen = false;
        cancelAnimationFrame(tourRaf);
        if (tourSpot) tourSpot.classList.add("hidden");
        if (tourCard) tourCard.classList.add("hidden");
        tourIdx = -1;
        if (tourStartBtn) tourStartBtn.focus();
    };
    if (tourStartBtn && tourCard) {
        tourStartBtn.addEventListener("click", startTour);
        tourEndBtn.addEventListener("click", endTour);
        tourBack.addEventListener("click", () => showTourStep(tourIdx - 1));
        tourNext.addEventListener("click", () => {
            if (tourIdx >= TOUR_STEPS.length - 1) endTour();
            else showTourStep(tourIdx + 1);
        });
        document.addEventListener("keydown", (e) => {
            if (!tourOpen) return;
            if (e.key === "Escape") { endTour(); return; }
            if (tourCard.contains(document.activeElement)) {
                if (e.key === "ArrowRight") { e.preventDefault(); tourNext.click(); }
                if (e.key === "ArrowLeft" && tourIdx > 0) { e.preventDefault(); tourBack.click(); }
            }
        });
        window.addEventListener("resize", () => { if (tourOpen) positionTour(); });
    }

    window.__simGuide = {
        help: GUIDE_HELP_BY_ID, helpFor: guideHelpFor,
        tourSteps: TOUR_STEPS, startTour, endTour,
        tourIndex: () => tourIdx, tourIsOpen: () => tourOpen,
    };
});
