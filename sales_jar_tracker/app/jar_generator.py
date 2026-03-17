"""
Generates the sales jar tracker image using Pillow.
Visual style:
- Blue gradient background
- Curved glass jar with coins filling proportional to sales %
- Left panels: Current Sales, Sales Target, Sales Growth gauge
- OVERFLOW! banner when current sales exceed target
"""

import math
import io
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 500

# ── Colours ───────────────────────────────────────────────────────────────────
BG_TOP        = (25,  80, 150)
BG_BOTTOM     = ( 8,  40, 100)
WHITE         = (255, 255, 255)
YELLOW        = (255, 210,   0)
GOLD_LIGHT    = (255, 215,  80)
GOLD_MID      = (220, 165,  20)
GOLD_DARK     = (155, 105,   0)
COIN_SHINE    = (255, 245, 155)
OVERFLOW_RED  = (210,  30,  30)
OVERFLOW_YELL = (255, 200,   0)
GRAY_LIGHT    = (200, 210, 225)
GAUGE_RED     = (210,  30,  30)
GAUGE_YELLOW  = (230, 200,   0)
GAUGE_GREEN   = ( 40, 175,  60)
PANEL_BLUE    = ( 15,  60, 130)
PANEL_GREEN   = ( 20, 120,  50)
PANEL_BORDER  = ( 70, 150, 250)
GREEN_BORDER  = ( 50, 190,  90)

# ── Jar geometry constants ────────────────────────────────────────────────────
JAR_CX      = 415   # horizontal centre
JAR_LID_TOP =  62   # top of lid cap
JAR_LID_BOT =  98   # bottom of lid cap
JAR_NECK_Y  = 128   # bottom of neck (shoulder starts here)
JAR_SHLDR_Y = 172   # bottom of shoulder (body starts here)
JAR_BOT_Y   = 440   # bottom of jar
JAR_LID_HW  =  70   # lid half-width
JAR_NECK_HW =  60   # neck half-width
JAR_BODY_HW = 150   # body half-width at widest
JAR_BR      =  24   # bottom corner radius


# ── Helpers ───────────────────────────────────────────────────────────────────

def _try_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
                 else ["arial.ttf", "DejaVuSans.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _centered_text(draw, text, cx, cy, font, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


def _poly_x_at_y(pts, y):
    """Return (left_x, right_x) of a polygon at scanline y."""
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
    if not hits:
        return 0, 0
    return min(hits), max(hits)


def _shoulder_curve(cx, hw_start, hw_end, y_start, y_end, side, steps=14):
    """Return points for one side of the jar shoulder (ease-out curve)."""
    pts = []
    sign = 1 if side == "right" else -1
    for i in range(steps + 1):
        t    = i / steps
        ease = math.sin(t * math.pi / 2)   # ease-out
        x = cx + sign * (hw_start + (hw_end - hw_start) * ease)
        y = y_start + (y_end - y_start) * t
        pts.append((x, y))
    return pts


def _jar_outline_pts():
    """Full jar polygon (lid + neck + shoulder + body + rounded bottom)."""
    cx = JAR_CX
    pts = []

    # Lid top-left → top-right
    pts += [(cx - JAR_LID_HW, JAR_LID_TOP), (cx + JAR_LID_HW, JAR_LID_TOP)]
    # Lid right side down
    pts += [(cx + JAR_LID_HW, JAR_LID_BOT), (cx + JAR_NECK_HW + 3, JAR_LID_BOT)]
    # Neck right side
    pts += [(cx + JAR_NECK_HW, JAR_NECK_Y)]
    # Right shoulder
    pts += _shoulder_curve(cx, JAR_NECK_HW, JAR_BODY_HW,
                           JAR_NECK_Y, JAR_SHLDR_Y, "right")[1:]
    # Right body straight down
    pts += [(cx + JAR_BODY_HW, JAR_BOT_Y - JAR_BR)]
    # Bottom-right rounded corner (0° → 90°)
    ccx, ccy = cx + JAR_BODY_HW - JAR_BR, JAR_BOT_Y - JAR_BR
    for i in range(7):
        a = math.radians(i * 15)
        pts.append((ccx + JAR_BR * math.cos(a), ccy + JAR_BR * math.sin(a)))
    # Bottom flat
    pts += [(cx + JAR_BODY_HW - JAR_BR, JAR_BOT_Y),
            (cx - JAR_BODY_HW + JAR_BR, JAR_BOT_Y)]
    # Bottom-left rounded corner (90° → 180°)
    ccx2, ccy2 = cx - JAR_BODY_HW + JAR_BR, JAR_BOT_Y - JAR_BR
    for i in range(7):
        a = math.radians(90 + i * 15)
        pts.append((ccx2 + JAR_BR * math.cos(a), ccy2 + JAR_BR * math.sin(a)))
    # Left body straight up
    pts += [(cx - JAR_BODY_HW, JAR_SHLDR_Y)]
    # Left shoulder (reverse)
    pts += list(reversed(_shoulder_curve(cx, JAR_NECK_HW, JAR_BODY_HW,
                                         JAR_NECK_Y, JAR_SHLDR_Y, "left")[:-1]))
    # Left neck & lid
    pts += [(cx - JAR_NECK_HW - 3, JAR_LID_BOT),
            (cx - JAR_LID_HW, JAR_LID_BOT),
            (cx - JAR_LID_HW, JAR_LID_TOP)]
    return pts


def _jar_interior_pts(wall=7):
    """Jar interior polygon (slightly inset — for coin clipping mask)."""
    cx  = JAR_CX
    nhw = JAR_NECK_HW  - wall
    bhw = JAR_BODY_HW  - wall
    br  = max(JAR_BR   - wall, 6)
    bot = JAR_BOT_Y    - wall // 2
    pts = []

    # Opening at top
    pts += [(cx - nhw, JAR_NECK_Y), (cx + nhw, JAR_NECK_Y)]
    # Right shoulder
    pts += _shoulder_curve(cx, nhw, bhw, JAR_NECK_Y, JAR_SHLDR_Y, "right")[1:]
    # Right body
    pts += [(cx + bhw, bot - br)]
    # Bottom-right corner
    ccx, ccy = cx + bhw - br, bot - br
    for i in range(7):
        a = math.radians(i * 15)
        pts.append((ccx + br * math.cos(a), ccy + br * math.sin(a)))
    pts += [(cx + bhw - br, bot), (cx - bhw + br, bot)]
    # Bottom-left corner
    ccx2, ccy2 = cx - bhw + br, bot - br
    for i in range(7):
        a = math.radians(90 + i * 15)
        pts.append((ccx2 + br * math.cos(a), ccy2 + br * math.sin(a)))
    # Left body
    pts += [(cx - bhw, JAR_SHLDR_Y)]
    # Left shoulder
    pts += list(reversed(_shoulder_curve(cx, nhw, bhw,
                                         JAR_NECK_Y, JAR_SHLDR_Y, "left")[:-1]))
    pts += [(cx - nhw, JAR_NECK_Y)]
    return pts


# ── Drawing stages ────────────────────────────────────────────────────────────

def _draw_gradient_bg(draw):
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _draw_coins_in_jar(img: Image.Image, fill_ratio: float):
    """Render gold coins inside the jar, clipped to the jar interior."""
    int_pts = _jar_interior_pts()
    ys      = [p[1] for p in int_pts]
    top_y   = min(ys)
    bot_y   = max(ys)
    interior_h = bot_y - top_y

    clamped   = min(fill_ratio, 1.06)
    coin_top  = bot_y - int(interior_h * clamped)
    coin_top  = max(coin_top, top_y - 12)   # allow slight overflow for effect

    # Coins layer
    coins = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd    = ImageDraw.Draw(coins)

    if fill_ratio > 0.01:
        # Fill the ENTIRE interior with dark gold (backdrop for coins)
        cd.polygon(int_pts, fill=GOLD_DARK)

        # Coin rows from bottom upward
        row_h   = 17
        row_num = 0
        row_y   = bot_y - row_h // 2

        while row_y > coin_top - row_h:
            xl, xr = _poly_x_at_y(int_pts, row_y)
            if xr - xl < 22:
                row_y  -= row_h
                row_num += 1
                continue
            offset   = 10 if row_num % 2 else 0
            cx_start = int(xl) + 14 + offset
            while cx_start < int(xr) - 10:
                cr = 9
                # Shadow
                cd.ellipse([cx_start - cr + 2, row_y - 4 + 2,
                             cx_start + cr + 2, row_y + 5 + 2],
                            fill=(100, 65, 0, 120))
                # Base coin
                cd.ellipse([cx_start - cr, row_y - 4,
                             cx_start + cr, row_y + 5],
                            fill=GOLD_MID, outline=GOLD_DARK, width=1)
                # Highlight
                cd.ellipse([cx_start - cr + 3, row_y - 2,
                             cx_start + cr - 3, row_y + 3],
                            fill=GOLD_LIGHT)
                # Shine dot
                cd.ellipse([cx_start - 3, row_y - 1,
                             cx_start + 2, row_y + 2],
                            fill=COIN_SHINE)
                cx_start += 21
            row_y  -= row_h
            row_num += 1

        # Wavy gold surface at top of coins
        wave_y = int(coin_top)
        xl_top, xr_top = _poly_x_at_y(int_pts, wave_y)
        for wx in range(int(xl_top), int(xr_top) + 1, 7):
            wy = wave_y + int(3 * math.sin(wx * 0.35))
            cd.ellipse([wx - 8, wy - 5, wx + 8, wy + 5], fill=GOLD_LIGHT)

    # Mask coins to jar interior AND only below the coin_top line
    mask = Image.new("L", (W, H), 0)
    md   = ImageDraw.Draw(mask)
    md.polygon(int_pts, fill=255)
    # Clear everything above the coin surface (so glass shows through)
    if fill_ratio < 1.0 and int(coin_top) > int(top_y):
        md.rectangle([0, 0, W, int(coin_top)], fill=0)
    img.paste(coins, mask=mask)


def _draw_glass(img: Image.Image):
    """Draw the glass jar shell (semi-transparent) over the coins."""
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(glass)

    outline = _jar_outline_pts()

    # Very light glass body tint
    gd.polygon(outline, fill=(185, 220, 250, 28))
    # Glass wall outline
    gd.polygon(outline, outline=(140, 195, 235, 210), width=3)

    # Lid cap — more opaque
    lid_pts = [
        (JAR_CX - JAR_LID_HW, JAR_LID_TOP),
        (JAR_CX + JAR_LID_HW, JAR_LID_TOP),
        (JAR_CX + JAR_LID_HW, JAR_LID_BOT),
        (JAR_CX - JAR_LID_HW, JAR_LID_BOT),
    ]
    gd.polygon(lid_pts, fill=(130, 185, 225, 200))
    gd.polygon(lid_pts, outline=(100, 160, 215, 230), width=2)
    # Lid band stripe
    gd.rectangle([JAR_CX - JAR_LID_HW + 2, JAR_LID_TOP + 4,
                  JAR_CX + JAR_LID_HW - 2, JAR_LID_BOT - 4],
                 fill=(160, 210, 240, 130))

    img.alpha_composite(glass)

    # Left shine strip
    shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(shine)
    shine_l = [
        (JAR_CX - JAR_BODY_HW + 6,  JAR_SHLDR_Y + 10),
        (JAR_CX - JAR_BODY_HW + 32, JAR_SHLDR_Y + 10),
        (JAR_CX - JAR_BODY_HW + 24, JAR_BOT_Y   - 40),
        (JAR_CX - JAR_BODY_HW + 6,  JAR_BOT_Y   - 40),
    ]
    sd.polygon(shine_l, fill=(255, 255, 255, 50))
    # Right shine strip (narrower)
    shine_r = [
        (JAR_CX + JAR_BODY_HW - 30, JAR_SHLDR_Y + 10),
        (JAR_CX + JAR_BODY_HW - 8,  JAR_SHLDR_Y + 10),
        (JAR_CX + JAR_BODY_HW - 8,  JAR_BOT_Y   - 40),
        (JAR_CX + JAR_BODY_HW - 20, JAR_BOT_Y   - 40),
    ]
    sd.polygon(shine_r, fill=(255, 255, 255, 28))
    img.alpha_composite(shine)


def _draw_budget_goal(draw):
    """Draw the horizontal BUDGET GOAL marker line."""
    goal_y = JAR_SHLDR_Y + int((JAR_BOT_Y - JAR_SHLDR_Y) * 0.10)
    draw.line([(JAR_CX - JAR_BODY_HW - 18, goal_y),
               (JAR_CX + JAR_BODY_HW + 18, goal_y)],
              fill=YELLOW, width=3)
    f = _try_font(13, bold=True)
    draw.text((JAR_CX + JAR_BODY_HW + 22, goal_y - 9),
              "BUDGET GOAL", font=f, fill=YELLOW)


def _draw_overflow_banner(draw):
    """Draw the OVERFLOW! sunburst banner above the jar."""
    cx, cy = JAR_CX, 42
    rays = 18
    pts  = []
    for i in range(rays * 2):
        a = math.pi * i / rays - math.pi / 2
        r = 65 if i % 2 == 0 else 40
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, fill=OVERFLOW_RED)
    draw.ellipse([cx - 52, cy - 28, cx + 52, cy + 28],
                 fill=OVERFLOW_RED, outline=OVERFLOW_YELL, width=3)
    _centered_text(draw, "OVERFLOW!", cx, cy, _try_font(36, bold=True), OVERFLOW_YELL)


def _draw_left_panels(draw, current_sales: float, target: float, growth_pct: float):
    f_lbl  = _try_font(12, bold=True)
    f_val  = _try_font(24, bold=True)
    f_gval = _try_font(28, bold=True)
    f_sub  = _try_font(11, bold=True)

    # Current Sales
    draw.rounded_rectangle([18, 75, 248, 158], radius=10,
                            fill=PANEL_BLUE, outline=PANEL_BORDER, width=2)
    draw.text((28, 85), "CURRENT SALES", font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${current_sales:,.0f}", 133, 126, f_val, WHITE)

    # Sales Target
    draw.rounded_rectangle([18, 170, 248, 253], radius=10,
                            fill=PANEL_GREEN, outline=GREEN_BORDER, width=2)
    draw.text((28, 180), "SALES TARGET", font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${target:,.0f}", 133, 221, f_val, WHITE)

    # Sales Growth gauge
    draw.rounded_rectangle([18, 265, 248, 425], radius=10,
                            fill=(12, 48, 115), outline=PANEL_BORDER, width=2)
    draw.text((28, 275), "SALES GROWTH", font=f_lbl, fill=GRAY_LIGHT)

    gcx, gcy, gr = 133, 362, 60
    for start, end, col in [(180, 220, GAUGE_RED),
                             (220, 260, GAUGE_YELLOW),
                             (260, 360, GAUGE_GREEN)]:
        draw.arc([gcx - gr, gcy - gr, gcx + gr, gcy + gr],
                 start=start, end=end, fill=col, width=14)

    clamped = min(growth_pct / 100, 1.97)
    angle   = math.radians(180 + clamped * 180)
    nx = gcx + int((gr - 13) * math.cos(angle))
    ny = gcy + int((gr - 13) * math.sin(angle))
    draw.line([(gcx, gcy), (nx, ny)], fill=WHITE, width=3)
    draw.ellipse([gcx - 5, gcy - 5, gcx + 5, gcy + 5], fill=WHITE)

    _centered_text(draw, f"{growth_pct:.0f}%", gcx, gcy - 16, f_gval, WHITE)

    diff  = growth_pct - 100
    label = (f"+{diff:.0f}% ABOVE TARGET!" if diff >= 0
             else f"{diff:.0f}% BELOW TARGET")
    col   = GAUGE_GREEN if diff >= 0 else GAUGE_RED
    _centered_text(draw, label, gcx, gcy + 18, f_sub, col)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_image(current_sales: float, monthly_target: float) -> bytes:
    """Return PNG bytes for the jar tracker image."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    _draw_gradient_bg(draw)

    fill_ratio = current_sales / monthly_target if monthly_target else 0
    growth_pct = fill_ratio * 100

    _draw_coins_in_jar(img, fill_ratio)
    _draw_glass(img)

    # Refresh draw after compositing
    draw = ImageDraw.Draw(img)

    _draw_budget_goal(draw)
    _draw_left_panels(draw, current_sales, monthly_target, growth_pct)

    if fill_ratio > 1.0:
        _draw_overflow_banner(draw)

    out = Image.new("RGB", (W, H))
    out.paste(img, mask=img.split()[3])

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
