"""Prepare visual assets for the QuizMaster presentation.

Generates:
  * Creative dark-navy background art (gradient glow orbs + dot grids) matching
    the QuizMaster brand gradient (#6366F1 -> #8B5CF6 -> #06B6D4).
  * A high-res recreation of the QuizMaster logo (from frontend favicon.svg).
  * Precisely cropped / resized versions of the repo screenshots so every
    picture placed in the deck matches its frame aspect ratio exactly
    (no stretching, no distortion). Tall full-page captures are cropped to
    their top "browser viewport" area, like a real browser would show.
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "docs", "screenshots")
OUT = os.path.join(ROOT, "presentation", "assets")
os.makedirs(OUT, exist_ok=True)

INDIGO = (99, 102, 241)
VIOLET = (139, 92, 246)
CYAN = (6, 182, 212)
NAVY = (10, 10, 32)

W, H = 2400, 1350  # background canvas (16:9)


def orb_layer(orbs):
    """orbs: list of (cx, cy, radius, colour, strength 0..1). Returns blurred glow layer."""
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    for cx, cy, r, col, s in orbs:
        c = tuple(int(v * s) for v in col)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    return layer.filter(ImageFilter.GaussianBlur(170))


def dot_grid(img, x0, y0, cols, rows, gap=46, r=3, alpha=42):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(cols):
        for j in range(rows):
            x, y = x0 + i * gap, y0 + j * gap
            d.ellipse([x - r, y - r, x + r, y + r], fill=(165, 170, 255, alpha))
    img.alpha_composite(overlay)


def ring(img, cx, cy, r, width=3, alpha=40, colour=(140, 150, 255)):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour + (alpha,), width=width)
    img.alpha_composite(overlay)


def make_bg(name, base, orbs, dots=None, rings=None):
    img = Image.new("RGB", (W, H), base)
    img = ImageChops.screen(img, orb_layer(orbs)).convert("RGBA")
    if rings:
        for args in rings:
            ring(img, *args)
    if dots:
        dot_grid(img, *dots)
    img.convert("RGB").save(os.path.join(OUT, name), quality=90)
    print("bg:", name)


# ---- Backgrounds -----------------------------------------------------------
make_bg("bg_cover.jpg", NAVY,
        orbs=[(-150, -120, 620, INDIGO, 0.55), (2050, 240, 560, VIOLET, 0.42),
              (1650, 1280, 520, CYAN, 0.30), (250, 1250, 420, VIOLET, 0.28)],
        dots=(1880, 90, 11, 6), rings=[(2230, 1080, 300, 3, 46), (2230, 1080, 190, 2, 34)])

make_bg("bg_content.jpg", (11, 11, 36),
        orbs=[(2350, -260, 560, INDIGO, 0.26), (-260, 1400, 560, CYAN, 0.16),
              (1200, -520, 480, VIOLET, 0.14)],
        dots=(1960, 80, 10, 4))

make_bg("bg_accent.jpg", NAVY,
        orbs=[(2200, 1150, 620, CYAN, 0.30), (-200, 100, 560, VIOLET, 0.36),
              (1250, 1420, 520, INDIGO, 0.28)],
        dots=(90, 1040, 10, 5), rings=[(150, 180, 230, 3, 40)])


# ---- Logo (recreated from frontend/static/img/favicon.svg) ----------------
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def grad_colour(t):
    if t < 0.55:
        return lerp(INDIGO, VIOLET, t / 0.55)
    return lerp(VIOLET, CYAN, (t - 0.55) / 0.45)


def make_logo():
    S = 2048  # supersample canvas
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    px = img.load()
    for y in range(S):
        for x in range(0, S, 4):  # step for speed; blocks filled below
            c = grad_colour((x + y) / (2 * S))
            for dx in range(4):
                px[x + dx, y] = c + (255,)
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, S, S], radius=int(S * 9 / 32), fill=255)
    img.putalpha(mask)

    d = ImageDraw.Draw(img)
    k = S / 32.0  # favicon viewBox is 32x32
    white = (255, 255, 255, 255)
    # magnifier ring
    cx, cy, r = 15 * k, 15 * k, 8.5 * k
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=white, width=int(3 * k))
    # handle
    x1, y1, x2, y2 = 18.5 * k, 18.5 * k, 25 * k, 25 * k
    d.line([x1, y1, x2, y2], fill=white, width=int(3 * k))
    rr = 1.5 * k
    d.ellipse([x2 - rr, y2 - rr, x2 + rr, y2 + rr], fill=white)
    # checkmark
    pts = [(11.5 * k, 15.2 * k), (14.1 * k, 17.8 * k), (19.1 * k, 12.6 * k)]
    d.line(pts, fill=white, width=int(2.4 * k), joint="curve")
    rr = 1.2 * k
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=white)

    img.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "logo.png"))
    print("logo: logo.png")


make_logo()


# ---- Screenshot crops ------------------------------------------------------
def crop_to_ratio(out, src, ratio, top_frac=0.0, max_w=1400):
    """Crop image to width/height == ratio. top_frac 0 = keep top, 1 = keep bottom."""
    im = Image.open(os.path.join(SHOTS, src)).convert("RGB")
    w, h = im.size
    cur = w / h
    if cur > ratio:  # too wide -> trim sides (centre)
        nw = int(h * ratio)
        x0 = (w - nw) // 2
        box = (x0, 0, x0 + nw, h)
    else:            # too tall -> trim top/bottom per top_frac
        nh = int(w / ratio)
        y0 = int((h - nh) * top_frac)
        box = (0, y0, w, y0 + nh)
    im = im.crop(box)
    if im.size[0] > max_w:
        im = im.resize((max_w, int(max_w / ratio)), Image.LANCZOS)
    im.save(os.path.join(OUT, out), quality=87)
    print(f"shot: {out}  {im.size[0]}x{im.size[1]} (from {src})")


# name, source, target ratio (w/h), vertical anchor, max width
JOBS = [
    ("home.jpg",          "01-home.png",               1.60, 0.00, 1440),
    ("login.jpg",         "02-login.png",              1.60, 0.00, 1000),
    ("explore.jpg",       "05-explore.png",            1.60, 0.00, 1000),
    ("quiz_player.jpg",   "08-quiz-player.png",        1.60, 0.00, 1100),
    ("results.jpg",       "09-results.png",            1.60, 0.00, 1100),
    ("quiz_detail.jpg",   "07-quiz-detail.png",        1.60, 0.00, 1000),
    ("history.jpg",       "06-history.png",            1.60, 0.00, 1000),
    ("dashboard.jpg",     "04-student-dashboard.png",  1.48, 0.00, 1400),
    ("dash_banner.jpg",   "04-student-dashboard.png",  2.35, 0.00, 1300),
    ("admin_banner.jpg",  "10-admin-overview.png",     2.35, 0.00, 1300),
    ("admin_overview.jpg","10-admin-overview.png",     1.48, 0.00, 1300),
    ("admin_quizzes.jpg", "11-admin-quizzes.png",      1.60, 0.00, 1250),
    ("question_bank.jpg", "12-question-bank.png",      1.60, 0.00, 1250),
    ("analytics.jpg",     "13-admin-analytics.png",    1.48, 0.00, 1250),
    ("tqm_overview.jpg",  "14-tqm-overview.png",       1.35, 0.00, 1300),
    ("pareto.jpg",        "16-pareto.png",             1.35, 0.00, 1200),
    ("control_chart.jpg", "21-control-chart.png",      1.35, 0.00, 1200),
    ("mobile.jpg",        "23-mobile-home.png",        0.52, 0.00, 720),
]
for job in JOBS:
    crop_to_ratio(*job)

print("Done.")
