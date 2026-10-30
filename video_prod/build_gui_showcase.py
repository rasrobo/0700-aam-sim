#!/usr/bin/env python3
"""
Produce the complete narrated documentary demo for the 0700-AAM Sovereign Web GUI Simulator:
1. Synthesizes Edge-TTS neural voiceover with millisecond subtitles
2. Generates high-resolution 1080p skeuomorphic visual cards of the GUI hardware modules
3. Renders smooth 1080p 60fps MP4 clips with Ken Burns camera motion via FFmpeg
4. Mixes ducked ambient score with EBU R128 loudness audio mastering
5. Assembles final 1080p documentary master with burn_subtitles=False (companion SRT for CC)
6. Uploads unlisted to YouTube via gpu.sqs.chat
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCUVIBE_APP = Path.home() / "docuvibe" / "app"
sys.path.insert(0, str(DOCUVIBE_APP))

from config import MUSIC_DIR
from audio_engine import build_documentary_audio
from renderer import render_full_documentary

PROD_DIR = REPO_ROOT / "video_prod"
CLIPS_DIR = PROD_DIR / "clips"
OUTPUT_DIR = PROD_DIR / "output"

CLIPS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCENES = [
    {
        "id": 1,
        "title": "Act 1: Sovereign Skeuomorphic Architecture",
        "narration": (
            "Welcome to the 0700-AAM Sovereign Web Simulator: a photorealistic one-to-one "
            "hardware groovebox simulator running entirely inside any modern web browser. "
            "Modeled with meticulous physical precision after the BE 0700-AAM architecture, "
            "it delivers an authentic tactile control surface with zero native dependencies, "
            "zero build steps, and zero hardware barriers."
        ),
        "visual_key": "chassis"
    },
    {
        "id": 2,
        "title": "Act 2: The 6-View Touchscreen Operating System",
        "narration": (
            "At the center is an eight-hundred-by-four-hundred-and-eighty high-contrast touchscreen interface "
            "featuring six dedicated functional views. From the Main Sequencer and live audio oscilloscope, "
            "to the 16-by-16 Step Sequencer grid with running playhead cursor, sixteen-channel Track Mixer with "
            "live peak VU metering, Sampler waveform display, and Pad Filter Envelope editing."
        ),
        "visual_key": "screen"
    },
    {
        "id": 3,
        "title": "Act 3: Procedural Real-Time Web Audio Engine",
        "narration": (
            "Built directly into the simulator is a zero-latency procedural sound engine powered by the Web Audio API. "
            "Strike any of the sixteen pads across Banks A through H to trigger dynamic pitch-enveloped 808 kicks, "
            "dual-body noise snares, metallic six-oscillator hi-hats, hand claps, toms, and tuned resonant analog sub-bass, "
            "with full keyboard hotkey support."
        ),
        "visual_key": "pads"
    },
    {
        "id": 4,
        "title": "Act 4: Live ComProtocol WebSocket Bridge & Web Launch",
        "narration": (
            "For embedded firmware developers, the simulator embeds a wire-accurate binary ComProtocol WebSocket bridge. "
            "Every pad strike, knob rotation, and transport command is framed into standard MT packets and verified in "
            "continuous integration. It is one hundred percent open source under AGPL version three, and live right now "
            "on GitHub Pages at rasrobo.github.io/0700-aam-sim."
        ),
        "visual_key": "bridge"
    }
]

W, H = 1920, 1080
BG_DARK = (13, 17, 23)
PANEL_BG = (22, 27, 34)
CARD_BG = (28, 33, 40)
BORDER_COLOR = (48, 54, 61)
CYAN_ACCENT = (0, 240, 255)
AMBER_ACCENT = (255, 179, 0)
GREEN_ACCENT = (0, 230, 118)
PINK_ACCENT = (255, 64, 129)
TEXT_WHITE = (240, 246, 252)
TEXT_MUTED = (139, 148, 158)

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/hack"]

def get_font(size: int, bold: bool = False):
    names = (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Hack-Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Hack-Regular.ttf"])
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()

def draw_header(draw, title: str, subtitle: str, act_num: int):
    draw.rectangle([(0, 0), (W, 110)], fill=PANEL_BG)
    draw.line([(0, 110), (W, 110)], fill=BORDER_COLOR, width=2)
    draw.line([(0, 108), (W, 108)], fill=CYAN_ACCENT, width=2)

    f_badge = get_font(20, bold=True)
    draw.rectangle([(60, 32), (180, 78)], fill=(33, 38, 45), outline=CYAN_ACCENT, width=1)
    draw.text((78, 43), f"ACT {act_num}", font=f_badge, fill=CYAN_ACCENT)

    f_title = get_font(32, bold=True)
    draw.text((205, 36), title, font=f_title, fill=TEXT_WHITE)

    f_sub = get_font(18, bold=False)
    draw.text((W - 520, 45), subtitle, font=f_sub, fill=TEXT_MUTED)

def draw_footer(draw):
    draw.rectangle([(0, H - 70), (W, H)], fill=PANEL_BG)
    draw.line([(0, H - 70), (W, H - 70)], fill=BORDER_COLOR, width=1)
    f_foot = get_font(18, bold=True)
    draw.text((60, H - 46), "0700-AAM SOVEREIGN WEB HARDWARE SIMULATOR", font=f_foot, fill=TEXT_MUTED)
    draw.text((W - 550, H - 46), "DEMO: https://rasrobo.github.io/0700-aam-sim", font=f_foot, fill=CYAN_ACCENT)

def generate_scene_image(scene_info: Dict[str, Any], out_path: Path):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    act = scene_info["id"]

    draw_header(draw, scene_info["title"], "BE 0700-AAM Firmware Simulation Engine", act)
    draw_footer(draw)

    vk = scene_info["visual_key"]

    if vk == "chassis":
        # Draw physical layout card
        draw.rounded_rectangle([(60, 140), (W - 60, H - 100)], radius=16, fill=CARD_BG, outline=BORDER_COLOR, width=2)

        # Left section: 7" OLED Display Mock
        draw.rounded_rectangle([(100, 170), (1050, 720)], radius=12, fill=(10, 13, 16), outline=(0, 200, 230), width=3)
        f_screen_hdr = get_font(24, bold=True)
        draw.text((130, 195), "0700-AAM FIRMWARE OS v1.0.0", font=f_screen_hdr, fill=CYAN_ACCENT)
        draw.text((820, 195), "120.0 BPM  4/4  MAIN", font=f_screen_hdr, fill=AMBER_ACCENT)

        # Audio Oscilloscope waveform representation
        points = []
        import math
        for x in range(130, 1020, 8):
            y = 350 + int(70 * math.sin((x - 130) * 0.05) * math.cos((x - 130) * 0.015))
            points.append((x, y))
        draw.line(points, fill=GREEN_ACCENT, width=3)

        # Virtual buttons / tabs
        tabs = ["MAIN", "GRID SEQ", "TRACK MIX", "SAMPLER", "PAD EDIT", "PREFS"]
        for idx, t in enumerate(tabs):
            bx = 130 + idx * 148
            fill_col = (0, 70, 90) if idx == 0 else (20, 25, 30)
            text_col = CYAN_ACCENT if idx == 0 else TEXT_MUTED
            draw.rounded_rectangle([(bx, 640), (bx + 138, 695)], radius=6, fill=fill_col, outline=CYAN_ACCENT if idx == 0 else BORDER_COLOR)
            f_tab = get_font(16, bold=True)
            draw.text((bx + 18, 658), t, font=f_tab, fill=text_col)

        # Right section: 4 Q-Link Rotary Knobs with 360 SVG LED rings
        draw.rounded_rectangle([(1100, 170), (1860, 480)], radius=12, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        f_sec = get_font(20, bold=True)
        draw.text((1130, 195), "Q-LINK ASSIGNABLE ENCODERS & LED INDICATORS", font=f_sec, fill=TEXT_WHITE)

        qlinks = [
            ("Q1: CUTOFF", "850 Hz", CYAN_ACCENT),
            ("Q2: RESONANCE", "42%", AMBER_ACCENT),
            ("Q3: DECAY", "1.2x", GREEN_ACCENT),
            ("Q4: TUNE", "+2 ST", PINK_ACCENT)
        ]
        for idx, (label, val, col) in enumerate(qlinks):
            kx = 1140 + idx * 180
            draw.ellipse([(kx, 250), (kx + 110, 360)], outline=col, width=4)
            draw.ellipse([(kx + 15, 265), (kx + 95, 345)], fill=(33, 38, 45), outline=BORDER_COLOR)
            draw.line([(kx + 55, 305), (kx + 55 + int(30 * math.cos(idx * 1.2)), 305 - int(30 * math.sin(idx * 1.2)))], fill=col, width=4)
            f_ql = get_font(15, bold=True)
            draw.text((kx + 5, 385), label, font=f_ql, fill=TEXT_WHITE)
            draw.text((kx + 22, 415), val, font=f_ql, fill=col)

        # Right lower: Transport cluster & Data dial
        draw.rounded_rectangle([(1100, 510), (1860, 720)], radius=12, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((1130, 530), "CENTRAL JOG WHEEL, TOUCH STRIP & TRANSPORT", font=f_sec, fill=TEXT_WHITE)

        # Jog Wheel
        draw.ellipse([(1140, 570), (1250, 680)], fill=(33, 38, 45), outline=CYAN_ACCENT, width=3)
        draw.ellipse([(1180, 610), (1210, 640)], fill=(45, 52, 60))

        # Touch strip
        draw.rounded_rectangle([(1280, 575), (1480, 675)], radius=6, fill=(15, 18, 22), outline=BORDER_COLOR)
        draw.rounded_rectangle([(1285, 620), (1420, 630)], radius=3, fill=CYAN_ACCENT)

        # Transport buttons
        transports = [("REC", (255, 64, 64)), ("DUB", AMBER_ACCENT), ("STOP", TEXT_WHITE), ("PLAY", GREEN_ACCENT)]
        for idx, (lbl, col) in enumerate(transports):
            tx = 1515 + idx * 82
            draw.rounded_rectangle([(tx, 595), (tx + 72, 655)], radius=6, fill=(28, 33, 40), outline=col, width=2)
            f_tb = get_font(15, bold=True)
            draw.text((tx + 16, 615), lbl, font=f_tb, fill=col)

        # Bottom feature pill badges
        badges = [
            "16 RGB Silicone Pads", "Banks A-H (128 Virtual Pads)", "800x480 OLED Touchscreen",
            "Procedural Web Audio Engine", "Binary ComProtocol WebSocket", "AGPL-3.0 Sovereign Open Source"
        ]
        for idx, b in enumerate(badges):
            bx = 100 + idx * 290
            draw.rounded_rectangle([(bx, 750), (bx + 275, 800)], radius=8, fill=PANEL_BG, outline=BORDER_COLOR)
            f_bg = get_font(14, bold=True)
            draw.text((bx + 15, 765), f"✓ {b}", font=f_bg, fill=CYAN_ACCENT)

    elif vk == "screen":
        # 6-view touchscreen operating system
        draw.rounded_rectangle([(60, 140), (W - 60, H - 100)], radius=16, fill=CARD_BG, outline=BORDER_COLOR, width=2)

        views = [
            ("1. MAIN SEQUENCE & OSCILLOSCOPE", "Real-time master clock, BPM stats, running transport indicators, and live oscilloscope waveform visualization.", CYAN_ACCENT),
            ("2. 16x16 STEP SEQUENCER GRID", "Full 16-channel polyphonic trigger matrix with real-time running playhead cursor and per-step velocity latching.", AMBER_ACCENT),
            ("3. 16-CHANNEL TRACK MIXER", "Studio fader desk with live peak VU level meters, solo/mute toggles, and master bus limiter.", GREEN_ACCENT),
            ("4. SAMPLER WAVEFORM DISPLAY", "Sample slicing and inspection canvas with zero-crossing detection and trim markers.", PINK_ACCENT),
            ("5. PAD FILTER ENVELOPE (AHDSR)", "Attack, Hold, Decay, Sustain, and Release envelope modulation with resonant lowpass filter tracking.", (180, 100, 255)),
            ("6. PROTOCOL PREFERENCES", "Hardware link status, active packet counter, loopback diagnostics, and golden trace exports.", TEXT_WHITE),
        ]

        for idx, (title, desc, col) in enumerate(views):
            row = idx // 2
            col_idx = idx % 2
            vx = 100 + col_idx * 870
            vy = 170 + row * 200

            draw.rounded_rectangle([(vx, vy), (vx + 840, vy + 175)], radius=10, fill=PANEL_BG, outline=col, width=2)
            f_vt = get_font(22, bold=True)
            draw.text((vx + 25, vy + 20), title, font=f_vt, fill=col)
            f_vd = get_font(17, bold=False)

            # Word wrap description
            words = desc.split()
            lines = []
            cur = ""
            for w in words:
                if len(cur + " " + w) < 70:
                    cur = (cur + " " + w).strip()
                else:
                    lines.append(cur)
                    cur = w
            if cur: lines.append(cur)

            for l_idx, l in enumerate(lines):
                draw.text((vx + 25, vy + 65 + l_idx * 28), l, font=f_vd, fill=TEXT_MUTED)

            draw.rectangle([(vx + 25, vy + 135), (vx + 200, vy + 140)], fill=col)

    elif vk == "pads":
        # 16 RGB velocity pads sound engine matrix
        draw.rounded_rectangle([(60, 140), (W - 60, H - 100)], radius=16, fill=CARD_BG, outline=BORDER_COLOR, width=2)

        # Bank selector banner
        banks = [("BANK A", CYAN_ACCENT), ("BANK B", AMBER_ACCENT), ("BANK C", GREEN_ACCENT), ("BANK D", PINK_ACCENT),
                 ("BANK E", (255, 235, 59)), ("BANK F", (179, 136, 255)), ("BANK G", (255, 82, 82)), ("BANK H", TEXT_WHITE)]
        draw.text((100, 165), "ACTIVE PAD BANK SELECTOR (128 VIRTUAL PADS TOTAL):", font=get_font(20, bold=True), fill=TEXT_WHITE)
        for b_idx, (bname, bcol) in enumerate(banks):
            bx = 100 + b_idx * 210
            fill_b = (0, 70, 90) if b_idx == 0 else PANEL_BG
            draw.rounded_rectangle([(bx, 205), (bx + 195, 255)], radius=6, fill=fill_b, outline=bcol, width=2 if b_idx == 0 else 1)
            draw.text((bx + 50, 222), bname, font=get_font(16, bold=True), fill=bcol)

        # 4x4 Pad Grid Layout
        pad_data = [
            ("13. SUB BASS 1", "1", "45 Hz Saw Sine", (180, 100, 255)),
            ("14. SUB BASS 2", "2", "55 Hz 808 Tone", (180, 100, 255)),
            ("15. SUB BASS 3", "3", "65 Hz Acid Drop", (180, 100, 255)),
            ("16. SUB BASS 4", "4", "75 Hz Reso Sine", (180, 100, 255)),

            ("9. RIMSHOT", "Q", "Acoustic Rim", CYAN_ACCENT),
            ("10. SHAKER", "W", "16th Metal Shaker", CYAN_ACCENT),
            ("11. CRASH", "E", "Dual Cymbal Ring", CYAN_ACCENT),
            ("12. RIDE BELL", "R", "Brass Ping Transient", CYAN_ACCENT),

            ("5. CLAP 808", "A", "Triple Stutter Burst", AMBER_ACCENT),
            ("6. TOM LOW", "S", "Analog Pitch Drop", AMBER_ACCENT),
            ("7. TOM MID", "D", "Resonant Body", AMBER_ACCENT),
            ("8. TOM HIGH", "F", "Tight Pitch Decay", AMBER_ACCENT),

            ("1. KICK 808", "Z", "Pitch-Envelope Sub", GREEN_ACCENT),
            ("2. SNARE 909", "X", "Dual-Osc Noise Wire", GREEN_ACCENT),
            ("3. CLOSED HH", "C", "6-Osc Metal Cluster", GREEN_ACCENT),
            ("4. OPEN HH", "V", "Extended Sizzle Tail", GREEN_ACCENT),
        ]

        for p_idx, (pname, hotkey, desc, col) in enumerate(pad_data):
            p_row = p_idx // 4
            p_col = p_idx % 4
            px = 100 + p_col * 425
            py = 285 + p_row * 125

            draw.rounded_rectangle([(px, py), (px + 400, py + 110)], radius=10, fill=PANEL_BG, outline=col, width=2)
            draw.ellipse([(px + 20, py + 20), (px + 45, py + 45)], fill=col)

            draw.text((px + 55, py + 22), pname, font=get_font(18, bold=True), fill=TEXT_WHITE)

            # Hotkey badge
            draw.rounded_rectangle([(px + 330, py + 18), (px + 375, py + 52)], radius=4, fill=(40, 46, 56), outline=col)
            draw.text((px + 345, py + 24), hotkey, font=get_font(16, bold=True), fill=col)

            draw.text((px + 55, py + 62), desc, font=get_font(15, bold=False), fill=TEXT_MUTED)

    elif vk == "bridge":
        # WebSocket Bridge & Open Source architecture
        draw.rounded_rectangle([(60, 140), (W - 60, H - 100)], radius=16, fill=CARD_BG, outline=BORDER_COLOR, width=2)

        # Left: Binary ComProtocol Wire Specs
        draw.rounded_rectangle([(100, 175), (960, 780)], radius=12, fill=PANEL_BG, outline=CYAN_ACCENT, width=2)
        draw.text((130, 205), "BINARY COMPROTOCOL WIRE FRAMING", font=get_font(24, bold=True), fill=CYAN_ACCENT)

        proto_items = [
            ("Preamble Magic Bytes", "0x4D 0x54 ('M' 'T') exactly mirrors hardware firmware bus", CYAN_ACCENT),
            ("Packet Direction", "0x00 Request (Device->Host) / 0x01 Response (Host->Device)", TEXT_WHITE),
            ("Command Routing", "EN_PKT_PAD (0x03), EN_PKT_KNOBS (0x04), EN_PKT_BUTTON (0x01)", AMBER_ACCENT),
            ("Payload Encoding", "N-byte parameter vectors (Pad ID, Velocity, LED RGB, Knob Delta)", TEXT_WHITE),
            ("CRC-8 Checksum", "CRC-8 with generator polynomial 0x31 (x^8 + x^5 + x^4 + 1)", GREEN_ACCENT),
            ("WebSocket Bridge", "Bidirectional JSON/Binary frame transport on ws://localhost:8080/ws", PINK_ACCENT)
        ]

        for idx, (title, desc, col) in enumerate(proto_items):
            py = 265 + idx * 80
            draw.text((130, py), f"• {title}:", font=get_font(18, bold=True), fill=col)
            draw.text((150, py + 26), desc, font=get_font(15, bold=False), fill=TEXT_MUTED)

        # Right: GitHub Pages & Sovereign Open Source
        draw.rounded_rectangle([(1000, 175), (1860, 780)], radius=12, fill=PANEL_BG, outline=GREEN_ACCENT, width=2)
        draw.text((1030, 205), "SOVEREIGN AGPL-3.0 DEPLOYMENT", font=get_font(24, bold=True), fill=GREEN_ACCENT)

        # Live demo URL card
        draw.rounded_rectangle([(1030, 260), (1830, 390)], radius=10, fill=(10, 35, 25), outline=GREEN_ACCENT, width=2)
        draw.text((1055, 285), "LIVE DEMO RUNNING ON GITHUB PAGES:", font=get_font(18, bold=True), fill=GREEN_ACCENT)
        draw.text((1055, 325), "https://rasrobo.github.io/0700-aam-sim/", font=get_font(24, bold=True), fill=TEXT_WHITE)

        # Repo card
        draw.rounded_rectangle([(1030, 420), (1830, 550)], radius=10, fill=CARD_BG, outline=BORDER_COLOR, width=2)
        draw.text((1055, 445), "PUBLIC OPEN SOURCE REPOSITORY:", font=get_font(18, bold=True), fill=CYAN_ACCENT)
        draw.text((1055, 485), "https://github.com/rasrobo/0700-aam-sim", font=get_font(24, bold=True), fill=TEXT_WHITE)

        # Quality badges
        badges_r = [
            ("✓ 100% Passing CI Tests", GREEN_ACCENT),
            ("✓ AGPLv3 Copyleft Licensed", CYAN_ACCENT),
            ("✓ Zero Dependency Web Audio Engine", AMBER_ACCENT),
            ("✓ Works in Chrome, Firefox, Safari, Edge", PINK_ACCENT)
        ]
        for idx, (b_txt, b_col) in enumerate(badges_r):
            by = 585 + idx * 45
            draw.text((1055, by), b_txt, font=get_font(18, bold=True), fill=b_col)

    img.save(out_path, quality=95)
    return out_path

def render_scene_clip(scene_info: Dict[str, Any], timing: Dict[str, Any], out_mp4: Path, fps: int = 60) -> Path:
    dur = max(3.5, float(timing["duration"]))
    frame_png = out_mp4.with_suffix(".png")
    generate_scene_image(scene_info, frame_png)

    # Smooth Ken Burns zoompan
    frames = int(dur * fps)
    zoom = f"zoompan=z='min(zoom+0.00025,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={fps}"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(frame_png),
        "-t", f"{dur:.3f}",
        "-vf", zoom,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True)
    return out_mp4

def main():
    print("=== [1/5] Synthesizing Voiceover & Aligning Subtitles ===")
    music_track = MUSIC_DIR / "ambient_score.mp3"
    audio = build_documentary_audio(
        scenes=SCENES,
        voice="en-US-ChristopherNeural",
        music_track=music_track,
        prefix="0700_gui_showcase"
    )

    timings = {t["id"]: t for t in audio["scene_timings"]}
    total_duration = audio["total_duration"]
    print(f"Total Video Runtime: {total_duration:.2f}s across {len(SCENES)} acts.")

    print("=== [2/5] Rendering High-Definition 1080p 60fps Visual Clips ===")
    clips: List[Path] = []
    for sc in SCENES:
        sid = sc["id"]
        clip_path = CLIPS_DIR / f"gui_scene_{sid:02d}.mp4"
        print(f"Rendering Act {sid}: {sc['title']} ({timings[sid]['duration']:.2f}s)...")
        render_scene_clip(sc, timings[sid], clip_path, fps=60)
        clips.append(clip_path)

    final_mp4 = OUTPUT_DIR / "0700_aam_gui_showcase_1080p.mp4"
    print(f"=== [3/5] Muxing Clean 1080p Master (burn_subtitles=False) ===")
    render_full_documentary(
        scene_clips=clips,
        audio_master=audio["final_audio"],
        subtitles_srt=audio["master_srt"],
        output_mp4=final_mp4,
        total_duration=total_duration,
        burn_subtitles=False
    )

    srt_out = OUTPUT_DIR / "0700_aam_gui_showcase.srt"
    shutil.copy2(audio["master_srt"], srt_out)
    print(f"Master MP4 Generated: {final_mp4} ({final_mp4.stat().st_size / (1024*1024):.1f} MB)")
    print(f"Master SRT Subtitles Saved: {srt_out}")

    print("=== [4/5] Copying Master to gpu.sqs.chat for YouTube Upload ===")
    subprocess.run(["scp", str(final_mp4), "gpu.sqs.chat:/tmp/0700_aam_gui_showcase_1080p.mp4"], check=True)

    print("=== [5/5] Uploading Demo Video to YouTube via gpu.sqs.chat ===")
    yt_cmd = (
        "~/install-recordings/youtube/youtube-auth-upload.sh "
        "/tmp/0700_aam_gui_showcase_1080p.mp4 "
        "\"0700-AAM Sovereign Web Hardware Simulator (BE 0700-AAM Demo)\" "
        "--desc \"Walkthrough of the 0700-AAM Sovereign Web Simulator: a 1:1 photorealistic skeuomorphic hardware groovebox simulator with procedural Web Audio DSP synthesis, 6-view touchscreen operating system, 128 virtual pads (Banks A-H), knurled Q-Link encoders, and binary ComProtocol WebSocket bridge. Live browser demo at https://rasrobo.github.io/0700-aam-sim/ | Source code: https://github.com/rasrobo/0700-aam-sim\" "
        "--tags \"0700-aam,groovebox,synthesizer,web-audio,simulator,musictribe,firmware,hardware-simulation,juce,cpp\""
    )
    result = subprocess.run(["ssh", "gpu.sqs.chat", yt_cmd], capture_output=True, text=True, check=True)
    print("YouTube Upload Output:")
    print(result.stdout)
    if result.stderr:
        print("YouTube Stderr:", result.stderr)

    # Clean remote temp
    subprocess.run(["ssh", "gpu.sqs.chat", "rm -f /tmp/0700_aam_gui_showcase_1080p.mp4"], check=False)
    print("=== ALL COMPLETE ===")

if __name__ == "__main__":
    main()
