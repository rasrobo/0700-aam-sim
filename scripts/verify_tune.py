#!/usr/bin/env python3
"""verify_tune.py — check a rendered melody against a published lead sheet.

This is the checks-and-balances step for any song the simulator plays. The reference comes
from a published ABC score (parsed with music21), the pitches come from an audio file, and
the comparison searches transpositions so a legitimate key change is not scored as an error.

    python3 scripts/verify_tune.py --abc rising --audio web/samples-rising/gm_melody_loop.wav

Exit code is 0 only when the best transposition matches enough of the score.

Why transposition search: a tune is a sequence of intervals. If everything is shifted by a
constant, the melody is still correct — it is just in another key. The check reports the
shift it found, so a wrong melody and a transposed-correct melody are different results.

Requires: music21, numpy, librosa (pip install music21 numpy librosa)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Published scores, embedded so the check works offline. Both are traditional tunes; the
# sheet is the reference, not this file.
SCORES = {
    "rising": {
        "source": "https://englishtap.co.uk/music/abc-notation-files/"
                  "abc-guitar-house-of-the-rising-sun.abc",
        "abc": """X:1
T:House of the Rising Sun
M:6/8
L:1/8
K:C
E2||"Am" A4 B2 |"C" c4 e2 |"D" d4 A2 |"F" c4 e2 |
"Am" A4 A2|"E" E4 E2 |"Am" A6 |"E" E6||
""",
        "bars_per_cycle": 8,
        "counts": 8,          # one long note per bar
    },
    "saints": {
        "source": "https://demodb.org/en/songs/when_the_saints_go_marching_in",
        "abc": """X:18787
T:When the saints go marching in
L:1/4
K:C
z C E F |: "C" G4- | G C E F | G4- |
G C E F | G2 "Em/B" E2 | "Am" C2 "Dm" E2 |
"G7" D4- | D E E D | "C" C3 C | "C7" E2 G2 |
"F" G F3- | "Fm" F F E F | "C" G2 "Am" E2 |
"Dm7" C2 "G7" D2 | "C" C4- :|
""",
        "bars_per_cycle": 8,
        "counts": 8,
    },
}


def score_notes(spec: dict) -> list[str]:
    """Melody notes from the score, one per bar (the note that carries the bar)."""
    from music21 import converter
    s = converter.parse(spec["abc"], format="abc")
    part = s.parts[0]
    from music21 import stream, note, chord, meter
    out: list[str] = []
    # group by measure and take the longest-pitched note in each
    # an ABC pickup ("E2||") makes the first measure short; drop it or every bar is off by one
    flat = part.flatten().notes
    measures: dict[int, list] = {}
    for el in flat:
        measures.setdefault(el.measureNumber, []).append(el)
    full = max(sum(x.duration.quarterLength for x in v) for v in measures.values())
    measures = {m: v for m, v in measures.items()
                if sum(x.duration.quarterLength for x in v) >= full * 0.9}
    for m in sorted(measures):
        best = None
        for el in measures[m]:
            cands = [el] if isinstance(el, note.Note) else (
                list(el.notes) if isinstance(el, chord.Chord) else [])
            for c in cands:
                if best is None or c.duration.quarterLength > best.duration.quarterLength:
                    best = c
        if best is not None:
            out.append(best.nameWithOctave)
    return out


def audio_pitches(path: Path, count: int) -> list[str]:
    """Fundamental pitch per bar, using pyin.

    A plain FFT peak picks harmonics: a C5 sung by an organ has more energy at C6 than at
    C5, and the first version of this check reported the melody a twelfth too high. pyin is
    built for monophonic fundamental tracking, so it reports the note that was written.
    """
    import librosa
    import numpy as np
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    f0, voiced, _ = librosa.pyin(y, fmin=100, fmax=1200, sr=sr, frame_length=2048)
    times = librosa.times_like(f0, sr=sr)
    span = (len(y) / sr) / count
    out = []
    for i in range(count):
        sel = (times >= i * span) & (times < (i + 1) * span) & voiced
        vals = f0[sel]
        vals = vals[~np.isnan(vals)]
        if not len(vals):
            continue
        hz = float(np.median(vals))
        midi = int(round(librosa.hz_to_midi(hz)))
        out.append(librosa.midi_to_note(midi, unicode=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", required=True, choices=sorted(SCORES))
    ap.add_argument("--audio", required=True)
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="fraction of bars that must pitch-match at the best transposition")
    args = ap.parse_args()

    spec = SCORES[args.abc]
    from music21 import interval, note

    expected = score_notes(spec)[: spec["counts"]]
    got = audio_pitches(Path(args.audio), spec["counts"])
    if not got:
        print("no pitches found in the audio")
        return 2

    print(f"score   ({spec['source']})")
    print(f"  {args.abc}: {' '.join(expected)}")
    print(f"audio   {Path(args.audio).name}")
    print(f"  detected: {' '.join(got)}")

    best = (-1.0, 0)
    n = min(len(expected), len(got))
    for shift in range(-12, 13):
        hits = 0
        for i in range(n):
            want = note.Note(expected[i]).transpose(shift)
            # compare the actual pitch, not the pitch class: .name drops the octave, so an
            # A3 against an A4 was scoring as a match and hiding an octave error
            if want.nameWithOctave == note.Note(got[i]).nameWithOctave:
                hits += 1
        score = hits / n
        if score > best[0]:
            best = (score, shift)

    frac, shift = best
    same_key = shift == 0
    print(f"\nbest transposition: {shift:+d} semitones "
          f"({'as written' if same_key else 'transposed'})")
    print(f"bar matches: {frac * 100:.0f}%  (need {args.threshold * 100:.0f}%)")
    ok = frac >= args.threshold
    print("PASS — the melody matches the published score" if ok else "FAIL — does not match")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
