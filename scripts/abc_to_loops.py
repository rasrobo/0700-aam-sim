#!/usr/bin/env python3
"""abc_to_loops.py — turn a published ABC score into loop samples, with no transcription.

Every previous attempt at a song went through a table I typed by hand, and every one of them
was wrong somewhere. This removes that step: music21 reads the score, the notes go to MIDI,
FluidSynth renders them with a General MIDI soundfont, and the result is cut into loops the
sampler can trigger.

    python3 scripts/abc_to_loops.py --abc rising --out web/samples-rising

The score is the arrangement. If it sounds wrong, the score is wrong — not a table.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SR = 48000
SF2 = "/usr/share/sounds/sf2/TimGM6mb.sf2"
PROG = {"drums": 0, "bass": 33, "chords": 16, "melody": 56, "pad": 48}
CHAN = {"drums": 9, "bass": 0, "chords": 1, "melody": 2, "pad": 3}

SCORES = {
    "rising": """X:1
T:House of the Rising Sun
M:6/8
L:1/8
K:Am
E2||"Am" A4 B2 |"C" c4 e2 |"D" d4 A2 |"F" c4 e2 |
"Am" A4 A2|"E" E4 E2 |"Am" A6 |"E" E6||
""",
    "saints": """X:18787
T:When the saints go marching in
L:1/4
K:C
z C E F |: "C" G4- | G C E F | G4- |
G C E F | G2 "Em/B" E2 | "Am" C2 "Dm" E2 |
"G7" D4- | D E E D | "C" C3 C | "C7" E2 G2 |
"F" G F3- | "Fm" F F E F | "C" G2 "Am" E2 |
"Dm7" C2 "G7" D2 | "C" C4- :|
""",
}


def chord_symbols(abc: str) -> list[str]:
    import re
    return re.findall(r'"([^"]+)"', abc)


def parse(abc: str):
    """Return (melody_events, chord_events, bars) with times in quarter lengths."""
    from music21 import converter
    s = converter.parse(abc, format="abc")
    part = s.parts[0]

    # melody: every note with its offset and duration, in quarter lengths
    mel = []
    for el in part.flatten().notes:
        if el.isChord:
            n = el.notes[0]
        else:
            n = el
        mel.append((float(el.offset), float(el.duration.quarterLength), n.pitch.midi))

    # chords: take the harmony symbols in order, one bar each
    syms = chord_symbols(abc)
    chords = []
    try:
        ts = s.recurse().getElementsByClass("TimeSignature")[0]
        bar_ql = ts.barDuration.quarterLength
    except Exception:
        bar_ql = 4.0
    for i, sym in enumerate(syms):
        chords.append((i * bar_ql, bar_ql, sym))
    return mel, chords, bar_ql


def render(events, part: str, out: Path, total: float, bpm: float):
    import fluidsynth
    out.unlink(missing_ok=True)
    fs = fluidsynth.Synth(samplerate=float(SR))
    fs.setting("audio.file.name", str(out))
    fs.setting("audio.file.type", "wav")
    fs.start(driver="file")
    sf = fs.sfload(SF2)
    ch = CHAN[part]
    if part != "drums":          # channel 10 is the GM drum kit
        fs.program_select(ch, sf, 0, PROG[part])

    ql_to_s = 60.0 / bpm
    # drum events carry their own velocity; melodic ones do not
    sched = []
    for ev in events:
        if len(ev) == 4:
            t, d, n, vel = ev
        else:
            t, d, n = ev
            vel = 96
        sched.append((t * ql_to_s, d * ql_to_s, n, vel))
    sched.sort()

    t0 = time.time()
    idx = 0
    pending: list[tuple[float, int]] = []
    while True:
        now = time.time() - t0
        if now >= total:
            break
        while idx < len(sched) and sched[idx][0] <= now:
            at, dur, note, vel = sched[idx]
            fs.noteon(ch, note, vel)
            pending.append((at + max(0.05, dur), note))
            idx += 1
        still = []
        for end, note in pending:
            if end <= now:
                fs.noteoff(ch, note)
            else:
                still.append((end, note))
        pending = still
        time.sleep(0.004)
    for _, note in pending:
        fs.noteoff(ch, note)
    time.sleep(0.12)
    fs.delete()


def drum_events(bars: int, bar_ql: float, swing: float = 0.5):
    ev = []
    for b in range(bars):
        base = b * bar_ql
        ev += [(base, 0.25, 36, 100), (base + bar_ql * 0.5, 0.25, 38, 92)]
        for i in range(int(bar_ql * 2)):
            ev.append((base + i * 0.5, 0.1, 42, 52))
    return ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", required=True, choices=sorted(SCORES))
    ap.add_argument("--bpm", type=float, default=100.0)
    ap.add_argument("--bars", type=int, default=0, help="bars to cut (0 = all)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    mel, chords, bar_ql = parse(SCORES[args.abc])
    total_ql = max(t + d for t, d, _ in mel)
    bars = args.bars or int(total_ql // bar_ql) or 1
    span_s = bars * bar_ql * 60.0 / args.bpm
    out = Path(args.out or f"web/samples-{args.abc}")
    out.mkdir(parents=True, exist_ok=True)

    # melody restricted to the cut
    cut_ql = bars * bar_ql
    mel = [(t, d, n) for t, d, n in mel if t < cut_ql]
    print(f"{args.abc}: {len(mel)} melody notes, {len(chords)} chords, "
          f"{bars} bars = {span_s:.1f}s at {args.bpm} BPM")

    # chords: render each symbol's triad as a sustained block
    from music21 import chord as m21chord
    chord_ev = []
    for t, d, sym in chords[:bars]:
        try:
            c = m21chord.Chord(sym)
        except Exception:
            continue
        for n in c.pitches:
            chord_ev.append((t, d * 0.9, n.midi))

    # bass: chord roots an octave down
    bass_ev = []
    for t, d, sym in chords[:bars]:
        try:
            c = m21chord.Chord(sym)
            root = c.root()
            if root is None:
                root = c.pitches[0]
        except Exception:
            continue
        bass_ev.append((t, d * 0.9, root.midi - 12))

    parts = {
        "drums": drum_events(bars, bar_ql),
        "bass": bass_ev,
        "chords": chord_ev,
        "melody": mel,
    }
    pads = {}
    for i, (name, ev) in enumerate(parts.items()):
        p = out / f"abc_{name}.wav"
        render(ev, name, p, span_s + 0.4, args.bpm)
        # trim to an exact loop length so layering cannot drift
        trimmed = out / f"abc_{name}_loop.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-t", f"{span_s:.3f}",
                        "-af", "afade=t=out:st=" + f"{span_s - 0.15:.3f}" + ":d=0.15",
                        str(trimmed)], check=True)
        pads[str(i)] = f"abc_{name}_loop"
        print(f"  pad {i+1}: {pads[str(i)]:16s} {span_s:.2f}s")

    (out / "manifest.json").write_text(
        '{"about":"Rendered directly from a published ABC score, no transcription.",'
        f'"pads":{__import__("json").dumps(pads)}}}')
    print(f"wrote {out}/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
