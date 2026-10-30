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
            "and a tactile navigation cluster. And this is 0700-AAM-SIM: our photorealistic, one-to-one "
            "skeuomorphic software simulator running directly in your web browser with complete hardware button parity—"
            "with every single button in the exact same location as the physical device: the four function columns "
            "directly beneath the touchscreen flanking the central jog wheel, Bank select A through D with individual status LEDs, "
            "and the four corner buttons Back, Copy, minus, and plus surrounding the central data wheel."
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
        draw.text((2020, 370), "1:1 Photorealistic Skeuomorphic Browser Interface (1:1 Hardware Button Parity)", font=get_font(28, bold=False), fill=TEXT_MUTED)

        # Draw skeuomorphic simulator mock matching the exact physical layout
        # Outer chassis inside card
        sim_chassis_rect = [(2000, 440), (3700, 1560)]
        draw.rounded_rectangle(sim_chassis_rect, radius=20, fill=(18, 22, 28), outline=(60, 70, 82), width=3)

        # 1. LEFT: Touch Strip + 16 RGB Velocity Pads (x: 2020 to 2480)
        # Touch Strip Ribbon
        draw.rounded_rectangle([(2020, 480), (2045, 1260)], radius=6, fill=(10, 12, 16), outline=BORDER_COLOR)
        draw.rectangle([(2025, 800), (2040, 840)], fill=CYAN_ACCENT)
        # 16 Pads (4x4)
        draw.rounded_rectangle([(2060, 480), (2480, 1260)], radius=14, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((2080, 500), "16 VELOCITY PADS", font=get_font(22, bold=True), fill=TEXT_WHITE)
        pad_colors_row = [GREEN_ACCENT, AMBER_ACCENT, CYAN_ACCENT, (180, 100, 255)]
        for r in range(4):
            for c in range(4):
                px = 2080 + c * 96
                py = 540 + r * 140
                pcol = pad_colors_row[3 - r]
                draw.rounded_rectangle([(px, py), (px + 86, py + 120)], radius=8, fill=(28, 34, 44), outline=pcol, width=2)
                pnum = (3 - r) * 4 + c + 1
                draw.text((px + 12, py + 15), f"P{pnum}", font=get_font(18, bold=True), fill=TEXT_WHITE)
        # Pad utility buttons under pads
        pad_utils = ["FULL LVL", "16 LVL", "ERASE"]
        for u_idx, utxt in enumerate(pad_utils):
            ux = 2080 + u_idx * 130
            draw.rounded_rectangle([(ux, 1140), (ux + 115, 1200)], radius=6, fill=(25, 30, 38), outline=BORDER_COLOR)
            draw.text((ux + 15, 1160), utxt, font=get_font(16, bold=True), fill=AMBER_ACCENT if u_idx < 2 else PINK_ACCENT)

        # 2. CENTER: 7" LCD Display + 2x5 Mode Matrix + 1:1 Jog Wheel Surround Bezel (x: 2500 to 3380)
        # 7" LCD display (top-center)
        draw.rounded_rectangle([(2500, 480), (3380, 880)], radius=14, fill=(10, 13, 17), outline=CYAN_ACCENT, width=3)
        draw.text((2530, 505), "0700-AAM FIRMWARE OS v1.0.0", font=get_font(28, bold=True), fill=CYAN_ACCENT)
        draw.text((3120, 505), "120.0 BPM", font=get_font(28, bold=True), fill=AMBER_ACCENT)
        # Live Oscilloscope inside display
        import math
        points = []
        for x in range(2530, 3350, 10):
            y = 660 + int(70 * math.sin((x - 2530) * 0.04) * math.cos((x - 2530) * 0.015))
            points.append((x, y))
        draw.line(points, fill=GREEN_ACCENT, width=3)
        # 6 View Tabs
        tabs = ["MAIN", "GRID", "MIXER", "SAMPLE", "EDIT", "PREFS"]
        for idx, t in enumerate(tabs):
            bx = 2530 + idx * 135
            draw.rounded_rectangle([(bx, 810), (bx + 125, 860)], radius=6, fill=(0, 60, 80) if idx == 0 else (22, 26, 34), outline=CYAN_ACCENT if idx == 0 else BORDER_COLOR)
            draw.text((bx + 18, 825), t, font=get_font(18, bold=True), fill=CYAN_ACCENT if idx == 0 else TEXT_MUTED)

        # 1:1 Physical Hardware Control Deck Directly Beneath 7" Display (y: 895 to 1540)
        draw.rounded_rectangle([(2500, 895), (3380, 1540)], radius=14, fill=PANEL_BG, outline=BORDER_COLOR, width=2)

        # 1. LEFT FLANK: Columns 1 & 2 (x: 2515 to 2760)
        # Col 1: MAIN, TAP TEMPO, NOTE REPEAT, STEP SEQ
        col1_btns = [("MAIN", "GRID", CYAN_ACCENT), ("TAP TEMPO", "MASTER", TEXT_WHITE), ("NOTE REPEAT", "LATCH", TEXT_WHITE), ("STEP SEQ", "AUTOMATION", TEXT_WHITE)]
        for idx, (p_text, s_text, col) in enumerate(col1_btns):
            by = 915 + idx * 115
            draw.rounded_rectangle([(2515, by), (2630, by + 85)], radius=6, fill=(28, 33, 42), outline=col, width=2 if idx == 0 else 1)
            draw.text((2530, by + 18), p_text, font=get_font(15, bold=True), fill=col)
            draw.text((2530, by + 48), s_text, font=get_font(12, bold=False), fill=TEXT_MUTED)

        # Col 2: BROWSE, TRACK MIX, TRACK MUTE
        col2_btns = [("BROWSE", "SAVE", TEXT_WHITE), ("TRACK MIX", "PAD MIX", TEXT_WHITE), ("TRACK MUTE", "PAD MUTE", TEXT_WHITE)]
        for idx, (p_text, s_text, col) in enumerate(col2_btns):
            by = 915 + idx * 115
            draw.rounded_rectangle([(2645, by), (2760, by + 85)], radius=6, fill=(28, 33, 42), outline=col, width=1)
            draw.text((2660, by + 18), p_text, font=get_font(15, bold=True), fill=col)
            draw.text((2660, by + 48), s_text, font=get_font(12, bold=False), fill=TEXT_MUTED)

        # 2. CENTER: Banks A-D on top + Central Jog Wheel flanked by 4 corner buttons (x: 2775 to 3105)
        # Banks Row
        banks_short = [("BANK A", CYAN_ACCENT), ("BANK B", AMBER_ACCENT), ("BANK C", GREEN_ACCENT), ("BANK D", PINK_ACCENT)]
        for b_idx, (bname, bcol) in enumerate(banks_short):
            bx = 2775 + b_idx * 82
            draw.rounded_rectangle([(bx, 915), (bx + 76, 985)], radius=6, fill=(0, 45, 60) if b_idx == 0 else (24, 28, 36), outline=bcol, width=2 if b_idx == 0 else 1)
            draw.ellipse([(bx + 12, 930), (bx + 22, 940)], fill=bcol)
            draw.text((bx + 26, 926), bname.split()[1], font=get_font(14, bold=True), fill=TEXT_WHITE)
            draw.text((bx + 26, 952), ["E", "F", "G", "H"][b_idx], font=get_font(12, bold=False), fill=TEXT_MUTED)

        # 4 Corner Buttons surrounding the Jog Wheel:
        # Top-Left: BACK / UNDO
        draw.rounded_rectangle([(2775, 1030), (2880, 1115)], radius=6, fill=(28, 33, 42), outline=BORDER_COLOR)
        draw.text((2800, 1045), "BACK", font=get_font(16, bold=True), fill=TEXT_WHITE)
        draw.text((2800, 1075), "UNDO", font=get_font(12, bold=False), fill=TEXT_MUTED)

        # Top-Right: COPY / PASTE
        draw.rounded_rectangle([(3000, 1030), (3105, 1115)], radius=6, fill=(28, 33, 42), outline=BORDER_COLOR)
        draw.text((3025, 1045), "COPY", font=get_font(16, bold=True), fill=TEXT_WHITE)
        draw.text((3025, 1075), "PASTE", font=get_font(12, bold=False), fill=TEXT_MUTED)

        # Central Rotary Jog Wheel (centered between the 4 corner buttons)
        draw.ellipse([(2835, 1100), (3045, 1310)], fill=(35, 40, 50), outline=CYAN_ACCENT, width=4)
        draw.ellipse([(2865, 1125), (2905, 1165)], fill=(20, 24, 30)) # finger dimple
        draw.ellipse([(2895, 1160), (2985, 1250)], fill=(50, 58, 70), outline=(90, 100, 115)) # enter button
        draw.text((2915, 1195), "ENTER", font=get_font(16, bold=True), fill=TEXT_WHITE)

        # Bottom-Left: - / DEC
        draw.rounded_rectangle([(2775, 1295), (2880, 1380)], radius=6, fill=(28, 33, 42), outline=BORDER_COLOR)
        draw.text((2815, 1310), "-", font=get_font(24, bold=True), fill=TEXT_WHITE)
        draw.text((2805, 1345), "DEC", font=get_font(12, bold=False), fill=TEXT_MUTED)

        # Bottom-Right: + / INC
        draw.rounded_rectangle([(3000, 1295), (3105, 1380)], radius=6, fill=(28, 33, 42), outline=BORDER_COLOR)
        draw.text((3040, 1310), "+", font=get_font(24, bold=True), fill=TEXT_WHITE)
        draw.text((3035, 1345), "INC", font=get_font(12, bold=False), fill=TEXT_MUTED)

        # 3. RIGHT FLANK: Columns 4 & 5 (x: 3120 to 3365)
        # Col 4: TC, SAMPLER, SAMPLE EDIT
        col4_btns = [("TC", "ON/OFF", TEXT_WHITE), ("SAMPLER", "LOOPER", TEXT_WHITE), ("SMP EDIT", "LINK EDIT", TEXT_WHITE)]
        for idx, (p_text, s_text, col) in enumerate(col4_btns):
            by = 915 + idx * 115
            draw.rounded_rectangle([(3120, by), (3235, by + 85)], radius=6, fill=(28, 33, 42), outline=col, width=1)
            draw.text((3135, by + 18), p_text, font=get_font(15, bold=True), fill=col)
            draw.text((3135, by + 48), s_text, font=get_font(12, bold=False), fill=TEXT_MUTED)

        # Col 5: NEXT SEQ, MENU, SHIFT, PROG EDIT
        col5_btns = [("NEXT SEQ", "FX", TEXT_WHITE), ("MENU", "PREFS", TEXT_WHITE), ("SHIFT", "LOCK", AMBER_ACCENT), ("PROG EDIT", "MIDI CTRL", TEXT_WHITE)]
        for idx, (p_text, s_text, col) in enumerate(col5_btns):
            by = 915 + idx * 115
            draw.rounded_rectangle([(3250, by), (3365, by + 85)], radius=6, fill=(45, 38, 24) if idx == 2 else (28, 33, 42), outline=col, width=2 if idx == 2 else 1)
            if idx == 2:
                draw.ellipse([(3265, by + 15), (3275, by + 25)], fill=AMBER_ACCENT)
                draw.text((3285, by + 15), p_text, font=get_font(15, bold=True), fill=col)
            else:
                draw.text((3265, by + 18), p_text, font=get_font(15, bold=True), fill=col)
            draw.text((3265, by + 48), s_text, font=get_font(12, bold=False), fill=TEXT_MUTED)

        # 3. RIGHT: 4 Q-Link Encoders + 5 Transport Buttons (x: 3410 to 3680)
        draw.rounded_rectangle([(3410, 480), (3680, 1020)], radius=14, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((3430, 505), "4 Q-LINKS", font=get_font(22, bold=True), fill=TEXT_WHITE)
        qnames = [("Q1", "850 Hz", CYAN_ACCENT), ("Q2", "42%", AMBER_ACCENT), ("Q3", "1.2x", GREEN_ACCENT), ("Q4", "+2 ST", PINK_ACCENT)]
        for q_idx, (qlbl, qval, qcol) in enumerate(qnames):
            qy = 550 + q_idx * 110
            draw.ellipse([(3430, qy), (3500, qy + 70)], outline=qcol, width=3)
            draw.ellipse([(3445, qy + 15), (3485, qy + 55)], fill=(35, 42, 52))
            draw.text((3520, qy + 12), qlbl, font=get_font(20, bold=True), fill=TEXT_WHITE)
            draw.text((3520, qy + 40), qval, font=get_font(18, bold=True), fill=qcol)

        # 5 Transport Buttons
        draw.rounded_rectangle([(3410, 1050), (3680, 1530)], radius=14, fill=PANEL_BG, outline=BORDER_COLOR, width=2)
        draw.text((3430, 1070), "TRANSPORT", font=get_font(20, bold=True), fill=TEXT_WHITE)
        tb_list = [("REC", (255, 64, 64)), ("OVERDUB", AMBER_ACCENT), ("STOP", TEXT_WHITE), ("PLAY", GREEN_ACCENT), ("PLAY START", GREEN_ACCENT)]
        for t_idx, (tlbl, tcol) in enumerate(tb_list):
            ty = 1110 + t_idx * 78
            draw.rounded_rectangle([(3430, ty), (3660, ty + 65)], radius=8, fill=(28, 33, 42), outline=tcol, width=2)
            draw.ellipse([(3445, ty + 25), (3457, ty + 37)], fill=tcol)
            draw.text((3470, ty + 20), tlbl, font=get_font(20, bold=True), fill=tcol)

        # Right feature callouts
        sim_callouts = [
            "✓ 1:1 Hardware Button Parity (Jog & Cursors)", "✓ Instant 1-Click Zero-Install Web Execution",
            "✓ Full 2x5 Mode Matrix & 8 Pad Banks", "✓ Procedural Web Audio Zero-Latency Synth",
            "✓ Binary ComProtocol WebSocket Bridge", "✓ AGPLv3 Sovereign Open Source"
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
        "\"0700-AAM Sovereign Web Hardware Simulator (1:1 Hardware Parity & 4K Demo)\" "
        "--desc \"Walkthrough of the 0700-AAM Sovereign Web Simulator in 4K Ultra HD featuring 1:1 physical control surface parity with the BE 0700-AAM groovebox. Complete hardware button matrix including directional D-Pad cursors around the central jog wheel, Back/Undo, Copy/Paste, +/- increment buttons, Bank Select with illuminated status LEDs, procedural Web Audio synthesis, 6-view touchscreen operating interface, 128 virtual pads, knurled Q-Link encoders, and binary ComProtocol WebSocket bridge.\n\nLive 1-Click Web Demo: https://rasrobo.github.io/0700-aam-sim/\nGitHub Repository: https://github.com/rasrobo/0700-aam-sim\n\nMusic: 'The Complex' by Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0 License (http://creativecommons.org/licenses/by/4.0/)\nIndependent simulator; not affiliated with Music Tribe / Behringer.\" "
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
