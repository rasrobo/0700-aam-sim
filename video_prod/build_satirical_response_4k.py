#!/usr/bin/env python3
"""
Produce the 4K Ultra HD (3840x2160) Satirical Response Video:
"I don't think I have any use for an embedded hardware simulator..."

Key Features:
1. Open-source CC-BY 4.0 music: "The Complex" by Kevin MacLeod
2. 4K Ultra HD resolution (3840x2160) with Ken Burns motion
3. Deadpan satirical contrast: Physical Silicon Fire vs 1:1 Software Simulation
4. Clean presentation export (burn_subtitles=False per video production rule)
5. Upload unlisted to YouTube via gpu.sqs.chat
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
ASSETS_DIR = PROD_DIR / "assets"
CLIPS_DIR = PROD_DIR / "clips_4k"
OUTPUT_DIR = PROD_DIR / "output"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 3840, 2160
FPS = 30

BG_DARK = (11, 14, 19)
PANEL_BG = (18, 22, 28)
CARD_BG = (24, 29, 37)
BORDER_COLOR = (42, 48, 56)
CYAN_ACCENT = (0, 240, 255)
AMBER_ACCENT = (255, 179, 0)
GREEN_ACCENT = (0, 230, 118)
PINK_ACCENT = (255, 64, 129)
RED_ACCENT = (255, 82, 82)
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

SCENES = [
    {
        "id": 1,
        "title": "Act 1: The Character-Building Aroma of Burnt Silicon",
        "narration": (
            "You make a compelling point. Why would anyone ever need an embedded hardware simulator? "
            "Why test firmware cleanly in modern C++ when you could instead brick a four-hundred-dollar prototype groovebox "
            "at three in the morning? That distinct, comforting smell of vaporized FR-four fiberglass "
            "lets the entire office know you are doing real engineering."
        ),
        "visual_key": "smoke"
    },
    {
        "id": 2,
        "title": "Act 2: Artisanal Manual QA vs Headless Verification",
        "narration": (
            "Some people brag about automated CI/CD pipelines. They love that two thousand wire-accurate "
            "binary ComProtocol packets can pass unit tests in eighteen hundredths of a second. "
            "But what happened to artisan, hand-crafted firmware development? If you aren't physically "
            "mashing sixteen silicone pads ten thousand times until your thumbs go numb, can you even look yourself in the mirror?"
        ),
        "visual_key": "manual_qa"
    },
    {
        "id": 3,
        "title": "Act 3: The Seamless Romance of Customs & International Shipping",
        "narration": (
            "And think of your remote open source contributors. Giving them a zero-install web URL where the entire "
            "seven-inch touchscreen, velocity pads, and ComProtocol bridge run instantly at sixty frames a second? "
            "Where is the character-building struggle? It is much more romantic to ship fifty fragile developer boards "
            "through international customs, have three lost in transit, and wait six weeks for replacement tactile switches."
        ),
        "visual_key": "customs"
    },
    {
        "id": 4,
        "title": "Act 4: Zero Solder Required — 0700-AAM Sovereign Web Simulator",
        "narration": (
            "So keep your dangling jumper wires, your multimeter, and your fire extinguisher. "
            "But for the rest of us who prefer shipping working firmware over ordering replacement motherboards, "
            "the 0700-AAM Sovereign Web Simulator is live right now in four K on GitHub Pages at "
            "rasrobo.github.io/0700-aam-sim. Zero solder required."
        ),
        "visual_key": "showcase"
    }
]

def draw_header_4k(draw, title: str, subtitle: str, act_num: int):
    draw.rectangle([(0, 0), (W, 200)], fill=PANEL_BG)
    draw.line([(0, 200), (W, 200)], fill=BORDER_COLOR, width=3)
    draw.line([(0, 196), (W, 196)], fill=AMBER_ACCENT, width=4)

    # Act Badge
    draw.rounded_rectangle([(100, 50), (320, 150)], radius=12, fill=(30, 36, 45), outline=AMBER_ACCENT, width=2)
    f_badge = get_font(38, bold=True)
    draw.text((135, 75), f"ACT {act_num}", font=f_badge, fill=AMBER_ACCENT)

    f_title = get_font(52, bold=True)
    draw.text((360, 55), title, font=f_title, fill=TEXT_WHITE)

    f_sub = get_font(30, bold=False)
    draw.text((365, 128), subtitle, font=f_sub, fill=TEXT_MUTED)

    # 4K & Satire badge in top right
    draw.rounded_rectangle([(W - 650, 60), (W - 100, 140)], radius=10, fill=(35, 18, 20), outline=RED_ACCENT, width=2)
    f_badge_rt = get_font(28, bold=True)
    draw.text((W - 610, 80), "4K SATIRE  •  EMBEDDED DEV", font=f_badge_rt, fill=RED_ACCENT)

def draw_footer_4k(draw):
    draw.rectangle([(0, H - 120), (W, H)], fill=PANEL_BG)
    draw.line([(0, H - 120), (W, H - 120)], fill=BORDER_COLOR, width=2)

    f_foot = get_font(32, bold=True)
    draw.text((100, H - 80), "0700-AAM SOVEREIGN WEB HARDWARE SIMULATOR", font=f_foot, fill=TEXT_MUTED)

    f_link = get_font(32, bold=True)
    draw.text((W - 950, H - 80), "TRY LIVE: https://rasrobo.github.io/0700-aam-sim", font=f_link, fill=CYAN_ACCENT)

def generate_4k_scene_image(scene_info: Dict[str, Any], out_path: Path):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    act = scene_info["id"]

    draw_header_4k(draw, scene_info["title"], "Response to: \"I don't think I have any use for an embedded hardware simulator...\"", act)
    draw_footer_4k(draw)

    vk = scene_info["visual_key"]

    if vk == "smoke":
        # Left: Purist / Burnt silicon reality
        draw.rounded_rectangle([(100, 260), (1880, H - 180)], radius=24, fill=CARD_BG, outline=RED_ACCENT, width=3)
        draw.text((160, 310), "THE PURIST ROUTE: REAL HARDWARE ONLY", font=get_font(42, bold=True), fill=RED_ACCENT)
        draw.text((160, 370), "No simulator. Full desk footprint. Unfiltered high-voltage consequences.", font=get_font(28, bold=False), fill=TEXT_MUTED)

        hw_img_p = ASSETS_DIR / "hardware_photo.png"
        if hw_img_p.exists():
            hw_raw = Image.open(hw_img_p)
            hw_target_w = 1680
            hw_target_h = int(hw_target_w * hw_raw.height / hw_raw.width)
            hw_scaled = hw_raw.resize((hw_target_w, min(hw_target_h, 850)), Image.LANCZOS)
            img.paste(hw_scaled, (150, 440))

        # Warning badges
        warnings = [
            ("FLASHER BRICK HAZARD", "Accidental bootloader overwrite bricks flash memory ($400)", RED_ACCENT),
            ("PROBE SLIP DISASTER", "Oscilloscope ground clip shorts 12V rail into 3.3V logic line", AMBER_ACCENT),
            ("DESK TAKEOVER", "Requires bench power supply, logic analyzer, and fire extinguisher", TEXT_WHITE),
        ]
        for w_idx, (w_t, w_d, w_col) in enumerate(warnings):
            wy = 1360 + w_idx * 160
            draw.rounded_rectangle([(160, wy), (1820, wy + 130)], radius=12, fill=(32, 18, 20), outline=w_col, width=2)
            draw.text((190, wy + 25), f"⚠️  {w_t}", font=get_font(32, bold=True), fill=w_col)
            draw.text((190, wy + 75), w_d, font=get_font(26, bold=False), fill=TEXT_MUTED)

        # Right: The Sovereign Simulator
        draw.rounded_rectangle([(1960, 260), (3740, H - 180)], radius=24, fill=CARD_BG, outline=CYAN_ACCENT, width=4)
        draw.text((2020, 310), "THE COWARD'S ROUTE: 1:1 ZERO-RISK SIMULATOR", font=get_font(42, bold=True), fill=CYAN_ACCENT)
        draw.text((2020, 370), "Deterministic software execution with wire-accurate ComProtocol fidelity", font=get_font(28, bold=False), fill=TEXT_MUTED)

        features = [
            ("0.0 Volts on Your Desk", "Zero danger of electrocution, blown fuses, or magic smoke plumes.", GREEN_ACCENT),
            ("Instant Memory Reset", "Segmentation fault? Simply press Ctrl+R to revive the groovebox in 5ms.", CYAN_ACCENT),
            ("Runs Anywhere", "Runs on MacBook, ThinkPad, iPad, Chromebook, or Linux desktop without drivers.", AMBER_ACCENT),
            ("Wire-Accurate CRC-8 Protocol", "Binary byte-for-byte protocol validation against official specs.", PINK_ACCENT),
            ("Zero Solder Spatters", "Keeps your mahogany desk completely clean and burn-mark free.", GREEN_ACCENT)
        ]
        for f_idx, (f_t, f_d, f_col) in enumerate(features):
            fy = 480 + f_idx * 240
            draw.rounded_rectangle([(2020, fy), (3680, fy + 200)], radius=16, fill=PANEL_BG, outline=f_col, width=2)
            draw.text((2060, fy + 40), f"✓  {f_t}", font=get_font(36, bold=True), fill=f_col)
            draw.text((2060, fy + 110), f_d, font=get_font(28, bold=False), fill=TEXT_MUTED)

    elif vk == "manual_qa":
        # Manual QA vs Headless Verification
        draw.rounded_rectangle([(100, 260), (1880, H - 180)], radius=24, fill=CARD_BG, outline=AMBER_ACCENT, width=3)
        draw.text((160, 310), "ARTISANAL MANUAL QA (THUMB DESTRUCTION)", font=get_font(42, bold=True), fill=AMBER_ACCENT)
        draw.text((160, 370), "Hand-crafted pad mashing by sleep-deprived human firmware engineers", font=get_font(28, bold=False), fill=TEXT_MUTED)

        manual_stats = [
            ("Time Required", "4.5 Hours per regression test", RED_ACCENT),
            ("Pad Strikes", "10,000 manual thumb strikes across 8 banks", AMBER_ACCENT),
            ("Thumb Condition", "Swollen, bruised, repetitive strain injury", RED_ACCENT),
            ("Reproducibility", "Near 0% — depends on coffee and adrenaline levels", TEXT_MUTED),
            ("CI/CD Compatibility", "Requires physically trapping an engineer in a server rack", RED_ACCENT)
        ]
        for m_idx, (m_lbl, m_val, m_col) in enumerate(manual_stats):
            my = 480 + m_idx * 240
            draw.rounded_rectangle([(160, my), (1820, my + 200)], radius=16, fill=(28, 24, 20), outline=m_col, width=2)
            draw.text((200, my + 40), m_lbl, font=get_font(32, bold=True), fill=m_col)
            draw.text((200, my + 110), m_val, font=get_font(28, bold=False), fill=TEXT_WHITE)

        # Right: Headless CI/CD
        draw.rounded_rectangle([(1960, 260), (3740, H - 180)], radius=24, fill=CARD_BG, outline=GREEN_ACCENT, width=4)
        draw.text((2020, 310), "SOVEREIGN CI/CD AUTOMATION (HEADLESS HARNESS)", font=get_font(42, bold=True), fill=GREEN_ACCENT)
        draw.text((2020, 370), "Deterministic scenario runner executing 2,000+ packets in parallel", font=get_font(28, bold=False), fill=TEXT_MUTED)

        ci_stats = [
            ("Total Test Runtime", "0.18 Seconds for 4/4 test suites", GREEN_ACCENT),
            ("Packet Throughput", "2,000+ binary ComProtocol frames parsed deterministically", CYAN_ACCENT),
            ("Golden State Verification", "100% byte-for-byte state trace matching against golden runs", GREEN_ACCENT),
            ("Human Fatigue", "0% — run on every GitHub push, pull request, or local commit", TEXT_WHITE),
            ("CI/CD Compatibility", "Zero-dependency C++17 runs cleanly in headless Docker containers", GREEN_ACCENT)
        ]
        for c_idx, (c_lbl, c_val, c_col) in enumerate(ci_stats):
            cy = 480 + c_idx * 240
            draw.rounded_rectangle([(2020, cy), (3680, cy + 200)], radius=16, fill=PANEL_BG, outline=c_col, width=2)
            draw.text((2060, cy + 40), c_lbl, font=get_font(32, bold=True), fill=c_col)
            draw.text((2060, cy + 110), c_val, font=get_font(28, bold=False), fill=TEXT_WHITE)

    elif vk == "customs":
        # Logistics & Contributor Onboarding
        draw.rounded_rectangle([(100, 260), (1880, H - 180)], radius=24, fill=CARD_BG, outline=RED_ACCENT, width=3)
        draw.text((160, 310), "HARDWARE LOGISTICS: FEDEX & CUSTOMS HELL", font=get_font(42, bold=True), fill=RED_ACCENT)
        draw.text((160, 370), "Distributing 50 physical grooveboxes to open-source developers worldwide", font=get_font(28, bold=False), fill=TEXT_MUTED)

        customs_steps = [
            ("Customs Clearance Delay", "Held at Frankfurt Customs Hub — Tariff code disputed (6 weeks)", RED_ACCENT),
            ("Shipping Cost", "$14,500 in DHL international express fees & duty tariffs", RED_ACCENT),
            ("Damaged in Transit", "3 units arrived with smashed OLED screens and bent encoder shafts", AMBER_ACCENT),
            ("Contributor Churn", "Developer lost interest and took a job at Google before box arrived", TEXT_MUTED),
            ("Scalability", "Capped at hardware budget; remote contributors left completely stranded", RED_ACCENT)
        ]
        for s_idx, (s_lbl, s_val, s_col) in enumerate(customs_steps):
            sy = 480 + s_idx * 240
            draw.rounded_rectangle([(160, sy), (1820, sy + 200)], radius=16, fill=(30, 20, 22), outline=s_col, width=2)
            draw.text((200, sy + 40), s_lbl, font=get_font(32, bold=True), fill=s_col)
            draw.text((200, sy + 110), s_val, font=get_font(28, bold=False), fill=TEXT_WHITE)

        # Right: Web URL Onboarding
        draw.rounded_rectangle([(1960, 260), (3740, H - 180)], radius=24, fill=CARD_BG, outline=CYAN_ACCENT, width=4)
        draw.text((2020, 310), "SOVEREIGN WEB ONBOARDING: 1-CLICK URL", font=get_font(42, bold=True), fill=CYAN_ACCENT)
        draw.text((2020, 370), "Instant global deployment with zero customs forms, drivers, or shipping fees", font=get_font(28, bold=False), fill=TEXT_MUTED)

        web_steps = [
            ("Onboarding Friction", "140 Milliseconds load time directly in any modern browser", GREEN_ACCENT),
            ("Distribution Cost", "$0.00 — Hosted on GitHub Pages edge CDN", CYAN_ACCENT),
            ("Hardware Degradation", "Zero physical wear and tear; silicone pads never wear out", GREEN_ACCENT),
            ("Contributor Velocity", "Anyone with a browser can reproduce bugs and submit PRs instantly", TEXT_WHITE),
            ("Global Scalability", "Unlocks 1,000,000 concurrent developers without shipping a single box", CYAN_ACCENT)
        ]
        for w_idx, (w_lbl, w_val, w_col) in enumerate(web_steps):
            wy = 480 + w_idx * 240
            draw.rounded_rectangle([(2020, wy), (3680, wy + 200)], radius=16, fill=PANEL_BG, outline=w_col, width=2)
            draw.text((2060, wy + 40), w_lbl, font=get_font(32, bold=True), fill=w_col)
            draw.text((2060, wy + 110), w_val, font=get_font(28, bold=False), fill=TEXT_WHITE)

    elif vk == "showcase":
        # Final Showcase: 0700-AAM Sovereign Web Simulator Live Links & Summary
        draw.rounded_rectangle([(100, 260), (1880, H - 180)], radius=24, fill=CARD_BG, outline=CYAN_ACCENT, width=3)
        draw.text((160, 310), "0700-AAM SOVEREIGN WEB SIMULATOR", font=get_font(42, bold=True), fill=CYAN_ACCENT)
        draw.text((160, 370), "1:1 Hardware Parity with the BE 0700-AAM Standalone Groovebox", font=get_font(28, bold=False), fill=TEXT_MUTED)

        sim_features = [
            ("1:1 Hardware Geometry", "Physical button matrix, jog dial with directional surround, 4 Q-Links", CYAN_ACCENT),
            ("6-View Touchscreen Interface", "Main Sequencer, Step Grid, 16-Channel Mixer, Sample Canvas, Envelope, Prefs", AMBER_ACCENT),
            ("128 Virtual Pads", "Banks A through H with zero-latency Web Audio procedural synthesis", GREEN_ACCENT),
            ("ComProtocol WebSocket Bridge", "Wire-accurate binary packet emulation with CRC-8 checksum verification", PINK_ACCENT),
            ("Zero Solder Required", "Full skeuomorphic simulation without a single charred capacitor", TEXT_WHITE)
        ]
        for sf_idx, (sf_t, sf_d, sf_col) in enumerate(sim_features):
            sfy = 480 + sf_idx * 240
            draw.rounded_rectangle([(160, sfy), (1820, sfy + 200)], radius=16, fill=PANEL_BG, outline=sf_col, width=2)
            draw.text((200, sfy + 40), f"⚡ {sf_t}", font=get_font(34, bold=True), fill=sf_col)
            draw.text((200, sfy + 110), sf_d, font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Right: Live Demo & GitHub Card
        draw.rounded_rectangle([(1960, 260), (3740, H - 180)], radius=24, fill=CARD_BG, outline=GREEN_ACCENT, width=4)
        draw.text((2020, 310), "JOIN THE SOVEREIGN SIMULATOR REVOLUTION", font=get_font(42, bold=True), fill=GREEN_ACCENT)
        draw.text((2020, 370), "Open Source (AGPLv3) • Zero Install • 4K Ultra HD Presentation", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Live Demo Box
        draw.rounded_rectangle([(2020, 480), (3680, 800)], radius=18, fill=(12, 38, 28), outline=GREEN_ACCENT, width=3)
        draw.text((2060, 520), "TRY THE LIVE SIMULATOR IN YOUR BROWSER:", font=get_font(34, bold=True), fill=GREEN_ACCENT)
        draw.text((2060, 600), "https://rasrobo.github.io/0700-aam-sim/", font=get_font(46, bold=True), fill=TEXT_WHITE)
        draw.text((2060, 700), "Open directly in Chrome, Firefox, Safari, or Edge — works on mobile & desktop", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # GitHub Repo Box
        draw.rounded_rectangle([(2020, 860), (3680, 1180)], radius=18, fill=PANEL_BG, outline=CYAN_ACCENT, width=3)
        draw.text((2060, 900), "OPEN SOURCE GITHUB REPOSITORY:", font=get_font(34, bold=True), fill=CYAN_ACCENT)
        draw.text((2060, 980), "https://github.com/rasrobo/0700-aam-sim", font=get_font(46, bold=True), fill=TEXT_WHITE)
        draw.text((2060, 1080), "CMake build harness, ComProtocol unit tests, and skeuomorphic web UI", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Attribution Notice
        draw.rounded_rectangle([(2020, 1240), (3680, 1720)], radius=18, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((2060, 1280), "ATTRIBUTIONS & OPEN SOURCE CREDITS:", font=get_font(32, bold=True), fill=AMBER_ACCENT)
        attrs = [
            "• License: GNU Affero General Public License v3.0 (AGPL-3.0-or-later)",
            "• Music: \"The Complex\" by Kevin MacLeod (incompetech.com) — CC-BY 4.0",
            "• Hardware Base: Modeled on Music Tribe BE 0700-AAM architecture",
            "• Disclaimer: Independent simulator; not affiliated with Music Tribe / Behringer"
        ]
        for a_idx, atxt in enumerate(attrs):
            draw.text((2060, 1360 + a_idx * 75), atxt, font=get_font(28, bold=False), fill=TEXT_WHITE)

    img.save(out_path, quality=95)
    return out_path

def render_4k_scene_clip(scene_info: Dict[str, Any], timing: Dict[str, Any], out_mp4: Path) -> Path:
    dur = max(4.0, float(timing["duration"]))
    frame_png = out_mp4.with_suffix(".png")
    generate_4k_scene_image(scene_info, frame_png)

    frames = int(dur * FPS)
    zoom = f"zoompan=z='min(zoom+0.00018,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(frame_png),
        "-t", f"{dur:.3f}",
        "-vf", zoom,
        "-c:v", "libx264", "-preset", "faster", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True)
    return out_mp4

def main():
    print("=== [1/5] Synthesizing Deadpan Satirical Voiceover (Kevin MacLeod Score) ===")
    open_source_music = MUSIC_DIR / "the_complex_investigative_score.mp3"
    assert open_source_music.exists(), f"Missing music: {open_source_music}"

    audio = build_documentary_audio(
        scenes=SCENES,
        voice="en-US-ChristopherNeural",
        music_track=open_source_music,
        prefix="satirical_resp_4k"
    )

    timings = {t["id"]: t for t in audio["scene_timings"]}
    total_duration = audio["total_duration"]
    print(f"Total Video Runtime: {total_duration:.2f}s across {len(SCENES)} acts.")

    print("=== [2/5] Rendering High-Definition 4K UHD (3840x2160) Visual Clips ===")
    clips: List[Path] = []
    for sc in SCENES:
        sid = sc["id"]
        clip_path = CLIPS_DIR / f"satirical_4k_scene_{sid:02d}.mp4"
        print(f"Rendering Act {sid}: {sc['title']} ({timings[sid]['duration']:.2f}s) in 4K...")
        render_4k_scene_clip(sc, timings[sid], clip_path)
        clips.append(clip_path)

    final_mp4 = OUTPUT_DIR / "0700_aam_satirical_response_4k.mp4"
    print(f"=== [3/5] Muxing Clean 4K Master (burn_subtitles=False) ===")
    render_full_documentary(
        scene_clips=clips,
        audio_master=audio["final_audio"],
        subtitles_srt=audio["master_srt"],
        output_mp4=final_mp4,
        total_duration=total_duration,
        burn_subtitles=False
    )

    srt_out = OUTPUT_DIR / "0700_aam_satirical_response_4k.srt"
    shutil.copy2(audio["master_srt"], srt_out)
    print(f"Master 4K MP4 Generated: {final_mp4} ({final_mp4.stat().st_size / (1024*1024):.1f} MB)")
    print(f"Master SRT Subtitles Saved: {srt_out}")

    print("=== [4/5] Copying 4K Master to gpu.sqs.chat for YouTube Upload ===")
    subprocess.run(["scp", str(final_mp4), "gpu.sqs.chat:/tmp/0700_aam_satirical_response_4k.mp4"], check=True)

    print("=== [5/5] Uploading 4K Video to YouTube via gpu.sqs.chat ===")
    yt_script = f'''
~/install-recordings/youtube/youtube-auth-upload.sh \\
  /tmp/0700_aam_satirical_response_4k.mp4 \\
  "\\\"I don’t think I have any use for an embedded hardware simulator...\\\" (Satirical Response)" \\
  --desc "A satirical response to the timeless objection: \\"I don't think I have any use for an embedded hardware simulator...\\"

Why test firmware cleanly in zero-dependency modern C++ when you could instead brick a physical prototype at 3:00 AM, burn through customs clearance on 50 developer boards, and manually mash 16 silicone pads for 4 hours?

The 0700-AAM Sovereign Web Simulator delivers 1:1 hardware control surface parity with the BE 0700-AAM groovebox:
• 1:1 Skeuomorphic chassis matching physical hardware layout
• 6-view 800x480 touchscreen interface (Sequencer, Grid, Mixer, Sample, Edit, Prefs)
• 128 virtual velocity-sensitive pads across Banks A through H
• Real-time Web Audio procedural synthesis engine
• Wire-accurate binary ComProtocol WebSocket bridge with CRC-8 checksum verification
• Headless automated scenario test harness (passes in under 0.2s in CI)

Try the Live 4K Simulator in your browser (Zero Install):
https://rasrobo.github.io/0700-aam-sim/

GitHub Repository:
https://github.com/rasrobo/0700-aam-sim

Music: 'The Complex' by Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0 License (http://creativecommons.org/licenses/by/4.0/)
Independent open-source simulator (AGPLv3); not affiliated with Music Tribe / Behringer." \\
  --tags "0700-aam,embedded,hardware-simulator,firmware,groovebox,synthesizer,satire,musictribe,behringer,4k,web-audio,cpp"
'''
    result = subprocess.run(["ssh", "gpu.sqs.chat", "bash -s"], input=yt_script, capture_output=True, text=True, check=True)
    print("YouTube Upload Output:")
    print(result.stdout)
    if result.stderr:
        print("YouTube Stderr:", result.stderr)

    # Clean remote temp
    subprocess.run(["ssh", "gpu.sqs.chat", "rm -f /tmp/0700_aam_satirical_response_4k.mp4"], check=False)
    print("=== ALL COMPLETE ===")

if __name__ == "__main__":
    main()
