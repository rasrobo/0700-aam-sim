#!/usr/bin/env python3
"""make_piano_kit.py — render the bundled kit's pitched samples as piano.

Replaces make_warm_kit.py. Lessons that forced this (2026-11-22, all from
listening, not measuring):
  1. Vibrato + a detuned second oscillator = a warpy, string-like wobble.
     Pitch-tracked afterwards: ~18 cents peak-to-peak on the old mel_cs4.
     A keygroup stretches it further (vibrato rate scales with pitch).
     Piano has neither — its pitch is rock steady.
  2. Sustained synth pads pile up when chords change every half second.
     Piano decays naturally per note, so loops stay clear.
  3. Everything was full blast. These renders peak at 0.62 and the
     manifest gains came down too; the master limiter is a safety net,
     not a loudness maker.

Piano model (additive): 12 partials with real-piano inharmonicity
(f_k = k*f0*sqrt(1+B*k^2)), per-partial exponential decays (high partials
die first, fundamental rings longest), a short brightness burst and a
hammer-noise tick at the attack. No vibrato, no detune, no chorus.

    python3 scripts/make_piano_kit.py            # writes into web/samples/

Drums are not touched. Format matches the kit: 48 kHz mono 16-bit WAV,
same filenames and root notes as web/samples/manifest.json.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48000
B_INHARM = 1.5e-4
rng = np.random.default_rng(7)


def freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def piano(midi, dur=3.0, vol=0.62, decay_scale=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0 = freq(midi)
    # Lower notes ring longer, like the real thing.
    T0 = float(np.clip(3.2 * (110.0 / f0) ** 0.5, 1.6, 3.6)) * decay_scale
    sig = np.zeros(n)
    for k in range(1, 13):
        fk = k * f0 * np.sqrt(1 + B_INHARM * k * k)
        if fk > SR / 2 - 100:
            break
        ak = 1.0 / k ** 1.4
        Tk = T0 / (1 + 0.35 * (k - 1))
        sig += ak * np.sin(2 * np.pi * fk * t) * np.exp(-t / Tk)
        # brightness burst: high partials flare at the hammer strike
        if k >= 4:
            sig += 0.6 * ak * np.sin(2 * np.pi * fk * t) * np.exp(-t / 0.1)
    # hammer tick: a few ms of noise
    tick = rng.standard_normal(int(0.006 * SR))
    sig[:len(tick)] += 0.12 * tick * np.exp(-np.arange(len(tick)) / (0.002 * SR))
    sig /= np.max(np.abs(sig)) + 1e-9
    # 2 ms attack ramp (no click), gentle end fade
    sig[:int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    fade = int(0.15 * SR)
    sig[-fade:] *= np.linspace(1, 0, fade)
    return sig * vol


def stab(midis, dur=1.4, vol=0.6):
    sig = sum(piano(m, dur, 1.0, decay_scale=0.5) for m in midis)
    sig /= np.max(np.abs(sig)) + 1e-9
    return sig * vol


KIT = {
    "mel_b3.wav": 59, "mel_cs4.wav": 61, "mel_d4.wav": 62,
    "mel_e4.wav": 64, "mel_fs4.wav": 66, "mel_gs4.wav": 68,
    "hook_fs4.wav": 66, "hook_e4.wav": 64, "hook_gs4.wav": 68,
    "bass_fs1.wav": 42, "bass_e1.wav": 40, "bass_gs1.wav": 44,
}


def write_wav(path, sig):
    pcm = (np.clip(sig, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "web" / "samples"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, root in KIT.items():
        write_wav(out / name, piano(root))
        print("wrote", out / name, f"(piano, root MIDI {root})")
    write_wav(out / "stab_fsm.wav", stab([54, 57, 61]))
    print("wrote", out / "stab_fsm.wav", "(F#m piano stab)")


if __name__ == "__main__":
    main()
