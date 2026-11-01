import math
import os
import shutil
import subprocess
import threading
import time

import arabic_reshaper
from flask import Flask, Response, abort, send_from_directory
from PIL import Image, ImageDraw, ImageFont

try:
    from bidi import get_display
except ImportError:
    from bidi.algorithm import get_display


class Config:
    CHANNEL_NAME = "LMC HD"
    WIDTH = 854
    HEIGHT = 480
    FPS = 25
    VIDEO_BITRATE = "450k"
    AUDIO_BITRATE = "32k"
    HLS_TIME = 6
    HLS_LIST_SIZE = 6
    PORT = 10000
    HLS_DIR = "/tmp/hls"
    LOGO_PATH = "/tmp/logo.png"
    TICKER_PATH = "/tmp/ticker.png"
    BASE_CLIP = "/tmp/base.mp4"
    PLAYLIST = "lmc_hd.m3u8"

    LOGO_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    TICKER_FONTS = ["Amiri-Bold.ttf", "Amiri-Regular.ttf"]

    TICKER_TEXT = "ينطلق البث الرسمي لقناة LMC HD بتاريخ 18 ديسمبر 2026 — ترقبونا"
    TICKER_FONT_SIZE = 40
    TICKER_SPEED = 100  # pixels per second (approximate)
    TICKER_PADDING = 40
    BAR_H = 64

    BG_TOP = (8, 12, 28)
    BG_BOTTOM = (20, 30, 70)
    BAR_COLOR = (255, 255, 255)
    BAR_LINE_COLOR = (230, 190, 90)
    TICKER_COLOR = (0, 0, 0)
    GOLD = (230, 190, 90)
    WHITE = (255, 255, 255)
    RESTART_DELAY = 3


app = Flask(__name__)


def find_ticker_font():
    for name in Config.TICKER_FONTS:
        for root, _dirs, files in os.walk("/usr/share/fonts"):
            if name in files:
                return os.path.join(root, name)
    return Config.LOGO_FONT


def make_logo():
    w, h = Config.WIDTH, Config.HEIGHT
    s = h / 1080.0

    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / (h - 1)
        color = tuple(
            int(Config.BG_TOP[i] + (Config.BG_BOTTOM[i] - Config.BG_TOP[i]) * t)
            for i in range(3)
        )
        draw.line([(0, y), (w, y)], fill=color)

    big = ImageFont.truetype(Config.LOGO_FONT, int(380 * s))
    small = ImageFont.truetype(Config.LOGO_FONT, int(170 * s))

    parts = Config.CHANNEL_NAME.split(" ", 1)
    main_text = parts[0]
    sub_text = parts[1] if len(parts) > 1 else ""

    # logo is shifted up a little to leave room for the bottom bar
    shift = Config.BAR_H // 2

    b1 = draw.textbbox((0, 0), main_text, font=big)
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    x1 = (w - w1) // 2 - b1[0]
    y1 = h // 2 - h1 - int(30 * s) - b1[1] - shift
    draw.text((x1, y1), main_text, font=big, fill=Config.WHITE)

    line_y = h // 2 + int(20 * s) - shift
    half = int(330 * s)
    draw.rectangle(
        [(w // 2 - half, line_y), (w // 2 + half, line_y + max(2, int(8 * s)))],
        fill=Config.GOLD,
    )

    if sub_text:
        b2 = draw.textbbox((0, 0), sub_text, font=small)
        w2 = b2[2] - b2[0]
        x2 = (w - w2) // 2 - b2[0]
        y2 = line_y + int(50 * s) - b2[1]
        draw.text((x2, y2), sub_text, font=small, fill=Config.GOLD)

    # bottom bar for the ticker (white bar with a thin gold line on top)
    bar_top = h - Config.BAR_H
    draw.rectangle([(0, bar_top), (w, h)], fill=Config.BAR_COLOR)
    draw.rectangle([(0, bar_top), (w, bar_top + 3)], fill=Config.BAR_LINE_COLOR)

    img.save(Config.LOGO_PATH)


def make_ticker():
    """Render the Arabic ticker text as a transparent PNG. Returns its width."""
    font = ImageFont.truetype(
        find_ticker_font(),
        Config.TICKER_FONT_SIZE,
        layout_engine=ImageFont.Layout.BASIC,
    )
    text = get_display(arabic_reshaper.reshape(Config.TICKER_TEXT))

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = probe.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]

    pad = Config.TICKER_PADDING
    img = Image.new("RGBA", (tw + pad * 2, Config.BAR_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad - bb[0]
    y = (Config.BAR_H - th) // 2 - bb[1] + 2
    d.text((x, y), text, font=font, fill=Config.TICKER_COLOR + (255,))
    img.save(Config.TICKER_PATH)
    return img.width


def encode_base_clip(ticker_w):
    """Encode ONE seamless loop: the text crosses the screen exactly once."""
    fps = Config.FPS
    gop = fps * Config.HLS_TIME
    span = Config.WIDTH + ticker_w
    cycles = math.ceil(span / float(Config.TICKER_SPEED) / Config.HLS_TIME)
    duration = cycles * Config.HLS_TIME
    speed = span / float(duration)
    y = Config.HEIGHT - Config.BAR_H

    flt = (
        "[0:v][1:v]overlay=x='W-mod(t*%.4f,W+w)':y=%d:eof_action=repeat,"
        "format=yuv420p[v]" % (speed, y)
    )

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-loop", "1", "-framerate", str(fps), "-i", Config.LOGO_PATH,
        "-i", Config.TICKER_PATH,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex", flt,
        "-map", "[v]", "-map", "2:a",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-r", str(fps),
        "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
        "-b:v", Config.VIDEO_BITRATE,
        "-maxrate", Config.VIDEO_BITRATE,
        "-bufsize", "900k",
        "-c:a", "aac", "-b:a", Config.AUDIO_BITRATE,
        "-shortest",
        Config.BASE_CLIP,
    ]
    subprocess.run(cmd, check=True)


def build_stream_cmd():
    """Loop the encoded clip with no re-encoding (near-zero CPU)."""
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-re", "-stream_loop", "-1", "-i", Config.BASE_CLIP,
        "-c", "copy",
        "-f", "hls",
        "-hls_time", str(Config.HLS_TIME),
        "-hls_list_size", str(Config.HLS_LIST_SIZE),
        "-hls_flags", "delete_segments+independent_segments",
        "-hls_segment_filename", os.path.join(Config.HLS_DIR, "seg_%05d.ts"),
        os.path.join(Config.HLS_DIR, Config.PLAYLIST),
    ]


def stream_supervisor():
    while True:
        try:
            if not os.path.isfile(Config.BASE_CLIP):
                print("[LMC] preparing logo and ticker...", flush=True)
                make_logo()
                ticker_w = make_ticker()
                print("[LMC] encoding base clip...", flush=True)
                encode_base_clip(ticker_w)
                print("[LMC] base clip ready", flush=True)

            shutil.rmtree(Config.HLS_DIR, ignore_errors=True)
            os.makedirs(Config.HLS_DIR, exist_ok=True)
            print("[LMC] starting stream", flush=True)
            proc = subprocess.Popen(build_stream_cmd())
            proc.wait()
            print("[LMC] stream stopped, restarting...", flush=True)
        except Exception as e:
            print("[LMC] supervisor error:", e, flush=True)
            try:
                os.remove(Config.BASE_CLIP)
            except OSError:
                pass
        time.sleep(Config.RESTART_DELAY)


@app.after_request
def add_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


@app.route("/")
def index():
    return Response(
        "%s is live: /live/%s" % (Config.CHANNEL_NAME, Config.PLAYLIST),
        mimetype="text/plain",
    )


@app.route("/ping")
def ping():
    return Response("ok", mimetype="text/plain")


@app.route("/live/<path:name>")
def live(name):
    full = os.path.join(Config.HLS_DIR, name)
    if not os.path.isfile(full):
        abort(404)
    resp = send_from_directory(Config.HLS_DIR, name)
    if name.endswith(".m3u8"):
        resp.headers["Content-Type"] = "application/vnd.apple.mpegurl"
        resp.headers["Cache-Control"] = "no-cache, no-store"
    elif name.endswith(".ts"):
        resp.headers["Content-Type"] = "video/mp2t"
    return resp


threading.Thread(target=stream_supervisor, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT)
