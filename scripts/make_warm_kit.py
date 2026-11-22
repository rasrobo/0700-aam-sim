#!/usr/bin/env python3
"""make_warm_kit.py — render the bundled kit's pitched samples as warm,
sustained synth voices, replacing the original placeholder blips.

Why: the shipped melodic samples were 0.5 s dry blips with a flat envelope,
and the bass samples peaked around -24 dB under the melody. One-shot blips
are fine for drums, but a keygroup source gets pitched across two octaves —
a blip stretched that far sounds broken, and every song built on it sounds
broken too. These renders are the voices that proved themselves in the
Canon in D session: fundamental-forward so pitch reads clearly, a real
ADSR with sustain, gentle vibrato and detune for warmth, and matched levels.

    python3 scripts/make_warm_kit.py            # writes into web/samples/
    python3 scripts/make_warm_kit.py --out DIR  # render somewhere else

Drum samples (kick/snare/hats/clap) are NOT touched — they were fine.
Format matches the kit: 48 kHz, mono, 16-bit WAV, same filenames and the
same root notes as web/samples/manifest.json.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

SR = 48000


def freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def adsr(n, a=0.02, d=0.1, s=0.8, r=0.35):
    env = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    if na:
        env[:na] = np.linspace(0, 1, na)
    if nd:
        env[na:na + nd] = np.linspace(1, s, nd)
    if nr:
        env[-nr:] *= np.linspace(1, 0, nr)
    return env


def lowpass(sig, cutoff):
    return lfilter([cutoff], [1, -(1 - cutoff)], sig)


def vibrato_phase(t, f, cents=5.0, rate=5.0, delay=0.3):
    """Phase for an oscillator with vibrato that fades in after `delay` s."""
    depth = cents / 1200.0
    vib = np.where(t > delay, depth * (1 - np.exp(-(t - delay) / 0.4)), 0.0)
    return 2 * np.pi * f * t + 2 * np.pi * f * np.cumsum(vib * np.sin(2 * np.pi * rate * t)) / SR


def lead(midi, dur=3.0, vol=0.8):
    """Warm sustained lead: fundamental-forward, detuned saw layer, vibrato.
    3 s long so keygroup pitches up to +11 semitones still ring > 1.4 s."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq(midi)
    ph = vibrato_phase(t, f)
    sig = 0.9 * np.sin(ph) + 0.2 * np.sin(2 * ph)
    saw = 2 * ((ph / (2 * np.pi)) % 1) - 1
    sig += 0.45 * saw
    # detuned second saw, summed to mono = slow chorus warmth
    ph2 = vibrato_phase(t, f * 2 ** (6 / 1200.0))
    sig += 0.22 * (2 * ((ph2 / (2 * np.pi)) % 1) - 1)
    sig = lowpass(sig, 0.22)
    sig /= np.max(np.abs(sig)) + 1e-9
    return sig * adsr(n, a=0.02, d=0.12, s=0.78, r=0.5) * vol


def pluck(midi, dur=1.8, vol=0.75):
    """Brighter hook/arp voice: faster decay, more saw."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq(midi)
    ph = vibrato_phase(t, f, cents=3.0)
    sig = 0.8 * np.sin(ph) + 0.55 * (2 * ((ph / (2 * np.pi)) % 1) - 1) + 0.15 * np.sin(2 * ph)
    sig = lowpass(sig, 0.3)
    sig /= np.max(np.abs(sig)) + 1e-9
    return sig * adsr(n, a=0.005, d=0.25, s=0.35, r=0.3) * vol


def bass(midi, dur=2.4, vol=0.9):
    """Round bass: sine + a touch of 2nd harmonic, long sustain, real level."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq(midi)
    sig = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) + 0.1 * np.sin(2 * np.pi * 3 * f * t)
    sig = lowpass(sig, 0.12)
    sig /= np.max(np.abs(sig)) + 1e-9
    return sig * adsr(n, a=0.01, d=0.1, s=0.82, r=0.25) * vol


def stab(midis, dur=0.9, vol=0.8):
    """Chord stab: the lead voice summed over the triad, quick decay."""
    sig = sum(lead(m, dur, 1.0) for m in midis)
    n = len(sig)
    sig = sig / (np.max(np.abs(sig)) + 1e-9)
    return sig * adsr(n, a=0.005, d=0.2, s=0.3, r=0.25) * vol


# filename -> (voice, root midi) — roots identical to manifest.json
KIT = {
    "mel_b3.wav":   (lead, 59),
    "mel_cs4.wav":  (lead, 61),   # the keygroup workhorse
    "mel_d4.wav":   (lead, 62),
    "mel_e4.wav":   (lead, 64),
    "mel_fs4.wav":  (lead, 66),
    "mel_gs4.wav":  (lead, 68),
    "hook_fs4.wav": (pluck, 66),
    "hook_e4.wav":  (pluck, 64),
    "hook_gs4.wav": (pluck, 68),
    "bass_fs1.wav": (bass, 42),
    "bass_e1.wav":  (bass, 40),
    "bass_gs1.wav": (bass, 44),
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
    for name, (voice, root) in KIT.items():
        write_wav(out / name, voice(root))
        print("wrote", out / name, f"(root MIDI {root})")
    write_wav(out / "stab_fsm.wav", stab([54, 57, 61]))  # F#m triad, root 54
    print("wrote", out / "stab_fsm.wav", "(F#m stab)")


if __name__ == "__main__":
    main()
