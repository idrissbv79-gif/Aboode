import os
import shutil
import subprocess
import threading
import time

from flask import Flask, Response, abort, send_from_directory
from PIL import Image, ImageDraw, ImageFont


class Config:
    CHANNEL_NAME = "LMC HD"
    WIDTH = 854
    HEIGHT = 480
    FPS = 10
    VIDEO_BITRATE = "250k"
    AUDIO_BITRATE = "32k"
    HLS_TIME = 6
    HLS_LIST_SIZE = 6
    PORT = 10000
    HLS_DIR = "/tmp/hls"
    LOGO_PATH = "/tmp/logo.png"
    BASE_CLIP = "/tmp/base.mp4"
    PLAYLIST = "lmc_hd.m3u8"
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    BG_TOP = (8, 12, 28)
    BG_BOTTOM = (20, 30, 70)
    GOLD = (230, 190, 90)
    WHITE = (255, 255, 255)
    RESTART_DELAY = 3


app = Flask(__name__)


def make_logo():
    w, h = Config.WIDTH, Config.HEIGHT
    s = h / 1080.0  # scale factor relative to the 1080p design

    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / (h - 1)
        color = tuple(
            int(Config.BG_TOP[i] + (Config.BG_BOTTOM[i] - Config.BG_TOP[i]) * t)
            for i in range(3)
        )
        draw.line([(0, y), (w, y)], fill=color)

    big = ImageFont.truetype(Config.FONT_PATH, int(380 * s))
    small = ImageFont.truetype(Config.FONT_PATH, int(170 * s))

    parts = Config.CHANNEL_NAME.split(" ", 1)
    main_text = parts[0]
    sub_text = parts[1] if len(parts) > 1 else ""

    b1 = draw.textbbox((0, 0), main_text, font=big)
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    x1 = (w - w1) // 2 - b1[0]
    y1 = h // 2 - h1 - int(30 * s) - b1[1]
    draw.text((x1, y1), main_text, font=big, fill=Config.WHITE)

    line_y = h // 2 + int(20 * s)
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

    img.save(Config.LOGO_PATH)


def encode_base_clip():
    """Encode the logo ONCE into a short clip (one GOP = HLS_TIME seconds)."""
    gop = Config.FPS * Config.HLS_TIME
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-loop", "1", "-framerate", str(Config.FPS), "-i", Config.LOGO_PATH,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(Config.HLS_TIME),
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p", "-r", str(Config.FPS),
        "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
        "-b:v", Config.VIDEO_BITRATE,
        "-maxrate", Config.VIDEO_BITRATE,
        "-bufsize", "500k",
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
                print("[LMC] encoding base clip...", flush=True)
                make_logo()
                encode_base_clip()
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
