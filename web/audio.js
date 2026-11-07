/**
 * 0700-AAM Sovereign Web Audio Engine
 * High-performance, zero-latency procedural drum synthesizers,
 * analog bass engine, multi-mode master filter, and sample playback.
 */

class AudioEngine {
    constructor() {
        this.ctx = null;
        this.masterGain = null;
        this.filterNode = null;
        this.analyser = null;
        this.isInitialized = false;

        // Sound parameters modulated by Q-Links
        this.params = {
            cutoff: 8000,     // Q1 (Hz)
            resonance: 1.5,   // Q2 (Q factor)
            decay: 1.0,       // Q3 (Multiplier)
            tuning: 0         // Q4 (Semitones)
        };

        // Pad instrument definitions
        this.instruments = [
            { id: 1,  name: "808 Kick",    type: "kick" },
            { id: 2,  name: "909 Snare",   type: "snare" },
            { id: 3,  name: "Closed Hat",  type: "hihat_closed" },
            { id: 4,  name: "Open Hat",    type: "hihat_open" },
            { id: 5,  name: "Hand Clap",   type: "clap" },
            { id: 6,  name: "Low Tom",     type: "tom_low" },
            { id: 7,  name: "Mid Tom",     type: "tom_mid" },
            { id: 8,  name: "High Tom",    type: "tom_high" },
            { id: 9,  name: "Rimshot",     type: "rimshot" },
            { id: 10, name: "Shaker",      type: "shaker" },
            { id: 11, name: "Crash Cym",   type: "crash" },
            { id: 12, name: "Ride Bell",   type: "ride" },
            { id: 13, name: "Sub Bass C",  type: "bass", note: 36 }, // C2
            { id: 14, name: "Sub Bass Eb", type: "bass", note: 39 }, // Eb2
            { id: 15, name: "Sub Bass F",  type: "bass", note: 41 }, // F2
            { id: 16, name: "Sub Bass G",  type: "bass", note: 43 }, // G2
        ];
    }

    init() {
        if (this.isInitialized) return;
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.ctx = new AudioCtx();

        this.masterGain = this.ctx.createGain();
        this.masterGain.gain.setValueAtTime(0.85, this.ctx.currentTime);

        this.filterNode = this.ctx.createBiquadFilter();
        this.filterNode.type = "lowpass";
        this.filterNode.frequency.setValueAtTime(this.params.cutoff, this.ctx.currentTime);
        this.filterNode.Q.setValueAtTime(this.params.resonance, this.ctx.currentTime);

        this.analyser = this.ctx.createAnalyser();
        this.analyser.fftSize = 256;

        this.filterNode.connect(this.masterGain);
        this.masterGain.connect(this.analyser);
        this.analyser.connect(this.ctx.destination);

        this.isInitialized = true;
    }

    ensureContext() {
        if (!this.isInitialized) {
            this.init();
        }
        if (this.ctx && this.ctx.state === "suspended") {
            this.ctx.resume();
        }
        // load the bundled samples as soon as there is a context to decode them in; the
        // guard stops loadSamples' own ensureContext call from recursing
        if (this.ctx && !this.samplesReady && !this.samplesLoading && !this._samplerKicked) {
            this._samplerKicked = true;
            this.loadSamples("samples/");
        }
    }

    setMasterVolume(val) { // 0.0 to 1.0
        if (!this.masterGain) return;
        const gain = Math.max(0.001, Math.min(1.0, val));
        this.masterGain.gain.setTargetAtTime(gain, this.ctx.currentTime, 0.02);
    }

    setFilterCutoff(normalized) { // 0.0 to 1.0
        // Logarithmic scale 60Hz to 20000Hz
        const minF = 60;
        const maxF = 20000;
        this.params.cutoff = minF * Math.pow(maxF / minF, normalized);
        if (this.filterNode) {
            this.filterNode.frequency.setTargetAtTime(this.params.cutoff, this.ctx.currentTime, 0.02);
        }
    }

    setResonance(normalized) { // 0.0 to 1.0 -> 0.1 to 18
        this.params.resonance = 0.1 + normalized * 17.9;
        if (this.filterNode) {
            this.filterNode.Q.setTargetAtTime(this.params.resonance, this.ctx.currentTime, 0.02);
        }
    }

    setDecay(normalized) { // 0.0 to 1.0 -> 0.2 to 2.5 multiplier
        this.params.decay = 0.2 + normalized * 2.3;
    }

    setTuning(normalized) { // 0.0 to 1.0 -> -12 to +12 semitones
        this.params.tuning = Math.round((normalized - 0.5) * 24);
    }

    async loadSamples(base = "samples/", force = false) {
        // Bundled samples, fetched on first user gesture (an AudioContext cannot decode
        // before that). Silent no-op if the folder is missing, so the synth voices still
        // work in a bare checkout.
        if (this.samplesLoading) return this.samplesReady;
        if (this.samplesReady && !force) return this.samplesReady;
        if (force) { this.samplesReady = false; this.samples = {}; this.samplePads = {}; }
        this.samplesLoading = true;
        try {
            this.ensureContext();
            const man = await (await fetch(base + "manifest.json", { cache: "no-store" })).json();
            const pads = man.pads || {};
            const names = [...new Set(Object.values(pads))];
            const loaded = await Promise.all(names.map(async (n) => {
                const r = await fetch(base + n + ".wav");
                const ab = await r.arrayBuffer();
                return [n, await this.ctx.decodeAudioData(ab)];
            }));
            this.samples = Object.fromEntries(loaded);
            this.samplePads = pads;
            this.sampleMix = man.mix || {};
            this.sampleNotes = man.notes || {};
            this.samplesReady = true;
            console.log("[sampler] loaded", names.length, "samples");
        } catch (e) {
            console.warn("[sampler] no samples loaded, using synth voices:", e.message);
            this.samplesReady = false;
        } finally {
            this.samplesLoading = false;
        }
        return this.samplesReady;
    }

    // Mirrors upstream Kick's DrumSampler/samplerVoice (upstream/Kick/modules/engine/
    // objects/sampler): one voice per hit, gain from velocity, per-voice level and pan from
    // the program, pitch factor from the instrument's tuning. One-shot, as DrumSampler is.
    _sampleVoice(name, velNorm, when, extraRate) {
        const buf = this.samples && this.samples[name];
        if (!buf) return null;
        const mix = (this.sampleMix && this.sampleMix[name]) || { gain: 1.0, pan: 0.0 };
        const src = this.ctx.createBufferSource();
        src.buffer = buf;
        src.playbackRate.value = Math.pow(2, this.params.tuning / 12.0) * (extraRate || 1);
        const g = this.ctx.createGain();
        g.gain.value = velNorm * (mix.gain != null ? mix.gain : 1.0);
        let node = g;
        if (this.ctx.createStereoPanner && mix.pan) {
            const p = this.ctx.createStereoPanner();
            p.pan.value = Math.max(-1, Math.min(1, mix.pan));
            g.connect(p); node = p;
        }
        src.connect(g);
        node.connect(this.filterNode);
        src.start(Math.max(this.ctx.currentTime, when == null ? 0 : when));
        return src;
    }

    scheduleSample(name, when, velNorm) {
        return !!this._sampleVoice(name, velNorm, when, null);
    }

    // Keygroup playback, as upstream's KeygroupSampler does: one sample covers a range and
    // every note is a playback-rate shift from the sample's root note.
    schedulePitch(padIndex, midiNote, when, velNorm) {
        const name = this.samplePads && this.samplePads[padIndex];
        if (!name) return false;
        const roots = this.sampleNotes || {};
        const root = roots[padIndex];
        const semis = (root == null) ? 0 : (midiNote - root);
        return !!this._sampleVoice(name, velNorm, when, Math.pow(2, semis / 12));
    }

    playSample(name, velNorm) {
        const v = this._sampleVoice(name, velNorm, null);
        return !!v;
    }

    triggerPad(padIndex, velocity = 127) { // padIndex 0 to 15
        this.ensureContext();
        if (!this.ctx) return;

        const velNorm = Math.max(0.1, Math.min(1.0, velocity / 127.0));
        // A pad that has a bundled sample plays the sample; everything else keeps the
        // synthesised voice. This is what the real KICK does -- it is a sampler -- and the
        // model previously had no way to load a sound at all.
        const sampleName = this.samplePads && this.samplePads[padIndex];
        if (sampleName && this.samples && this.samples[sampleName]) {
            this.playSample(sampleName, velNorm);
            return;
        }
        const instr = this.instruments[padIndex % this.instruments.length];
        const now = this.ctx.currentTime;

        switch (instr.type) {
            case "kick":
                this.playKick(now, velNorm);
                break;
            case "snare":
                this.playSnare(now, velNorm);
                break;
            case "hihat_closed":
                this.playHiHat(now, velNorm, 0.05 * this.params.decay);
                break;
            case "hihat_open":
                this.playHiHat(now, velNorm, 0.35 * this.params.decay);
                break;
            case "clap":
                this.playClap(now, velNorm);
                break;
            case "tom_low":
                this.playTom(now, velNorm, 90);
                break;
            case "tom_mid":
                this.playTom(now, velNorm, 130);
                break;
            case "tom_high":
                this.playTom(now, velNorm, 180);
                break;
            case "rimshot":
                this.playRimshot(now, velNorm);
                break;
            case "shaker":
                this.playShaker(now, velNorm);
                break;
            case "crash":
                this.playCrash(now, velNorm);
                break;
            case "ride":
                this.playRide(now, velNorm);
                break;
            case "bass":
                this.playBass(now, velNorm, instr.note);
                break;
            default:
                this.playKick(now, velNorm);
                break;
        }
    }

    // --- Procedural Synth Engines ---

    playKick(t, vel) {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        const basePitch = 150 * Math.pow(2, this.params.tuning / 12.0);
        const subPitch = 44 * Math.pow(2, this.params.tuning / 12.0);

        osc.type = "sine";
        osc.frequency.setValueAtTime(basePitch, t);
        osc.frequency.exponentialRampToValueAtTime(subPitch, t + 0.07);

        // Click transient
        const clickOsc = this.ctx.createOscillator();
        const clickGain = this.ctx.createGain();
        clickOsc.type = "square";
        clickOsc.frequency.setValueAtTime(320, t);
        clickGain.gain.setValueAtTime(0.5 * vel, t);
        clickGain.gain.exponentialRampToValueAtTime(0.001, t + 0.015);
        clickOsc.connect(clickGain);
        clickGain.connect(this.filterNode);
        clickOsc.start(t);
        clickOsc.stop(t + 0.02);

        const decay = 0.38 * this.params.decay;
        gain.gain.setValueAtTime(1.0 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + decay);

        osc.connect(gain);
        gain.connect(this.filterNode);

        osc.start(t);
        osc.stop(t + decay + 0.02);
    }

    playSnare(t, vel) {
        // Body oscillator
        const osc = this.ctx.createOscillator();
        const oscGain = this.ctx.createGain();
        const bodyFreq = 185 * Math.pow(2, this.params.tuning / 12.0);

        osc.type = "triangle";
        osc.frequency.setValueAtTime(bodyFreq, t);
        osc.frequency.exponentialRampToValueAtTime(70, t + 0.08);

        oscGain.gain.setValueAtTime(0.7 * vel, t);
        oscGain.gain.exponentialRampToValueAtTime(0.001, t + 0.18 * this.params.decay);
        osc.connect(oscGain);
        oscGain.connect(this.filterNode);

        // Noise snare wire
        const bufferSize = this.ctx.sampleRate * 0.25;
        const noiseBuffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const output = noiseBuffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            output[i] = Math.random() * 2 - 1;
        }

        const whiteNoise = this.ctx.createBufferSource();
        whiteNoise.buffer = noiseBuffer;

        const noiseFilter = this.ctx.createBiquadFilter();
        noiseFilter.type = "highpass";
        noiseFilter.frequency.setValueAtTime(1000, t);

        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(0.9 * vel, t);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, t + 0.22 * this.params.decay);

        whiteNoise.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        noiseGain.connect(this.filterNode);

        osc.start(t);
        whiteNoise.start(t);
        osc.stop(t + 0.25);
        whiteNoise.stop(t + 0.25);
    }

    playHiHat(t, vel, decayDuration) {
        // Metallic ratios
        const freqs = [205, 305, 415, 520, 620, 800];
        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0.6 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + decayDuration);

        const bandpass = this.ctx.createBiquadFilter();
        bandpass.type = "bandpass";
        bandpass.frequency.setValueAtTime(7500, t);
        bandpass.Q.setValueAtTime(1.8, t);

        const highpass = this.ctx.createBiquadFilter();
        highpass.type = "highpass";
        highpass.frequency.setValueAtTime(6000, t);

        freqs.forEach(f => {
            const osc = this.ctx.createOscillator();
            osc.type = "square";
            osc.frequency.setValueAtTime(f * Math.pow(2, this.params.tuning / 12.0), t);
            osc.connect(bandpass);
            osc.start(t);
            osc.stop(t + decayDuration + 0.05);
        });

        bandpass.connect(highpass);
        highpass.connect(gain);
        gain.connect(this.filterNode);
    }

    playClap(t, vel) {
        const bufferSize = this.ctx.sampleRate * 0.3;
        const noiseBuffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = noiseBuffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }

        const source = this.ctx.createBufferSource();
        source.buffer = noiseBuffer;

        const filter = this.ctx.createBiquadFilter();
        filter.type = "bandpass";
        filter.frequency.setValueAtTime(1200, t);
        filter.Q.setValueAtTime(1.2, t);

        const gain = this.ctx.createGain();
        // Stuttered bursts
        gain.gain.setValueAtTime(0.8 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.015);
        gain.gain.setValueAtTime(0.8 * vel, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.035);
        gain.gain.setValueAtTime(0.9 * vel, t + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25 * this.params.decay);

        source.connect(filter);
        filter.connect(gain);
        gain.connect(this.filterNode);

        source.start(t);
        source.stop(t + 0.35);
    }

    playTom(t, vel, basePitch) {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        const tunedPitch = basePitch * Math.pow(2, this.params.tuning / 12.0);

        osc.type = "sine";
        osc.frequency.setValueAtTime(tunedPitch * 1.5, t);
        osc.frequency.exponentialRampToValueAtTime(tunedPitch, t + 0.06);

        const decay = 0.28 * this.params.decay;
        gain.gain.setValueAtTime(0.9 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + decay);

        osc.connect(gain);
        gain.connect(this.filterNode);
        osc.start(t);
        osc.stop(t + decay + 0.05);
    }

    playRimshot(t, vel) {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(800 * Math.pow(2, this.params.tuning / 12.0), t);

        gain.gain.setValueAtTime(0.8 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.03);

        osc.connect(gain);
        gain.connect(this.filterNode);
        osc.start(t);
        osc.stop(t + 0.05);
    }

    playShaker(t, vel) {
        const bufferSize = this.ctx.sampleRate * 0.12;
        const noiseBuffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = noiseBuffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }

        const source = this.ctx.createBufferSource();
        source.buffer = noiseBuffer;

        const filter = this.ctx.createBiquadFilter();
        filter.type = "bandpass";
        filter.frequency.setValueAtTime(4500, t);
        filter.Q.setValueAtTime(2.0, t);

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0.5 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.08 * this.params.decay);

        source.connect(filter);
        filter.connect(gain);
        gain.connect(this.filterNode);
        source.start(t);
        source.stop(t + 0.12);
    }

    playCrash(t, vel) {
        this.playHiHat(t, vel * 1.2, 0.95 * this.params.decay);
    }

    playRide(t, vel) {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(2200 * Math.pow(2, this.params.tuning / 12.0), t);

        gain.gain.setValueAtTime(0.6 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.7 * this.params.decay);

        osc.connect(gain);
        gain.connect(this.filterNode);
        osc.start(t);
        osc.stop(t + 0.75);
    }

    playBass(t, vel, midiNote) {
        const osc = this.ctx.createOscillator();
        const oscSub = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        const filter = this.ctx.createBiquadFilter();

        const freq = 440 * Math.pow(2, (midiNote + this.params.tuning - 69) / 12.0);

        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(freq, t);

        oscSub.type = "sine";
        oscSub.frequency.setValueAtTime(freq / 2.0, t);

        filter.type = "lowpass";
        filter.frequency.setValueAtTime(freq * 3.5, t);
        filter.frequency.exponentialRampToValueAtTime(freq * 1.2, t + 0.25);
        filter.Q.setValueAtTime(4.0, t);

        const decay = 0.45 * this.params.decay;
        gain.gain.setValueAtTime(0.85 * vel, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + decay);

        osc.connect(filter);
        oscSub.connect(filter);
        filter.connect(gain);
        gain.connect(this.filterNode);

        osc.start(t);
        oscSub.start(t);
        osc.stop(t + decay + 0.05);
        oscSub.stop(t + decay + 0.05);
    }
}

window.AudioEngine = AudioEngine;
