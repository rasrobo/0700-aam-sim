#!/usr/bin/env python3
"""diagnose_tune.py — produce listening artefacts and a rhythm table for a rendered tune.

When "the gates pass but it does not sound like the song", the problem is in a part, not in
the notes. This emits, from the same loops the sampler plays:

  1. a MIDI file of the parsed score, so the score itself can be auditioned anywhere
  2. one short mp3 per part (melody alone, melody+chords, melody+bass, full mix)
  3. a table of score onset times vs the onset times detected in the render, with the
     mean and worst timing error and the note count on each side

    python3 scripts/diagnose_tune.py --abc saints --dir web/samples-abc-saints2 --out /tmp/diag
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np

SR = 48000


def load_module():
    spec = importlib.util.spec_from_file_location(
        "abc_to_loops", Path(__file__).with_name("abc_to_loops.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_midi(abc: str, out: Path):
    from music21 import converter
    s = converter.parse(abc, format="abc").stripTies()
    s.write("midi", fp=str(out))
    return len(list(s.recurse().notes))


def mix_parts(paths: list[Path], out: Path, seconds: float):
    inputs = []
    for p in paths:
        inputs += ["-i", str(p)]
    n = len(paths)
    flt = "".join(f"[{i}:a]" for i in range(n)) + f"amix=inputs={n}:duration=shortest:normalize=0"
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs +
                   ["-filter_complex", flt, "-t", f"{seconds}", "-b:a", "192k", str(out)],
                   check=True)


def onsets(path: Path, limit_s: float):
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True, duration=limit_s)
    return librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", required=True, choices=["saints", "rising"])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default="/tmp/diag")
    ap.add_argument("--seconds", type=float, default=20.0)
    args = ap.parse_args()

    mod = load_module()
    d = Path(args.dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads((d / "manifest.json").read_text())
    bpm = float(man.get("bpm", 120.0))

    # 1. the score as MIDI
    mid = out / f"{args.abc}_{int(bpm)}bpm.mid"
    n_notes = write_midi(mod.SCORES[args.abc], mid)
    print(f"score MIDI : {mid}  ({n_notes} notes, {bpm:g} BPM)")

    # 2. isolated parts
    parts = {k: d / f"abc_{k}_loop.wav" for k in ("melody", "chords", "bass", "drums")}
    stacks = {
        "1_melody_only": [parts["melody"]],
        "2_melody_chords": [parts["melody"], parts["chords"]],
        "3_melody_bass": [parts["melody"], parts["bass"]],
        "4_full_mix": [parts["melody"], parts["chords"], parts["bass"], parts["drums"]],
    }
    for name, ps in stacks.items():
        if not all(p.exists() for p in ps):
            continue
        mp3 = out / f"{args.abc}_{name}.mp3"
        mix_parts(ps, mp3, args.seconds)
        print(f"  {mp3.name:28s} {', '.join(p.stem.replace('abc_','').replace('_loop','') for p in ps)}")

    # 3. rhythm table
    mel, chords, bar_ql = mod.read_score(mod.SCORES[args.abc])
    ql_to_s = 60.0 / bpm
    score_on = np.array([t * ql_to_s for t, _, _ in mel if t * ql_to_s < args.seconds])
    audio_on = np.array(onsets(parts["melody"], args.seconds))
    n = min(len(score_on), len(audio_on))
    if n:
        err = (audio_on[:n] - score_on[:n]) * 1000
        print(f"\nmelody onsets: score {len(score_on)} | render {len(audio_on)} "
              f"| compared {n}")
        print(f"timing error: mean {err.mean():+.0f} ms, "
              f"median {np.median(err):+.0f} ms, worst {np.abs(err).max():.0f} ms")
        print("first 10 (score_s, render_s, delta_ms):")
        for i in range(min(10, n)):
            print(f"  {score_on[i]:5.2f}  {audio_on[i]:5.2f}  {err[i]:+6.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
