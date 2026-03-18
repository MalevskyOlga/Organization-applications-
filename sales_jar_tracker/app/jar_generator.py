"""
Sales Jar Tracker — image generator (v3, reference-quality).

Visual improvements:
- Sky-like radial gradient background
- Realistic wide-mouth glass jar with curved shoulders + shine strips
- Large 3D gold coins with dark edges, gold face, shine spot
- Coin-stack "edge stripes" on sides for depth illusion
- Overflow coins flying above jar opening
- OVERFLOW! sunburst badge with shadow
- Dashed BUDGET GOAL line
- Improved left panels with text shadows
"""

import math
import io
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 500

# ── Colours ───────────────────────────────────────────────────────────────────
WHITE         = (255, 255, 255)
YELLOW        = (255, 220,   0)
GOLD_SHINE    = (255, 252, 200)
GOLD_LIGHT    = (255, 222,  55)
GOLD_MID      = (232, 178,  28)
GOLD_DARK     = (162, 112,   5)
GOLD_EDGE     = ( 92,  58,   0)
OVERFLOW_RED  = (195,  20,  20)
OVERFLOW_YELL = (255, 220,   0)
GRAY_LIGHT    = (210, 220, 230)
GAUGE_RED     = (210,  30,  30)
GAUGE_YELLOW  = (230, 200,   0)
GAUGE_GREEN   = ( 40, 175,  60)
PANEL_BLUE    = ( 15,  55, 120)
PANEL_GREEN   = ( 20, 115,  50)
BORDER_BLUE   = ( 80, 155, 255)
BORDER_GREEN  = ( 60, 195,  95)

# ── Jar geometry ──────────────────────────────────────────────────────────────
JAR_CX      = 430
JAR_LID_TOP =  78   # thin metallic rim at top
JAR_LID_BOT =  92   # only 14 px tall — not a big cap
JAR_NECK_Y  = 120
JAR_SHLDR_Y = 152
JAR_BOT_Y   = 448
JAR_LID_HW  = 158   # lid wider than neck for rim effect
JAR_NECK_HW = 150   # neck almost same width as body → cylindrical look
JAR_BODY_HW = 160
JAR_BR      =  30


# ── Helpers ───────────────────────────────────────────────────────────────────

def _try_font(size: int, bold: bool = False):
    for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
                 else ["arial.ttf", "DejaVuSans.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _centered_text(draw, text, cx, cy, font, fill, shadow=None):
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    if shadow:
        draw.text((cx - tw // 2 + 2, cy - th // 2 + 2), text, font=font, fill=shadow)
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


def _poly_x_at_y(pts, y):
    hits = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if min(y1, y2) <= y <= max(y1, y2):
            if y1 == y2:
                hits += [x1, x2]
            else:
                hits.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1))
    return (min(hits), max(hits)) if hits else (0, 0)


def _shoulder_pts(cx, hw_start, hw_end, y_start, y_end, side, steps=14):
    sign = 1 if side == "right" else -1
    return [(cx + sign * (hw_start + (hw_end - hw_start) * math.sin(i / steps * math.pi / 2)),
             y_start + (y_end - y_start) * i / steps)
            for i in range(steps + 1)]


def _jar_outline_pts():
    cx = JAR_CX
    pts = [(cx - JAR_LID_HW, JAR_LID_TOP), (cx + JAR_LID_HW, JAR_LID_TOP),
           (cx + JAR_LID_HW, JAR_LID_BOT), (cx + JAR_NECK_HW + 3, JAR_LID_BOT),
           (cx + JAR_NECK_HW, JAR_NECK_Y)]
    pts += _shoulder_pts(cx, JAR_NECK_HW, JAR_BODY_HW, JAR_NECK_Y, JAR_SHLDR_Y, "right")[1:]
    pts += [(cx + JAR_BODY_HW, JAR_BOT_Y - JAR_BR)]
    ccx, ccy = cx + JAR_BODY_HW - JAR_BR, JAR_BOT_Y - JAR_BR
    for i in range(7):
        a = math.radians(i * 15)
        pts.append((ccx + JAR_BR * math.cos(a), ccy + JAR_BR * math.sin(a)))
    pts += [(cx + JAR_BODY_HW - JAR_BR, JAR_BOT_Y), (cx - JAR_BODY_HW + JAR_BR, JAR_BOT_Y)]
    ccx2, ccy2 = cx - JAR_BODY_HW + JAR_BR, JAR_BOT_Y - JAR_BR
    for i in range(7):
        a = math.radians(90 + i * 15)
        pts.append((ccx2 + JAR_BR * math.cos(a), ccy2 + JAR_BR * math.sin(a)))
    pts += [(cx - JAR_BODY_HW, JAR_SHLDR_Y)]
    pts += list(reversed(_shoulder_pts(cx, JAR_NECK_HW, JAR_BODY_HW, JAR_NECK_Y, JAR_SHLDR_Y, "left")[:-1]))
    pts += [(cx - JAR_NECK_HW - 3, JAR_LID_BOT), (cx - JAR_LID_HW, JAR_LID_BOT),
            (cx - JAR_LID_HW, JAR_LID_TOP)]
    return pts


def _jar_interior_pts(wall=8):
    cx = JAR_CX
    nhw = JAR_NECK_HW - wall
    bhw = JAR_BODY_HW - wall
    br  = max(JAR_BR - wall, 8)
    bot = JAR_BOT_Y - wall // 2
    pts = [(cx - nhw, JAR_NECK_Y), (cx + nhw, JAR_NECK_Y)]
    pts += _shoulder_pts(cx, nhw, bhw, JAR_NECK_Y, JAR_SHLDR_Y, "right")[1:]
    pts += [(cx + bhw, bot - br)]
    ccx, ccy = cx + bhw - br, bot - br
    for i in range(7):
        a = math.radians(i * 15)
        pts.append((ccx + br * math.cos(a), ccy + br * math.sin(a)))
    pts += [(cx + bhw - br, bot), (cx - bhw + br, bot)]
    ccx2, ccy2 = cx - bhw + br, bot - br
    for i in range(7):
        a = math.radians(90 + i * 15)
        pts.append((ccx2 + br * math.cos(a), ccy2 + br * math.sin(a)))
    pts += [(cx - bhw, JAR_SHLDR_Y)]
    pts += list(reversed(_shoulder_pts(cx, nhw, bhw, JAR_NECK_Y, JAR_SHLDR_Y, "left")[:-1]))
    pts += [(cx - nhw, JAR_NECK_Y)]
    return pts


# ── Drawing stages ────────────────────────────────────────────────────────────

def _draw_sky_bg(img: Image.Image, draw: ImageDraw.ImageDraw):
    """Sky gradient + Gaussian-blurred glow for a natural radial brightness."""
    from PIL import ImageFilter

    # Base vertical gradient
    for y in range(H):
        t = y / H
        r = int(170 * (1 - t) + 15  * t)
        g = int(208 * (1 - t) + 55  * t)
        b = int(252 * (1 - t) + 152 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Soft radial bloom via Gaussian blur — no visible hard oval edges
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    fcx  = int(W * 0.53)
    gd.ellipse([fcx - 240, -100, fcx + 240, 380], fill=(252, 255, 255, 180))
    gd.ellipse([fcx - 140, -70,  fcx + 140, 260], fill=(255, 255, 255, 220))
    gd.ellipse([fcx - 70,  -40,  fcx + 70,  180], fill=(255, 255, 255, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=72))
    img.alpha_composite(glow)


def _draw_coin(draw: ImageDraw.ImageDraw, cx: int, cy: int, rw: int, rh: int = None):
    """Single 3-D style coin: dark edge → gold face → shine spot."""
    if rh is None:
        rh = max(rw // 3, 5)
    # Drop shadow
    draw.ellipse([cx - rw + 2, cy - rh + 3, cx + rw + 3, cy + rh + 4],
                 fill=(60, 35, 0, 130))
    # Outer dark ring
    draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh],
                 fill=GOLD_DARK, outline=GOLD_EDGE, width=1)
    # Mid gold
    draw.ellipse([cx - rw + 3, cy - rh + 2, cx + rw - 3, cy + rh - 2], fill=GOLD_MID)
    # Light face
    draw.ellipse([cx - rw + 7, cy - rh + 3, cx + rw - 7, cy + rh - 3], fill=GOLD_LIGHT)
    # Shine spot (upper-left)
    sw, sh = max(rw // 2 - 1, 4), max(rh // 2, 3)
    draw.ellipse([cx - sw - 2, cy - sh - 1, cx - sw // 2, cy + sh // 2], fill=GOLD_SHINE)


def _draw_coins_in_jar(img: Image.Image, fill_ratio: float):
    """3-D coin pile inside jar, clipped to interior polygon."""
    int_pts = _jar_interior_pts()
    ys      = [p[1] for p in int_pts]
    top_y   = min(ys)
    bot_y   = max(ys)
    interior_h = bot_y - top_y

    clamped  = min(fill_ratio, 1.08)
    coin_top = bot_y - int(interior_h * clamped)
    coin_top = max(coin_top, top_y - 22)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    if fill_ratio > 0.01:
        # Warm gold backdrop
        draw.polygon(int_pts, fill=GOLD_MID)

        # ── Coin faces (rows from bottom up) ─────────────────────────────────
        row_h   = 24
        row_num = 0
        row_y   = int(bot_y) - row_h // 2

        while row_y > coin_top - row_h:
            xl, xr = _poly_x_at_y(int_pts, row_y)
            if xr - xl < 34:
                row_y -= row_h; row_num += 1; continue
            # Inset slightly from edges so coins don't poke into the glass wall
            xl_in = xl + 14
            xr_in = xr - 14
            offset   = 14 if row_num % 2 else 0
            cx_start = int(xl_in) + 6 + offset
            while cx_start < int(xr_in) - 12:
                _draw_coin(draw, cx_start, row_y, 14, 6)
                cx_start += 30
            row_y  -= row_h
            row_num += 1

        # ── Wavy top surface ──────────────────────────────────────────────────
        wave_y = int(coin_top)
        xl_t, xr_t = _poly_x_at_y(int_pts, wave_y)
        for wx in range(int(xl_t) + 18, int(xr_t) - 18, 30):
            wy = wave_y + int(4 * math.sin(wx * 0.25))
            _draw_coin(draw, wx, wy, 15, 7)

    # Mask: jar interior shape AND only below coin_top
    mask = Image.new("L", (W, H), 0)
    md   = ImageDraw.Draw(mask)
    md.polygon(int_pts, fill=255)
    if fill_ratio < 1.0 and int(coin_top) > int(top_y):
        md.rectangle([0, 0, W, int(coin_top)], fill=0)
    img.paste(layer, mask=mask)


def _draw_overflow_coins(img: Image.Image):
    """Larger coins flying/spilling above the jar for overflow state."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    # (cx, cy, rw, rh) — more spread out, larger sizes
    scattered = [
        (JAR_CX - 90, JAR_LID_TOP +  5, 16, 10),
        (JAR_CX - 55, JAR_LID_TOP - 22, 20,  8),
        (JAR_CX - 18, JAR_LID_TOP - 42, 22,  9),
        (JAR_CX + 22, JAR_LID_TOP - 48, 21, 10),
        (JAR_CX + 60, JAR_LID_TOP - 30, 19,  8),
        (JAR_CX + 92, JAR_LID_TOP -  4, 16,  9),
        (JAR_CX - 38, JAR_LID_TOP - 62, 15,  7),
        (JAR_CX + 38, JAR_LID_TOP - 68, 16,  7),
        (JAR_CX +  2, JAR_LID_TOP - 80, 18,  8),
        (JAR_CX - 72, JAR_LID_TOP - 42, 13,  6),
        (JAR_CX + 75, JAR_LID_TOP - 52, 14,  6),
    ]
    for cx, cy, rw, rh in scattered:
        _draw_coin(draw, cx, cy, rw, rh)
    img.alpha_composite(layer)


def _draw_glass_jar(img: Image.Image):
    """Glass jar shell: transparent body + lid + white shine strips."""
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(glass)

    outline = _jar_outline_pts()
    gd.polygon(outline, fill=(200, 228, 252, 6))    # near-invisible glass tint
    gd.polygon(outline, outline=(150, 200, 240, 195), width=4)

    # Lid rim — thin silver/metallic band (NOT a big blue cap)
    lid = [(JAR_CX - JAR_LID_HW, JAR_LID_TOP), (JAR_CX + JAR_LID_HW, JAR_LID_TOP),
           (JAR_CX + JAR_LID_HW, JAR_LID_BOT), (JAR_CX - JAR_LID_HW, JAR_LID_BOT)]
    gd.polygon(lid, fill=(155, 170, 185, 215))      # silver-gray rim
    gd.polygon(lid, outline=(120, 138, 158, 240), width=2)
    # Rim highlight stripe
    gd.rectangle([JAR_CX - JAR_LID_HW + 2, JAR_LID_TOP + 2,
                  JAR_CX + JAR_LID_HW - 2, JAR_LID_TOP + 6],
                 fill=(220, 232, 242, 140))
    img.alpha_composite(glass)

    # ── Soft glass shine strips — gradient fade inward using blurred strips ───
    from PIL import ImageFilter
    shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(shine)
    y1    = JAR_SHLDR_Y + 12
    y2    = JAR_BOT_Y   - 50

    # Left shine: multiple thin strips fading inward
    for offset, width, alpha in [(5, 7, 88), (12, 6, 68), (18, 5, 48),
                                  (23, 4, 30), (27, 3, 15), (30, 2, 7)]:
        sd.rectangle([JAR_CX - JAR_BODY_HW + offset, y1,
                      JAR_CX - JAR_BODY_HW + offset + width, y2],
                     fill=(255, 255, 255, alpha))
    # Right shine: faint strips
    for offset, width, alpha in [(5, 5, 28), (10, 4, 18), (14, 3, 10)]:
        sd.rectangle([JAR_CX + JAR_BODY_HW - offset - width, y1,
                      JAR_CX + JAR_BODY_HW - offset, y2],
                     fill=(255, 255, 255, alpha))

    shine = shine.filter(ImageFilter.GaussianBlur(radius=4))
    img.alpha_composite(shine)


def _draw_budget_goal(draw: ImageDraw.ImageDraw):
    """Dashed yellow BUDGET GOAL line."""
    goal_y = JAR_SHLDR_Y + int((JAR_BOT_Y - JAR_SHLDR_Y) * 0.10)
    x = JAR_CX - JAR_BODY_HW - 12
    while x < JAR_CX + JAR_BODY_HW + 12:
        draw.line([(x, goal_y), (min(x + 14, JAR_CX + JAR_BODY_HW + 12), goal_y)],
                  fill=YELLOW, width=3)
        x += 20
    f  = _try_font(13, bold=True)
    lx = JAR_CX + JAR_BODY_HW + 16
    # Shadow then text — no opaque background box
    draw.text((lx + 1, goal_y - 8), "BUDGET GOAL", font=f, fill=(0, 0, 0, 160))
    draw.text((lx,     goal_y - 9), "BUDGET GOAL", font=f, fill=YELLOW)


def _draw_overflow_badge(draw: ImageDraw.ImageDraw):
    """Red sunburst OVERFLOW! badge with shadow."""
    cx, cy = JAR_CX, 46
    # Shadow behind badge
    draw.ellipse([cx - 65, cy - 33, cx + 65, cy + 33], fill=(0, 0, 0, 80))
    # Sunburst
    pts = []
    for i in range(40):
        a = math.pi * i / 20 - math.pi / 2
        r = 70 if i % 2 == 0 else 46
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, fill=OVERFLOW_RED)
    draw.ellipse([cx - 57, cy - 29, cx + 57, cy + 29],
                 fill=OVERFLOW_RED, outline=OVERFLOW_YELL, width=3)
    _centered_text(draw, "OVERFLOW!", cx, cy, _try_font(34, bold=True),
                   OVERFLOW_YELL, shadow=(80, 0, 0))


def _draw_left_panels(draw: ImageDraw.ImageDraw,
                      current_sales: float, target: float, growth_pct: float):
    f_lbl  = _try_font(12, bold=True)
    f_val  = _try_font(24, bold=True)
    f_gval = _try_font(28, bold=True)
    f_sub  = _try_font(11, bold=True)

    # Current Sales
    draw.rounded_rectangle([15, 78, 248, 162], radius=10,
                            fill=PANEL_BLUE, outline=BORDER_BLUE, width=2)
    draw.text((26, 88), "CURRENT SALES", font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${current_sales:,.0f}", 131, 130, f_val, WHITE,
                   shadow=(0, 0, 0, 160))

    # Sales Target
    draw.rounded_rectangle([15, 172, 248, 256], radius=10,
                            fill=PANEL_GREEN, outline=BORDER_GREEN, width=2)
    draw.text((26, 182), "SALES TARGET", font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${target:,.0f}", 131, 224, f_val, WHITE,
                   shadow=(0, 0, 0, 160))

    # Sales Growth gauge
    draw.rounded_rectangle([15, 266, 248, 430], radius=10,
                            fill=(12, 45, 112), outline=BORDER_BLUE, width=2)
    draw.text((26, 276), "SALES GROWTH", font=f_lbl, fill=GRAY_LIGHT)

    gcx, gcy, gr = 131, 370, 62
    for start, end, col in [(180, 220, GAUGE_RED),
                             (220, 260, GAUGE_YELLOW),
                             (260, 360, GAUGE_GREEN)]:
        draw.arc([gcx - gr, gcy - gr, gcx + gr, gcy + gr],
                 start=start, end=end, fill=col, width=14)

    ang = math.radians(180 + min(growth_pct / 100, 1.97) * 180)
    nx  = gcx + int((gr - 14) * math.cos(ang))
    ny  = gcy + int((gr - 14) * math.sin(ang))
    draw.line([(gcx, gcy), (nx, ny)], fill=WHITE, width=3)
    draw.ellipse([gcx - 5, gcy - 5, gcx + 5, gcy + 5], fill=WHITE)

    _centered_text(draw, f"{growth_pct:.0f}%", gcx, gcy - 17, f_gval, WHITE,
                   shadow=(0, 0, 0, 180))

    diff  = growth_pct - 100
    label = f"+{diff:.0f}% ABOVE TARGET!" if diff >= 0 else f"{diff:.0f}% BELOW TARGET"
    _centered_text(draw, label, gcx, gcy + 20, f_sub,
                   GAUGE_GREEN if diff >= 0 else GAUGE_RED)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_image(current_sales: float, monthly_target: float) -> bytes:
    """Return PNG bytes for the jar tracker image."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    _draw_sky_bg(img, draw)

    fill_ratio = current_sales / monthly_target if monthly_target else 0
    growth_pct = fill_ratio * 100

    _draw_coins_in_jar(img, fill_ratio)
    _draw_glass_jar(img)

    draw = ImageDraw.Draw(img)
    _draw_budget_goal(draw)
    _draw_left_panels(draw, current_sales, monthly_target, growth_pct)

    if fill_ratio > 1.0:
        _draw_overflow_coins(img)
        draw = ImageDraw.Draw(img)
        _draw_overflow_badge(draw)

    out = Image.new("RGB", (W, H))
    out.paste(img, mask=img.split()[3])

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
