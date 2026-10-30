#!/usr/bin/env python3
"""
Produce the 4K Ultra HD (3840x2160) Sovereign Web Simulator Showcase:
1. Open-source CC-BY 4.0 music: "The Complex" by Kevin MacLeod
2. 4K Ultra HD resolution (3840x2160) with Ken Burns motion
3. Side-by-side hardware photography from BE 0700-AAM alongside the 1:1 web software simulator
4. EBU R128 mastered audio with clean video master (burn_subtitles=False, companion SRT for CC)
5. Uploads unlisted to YouTube via gpu.sqs.chat
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

# 4K Ultra HD dimensions
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
        "title": "Act 1: Physical Hardware & 1:1 Sovereign Software Simulator",
        "narration": (
            "This is the physical Behringer KICK, BE 0700-AAM: an integrated standalone groovebox "
            "featuring a seven-inch color touchscreen, sixteen RGB velocity pads, four continuous Q-Link encoders, "
            "and an analog capacitive touch strip. And this is 0700-AAM-SIM: our photorealistic, one-to-one "
            "skeuomorphic software simulator running directly in your web browser with zero installation, zero drivers, "
            "and zero hardware barriers."
        ),
        "visual_key": "comparison"
    },
    {
        "id": 2,
        "title": "Act 2: The 6-View Touchscreen Operating Interface",
        "narration": (
            "Every single module of the physical device's operating system has been faithfully modeled. "
            "The eight-hundred-by-four-hundred-and-eighty display features six dedicated functional views: "
            "the Main Sequencer with a real-time audio oscilloscope, the sixteen-by-sixteen polyphonic Step Sequencer "
            "with a live playhead cursor, the sixteen-channel Track Mixer with peak VU metering, the sample waveform editor, "
            "and full pad envelope modulation."
        ),
        "visual_key": "touchscreen"
    },
    {
        "id": 3,
        "title": "Act 3: Real-Time Procedural Sound Engine & 128 Virtual Pads",
        "narration": (
            "Under the hood is a zero-latency procedural sound engine powered by the Web Audio API. "
            "Strike any of the sixteen velocity-sensitive pads across Banks A through H to trigger dynamic pitch-enveloped "
            "808 sub kicks, dual-body noise snares, metallic six-oscillator hi-hats, hand claps, toms, and tuned analog sub-bass, "
            "playable instantly with your computer keyboard or MIDI controller."
        ),
        "visual_key": "pads"
    },
    {
        "id": 4,
        "title": "Act 4: Live Binary ComProtocol WebSocket Bridge & Web Launch",
        "narration": (
            "For embedded firmware developers, the simulator bridges directly over WebSocket using the wire-accurate "
            "binary ComProtocol, verified against four automated golden-file test suites in continuous integration. "
            "It is one hundred percent open source under AGPL version three, and live right now in four K on GitHub Pages "
            "at rasrobo.github.io/0700-aam-sim."
        ),
        "visual_key": "protocol"
    }
]

def draw_header_4k(draw, title: str, subtitle: str, act_num: int):
    draw.rectangle([(0, 0), (W, 200)], fill=PANEL_BG)
    draw.line([(0, 200), (W, 200)], fill=BORDER_COLOR, width=3)
    draw.line([(0, 196), (W, 196)], fill=CYAN_ACCENT, width=4)

    # Act Badge
    draw.rounded_rectangle([(100, 50), (320, 150)], radius=12, fill=(30, 36, 45), outline=CYAN_ACCENT, width=2)
    f_badge = get_font(38, bold=True)
    draw.text((135, 75), f"ACT {act_num}", font=f_badge, fill=CYAN_ACCENT)

    f_title = get_font(56, bold=True)
    draw.text((360, 55), title, font=f_title, fill=TEXT_WHITE)

    f_sub = get_font(32, bold=False)
    draw.text((365, 128), subtitle, font=f_sub, fill=TEXT_MUTED)

    # 4K & Open Source badge in top right
    draw.rounded_rectangle([(W - 550, 60), (W - 100, 140)], radius=10, fill=(15, 30, 25), outline=GREEN_ACCENT, width=2)
    f_badge_rt = get_font(28, bold=True)
    draw.text((W - 510, 80), "4K UHD  •  OPEN SOURCE", font=f_badge_rt, fill=GREEN_ACCENT)

def draw_footer_4k(draw):
    draw.rectangle([(0, H - 120), (W, H)], fill=PANEL_BG)
    draw.line([(0, H - 120), (W, H - 120)], fill=BORDER_COLOR, width=2)

    f_foot = get_font(32, bold=True)
    draw.text((100, H - 80), "0700-AAM SOVEREIGN WEB SIMULATOR (BE 0700-AAM HARNESS)", font=f_foot, fill=TEXT_MUTED)

    f_link = get_font(32, bold=True)
    draw.text((W - 950, H - 80), "TRY LIVE: https://rasrobo.github.io/0700-aam-sim", font=f_link, fill=CYAN_ACCENT)

def generate_4k_scene_image(scene_info: Dict[str, Any], out_path: Path):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    act = scene_info["id"]

    draw_header_4k(draw, scene_info["title"], "BE 0700-AAM Groovebox Firmware & Control Surface Emulation", act)
    draw_footer_4k(draw)

    vk = scene_info["visual_key"]

    if vk == "comparison":
        # 1:1 Side-by-side: Physical Hardware vs. Sovereign Web Simulator
        # Left Card: Physical Hardware
        draw.rounded_rectangle([(100, 260), (1880, H - 180)], radius=24, fill=CARD_BG, outline=BORDER_COLOR, width=3)
        draw.text((160, 310), "PHYSICAL HARDWARE: BE 0700-AAM GROOVEBOX", font=get_font(42, bold=True), fill=AMBER_ACCENT)
        draw.text((160, 370), "Music Tribe / NXP i.MX8M Mini Embedded Linux Architecture", font=get_font(28, bold=False), fill=TEXT_MUTED)

        hw_img_p = ASSETS_DIR / "hardware_photo.png"
        if hw_img_p.exists():
            hw_raw = Image.open(hw_img_p)
            hw_target_w = 1680
            hw_target_h = int(hw_target_w * hw_raw.height / hw_raw.width)
            hw_scaled = hw_raw.resize((hw_target_w, hw_target_h), Image.LANCZOS)
            img.paste(hw_scaled, (150, 440))

        # Hardware feature callouts
        hw_callouts = [
            "• Physical 7\" Touchscreen Display", "• 4 Continuous Q-Link Rotary Knobs",
            "• 16 RGB Velocity-Sensitive Silicone Pads", "• Central Jog Wheel & Transport Buttons",
            "• Capacitive Ribbon Touch Slider", "• 4 CV/Gate Jacks & 5-pin DIN MIDI"
        ]
        for c_idx, callout in enumerate(hw_callouts):
            cx = 160 + (c_idx % 2) * 850
            cy = 1620 + (c_idx // 2) * 55
            draw.text((cx, cy), callout, font=get_font(28, bold=True), fill=TEXT_WHITE)

        # Right Card: Sovereign Web Simulator
        draw.rounded_rectangle([(1960, 260), (3740, H - 180)], radius=24, fill=CARD_BG, outline=CYAN_ACCENT, width=4)
        draw.text((2020, 310), "SOVEREIGN WEB SIMULATOR: 0700-AAM-SIM", font=get_font(42, bold=True), fill=CYAN_ACCENT)
        draw.text((2020, 370), "1:1 Photorealistic Skeuomorphic Browser Interface (Zero Install)", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Draw skeuomorphic simulator mock matching the exact physical layout
        # Outer chassis inside card
        sim_chassis_rect = [(2020, 440), (3680, 1560)]
        draw.rounded_rectangle(sim_chassis_rect, radius=20, fill=(18, 22, 28), outline=(60, 70, 82), width=3)

        # Inside simulator: 7" LCD display (left-center)
        draw.rounded_rectangle([(2060, 480), (3000, 1020)], radius=16, fill=(10, 13, 17), outline=CYAN_ACCENT, width=3)
        draw.text((2100, 520), "0700-AAM FIRMWARE OS v1.0.0", font=get_font(36, bold=True), fill=CYAN_ACCENT)
        draw.text((2650, 520), "120.0 BPM  4/4", font=get_font(36, bold=True), fill=AMBER_ACCENT)

        # Oscilloscope line
        import math
        points = []
        for x in range(2100, 2960, 12):
            y = 700 + int(90 * math.sin((x - 2100) * 0.04) * math.cos((x - 2100) * 0.012))
            points.append((x, y))
        draw.line(points, fill=GREEN_ACCENT, width=4)

        # Tab buttons below display
        tabs = ["MAIN", "GRID SEQ", "TRACK MIX", "SAMPLER", "PAD EDIT", "PREFS"]
        for idx, t in enumerate(tabs):
            bx = 2100 + idx * 140
            draw.rounded_rectangle([(bx, 930), (bx + 130, 990)], radius=8, fill=(0, 60, 80) if idx == 0 else (25, 30, 38), outline=CYAN_ACCENT if idx == 0 else BORDER_COLOR)
            draw.text((bx + 15, 948), t, font=get_font(20, bold=True), fill=CYAN_ACCENT if idx == 0 else TEXT_MUTED)

        # 4 Q-Link knobs stacked on right side of display
        draw.rounded_rectangle([(3040, 480), (3640, 1020)], radius=16, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((3080, 510), "Q-LINK ENCODERS", font=get_font(28, bold=True), fill=TEXT_WHITE)
        qnames = [("Q1: CUTOFF", "850 Hz", CYAN_ACCENT), ("Q2: RESO", "42%", AMBER_ACCENT), ("Q3: DECAY", "1.2x", GREEN_ACCENT), ("Q4: TUNE", "+2 ST", PINK_ACCENT)]
        for q_idx, (qlbl, qval, qcol) in enumerate(qnames):
            qy = 570 + q_idx * 105
            draw.ellipse([(3080, qy), (3160, qy + 80)], outline=qcol, width=4)
            draw.ellipse([(3095, qy + 15), (3145, qy + 65)], fill=(35, 42, 52))
            draw.text((3190, qy + 12), qlbl, font=get_font(26, bold=True), fill=TEXT_WHITE)
            draw.text((3190, qy + 45), qval, font=get_font(24, bold=True), fill=qcol)

        # 16 Pads in lower section
        draw.rounded_rectangle([(2060, 1060), (3180, 1520)], radius=16, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((2100, 1080), "16 VELOCITY PADS (BANKS A-H = 128 PADS)", font=get_font(26, bold=True), fill=TEXT_WHITE)
        for r in range(4):
            for c in range(4):
                px = 2100 + c * 260
                py = 1125 + r * 95
                draw.rounded_rectangle([(px, py), (px + 245, py + 85)], radius=10, fill=(30, 36, 46), outline=GREEN_ACCENT if r == 3 else CYAN_ACCENT, width=2)
                pnum = (3 - r) * 4 + c + 1
                draw.text((px + 20, py + 25), f"PAD {pnum}", font=get_font(24, bold=True), fill=TEXT_WHITE)

        # Jog Wheel & Transport in lower right
        draw.rounded_rectangle([(3220, 1060), (3640, 1520)], radius=16, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.ellipse([(3350, 1100), (3510, 1260)], fill=(35, 42, 52), outline=CYAN_ACCENT, width=4)
        draw.ellipse([(3410, 1160), (3450, 1200)], fill=(50, 60, 72))
        draw.text((3365, 1280), "JOG WHEEL", font=get_font(24, bold=True), fill=TEXT_MUTED)

        # Transport buttons
        tb_list = [("REC", (255, 64, 64)), ("PLAY", GREEN_ACCENT), ("STOP", TEXT_WHITE)]
        for t_idx, (tlbl, tcol) in enumerate(tb_list):
            tx = 3250 + t_idx * 125
            draw.rounded_rectangle([(tx, 1340), (tx + 115, 1420)], radius=10, fill=(28, 33, 42), outline=tcol, width=3)
            draw.text((tx + 25, 1365), tlbl, font=get_font(26, bold=True), fill=tcol)

        # Right feature callouts
        sim_callouts = [
            "✓ Instant 1-Click Browser Execution", "✓ Zero Dependencies & Zero Compilation",
            "✓ Procedural Web Audio Sound Engine", "✓ Binary ComProtocol WebSocket Bridge",
            "✓ 100% Passing CI Regression Harness", "✓ AGPLv3 Sovereign Open Source"
        ]
        for s_idx, scallout in enumerate(sim_callouts):
            sx = 2020 + (s_idx % 2) * 850
            sy = 1620 + (s_idx // 2) * 55
            draw.text((sx, sy), scallout, font=get_font(28, bold=True), fill=CYAN_ACCENT)

    elif vk == "touchscreen":
        # 6-view touchscreen operating interface in 4K
        draw.rounded_rectangle([(100, 260), (W - 100, H - 180)], radius=24, fill=CARD_BG, outline=BORDER_COLOR, width=3)

        views_4k = [
            ("1. MAIN SEQUENCE & REAL-TIME OSCILLOSCOPE",
             "Displays master tempo clock, live BPM readouts, bar position counter, and real-time audio oscilloscope reflecting pad velocity dynamics.",
             CYAN_ACCENT),
            ("2. 16x16 POLYPHONIC STEP SEQUENCER GRID",
             "Interactive 16-channel trigger matrix with a real-time running playhead cursor, velocity latching, and per-step parameter automation.",
             AMBER_ACCENT),
            ("3. 16-CHANNEL DIGITAL TRACK MIXER",
             "Studio mixing console with individual track level faders, live peak-hold VU meters, solo/mute latching, and master stereo bus.",
             GREEN_ACCENT),
            ("4. SAMPLE INSPECTOR & WAVEFORM CANVAS",
             "Visual sample waveform viewer with zero-crossing detection, loop point markers, and peak amplitude visualization.",
             PINK_ACCENT),
            ("5. PAD FILTER ENVELOPE (AHDSR)",
             "Attack, Hold, Decay, Sustain, and Release envelope modulation with resonant lowpass cutoff and resonance modulation.",
             (180, 120, 255)),
            ("6. PROTOCOL DIAGNOSTICS & PREFERENCES",
             "Wire-accurate hardware link diagnostics, active packet counters, loopback latency testing, and golden-file trace export.",
             TEXT_WHITE),
        ]

        for idx, (title, desc, col) in enumerate(views_4k):
            row = idx // 2
            col_idx = idx % 2
            vx = 160 + col_idx * 1780
            vy = 320 + row * 490

            draw.rounded_rectangle([(vx, vy), (vx + 1720, vy + 440)], radius=20, fill=PANEL_BG, outline=col, width=3)
            draw.text((vx + 50, vy + 45), title, font=get_font(42, bold=True), fill=col)

            # Draw mini visual schematic
            draw.rounded_rectangle([(vx + 50, vy + 120), (vx + 1670, vy + 320)], radius=12, fill=(12, 15, 20), outline=BORDER_COLOR)

            if idx == 0:
                # Oscilloscope
                import math
                pts = [(vx + 70 + x, vy + 220 + int(60 * math.sin(x * 0.05))) for x in range(0, 1580, 10)]
                draw.line(pts, fill=col, width=3)
            elif idx == 1:
                # Step sequencer grid
                for step in range(16):
                    sx = vx + 80 + step * 98
                    draw.rectangle([(sx, vy + 150), (sx + 85, vy + 290)], fill=(0, 60, 50) if step % 4 == 0 else (25, 30, 38), outline=col if step == 4 else BORDER_COLOR)
            elif idx == 2:
                # Track mixer VU bars
                for ch in range(16):
                    cx = vx + 80 + ch * 98
                    vu_h = int(120 * (0.4 + 0.5 * (ch % 3) / 2))
                    draw.rectangle([(cx, vy + 300 - vu_h), (cx + 60, vy + 300)], fill=col)
            else:
                # Waveform / envelope
                draw.line([(vx + 100, vy + 280), (vx + 350, vy + 150), (vx + 700, vy + 220), (vx + 1200, vy + 220), (vx + 1550, vy + 280)], fill=col, width=4)

            draw.text((vx + 50, vy + 350), desc, font=get_font(26, bold=False), fill=TEXT_MUTED)

    elif vk == "pads":
        # 16 RGB velocity pads & sound engine
        draw.rounded_rectangle([(100, 260), (W - 100, H - 180)], radius=24, fill=CARD_BG, outline=BORDER_COLOR, width=3)

        # Bank Selector Row
        draw.text((160, 310), "ACTIVE PAD BANK SELECTOR (BANKS A THROUGH H — 128 VIRTUAL PADS):", font=get_font(36, bold=True), fill=TEXT_WHITE)
        banks = [("BANK A", CYAN_ACCENT), ("BANK B", AMBER_ACCENT), ("BANK C", GREEN_ACCENT), ("BANK D", PINK_ACCENT),
                 ("BANK E", (255, 235, 59)), ("BANK F", (179, 136, 255)), ("BANK G", (255, 82, 82)), ("BANK H", TEXT_WHITE)]
        for b_idx, (bname, bcol) in enumerate(banks):
            bx = 160 + b_idx * 440
            draw.rounded_rectangle([(bx, 380), (bx + 410, 480)], radius=12, fill=(0, 60, 75) if b_idx == 0 else PANEL_BG, outline=bcol, width=3 if b_idx == 0 else 1)
            draw.text((bx + 110, 410), bname, font=get_font(32, bold=True), fill=bcol)

        # 4x4 Grid in 4K
        pads_4k = [
            ("13. SUB BASS 1", "1", "45 Hz Saw-Sine Wave", (180, 100, 255)),
            ("14. SUB BASS 2", "2", "55 Hz 808 Sine Tone", (180, 100, 255)),
            ("15. SUB BASS 3", "3", "65 Hz Resonant Acid", (180, 100, 255)),
            ("16. SUB BASS 4", "4", "75 Hz Sub Drop", (180, 100, 255)),

            ("9. RIMSHOT", "Q", "Acoustic Hard Rim", CYAN_ACCENT),
            ("10. SHAKER", "W", "16th Metallic Shaker", CYAN_ACCENT),
            ("11. CRASH", "E", "Dual Cymbal Ring", CYAN_ACCENT),
            ("12. RIDE BELL", "R", "Brass Ping Transient", CYAN_ACCENT),

            ("5. CLAP 808", "A", "Triple Stutter Burst", AMBER_ACCENT),
            ("6. TOM LOW", "S", "Analog Pitch Envelope", AMBER_ACCENT),
            ("7. TOM MID", "D", "Resonant Body Tom", AMBER_ACCENT),
            ("8. TOM HIGH", "F", "Tight Pitch Decay", AMBER_ACCENT),

            ("1. KICK 808", "Z", "Pitch-Envelope Sub", GREEN_ACCENT),
            ("2. SNARE 909", "X", "Dual-Osc Noise Wire", GREEN_ACCENT),
            ("3. CLOSED HH", "C", "6-Osc Metal Cluster", GREEN_ACCENT),
            ("4. OPEN HH", "V", "Extended Sizzle Tail", GREEN_ACCENT),
        ]

        for p_idx, (pname, hotkey, desc, col) in enumerate(pads_4k):
            p_row = p_idx // 4
            p_col = p_idx % 4
            px = 160 + p_col * 885
            py = 530 + p_row * 330

            draw.rounded_rectangle([(px, py), (px + 840, py + 290)], radius=20, fill=PANEL_BG, outline=col, width=3)
            draw.ellipse([(px + 40, py + 40), (px + 90, py + 90)], fill=col)

            draw.text((px + 120, py + 45), pname, font=get_font(38, bold=True), fill=TEXT_WHITE)

            # Hotkey badge
            draw.rounded_rectangle([(px + 690, py + 35), (px + 790, py + 105)], radius=10, fill=(35, 42, 54), outline=col, width=2)
            draw.text((px + 725, py + 48), hotkey, font=get_font(36, bold=True), fill=col)

            draw.text((px + 120, py + 130), desc, font=get_font(30, bold=False), fill=TEXT_MUTED)
            draw.rectangle([(px + 120, py + 210), (px + 750, py + 220)], fill=(30, 36, 46))
            draw.rectangle([(px + 120, py + 210), (px + 520, py + 220)], fill=col)

    elif vk == "protocol":
        # Wire-Accurate ComProtocol & Open Source Launch in 4K
        draw.rounded_rectangle([(100, 260), (W - 100, H - 180)], radius=24, fill=CARD_BG, outline=BORDER_COLOR, width=3)

        # Left 4K Card: ComProtocol
        draw.rounded_rectangle([(160, 310), (1880, H - 240)], radius=20, fill=PANEL_BG, outline=CYAN_ACCENT, width=3)
        draw.text((220, 370), "WIRE-ACCURATE BINARY COMPROTOCOL", font=get_font(44, bold=True), fill=CYAN_ACCENT)

        proto_items_4k = [
            ("Header Preamble", "2 bytes: 0x4D 0x54 ('M' 'T') matches hardware UART bus exactly", CYAN_ACCENT),
            ("Packet Direction", "0x00 Request (Device->Host) / 0x01 Response (Host->Device)", TEXT_WHITE),
            ("Packet Type Routing", "EN_PKT_PAD (0x03), EN_PKT_KNOBS (0x04), EN_PKT_BUTTON (0x01), EN_PKT_SYSTEM (0x00)", AMBER_ACCENT),
            ("Payload Encoding", "Variable N-byte payload (Pad ID, Velocity, RGB LED Color, Knob Delta)", TEXT_WHITE),
            ("CRC-8 Checksum", "CRC-8 with generator polynomial 0x31 (x^8 + x^5 + x^4 + 1), initial value 0xFF", GREEN_ACCENT),
            ("Live WebSocket Bridge", "Bidirectional binary/JSON frame relay at ws://127.0.0.1:8080/ws", PINK_ACCENT),
            ("Automated CI Testing", "4 out of 4 test suites passing in 0.27s (Protocol, Hardware, Transport, Golden)", GREEN_ACCENT),
        ]
        for p_idx, (p_title, p_desc, p_col) in enumerate(proto_items_4k):
            py = 480 + p_idx * 160
            draw.text((220, py), f"• {p_title}:", font=get_font(34, bold=True), fill=p_col)
            draw.text((260, py + 55), p_desc, font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Right 4K Card: Deployment & Open Source
        draw.rounded_rectangle([(1960, 310), (3680, H - 240)], radius=20, fill=PANEL_BG, outline=GREEN_ACCENT, width=3)
        draw.text((2020, 370), "SOVEREIGN OPEN SOURCE DEPLOYMENT", font=get_font(44, bold=True), fill=GREEN_ACCENT)

        # Live Demo Box
        draw.rounded_rectangle([(2020, 480), (3620, 750)], radius=16, fill=(12, 38, 28), outline=GREEN_ACCENT, width=3)
        draw.text((2060, 520), "LIVE DEMO RUNNING ON GITHUB PAGES:", font=get_font(32, bold=True), fill=GREEN_ACCENT)
        draw.text((2060, 590), "https://rasrobo.github.io/0700-aam-sim/", font=get_font(44, bold=True), fill=TEXT_WHITE)
        draw.text((2060, 670), "Zero Install — Open directly in Chrome, Firefox, Safari, or Edge", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Public GitHub Repo Box
        draw.rounded_rectangle([(2020, 800), (3620, 1070)], radius=16, fill=CARD_BG, outline=CYAN_ACCENT, width=3)
        draw.text((2060, 840), "PUBLIC GITHUB REPOSITORY:", font=get_font(32, bold=True), fill=CYAN_ACCENT)
        draw.text((2060, 910), "https://github.com/rasrobo/0700-aam-sim", font=get_font(44, bold=True), fill=TEXT_WHITE)
        draw.text((2060, 990), "Clone, build with CMake, and run automated scenario golden tests", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Music Attribution & License Box
        draw.rounded_rectangle([(2020, 1120), (3620, 1600)], radius=16, fill=CARD_BG, outline=BORDER_COLOR, width=2)
        draw.text((2060, 1160), "OPEN SOURCE & ATTRIBUTION NOTICES:", font=get_font(32, bold=True), fill=AMBER_ACCENT)
        attrs = [
            "• Software License: GNU Affero General Public License v3.0 (AGPL-3.0-or-later)",
            "• Music Track: \"The Complex\" by Kevin MacLeod (incompetech.com)",
            "• Music License: Creative Commons Attribution 4.0 International (CC-BY 4.0)",
            "• Upstream Hardware: Based on BE 0700-AAM architecture by Music Tribe",
            "• Non-Affiliation: Independent simulator; not affiliated with Music Tribe / Behringer"
        ]
        for a_idx, atxt in enumerate(attrs):
            draw.text((2060, 1225 + a_idx * 65), atxt, font=get_font(28, bold=False), fill=TEXT_WHITE)

    img.save(out_path, quality=95)
    return out_path

def render_4k_scene_clip(scene_info: Dict[str, Any], timing: Dict[str, Any], out_mp4: Path) -> Path:
    if out_mp4.exists() and out_mp4.stat().st_size > 1000:
        print(f"Clip {out_mp4.name} already exists, reusing existing 4K render.")
        return out_mp4

    dur = max(4.0, float(timing["duration"]))
    frame_png = out_mp4.with_suffix(".png")
    generate_4k_scene_image(scene_info, frame_png)

    frames = int(dur * FPS)
    # Slow subtle 4K Ken Burns push-in
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
    print("=== [1/5] Synthesizing Voiceover with Open-Source Music (Kevin MacLeod) ===")
    # Use CC-BY 4.0 open source music: The Complex by Kevin MacLeod
    open_source_music = MUSIC_DIR / "the_complex_investigative_score.mp3"
    assert open_source_music.exists(), f"Missing music: {open_source_music}"

    audio = build_documentary_audio(
        scenes=SCENES,
        voice="en-US-ChristopherNeural",
        music_track=open_source_music,
        prefix="0700_gui_4k"
    )

    timings = {t["id"]: t for t in audio["scene_timings"]}
    total_duration = audio["total_duration"]
    print(f"Total Video Runtime: {total_duration:.2f}s across {len(SCENES)} acts.")

    print("=== [2/5] Rendering High-Definition 4K UHD (3840x2160) Visual Clips ===")
    clips: List[Path] = []
    for sc in SCENES:
        sid = sc["id"]
        clip_path = CLIPS_DIR / f"gui_4k_scene_{sid:02d}.mp4"
        print(f"Rendering Act {sid}: {sc['title']} ({timings[sid]['duration']:.2f}s) in 4K...")
        render_4k_scene_clip(sc, timings[sid], clip_path)
        clips.append(clip_path)

    final_mp4 = OUTPUT_DIR / "0700_aam_gui_showcase_4k.mp4"
    print(f"=== [3/5] Muxing Clean 4K Master (burn_subtitles=False) ===")
    render_full_documentary(
        scene_clips=clips,
        audio_master=audio["final_audio"],
        subtitles_srt=audio["master_srt"],
        output_mp4=final_mp4,
        total_duration=total_duration,
        burn_subtitles=False
    )

    srt_out = OUTPUT_DIR / "0700_aam_gui_showcase_4k.srt"
    shutil.copy2(audio["master_srt"], srt_out)
    print(f"Master 4K MP4 Generated: {final_mp4} ({final_mp4.stat().st_size / (1024*1024):.1f} MB)")
    print(f"Master SRT Subtitles Saved: {srt_out}")

    print("=== [4/5] Copying 4K Master to gpu.sqs.chat for YouTube Upload ===")
    subprocess.run(["scp", str(final_mp4), "gpu.sqs.chat:/tmp/0700_aam_gui_showcase_4k.mp4"], check=True)

    print("=== [5/5] Uploading 4K Demo Video to YouTube via gpu.sqs.chat ===")
    yt_cmd = (
        "~/install-recordings/youtube/youtube-auth-upload.sh "
        "/tmp/0700_aam_gui_showcase_4k.mp4 "
        "\"0700-AAM Sovereign Web Hardware Simulator (4K Demo & Walkthrough)\" "
        "--desc \"Walkthrough of the 0700-AAM Sovereign Web Simulator in 4K Ultra HD. 1:1 photorealistic skeuomorphic hardware simulation of the BE 0700-AAM groovebox with procedural Web Audio synthesis, 6-view touchscreen operating interface, 128 virtual pads (Banks A-H), knurled Q-Link encoders, and binary ComProtocol WebSocket bridge.\n\nLive 1-Click Web Demo: https://rasrobo.github.io/0700-aam-sim/\nGitHub Repository: https://github.com/rasrobo/0700-aam-sim\n\nMusic: 'The Complex' by Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0 License (http://creativecommons.org/licenses/by/4.0/)\nIndependent simulator; not affiliated with Music Tribe / Behringer.\" "
        "--tags \"0700-aam,groovebox,synthesizer,4k,web-audio,simulator,musictribe,firmware,hardware-simulation,juce,cpp\""
    )
    result = subprocess.run(["ssh", "gpu.sqs.chat", yt_cmd], capture_output=True, text=True, check=True)
    print("YouTube Upload Output:")
    print(result.stdout)
    if result.stderr:
        print("YouTube Stderr:", result.stderr)

    # Clean remote temp
    subprocess.run(["ssh", "gpu.sqs.chat", "rm -f /tmp/0700_aam_gui_showcase_4k.mp4"], check=False)
    print("=== ALL COMPLETE ===")

if __name__ == "__main__":
    main()
