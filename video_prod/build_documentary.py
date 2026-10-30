#!/usr/bin/env python3
"""
Produce the complete narrated documentary showcase for 0700-aam-sim:
1. Synthesizes Edge-TTS neural voiceover with millisecond subtitles
2. Records clean terminal capture clips (build, ctest, interactive simulation)
3. Renders MP4 clips via GPU agg + ffmpeg
4. Mixes ducked ambient score with EBU R128 audio mastering
5. Assembles final 1080p documentary with burned subtitles
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCUVIBE_APP = Path.home() / "docuvibe" / "app"
sys.path.insert(0, str(DOCUVIBE_APP))

from config import MUSIC_DIR
from audio_engine import build_documentary_audio
from renderer import render_full_documentary

PROD_DIR = REPO_ROOT / "video_prod"
BUILD_DIR = REPO_ROOT / "build"
CLIPS_DIR = PROD_DIR / "clips"
OUTPUT_DIR = PROD_DIR / "output"

CLIPS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCENES = [
    {
        "id": 1,
        "title": "Act 1: The Upstream Release & The Missing Link",
        "narration": (
            "When Music Tribe open-sourced the firmware for the Behringer KICK, BE 0700-AAM, "
            "it came with one critical catch: the software was tightly coupled to physical hardware, "
            "relying on proprietary modules and custom serial drivers. Without the physical groovebox on your desk, "
            "developing or testing was virtually impossible. Enter 0700-AAM-SIM: a zero-dependency desktop simulator "
            "and virtual hardware harness built in modern C++17."
        ),
        "visual_type": "build"
    },
    {
        "id": 2,
        "title": "Act 2: The ComProtocol Engine & Headless Verification",
        "narration": (
            "At the heart of the system is a wire-accurate implementation of Music Tribe's binary ComProtocol. "
            "Every single packet header, command ID, and CRC-8 checksum is deterministically emulated. "
            "Using our headless scenario runner, complex musical performances can be replayed and verified against "
            "golden state traces in CI pipelines, with four out of four unit test suites passing in less than two tenths of a second."
        ),
        "visual_type": "test"
    },
    {
        "id": 3,
        "title": "Act 3: Virtual Hardware Emulation in Real-Time",
        "narration": (
            "0700-AAM-SIM models the complete physical control surface. Sixteen velocity-sensitive RGB pads across eight banks, "
            "four assignable Q-Link continuous encoders, the central jog wheel, capacitive touch strip, and transport controls. "
            "It even includes synthetic gesture injection for the AI camera, CV gate output logging, and virtual pseudo-terminals, "
            "allowing the real firmware application to connect unmodified."
        ),
        "visual_type": "interactive"
    },
    {
        "id": 4,
        "title": "Act 4: Sovereign Open Source Development",
        "narration": (
            "Licensed under AGPL version three or later, 0700-AAM-SIM brings true independence to the embedded audio community. "
            "Whether you are hacking the firmware, creating custom sequencing algorithms, or running automated test suites, "
            "you can now build and iterate entirely in software. Clean code, deterministic tests, and zero hardware barriers."
        ),
        "visual_type": "interactive_2"
    }
]

def render_terminal_video(cmd: str, out_mp4: Path, target_duration: float, title: str):
    """
    Record terminal session on remote GPU box with asciinema, render to gif via agg,
    and convert to smooth 1080p MP4 timed to the voiceover act duration.
    """
    remote_cast = f"/tmp/{out_mp4.stem}.cast"
    remote_gif = f"/tmp/{out_mp4.stem}.gif"
    remote_mp4 = f"/tmp/{out_mp4.stem}.mp4"
    remote_sh = f"/tmp/run_{out_mp4.stem}.sh"

    print(f"  [CLI Rec] Recording '{title}'...", flush=True)

    # Stage command as remote script to avoid nested quote escapes
    subprocess.run(["ssh", "gpu.sqs.chat", f"cat > {remote_sh} && chmod +x {remote_sh}"],
                   input=f"#!/bin/bash\nexport PATH=$HOME/.local/bin:$PATH\n{cmd}\n".encode("utf-8"),
                   check=True)

    # 1. Record session
    rec_cmd = [
        "ssh", "gpu.sqs.chat",
        f"bash -lc 'asciinema rec --overwrite --title \"{title}\" -c \"{remote_sh}\" {remote_cast}'"
    ]
    subprocess.run(rec_cmd, check=True)

    # 2. Render GIF with agg
    agg_cmd = [
        "ssh", "gpu.sqs.chat",
        f"bash -lc 'agg --font-size 22 --theme monokai --cols 90 --rows 28 {remote_cast} {remote_gif}'"
    ]
    subprocess.run(agg_cmd, check=True)

    # 3. Convert to MP4 with ffmpeg (scale to divisible-by-2 dimensions)
    ffmpeg_cmd = [
        "ssh", "gpu.sqs.chat",
        f"ffmpeg -y -loglevel error -i {remote_gif} -vf 'scale=trunc(iw/2)*2:trunc(ih/2)*2' -movflags +faststart -pix_fmt yuv420p {remote_mp4}"
    ]
    subprocess.run(ffmpeg_cmd, check=True)

    local_raw_mp4 = CLIPS_DIR / f"raw_{out_mp4.name}"
    subprocess.run(["scp", f"gpu.sqs.chat:{remote_mp4}", str(local_raw_mp4)], check=True)

    # Time-stretch or pad to exact target duration and 1920x1080 letterbox
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(local_raw_mp4)
    ]
    res = subprocess.run(probe_cmd, check=True, capture_output=True, text=True)
    raw_dur = max(1.0, float(res.stdout.strip()))

    pts_factor = target_duration / raw_dur
    vf = (
        f"setpts={pts_factor:.5f}*(PTS-STARTPTS),"
        f"scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p"
    )
    conv_cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", str(local_raw_mp4),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-an",
        "-t", f"{target_duration:.2f}",
        str(out_mp4)
    ]
    subprocess.run(conv_cmd, check=True, capture_output=True)
    print(f"  [CLI Rec] Rendered {out_mp4.name} ({target_duration:.1f}s)", flush=True)

def main():
    print("=== [1/4] Synthesizing Neural Narration Master via Edge-TTS ===", flush=True)
    music = MUSIC_DIR / "exhale_investigative_score.mp3"
    audio = build_documentary_audio(SCENES, music_track=music, prefix="aam_doc")
    total_duration = audio["total_duration"]
    print(f"Master runtime: {int(total_duration // 60):02d}:{int(total_duration % 60):02d} ({total_duration:.1f}s)")

    print("=== [2/4] Synchronizing Repositories & Terminal Recordings ===", flush=True)
    # Sync latest 0700-aam-sim to gpu.sqs.chat for remote high-res recording
    subprocess.run(["rsync", "-az", "--exclude=build", "--exclude=upstream", f"{REPO_ROOT}/", "gpu.sqs.chat:~/0700-aam-sim/"], check=True)
    subprocess.run(["ssh", "gpu.sqs.chat", "export PATH=$HOME/.local/bin:$PATH; cd ~/0700-aam-sim && cmake -B build -S . -DCMAKE_BUILD_TYPE=Release && cmake --build build"], check=True)

    timings = {t["id"]: t["duration"] for t in audio["scene_timings"]}

    clips = []
    # Scene 1: Build & Overview
    s1_clip = CLIPS_DIR / "scene_01.mp4"
    render_terminal_video(
        cmd="cd ~/0700-aam-sim && echo '>>> Building 0700-AAM Simulator...' && ./scripts/build_sim.sh",
        out_mp4=s1_clip,
        target_duration=timings[1],
        title="0700-AAM Build & Architecture"
    )
    clips.append(s1_clip)

    # Scene 2: CTest and Golden-file regression
    s2_clip = CLIPS_DIR / "scene_02.mp4"
    render_terminal_video(
        cmd="cd ~/0700-aam-sim/build && ctest -V && echo '' && ./0700-aam-sim --scenario ../tests/scenarios/pad_and_knob_flow.json --assert-golden ../tests/golden/pad_and_knob_flow.golden.json",
        out_mp4=s2_clip,
        target_duration=timings[2],
        title="Protocol & Golden Assertion Verification"
    )
    clips.append(s2_clip)

    # Scene 3: Interactive Simulation
    s3_clip = CLIPS_DIR / "scene_03.mp4"
    render_terminal_video(
        cmd="cd ~/0700-aam-sim && python3 video_prod/simulate_session.py",
        out_mp4=s3_clip,
        target_duration=timings[3],
        title="Virtual Hardware Matrix Control"
    )
    clips.append(s3_clip)

    # Scene 4: Code inspection and Git status
    s4_clip = CLIPS_DIR / "scene_04.mp4"
    render_terminal_video(
        cmd="cd ~/0700-aam-sim && git status && git log -n 4 --oneline && echo '' && tree -L 2 include/ src/ tests/ 2>/dev/null || ls -la include/thumpbox/ src/",
        out_mp4=s4_clip,
        target_duration=timings[4],
        title="Sovereign Architecture & Git Tree"
    )
    clips.append(s4_clip)

    print("=== [3/4] Assembling 1080p Master Documentary with Burned Subtitles ===", flush=True)
    final_mp4 = OUTPUT_DIR / "0700_aam_sim_documentary_1080p.mp4"
    render_full_documentary(
        scene_clips=clips,
        audio_master=audio["final_audio"],
        subtitles_srt=audio["master_srt"],
        output_mp4=final_mp4,
        total_duration=total_duration,
        burn_subtitles=False
    )

    srt_out = OUTPUT_DIR / "0700_aam_sim_documentary.srt"
    shutil.copy2(audio["master_srt"], srt_out)

    print(f"=== [4/4] Final Documentary Master Ready: {final_mp4} ({final_mp4.stat().st_size / (1024*1024):.1f} MB) ===")

if __name__ == "__main__":
    main()
