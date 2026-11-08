#!/usr/bin/env python3
"""test_tune_render.py — independent checks on a rendered score loop.

Four checks, none of which trusts the renderer:

  1. OPENING   a hard-coded reference written from the tune (not read from the ABC) must
               match the audio, octave included.
  2. NOTES     the ABC-derived notes must appear in the audio with pitch and onset tolerance
               (+/- 80 ms). Reports precision and recall at note level, not one note per bar.
  3. CHORDS    chroma of the chord loop must agree with the chord symbol at each beat.
  4. OCTAVE    the same matcher must FAIL when the reference is shifted an octave — a check
               that cannot fail is not a check.

    python3 scripts/test_tune_render.py --abc saints --dir web/samples-abc-saints
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

TOL_S = 0.080          # ±80 ms
SCORE_THRESHOLD = 0.90

# Reference melodies written from the tune itself, independent of the ABC files.
# Pitches are scientific pitch notation, octave included.
OPENING = {
    # "oh when the saints (C E F) go marching in (G held)" twice: a held note is one
    # onset, so the gesture is eight notes, not nine
    "saints": ["C4", "E4", "F4", "G4", "C4", "E4", "F4", "G4"],
    "rising": ["A4", "B4", "C5", "E5", "D5", "A4", "C5", "E5"],
}


def detect_notes(path: Path, fmin=90, fmax=1600):
    """(onset seconds, duration seconds, midi) for each stable pitch in the audio."""
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    f0, voiced, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=2048)
    times = librosa.times_like(f0, sr=sr)
    hop = float(times[1] - times[0]) if len(times) > 1 else 0.01

    import librosa as _lr
    onsets = _lr.onset.onset_detect(y=y, sr=sr, units="time", backtrack=False)
    notes = []
    for on in onsets:
        sel = (times >= on) & (times < on + 0.30)
        vals = f0[sel & voiced]
        vals = vals[~np.isnan(vals)]
        if not len(vals):
            continue
        m = int(round(69 + 12 * np.log2(float(np.median(vals)) / 440)))
        notes.append((float(on), 0.0, m))
    return notes


def score_notes(abc: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "abc_to_loops", Path(__file__).with_name("abc_to_loops.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mel, chords, bar_ql = mod.read_score(mod.SCORES[abc])
    return mel, chords, bar_ql, mod


def estimate_latency(expected, detected):
    """Median offset between a detected note and the nearest score note of the same pitch.

    The renderer plus pyin introduce a constant delay (measured ~110 ms). That is latency,
    not a wrong note, so it is measured and removed before scoring rather than hidden by
    widening the tolerance.
    """
    deltas = []
    for t, d, m in expected:
        same = [(dt, dm) for dt, dd, dm in detected if dm == m]
        if same:
            dt = min(same, key=lambda x: abs(x[0] - t))[0]
            deltas.append(dt - t)
    return float(np.median(deltas)) if deltas else 0.0


def match(expected, detected, tol=TOL_S):
    """Precision/recall on (onset, midi) with a time tolerance."""
    used = set()
    tp = 0
    for t, d, m in expected:
        for i, (dt, dd, dm) in enumerate(detected):
            if i in used:
                continue
            if dm == m and abs(dt - t) <= tol:
                used.add(i)
                tp += 1
                break
    precision = tp / max(1, len(detected))
    recall = tp / max(1, len(expected))
    return precision, recall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", required=True, choices=sorted(OPENING))
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()

    d = Path(args.dir)
    import json as _json
    man = _json.loads((d / "manifest.json").read_text()) if (d / "manifest.json").exists() else {}
    BPM = float(man.get("bpm", 120.0))
    mel_loop = d / "abc_melody_loop.wav"
    chord_loop = d / "abc_chords_loop.wav"
    if not mel_loop.exists():
        print(f"missing {mel_loop}")
        return 2

    mel, chords, bar_ql, mod = score_notes(args.abc)
    detected = detect_notes(mel_loop)
    print(f"detected {len(detected)} notes in {mel_loop.name}")

    # ---- 1. opening, hard-coded reference ------------------------------------
    import librosa
    ref = [librosa.note_to_midi(n) for n in OPENING[args.abc]]
    got = [m for _, _, m in detected][:len(ref)]
    hits = sum(1 for a, b in zip(ref, got) if a == b)
    open_frac = hits / len(ref)
    print(f"\n1. OPENING  reference {OPENING[args.abc]}")
    print(f"   detected  {[librosa.midi_to_note(m, unicode=False) for m in got]}")
    print(f"   match {hits}/{len(ref)} = {open_frac*100:.0f}%")

    # ---- 2. note-level precision / recall -----------------------------------
    ql_to_s = 60.0 / BPM
    expected = [(t * ql_to_s, dd * ql_to_s, m) for t, dd, m in mel]
    lat = estimate_latency(expected, detected)
    print(f"   measured render+detect latency: {lat*1000:+.0f} ms (removed before matching)")
    expected = [(t + lat, dd, m) for t, dd, m in expected]
    p, r = match(expected, detected)
    f1 = 2 * p * r / max(1e-9, p + r)
    print(f"\n2. NOTES    score {len(expected)} | detected {len(detected)}")
    print(f"   precision {p*100:.0f}%  recall {r*100:.0f}%  F1 {f1*100:.0f}%")

    # ---- 3. chords vs chroma per beat ---------------------------------------
    import librosa
    y, sr = librosa.load(str(chord_loop), sr=22050, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    beat_s = 60.0 / BPM
    n_beats = int(len(y) / sr / beat_s)
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    ok = 0
    for b in range(n_beats):
        seg = chroma[:, int(b * beat_s * sr / 512):int((b + 1) * beat_s * sr / 512)]
        if seg.size == 0:
            continue
        pc = int(np.argmax(seg.mean(axis=1)))
        t_ql = b  # one beat = one quarter length
        sym = None
        for off, dur, fig in chords:
            if off <= t_ql < off + dur:
                sym = fig
        if sym is None:
            continue
        root = sym.split("/")[0][0]
        if root == names[pc]:
            ok += 1
    print(f"\n3. CHORDS   beat-level root agreement {ok}/{n_beats} = {100*ok/max(1,n_beats):.0f}%")

    # ---- 4. the octave test: this must fail --------------------------------
    shifted = [(t, dd, m + 12) for t, dd, m in expected]
    p2, r2 = match(shifted, detected)
    print(f"\n4. OCTAVE   same audio vs reference +12 semitones: "
          f"precision {p2*100:.0f}% recall {r2*100:.0f}% (must be low)")

    # ---- verdict -----------------------------------------------------------
    gates = [
        ("opening", open_frac, SCORE_THRESHOLD),
        ("notes F1", f1, SCORE_THRESHOLD),
        ("chords", ok / max(1, n_beats), 0.70),
        ("octave test fails", 1.0 - r2, 0.80),
    ]
    print("\n| gate | measured | threshold | result |")
    print("|---|---|---|---|")
    failed = 0
    for name, value, thr in gates:
        good = value >= thr
        failed += 0 if good else 1
        print(f"| {name} | {value*100:.0f}% | {thr*100:.0f}% | {'PASS' if good else 'FAIL'} |")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
