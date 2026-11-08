#!/usr/bin/env python3
"""abc_to_loops.py — render loop samples straight from a published ABC score.

No hand-written note tables. music21 reads the score, chords are placed by their absolute
offsets (not one per bar), the parts are rendered with FluidSynth + a GM soundfont, and the
result is cut on exact bar boundaries with identical lengths.

    python3 scripts/abc_to_loops.py --abc saints --bpm 120 --out web/samples-abc-saints

Parts:
  melody  trumpet (GM 56), straight from the score
  chords  organ (16), a short stab on beats 2 and 4
  bass    acoustic (33), root on beat 1 and fifth on beat 3 of every chord span
  drums   channel 10: kick 1 and 3, snare 2 and 4, swung eighths on the hat
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SR = 48000
SF2 = "/usr/share/sounds/sf2/TimGM6mb.sf2"
PROG = {"drums": 0, "bass": 33, "chords": 16, "melody": 56}
CHAN = {"drums": 9, "bass": 0, "chords": 1, "melody": 2}

SCORES = {
    "saints": """X:18787
T:When the saints go marching in
M:4/4
L:1/4
K:C
z C E F |: "C" G4- | G C E F | G4- |
G C E F | G2 "Em/B" E2 | "Am" C2 "Dm" E2 |
"G7" D4- | D E E D | "C" C3 C | "C7" E2 G2 |
"F" G F3- | "Fm" F F E F | "C" G2 "Am" E2 |
"Dm7" C2 "G7" D2 | "C" C4- :|
""",
    "rising": """X:1
T:House of the Rising Sun
M:6/8
L:1/8
K:Am
E2||"Am" A4 B2 |"C" c4 e2 |"D" d4 A2 |"F" c4 e2 |
"Am" A4 A2|"E" E4 E2 |"Am" A6 |"E" E6||
""",
}


def read_score(abc: str):
    """(melody[(ql_offset, ql_dur, midi)], chords[(ql_offset, ql_dur, symbol)], bar_ql)."""
    from music21 import converter, harmony
    s = converter.parse(abc, format="abc")
    part = s.parts[0]

    mel = []
    for el in part.recurse().notes:
        n = el.notes[0] if el.isChord else el
        ql = float(el.duration.quarterLength)
        if ql <= 0.05:
            continue          # chord symbols and grace artefacts, not melody
        mel.append((float(el.getOffsetInHierarchy(s)), ql, n.pitch.midi))

    syms = [(float(c.getOffsetInHierarchy(s)), c.figure)
            for c in part.recurse().getElementsByClass(harmony.ChordSymbol)]
    syms.sort()
    chords = []
    for i, (off, fig) in enumerate(syms):
        nxt = syms[i + 1][0] if i + 1 < len(syms) else float(part.highestTime)
        chords.append((off, nxt - off, fig))

    try:
        ts = s.recurse().getElementsByClass("TimeSignature")[0]
        bar_ql = float(ts.barDuration.quarterLength)
    except Exception:
        bar_ql = 4.0
    return mel, chords, bar_ql


def chord_notes(fig: str) -> list[int]:
    from music21 import harmony
    clean = fig.split("/")[0]          # the slash bass is not a chord tone
    try:
        return [p.midi for p in harmony.ChordSymbol(clean).pitches]
    except Exception:
        return []


def build_parts(mel, chords, bar_ql, bars):
    cut = bars * bar_ql
    melody = [(t, d, n) for t, d, n in mel if t < cut]

    chord_ev, bass_ev = [], []
    for off, dur, fig in chords:
        if off >= cut:
            continue
        notes = chord_notes(fig)
        if not notes:
            continue
        dur = min(dur, cut - off)
        root = min(notes) - 12
        span = int(dur // bar_ql) + 1
        for b in range(span):
            base = off + b * bar_ql
            for beat in (1.0, 3.0):                 # stabs on 2 and 4
                if base + beat < off + dur and base + beat < cut:
                    for n in notes:
                        chord_ev.append((base + beat, 0.4, n))
            if base < off + dur and base < cut:     # bass root
                bass_ev.append((base, 0.9, root))
            if base + 2 < off + dur and base + 2 < cut:
                bass_ev.append((base + 2, 0.9, root + 7))

    drums = []
    for b in range(bars):
        base = b * bar_ql
        drums += [(base, 0.25, 36, 100), (base + 2, 0.25, 36, 96),
                  (base + 1, 0.25, 38, 92), (base + 3, 0.25, 38, 92)]
        for i in range(int(bar_ql * 2)):
            swing = 0.0 if i % 2 == 0 else 0.08
            drums.append((base + i * 0.5 + swing, 0.1, 42, 50))
    return {"drums": drums, "bass": bass_ev, "chords": chord_ev, "melody": melody}


def render(events, part: str, out: Path, total_s: float, ql_to_s: float):
    import fluidsynth
    out.unlink(missing_ok=True)
    fs = fluidsynth.Synth(samplerate=float(SR))
    fs.setting("audio.file.name", str(out))
    fs.setting("audio.file.type", "wav")
    fs.start(driver="file")
    sf = fs.sfload(SF2)
    ch = CHAN[part]
    if part != "drums":
        fs.program_select(ch, sf, 0, PROG[part])

    sched = []
    for ev in events:
        if len(ev) == 4:
            t, d, n, vel = ev
        else:
            t, d, n = ev
            vel = 96
        sched.append((t * ql_to_s, d * ql_to_s, n, vel))
    sched.sort()

    t0, idx, pending = time.time(), 0, []
    while True:
        now = time.time() - t0
        if now >= total_s:
            break
        while idx < len(sched) and sched[idx][0] <= now:
            at, dur, note, vel = sched[idx]
            fs.noteon(ch, note, vel)
            pending.append((at + max(0.06, dur), note))
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", required=True, choices=sorted(SCORES))
    ap.add_argument("--bpm", type=float, default=120.0)
    ap.add_argument("--bars", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    mel, chords, bar_ql = read_score(SCORES[args.abc])
    total_bars = int(max(t + d for t, d, _ in mel) // bar_ql)
    bars = args.bars or total_bars
    ql_to_s = 60.0 / args.bpm
    loop_s = bars * bar_ql * ql_to_s

    out = Path(args.out or f"web/samples-abc-{args.abc}")
    out.mkdir(parents=True, exist_ok=True)
    parts = build_parts(mel, chords, bar_ql, bars)
    print(f"{args.abc}: {len(mel)} melody notes, {len(chords)} chords, "
          f"{bars} bars = {loop_s:.2f}s at {args.bpm:g} BPM")

    pads = {}
    for i, (name, ev) in enumerate(parts.items()):
        raw = out / f"abc_{name}.wav"
        render(ev, name, raw, loop_s + 0.5, ql_to_s)
        loop = out / f"abc_{name}_loop.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw),
                        "-t", f"{loop_s:.4f}",
                        "-af", f"afade=t=out:st={loop_s - 0.12:.3f}:d=0.12", str(loop)],
                       check=True)
        pads[str(i)] = f"abc_{name}_loop"
        print(f"  pad {i+1}: {pads[str(i)]:18s} {loop_s:.2f}s")

    (out / "manifest.json").write_text(json.dumps({
        "about": "Rendered directly from a published ABC score: music21 -> MIDI -> FluidSynth.",
        "pads": pads, "bars": bars, "bar_ql": bar_ql, "bpm": args.bpm,
    }, indent=2))
    print(f"wrote {out}/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
