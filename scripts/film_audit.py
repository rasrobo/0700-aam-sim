#!/usr/bin/env python3
"""film_audit.py — test what is actually audible in the delivered film.

Loop-level checks passed while the films still did not sound like the song, so this measures
the deliverables instead: the audition pack, the melody's presence in the film, per-part
loudness, loop restarts and a note-by-note rhythm table.

    python3 scripts/film_audit.py --abc saints --loops web/samples-abc-saints3 \
        --film /path/saints_film.mp4 --out /path/audition_saints
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100


def load_mod():
    spec = importlib.util.spec_from_file_location(
        "abc_to_loops", Path(__file__).with_name("abc_to_loops.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sh(cmd):
    subprocess.run(cmd, check=True)


def rms_db(path: Path) -> float:
    import librosa
    y, _ = librosa.load(str(path), sr=SR, mono=True)
    return float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-12))


def stack(parts: list[Path], out: Path, seconds: float):
    inputs = []
    for p in parts:
        inputs += ["-i", str(p)]
    n = len(parts)
    flt = "".join(f"[{i}:a]" for i in range(n)) + f"amix=inputs={n}:duration=shortest:normalize=0"
    sh(["ffmpeg", "-v", "error", "-y"] + inputs +
       ["-filter_complex", flt, "-t", f"{seconds}", "-b:a", "192k", str(out)])


def melody_notes(path: Path, limit: float | None = None):
    """Onset-anchored pitch detection, octave included."""
    import librosa
    kw = {"duration": limit} if limit else {}
    y, sr = librosa.load(str(path), sr=22050, mono=True, **kw)
    # on a full mix pyin locks onto the bass, so the signal is band-limited to the melody's
    # register first; otherwise the film appears to contain no melody at all
    from scipy.signal import butter, lfilter
    b, a = butter(4, [250 / (sr / 2), 1300 / (sr / 2)], btype="band")
    yb = lfilter(b, a, y).astype(np.float32)
    f0, voiced, _ = librosa.pyin(yb, fmin=250, fmax=1300, sr=sr, frame_length=2048)
    t = librosa.times_like(f0, sr=sr)
    onsets = librosa.onset.onset_detect(y=yb, sr=sr, units="time", backtrack=False)
    out = []
    for on in onsets:
        sel = (t >= on) & (t < on + 0.30) & voiced
        v = f0[sel]
        v = v[~np.isnan(v)]
        if len(v):
            m = int(round(69 + 12 * np.log2(float(np.median(v)) / 440)))
            out.append((float(on), m))
    return out, y, sr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", required=True, choices=["saints", "rising"])
    ap.add_argument("--loops", required=True)
    ap.add_argument("--film", required=True)
    ap.add_argument("--film-mp3", default=None, help="final delivered mp3")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    mod = load_mod()
    loops = Path(args.loops)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads((loops / "manifest.json").read_text())
    bpm = float(man.get("bpm", 120.0))
    ql = 60.0 / bpm

    # ---- 1. audition pack -----------------------------------------------------
    from music21 import converter
    mid = out / f"1_score_midi.mid"
    s = converter.parse(mod.SCORES[args.abc], format="abc").stripTies()
    s.write("midi", fp=str(mid))

    parts = {k: loops / f"abc_{k}_loop.wav" for k in ("melody", "chords", "bass", "drums")}
    stack([parts["melody"]], out / "2_melody_only.mp3", 20)
    stack([parts["melody"], parts["bass"]], out / "3_melody_bass.mp3", 20)
    stack([parts["melody"], parts["chords"]], out / "4_melody_chords.mp3", 20)
    stack([parts["melody"], parts["drums"]], out / "5_melody_drums.mp3", 20)
    stack(list(parts.values()), out / "6_full_loop.mp3", 20)

    film_src = Path(args.film_mp3) if args.film_mp3 else Path(args.film)
    notes, y, sr = melody_notes(film_src)
    first = notes[0][0] if notes else 0.0
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, first - 1.0):.2f}", "-t", "20",
        "-i", str(film_src), "-b:a", "192k", str(out / "7_film_first_20s_of_melody_entry.mp3")])

    # ---- 2. film audit -------------------------------------------------------
    total_s = len(y) / sr
    audible = sum(1 for t, m in notes if t < total_s)
    print(f"film duration {total_s:.1f}s | first melody note at {first:.2f}s | "
          f"{audible} melody notes detected")

    # note-level F1 against the score, latency removed
    mel, chords, bar_ql = mod.read_score(mod.SCORES[args.abc])
    expected = [(t * ql, d * ql, m) for t, d, m in mel]
    got = [(t, m) for t, m in notes]
    lat = 0.0
    if expected and got:
        deltas = []
        for t, d, m in expected:
            same = [gt for gt, gm in got if gm == m]
            if same:
                deltas.append(min(same, key=lambda x: abs(x - t)) - t)
        lat = float(np.median(deltas)) if deltas else 0.0
    # the melody enters partway through a film, so the score is slid across the timeline
    # and the best alignment is reported — comparing against t=0 scored 0% on a correct film
    best = (-1.0, 0.0)
    for cand in np.arange(0.0, max(1.0, total_s - 5.0), 0.25):
        used_c, tp_c = set(), 0
        for t, d, m in expected:
            for i, (gt, gm) in enumerate(got):
                if i in used_c:
                    continue
                if gm == m and abs(gt - (t + cand + lat)) <= 0.080:
                    used_c.add(i)
                    tp_c += 1
                    break
        pr = tp_c / max(1, len(got))
        rc = tp_c / max(1, len(expected))
        f = 2 * pr * rc / max(1e-9, pr + rc)
        if f > best[0]:
            best = (f, cand)
    entry = best[1]
    used, tp = set(), 0
    for t, d, m in expected:
        for i, (gt, gm) in enumerate(got):
            if i in used:
                continue
            if gm == m and abs(gt - (t + entry + lat)) <= 0.080:
                used.add(i)
                tp += 1
                break
    precision = tp / max(1, len(got))
    recall = tp / max(1, len(expected))
    f1 = 2 * precision * recall / max(1e-9, precision + recall)

    # ---- 3. loudness per part ------------------------------------------------
    lv = {k: rms_db(v) for k, v in parts.items() if v.exists()}
    loud = sorted(lv.items(), key=lambda kv: -kv[1])
    melody_lvl = lv.get("melody", -99)
    next_loud = max([v for k, v in lv.items() if k != "melody"] or [-99])

    # ---- 4. loop restarts ----------------------------------------------------
    # loop restarts: gaps in the melody longer than one phrase
    restarts, prev = [], None
    for t, m in notes:
        if prev is not None and t - prev > 12.0:
            restarts.append(round(t, 1))
        prev = t

    print("\n| item | value |")
    print("|---|---|")
    print(f"| film length | {total_s:.1f} s |")
    print(f"| first melody note | {first:.2f} s |")
    print(f"| melody notes detected | {audible} |")
    print(f"| latency removed | {lat*1000:+.0f} ms |")
    print(f"| melody entry in film | {entry:.1f} s |")
    print(f"| film note F1 vs score | {f1*100:.0f}% (P {precision*100:.0f} / R {recall*100:.0f}) |")
    for k in ("melody", "bass", "chords", "drums"):
        if k in lv:
            print(f"| {k} RMS | {lv[k]:.1f} dBFS |")
    print(f"| melody vs next-loudest | {melody_lvl - next_loud:+.1f} dB "
          f"({'OK' if melody_lvl - next_loud >= 3 else 'TOO QUIET'}) |")
    print(f"| loop restarts | {restarts if restarts else 'none detected'} |")

    # ---- 5. rhythm table, first 24 ------------------------------------------
    print("\n| # | score onset | film onset | err ms | score dur | render dur |")
    print("|---|---|---|---|---|---|")
    for i, (t, d, m) in enumerate(expected[:24]):
        match = next(((gt, gm) for gt, gm in got if gm == m and abs(gt - (t + entry + lat)) <= 0.08), None)
        if match:
            print(f"| {i+1} | {t:.2f} | {match[0]:.2f} | {(match[0]-t-entry-lat)*1000:+.0f} | {d:.2f} | — |")
        else:
            print(f"| {i+1} | {t:.2f} | — | — | {d:.2f} | — |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
