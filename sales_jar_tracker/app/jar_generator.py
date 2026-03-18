"""
Sales Jar Tracker - image generator v7.

Fixes over v6:
  - Removed JAR_BULGE (was causing bottom-corner artifacts)
  - Wider body ratio: NECK=110, BODY=192 (75% wider) - much rounder look
  - Longer shoulder: SHLDR_Y=185 (75px of curved transition, was 45)
  - Glass body fill: subtle blue tint on empty interior - no more white fog
  - Softer glass outline (less plastic-blue)
  - Reduced right shadow on coins
"""

import math
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 800, 500

WHITE         = (255, 255, 255)
YELLOW        = (255, 220,   0)
GOLD_SHINE    = (255, 255, 228)
GOLD_LIGHT    = (255, 238,  55)
GOLD_MID      = (246, 196,  26)
GOLD_DARK     = (218, 165,  18)
GOLD_EDGE     = (215, 165,  22)   # warm golden, barely darker than face - eliminates dark halos
OVERFLOW_RED  = (200,  22,  18)
OVERFLOW_YELL = (255, 225,   0)
GRAY_LIGHT    = (210, 220, 230)
GAUGE_RED     = (210,  30,  30)
GAUGE_YELLOW  = (230, 200,   0)
GAUGE_GREEN   = ( 40, 175,  60)
PANEL_BLUE    = ( 15,  55, 120)
PANEL_GREEN   = ( 20, 115,  50)
BORDER_BLUE   = ( 80, 155, 255)
BORDER_GREEN  = ( 60, 195,  95)

try:
    from bidi.algorithm import get_display as _bidi_display
    def _heb(s): return _bidi_display(s)
except ImportError:
    def _heb(s):
        words = s.split()
        return ' '.join(reversed(words)) if len(words) > 1 else s

JAR_CX      = 440          # shifted right to clear panels
JAR_RIM_TOP =  68
JAR_RIM_BOT =  86
JAR_NECK_Y  = 110
JAR_SHLDR_Y = 185          # long curved shoulder (75 px transition)
JAR_BOT_Y   = 458
JAR_RIM_HW  = 128
JAR_NECK_HW = 110          # narrow neck
JAR_BODY_HW = 192          # wide body - 75% wider than neck
JAR_BR      =  46


def _shoulder_pts(cx, hw_start, hw_end, y_start, y_end, side, steps=20):
    sign = 1 if side == "right" else -1
    return [
        (cx + sign * (hw_start + (hw_end - hw_start) * math.sin(i / steps * math.pi / 2)),
         y_start + (y_end - y_start) * i / steps)
        for i in range(steps + 1)
    ]


def _jar_outline_pts():
    cx  = JAR_CX
    bry = JAR_BOT_Y - JAR_BR
    pts = [
        (cx - JAR_RIM_HW, JAR_RIM_TOP),
        (cx + JAR_RIM_HW, JAR_RIM_TOP),
        (cx + JAR_RIM_HW, JAR_RIM_BOT),
        (cx + JAR_NECK_HW + 2, JAR_RIM_BOT),
        (cx + JAR_NECK_HW, JAR_NECK_Y),
    ]
    pts += _shoulder_pts(cx, JAR_NECK_HW, JAR_BODY_HW, JAR_NECK_Y, JAR_SHLDR_Y, "right")[1:]
    pts += [(cx + JAR_BODY_HW, bry)]
    ccx, ccy = cx + JAR_BODY_HW - JAR_BR, bry
    for i in range(7):
        a = math.radians(i * 15)
        pts.append((ccx + JAR_BR * math.cos(a), ccy + JAR_BR * math.sin(a)))
    pts += [(cx + JAR_BODY_HW - JAR_BR, JAR_BOT_Y), (cx - JAR_BODY_HW + JAR_BR, JAR_BOT_Y)]
    ccx2, ccy2 = cx - JAR_BODY_HW + JAR_BR, bry
    for i in range(7):
        a = math.radians(90 + i * 15)
        pts.append((ccx2 + JAR_BR * math.cos(a), ccy2 + JAR_BR * math.sin(a)))
    pts += [(cx - JAR_BODY_HW, bry)]
    pts += list(reversed(_shoulder_pts(cx, JAR_NECK_HW, JAR_BODY_HW, JAR_NECK_Y, JAR_SHLDR_Y, "left")[:-1]))
    pts += [
        (cx - JAR_NECK_HW - 2, JAR_RIM_BOT),
        (cx - JAR_RIM_HW,      JAR_RIM_BOT),
        (cx - JAR_RIM_HW,      JAR_RIM_TOP),
    ]
    return pts


def _jar_interior_pts(wall=9):
    cx  = JAR_CX
    nhw = JAR_NECK_HW - wall
    bhw = JAR_BODY_HW - wall
    br  = max(JAR_BR - wall, 8)
    bot = JAR_BOT_Y - wall // 2
    bry = bot - br
    pts = [(cx - nhw, JAR_NECK_Y), (cx + nhw, JAR_NECK_Y)]
    pts += _shoulder_pts(cx, nhw, bhw, JAR_NECK_Y, JAR_SHLDR_Y, "right")[1:]
    pts += [(cx + bhw, bry)]
    ccx, ccy = cx + bhw - br, bry
    for i in range(7):
        a = math.radians(i * 15)
        pts.append((ccx + br * math.cos(a), ccy + br * math.sin(a)))
    pts += [(cx + bhw - br, bot), (cx - bhw + br, bot)]
    ccx2, ccy2 = cx - bhw + br, bry
    for i in range(7):
        a = math.radians(90 + i * 15)
        pts.append((ccx2 + br * math.cos(a), ccy2 + br * math.sin(a)))
    pts += [(cx - bhw, bry)]
    pts += list(reversed(_shoulder_pts(cx, nhw, bhw, JAR_NECK_Y, JAR_SHLDR_Y, "left")[:-1]))
    return pts


def _poly_x_at_y(pts, y):
    hits = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if min(y1, y2) <= y <= max(y1, y2):
            hits.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1) if y1 != y2 else x1)
    return (min(hits), max(hits)) if hits else (0, 0)


def _try_font(size, bold=False):
    for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]):
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


def _draw_sky_bg(img, draw):
    for y in range(H):
        t = y / H
        r = int(165 * (1 - t) + 14  * t)
        g = int(205 * (1 - t) + 52  * t)
        b = int(252 * (1 - t) + 150 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    fcx  = int(W * 0.55)
    gd.ellipse([fcx - 280, -120, fcx + 280, 430], fill=(252, 255, 255, 140))
    gd.ellipse([fcx - 170, -85,  fcx + 170, 310], fill=(255, 255, 255, 185))
    gd.ellipse([fcx - 95,  -55,  fcx + 95,  220], fill=(255, 255, 255, 235))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius=80)))


def _draw_coin(draw, cx, cy, rw, rh=None):
    if rh is None:
        rh = max(rw * 5 // 12, 5)   # ~42% ratio - flatter, more coin-like
    # Very faint shadow - just 1px below
    draw.ellipse([cx - rw + 1, cy - rh + 1, cx + rw + 1, cy + rh + 2], fill=(22, 10, 0, 18))
    # Thin edge ring then quick gradient to bright centre
    draw.ellipse([cx - rw,     cy - rh,     cx + rw,     cy + rh    ], fill=GOLD_EDGE)
    draw.ellipse([cx - rw + 1, cy - rh + 1, cx + rw - 1, cy + rh - 1], fill=GOLD_DARK)
    draw.ellipse([cx - rw + 3, cy - rh + 2, cx + rw - 3, cy + rh - 2], fill=GOLD_MID)
    draw.ellipse([cx - rw + 5, cy - rh + 3, cx + rw - 5, cy + rh - 3], fill=GOLD_LIGHT)
    # Prominent upper-left shine spot
    sw = max(rw * 6 // 8, 5)
    sh = max(rh * 3 // 4, 3)
    draw.ellipse([cx - sw,     cy - sh - 1, cx,          cy + sh // 5], fill=GOLD_SHINE)


def _draw_coins_in_jar(img, fill_ratio):
    int_pts = _jar_interior_pts()
    ys      = [p[1] for p in int_pts]
    top_y   = min(ys)
    bot_y   = max(ys)
    h_int   = bot_y - top_y

    # Subtle glass-blue tint fills the whole interior (makes empty area look like glass)
    glass_fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass_fill).polygon(int_pts, fill=(195, 228, 255, 30))
    img.alpha_composite(glass_fill)

    if fill_ratio <= 0.01:
        return

    clamped  = min(fill_ratio, 1.08)
    flat_top = bot_y - int(h_int * clamped)
    flat_top = max(flat_top, top_y - 30)
    dome_h   = min(50, h_int * 0.10)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    draw.polygon(int_pts, fill=GOLD_MID)

    row_h   = 23   # tighter rows - coins overlap slightly
    row_num = 0
    row_y   = int(bot_y) - row_h // 2

    while row_y > flat_top - row_h:
        xl, xr = _poly_x_at_y(int_pts, row_y)
        if xr - xl < 50:
            row_y -= row_h; row_num += 1; continue
        xl_in    = xl + 14
        xr_in    = xr - 14
        offset   = 14 if row_num % 2 else 0
        cx_start = int(xl_in) + offset
        while cx_start < int(xr_in) - 14:
            near_top = row_y < flat_top + row_h * 2
            rw = 18 if near_top else 16
            _draw_coin(draw, cx_start, row_y, rw)
            cx_start += 29   # slight overlap for dense packing
        row_y  -= row_h
        row_num += 1

    xl_t, xr_t = _poly_x_at_y(int_pts, flat_top)
    for wx in range(int(xl_t) + 20, int(xr_t) - 20, 30):
        dx     = abs(wx - JAR_CX) / max(JAR_BODY_HW - 20, 1)
        dome_y = flat_top + int(dome_h * min(dx, 1.0) ** 1.6)
        _draw_coin(draw, wx, dome_y, 22)

    mask = Image.new("L", (W, H), 0)
    md   = ImageDraw.Draw(mask)
    md.polygon(int_pts, fill=255)
    if fill_ratio < 1.0 and int(flat_top) > int(top_y):
        md.rectangle([0, 0, W, int(flat_top) - 8], fill=0)
    img.paste(layer, mask=mask)


def _apply_glass_effect(img, int_pts):
    """Left-side blurred strip + right shadow + blue edge tints, all clipped to interior."""
    ys    = [p[1] for p in int_pts]
    top_y = int(min(ys))
    bot_y = int(max(ys))

    x_left  = int(JAR_CX - JAR_BODY_HW)
    x_right = int(JAR_CX + JAR_BODY_HW)

    combined = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 1. LEFT EDGE SHINE — very narrow strip (glass wall reflection only, not over coins)
    shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(shine)
    sd.rectangle([x_left,      top_y, x_left + 32, bot_y], fill=(255, 255, 255,  90))
    sd.rectangle([x_left,      top_y, x_left + 14, bot_y], fill=(255, 255, 255, 195))
    sd.rectangle([x_left + 1,  top_y, x_left +  6, bot_y], fill=(255, 255, 255, 255))
    shine = shine.filter(ImageFilter.GaussianBlur(radius=9))
    combined.alpha_composite(shine)

    # 2. RIGHT SHADOW — very subtle, only the glass wall itself (not over coins)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shd    = ImageDraw.Draw(shadow)
    shd.rectangle([x_right - 22, top_y, x_right, bot_y], fill=(5, 18, 55, 28))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
    combined.alpha_composite(shadow)

    # 3. BLUE GLASS EDGE TINTS
    edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ed   = ImageDraw.Draw(edge)
    ed.rectangle([x_left,       top_y, x_left + 20,  bot_y], fill=(140, 198, 255, 110))
    ed.rectangle([x_right - 20, top_y, x_right,      bot_y], fill=(105, 165, 238,  95))
    edge = edge.filter(ImageFilter.GaussianBlur(radius=8))
    combined.alpha_composite(edge)

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(int_pts, fill=255)
    clipped = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    clipped.paste(combined, mask=mask)
    img.alpha_composite(clipped)


def _draw_glass_outline(img):
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(glass)
    outline = _jar_outline_pts()
    gd.polygon(outline, fill=(200, 228, 255, 4))
    # Softer, less plastic outline
    gd.polygon(outline, outline=(165, 215, 252, 175), width=9)
    gd.polygon(outline, outline=(225, 245, 255, 80),  width=3)
    rim = [
        (JAR_CX - JAR_RIM_HW, JAR_RIM_TOP),
        (JAR_CX + JAR_RIM_HW, JAR_RIM_TOP),
        (JAR_CX + JAR_RIM_HW, JAR_RIM_BOT),
        (JAR_CX - JAR_RIM_HW, JAR_RIM_BOT),
    ]
    gd.polygon(rim, fill=(165, 190, 215, 210))
    gd.polygon(rim, outline=(115, 142, 168, 235), width=2)
    gd.rectangle([JAR_CX - JAR_RIM_HW + 3, JAR_RIM_TOP + 1,
                  JAR_CX + JAR_RIM_HW - 3, JAR_RIM_TOP + 6],
                 fill=(230, 245, 255, 160))
    img.alpha_composite(glass)


def _draw_overflow_coins(img):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    coins = [
        (JAR_CX - 148, JAR_RIM_TOP + 20, 13,  7),
        (JAR_CX - 115, JAR_RIM_TOP - 14, 18,  9),
        (JAR_CX -  78, JAR_RIM_TOP - 52, 22, 11),
        (JAR_CX -  38, JAR_RIM_TOP - 76, 25, 12),
        (JAR_CX +   0, JAR_RIM_TOP - 90, 27, 13),
        (JAR_CX +  40, JAR_RIM_TOP - 78, 25, 12),
        (JAR_CX +  80, JAR_RIM_TOP - 54, 22, 11),
        (JAR_CX + 117, JAR_RIM_TOP - 16, 18,  9),
        (JAR_CX + 150, JAR_RIM_TOP + 18, 13,  7),
        (JAR_CX -  60, JAR_RIM_TOP - 112, 16,  8),
        (JAR_CX +   0, JAR_RIM_TOP - 126, 15,  7),
        (JAR_CX +  62, JAR_RIM_TOP - 114, 16,  8),
        (JAR_CX -  25, JAR_RIM_TOP -  52, 13,  6),
        (JAR_CX +  27, JAR_RIM_TOP -  54, 13,  6),
        (JAR_CX -  98, JAR_RIM_TOP +   5, 11,  6),
        (JAR_CX + 100, JAR_RIM_TOP +   4, 11,  6),
    ]
    for cx, cy, rw, rh in coins:
        _draw_coin(draw, cx, cy, rw, rh)
    img.alpha_composite(layer)


def _draw_budget_goal(draw):
    goal_y = JAR_SHLDR_Y + int((JAR_BOT_Y - JAR_SHLDR_Y) * 0.06)
    x = JAR_CX - JAR_BODY_HW - 14
    while x < JAR_CX + JAR_BODY_HW + 14:
        draw.line([(x, goal_y), (min(x + 14, JAR_CX + JAR_BODY_HW + 14), goal_y)],
                  fill=YELLOW, width=3)
        x += 20
    f  = _try_font(13, bold=True)
    lx = JAR_CX + JAR_BODY_HW + 20
    draw.text((lx + 1, goal_y - 7), _heb("יעד תקציב"), font=f, fill=(0, 0, 0, 160))
    draw.text((lx,     goal_y - 8), _heb("יעד תקציב"), font=f, fill=YELLOW)


def _draw_overflow_badge(draw):
    cx, cy = JAR_CX, 44
    draw.ellipse([cx - 65, cy - 33, cx + 65, cy + 33], fill=(0, 0, 0, 80))
    pts = []
    for i in range(40):
        a = math.pi * i / 20 - math.pi / 2
        r = 72 if i % 2 == 0 else 46
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, fill=OVERFLOW_RED)
    draw.ellipse([cx - 58, cy - 30, cx + 58, cy + 30],
                 fill=OVERFLOW_RED, outline=OVERFLOW_YELL, width=3)
    _centered_text(draw, _heb("!עודף"), cx, cy, _try_font(34, bold=True),
                   OVERFLOW_YELL, shadow=(80, 0, 0))


def _draw_left_panels(draw, current_sales, target, growth_pct):
    f_lbl  = _try_font(12, bold=True)
    f_val  = _try_font(24, bold=True)
    f_gval = _try_font(28, bold=True)
    f_sub  = _try_font(11, bold=True)

    draw.rounded_rectangle([15, 78, 248, 162], radius=10,
                            fill=PANEL_BLUE, outline=BORDER_BLUE, width=2)
    draw.text((26, 88), _heb("מכירות נוכחיות"), font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${current_sales:,.0f}", 131, 130, f_val, WHITE, shadow=(0, 0, 0, 160))

    draw.rounded_rectangle([15, 172, 248, 256], radius=10,
                            fill=PANEL_GREEN, outline=BORDER_GREEN, width=2)
    draw.text((26, 182), _heb("יעד מכירות"), font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${target:,.0f}", 131, 224, f_val, WHITE, shadow=(0, 0, 0, 160))

    draw.rounded_rectangle([15, 266, 248, 430], radius=10,
                            fill=(12, 45, 112), outline=BORDER_BLUE, width=2)
    draw.text((26, 276), _heb("צמיחת מכירות"), font=f_lbl, fill=GRAY_LIGHT)

    gcx, gcy, gr = 131, 370, 62
    for start, end, col in [(180, 220, GAUGE_RED), (220, 260, GAUGE_YELLOW), (260, 360, GAUGE_GREEN)]:
        draw.arc([gcx - gr, gcy - gr, gcx + gr, gcy + gr], start=start, end=end, fill=col, width=14)

    ang = math.radians(180 + min(growth_pct / 100, 1.97) * 180)
    nx  = gcx + int((gr - 14) * math.cos(ang))
    ny  = gcy + int((gr - 14) * math.sin(ang))
    draw.line([(gcx, gcy), (nx, ny)], fill=WHITE, width=3)
    draw.ellipse([gcx - 5, gcy - 5, gcx + 5, gcy + 5], fill=WHITE)

    _centered_text(draw, f"{growth_pct:.0f}%", gcx, gcy - 17, f_gval, WHITE, shadow=(0, 0, 0, 180))

    diff  = growth_pct - 100
    label = _heb(f"+{diff:.0f}% מעל היעד!") if diff >= 0 else _heb(f"{diff:.0f}% מתחת ליעד")
    _centered_text(draw, label, gcx, gcy + 20, f_sub, GAUGE_GREEN if diff >= 0 else GAUGE_RED)


def generate_image(current_sales, monthly_target):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    _draw_sky_bg(img, draw)

    fill_ratio = current_sales / monthly_target if monthly_target else 0
    growth_pct = fill_ratio * 100

    int_pts = _jar_interior_pts()

    _draw_coins_in_jar(img, fill_ratio)
    _apply_glass_effect(img, int_pts)
    _draw_glass_outline(img)

    draw = ImageDraw.Draw(img)
    _draw_budget_goal(draw)
    _draw_left_panels(draw, current_sales, monthly_target, growth_pct)

    if fill_ratio > 1.0:
        _draw_overflow_coins(img)
        draw = ImageDraw.Draw(img)
        _draw_overflow_badge(draw)

    out = img.convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
