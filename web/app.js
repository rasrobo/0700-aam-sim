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
        sixteenLevel: false,
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
        masterGain: 0.85,
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

        // Mixer states (16 channels)
        mixer: Array.from({ length: 16 }, () => ({
            volume: 0.85,
            pan: 0.0,
            mute: false,
            solo: false,
            vuLevel: 0.0
        }))
    };

    // Default catchy groove:
    // Kick on 0, 4, 8, 12 (Steps 1, 5, 9, 13)
    [0, 4, 8, 12].forEach(s => state.pattern[0][s] = true);
    // Snare on 4, 12 (Steps 5, 13)
    [4, 12].forEach(s => state.pattern[1][s] = true);
    // Closed Hat on 0, 2, 4, 6, 8, 10, 12, 14
    [0, 2, 4, 6, 8, 10, 12, 14].forEach(s => state.pattern[2][s] = true);
    // Open Hat on 2, 10
    [2, 10].forEach(s => state.pattern[3][s] = true);
    // Hand Clap on 4, 12
    [4, 12].forEach(s => state.pattern[4][s] = true);
    // Shaker on all 16
    for (let s = 0; s < 16; s++) state.pattern[9][s] = true;
    // Bass on 0, 3, 6, 10
    state.pattern[12][0] = true;
    state.pattern[13][3] = true;
    state.pattern[14][6] = true;
    state.pattern[15][10] = true;

    // --- Instantiate Audio Engine ---
    const audio = new AudioEngine();

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
    const padElements = Array.from(document.querySelectorAll(".pad"));

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

    function triggerPadStrike(padIndex, velocity = 127, sendPacket = true) {
        audio.ensureContext();

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
        audio.triggerPad(padIndex, effectiveVel);

        // Update active instrument in Step Sequencer view
        const instNameTag = document.getElementById("stepseq-inst-name");
        if (instNameTag && audio.instruments[padIndex]) {
            instNameTag.innerText = `Pad ${padIndex + 1}: ${audio.instruments[padIndex].name}`;
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
            const vel = Math.round(60 + (1 - relY) * 67);
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

    // Plus & Minus Buttons
    document.getElementById("btn-plus").addEventListener("click", () => rotateJogWheel(15));
    document.getElementById("btn-minus").addEventListener("click", () => rotateJogWheel(-15));

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
        sendHwPacket(ComProtocol.CommandId.LEVEL_16, [state.sixteenLevel ? 0x01 : 0x00]);
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

            // Trigger active pattern steps
            for (let track = 0; track < 16; track++) {
                if (state.pattern[track][step]) {
                    const ch = state.mixer[track];
                    if (!ch.mute) {
                        triggerPadStrike(track, 110, false);
                        ch.vuLevel = 0.95;
                    }
                }
            }

            // Update LCD step sequencer cursor
            updateStepCursor(step);

            // Update bar display
            const bar = Math.floor(step / 16) + 1;
            const beat = Math.floor((step % 16) / 4) + 1;
            const sub = (step % 4) + 1;
            const barDisplay = document.getElementById("lcd-bar-display");
            if (barDisplay) barDisplay.innerText = `${bar}.${beat}.${sub}`;

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
    document.getElementById("btn-menu").addEventListener("click", () => switchView("prefs"));

    // --- Build Mini Pad Monitor in Main View ---
    const miniPadsContainer = document.getElementById("mini-pads");
    if (miniPadsContainer) {
        for (let i = 0; i < 16; i++) {
            const mp = document.createElement("div");
            mp.className = "mini-pad";
            mp.innerText = `P${i + 1}`;
            miniPadsContainer.appendChild(mp);
        }
    }

    // --- Build 16x16 Step Sequencer Grid ---
    const stepseqGrid = document.getElementById("stepseq-grid");
    if (stepseqGrid) {
        audio.instruments.forEach((instr, trackIdx) => {
            const row = document.createElement("div");
            row.className = "stepseq-row";

            const label = document.createElement("div");
            label.className = "step-label";
            label.innerText = `P${trackIdx + 1}: ${instr.name}`;
            row.appendChild(label);

            for (let step = 0; step < 16; step++) {
                const stepBtn = document.createElement("div");
                stepBtn.className = "step-btn";
                if (step % 4 === 0) stepBtn.classList.add("group-beat");
                if (state.pattern[trackIdx][step]) stepBtn.classList.add("active");
                stepBtn.dataset.track = trackIdx;
                stepBtn.dataset.step = step;

                stepBtn.addEventListener("click", () => {
                    state.pattern[trackIdx][step] = !state.pattern[trackIdx][step];
                    stepBtn.classList.toggle("active", state.pattern[trackIdx][step]);
                    if (state.pattern[trackIdx][step]) audio.triggerPad(trackIdx, 100);
                });

                row.appendChild(stepBtn);
            }

            stepseqGrid.appendChild(row);
        });
    }

    // Step Sequencer Toolbar Actions
    document.getElementById("btn-clear-seq").addEventListener("click", () => {
        for (let t = 0; t < 16; t++) {
            for (let s = 0; s < 16; s++) {
                state.pattern[t][s] = false;
            }
        }
        document.querySelectorAll(".step-btn").forEach(btn => btn.classList.remove("active"));
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

    // --- Oscilloscope & Real-time Visualizer ---
    const scopeCanvas = document.getElementById("scope-canvas");
    const scopeCtx = scopeCanvas.getContext("2d");

    function renderScope() {
        requestAnimationFrame(renderScope);

        // Update Mixer VU Fills
        for (let i = 0; i < 16; i++) {
            const ch = state.mixer[i];
            ch.vuLevel = Math.max(0, ch.vuLevel - 0.04);
            const vuEl = document.getElementById(`vu-${i}`);
            if (vuEl) vuEl.style.height = `${ch.vuLevel * 100}%`;
        }

        if (!audio.analyser) {
            // Draw idle resting line
            scopeCtx.fillStyle = "#06070a";
            scopeCtx.fillRect(0, 0, scopeCanvas.width, scopeCanvas.height);
            scopeCtx.strokeStyle = "#1a2530";
            scopeCtx.lineWidth = 1;
            scopeCtx.beginPath();
            scopeCtx.moveTo(0, scopeCanvas.height / 2);
            scopeCtx.lineTo(scopeCanvas.width, scopeCanvas.height / 2);
            scopeCtx.stroke();
            return;
        }

        const bufferLength = audio.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        audio.analyser.getByteTimeDomainData(dataArray);

        scopeCtx.fillStyle = "#06070a";
        scopeCtx.fillRect(0, 0, scopeCanvas.width, scopeCanvas.height);

        // Grid lines
        scopeCtx.strokeStyle = "rgba(0, 210, 255, 0.08)";
        scopeCtx.lineWidth = 1;
        for (let x = 0; x < scopeCanvas.width; x += 40) {
            scopeCtx.beginPath();
            scopeCtx.moveTo(x, 0);
            scopeCtx.lineTo(x, scopeCanvas.height);
            scopeCtx.stroke();
        }

        // Waveform
        scopeCtx.lineWidth = 2;
        scopeCtx.strokeStyle = "#00d2ff";
        scopeCtx.shadowColor = "#00d2ff";
        scopeCtx.shadowBlur = 6;
        scopeCtx.beginPath();

        const sliceWidth = scopeCanvas.width * 1.0 / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * scopeCanvas.height / 2;

            if (i === 0) scopeCtx.moveTo(x, y);
            else scopeCtx.lineTo(x, y);

            x += sliceWidth;
        }

        scopeCtx.lineTo(scopeCanvas.width, scopeCanvas.height / 2);
        scopeCtx.stroke();
        scopeCtx.shadowBlur = 0;
    }
    renderScope();

    // --- Sampler Waveform Drawing ---
    const samplerCanvas = document.getElementById("sampler-canvas");
    if (samplerCanvas) {
        const sCtx = samplerCanvas.getContext("2d");
        sCtx.fillStyle = "#07080c";
        sCtx.fillRect(0, 0, samplerCanvas.width, samplerCanvas.height);

        // Draw synthetic drum waveform sample
        sCtx.strokeStyle = "#00d2ff";
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

        // Jog Wheel: [ = CCW, ] = CW, Enter = Click
        if (e.key === "[") rotateJogWheel(-15);
        else if (e.key === "]") rotateJogWheel(15);
        else if (e.key === "Enter") jogCenterBtn.click();

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
});
