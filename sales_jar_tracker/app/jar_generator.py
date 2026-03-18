"""
Sales Jar Tracker - image generator v4 (photorealistic).

Key techniques:
  - Sky: Gaussian-blurred radial bloom on blue gradient
  - Coins: dome-shaped natural heap, large layered 3D coins
  - Glass cylinder: per-column gradient (strong left shine, right shadow)
                    + subtle glass-blue tint at walls
  - Rim: thin silver metallic band
  - Overflow: dramatic arc of large flying coins above jar
"""

import math
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 800, 500

WHITE         = (255, 255, 255)
YELLOW        = (255, 220,   0)
GOLD_SHINE    = (255, 252, 200)
GOLD_LIGHT    = (255, 225,  60)
GOLD_MID      = (235, 180,  30)
GOLD_DARK     = (165, 115,   5)
GOLD_EDGE     = ( 95,  60,   0)
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

JAR_CX      = 430
JAR_RIM_TOP =  76
JAR_RIM_BOT =  92
JAR_NECK_Y  = 122
JAR_SHLDR_Y = 154
JAR_BOT_Y   = 448
JAR_RIM_HW  = 162
JAR_NECK_HW = 152
JAR_BODY_HW = 162
JAR_BR      =  30


def _shoulder_pts(cx, hw_start, hw_end, y_start, y_end, side, steps=12):
    sign = 1 if side == "right" else -1
    return [(cx + sign * (hw_start + (hw_end - hw_start) * math.sin(i / steps * math.pi / 2)),
             y_start + (y_end - y_start) * i / steps)
            for i in range(steps + 1)]


def _jar_outline_pts():
    cx = JAR_CX
    pts = [(cx - JAR_RIM_HW, JAR_RIM_TOP), (cx + JAR_RIM_HW, JAR_RIM_TOP),
           (cx + JAR_RIM_HW, JAR_RIM_BOT), (cx + JAR_NECK_HW + 2, JAR_RIM_BOT),
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
    pts += [(cx - JAR_NECK_HW - 2, JAR_RIM_BOT), (cx - JAR_RIM_HW, JAR_RIM_BOT), (cx - JAR_RIM_HW, JAR_RIM_TOP)]
    return pts


def _jar_interior_pts(wall=8):
    cx  = JAR_CX
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
    fcx  = int(W * 0.53)
    gd.ellipse([fcx - 260, -110, fcx + 260, 400], fill=(252, 255, 255, 170))
    gd.ellipse([fcx - 155, -75,  fcx + 155, 280], fill=(255, 255, 255, 210))
    gd.ellipse([fcx - 80,  -45,  fcx + 80,  195], fill=(255, 255, 255, 255))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius=75)))


def _draw_coin(draw, cx, cy, rw, rh=None):
    if rh is None:
        rh = max(rw * 2 // 5, 5)
    draw.ellipse([cx - rw + 2, cy - rh + 3, cx + rw + 3, cy + rh + 4], fill=(50, 28, 0, 120))
    draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=GOLD_EDGE)
    draw.ellipse([cx - rw + 2, cy - rh + 1, cx + rw - 2, cy + rh - 1], fill=GOLD_DARK)
    draw.ellipse([cx - rw + 4, cy - rh + 2, cx + rw - 4, cy + rh - 2], fill=GOLD_MID)
    draw.ellipse([cx - rw + 7, cy - rh + 3, cx + rw - 7, cy + rh - 3], fill=GOLD_LIGHT)
    sw = max(rw // 2, 5)
    sh = max(rh // 2, 3)
    draw.ellipse([cx - sw - 1, cy - sh - 1, cx - sw // 3, cy + sh // 3], fill=GOLD_SHINE)


def _draw_coins_in_jar(img, fill_ratio):
    int_pts = _jar_interior_pts()
    ys      = [p[1] for p in int_pts]
    top_y   = min(ys)
    bot_y   = max(ys)
    h_int   = bot_y - top_y

    if fill_ratio <= 0.01:
        return

    clamped  = min(fill_ratio, 1.08)
    flat_top = bot_y - int(h_int * clamped)
    flat_top = max(flat_top, top_y - 26)
    dome_h   = min(38, h_int * 0.09)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    draw.polygon(int_pts, fill=GOLD_MID)

    row_h   = 22
    row_num = 0
    row_y   = int(bot_y) - row_h // 2

    while row_y > flat_top - row_h:
        xl, xr = _poly_x_at_y(int_pts, row_y)
        if xr - xl < 40:
            row_y -= row_h; row_num += 1; continue
        xl_in = xl + 16
        xr_in = xr - 16
        offset   = 12 if row_num % 2 else 0
        cx_start = int(xl_in) + offset
        while cx_start < int(xr_in) - 14:
            near_top = row_y < flat_top + row_h * 2
            rw = 16 if near_top else 14
            _draw_coin(draw, cx_start, row_y, rw, max(rw * 2 // 5, 6))
            cx_start += 30
        row_y  -= row_h
        row_num += 1

    xl_t, xr_t = _poly_x_at_y(int_pts, flat_top)
    for wx in range(int(xl_t) + 20, int(xr_t) - 20, 28):
        dx     = abs(wx - JAR_CX) / max(JAR_BODY_HW - 20, 1)
        dome_y = flat_top + int(dome_h * min(dx, 1.0) ** 1.6)
        _draw_coin(draw, wx, dome_y, 18, 8)

    mask = Image.new("L", (W, H), 0)
    md   = ImageDraw.Draw(mask)
    md.polygon(int_pts, fill=255)
    if fill_ratio < 1.0 and int(flat_top) > int(top_y):
        md.rectangle([0, 0, W, int(flat_top) - 8], fill=0)
    img.paste(layer, mask=mask)


def _apply_cylindrical_lighting(img, int_pts):
    ys    = [p[1] for p in int_pts]
    top_y = int(min(ys)) + 4
    bot_y = int(max(ys)) - 8

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od      = ImageDraw.Draw(overlay)

    x_left  = int(JAR_CX - JAR_BODY_HW)
    x_right = int(JAR_CX + JAR_BODY_HW)
    jar_w   = x_right - x_left

    for x in range(x_left, x_right):
        t = (x - x_left) / jar_w

        if t < 0.25:
            s = (0.25 - t) / 0.25
            alpha = int(s ** 1.8 * 215)
            od.line([(x, top_y), (x, bot_y)], fill=(255, 255, 255, alpha))
        elif t < 0.35:
            s = (0.35 - t) / 0.10
            alpha = int(s * 55)
            od.line([(x, top_y), (x, bot_y)], fill=(255, 255, 255, alpha))

        if t > 0.78:
            s = (t - 0.78) / 0.22
            alpha = int(s ** 1.5 * 105)
            od.line([(x, top_y), (x, bot_y)], fill=(10, 22, 55, alpha))

        if t < 0.07:
            s = (0.07 - t) / 0.07
            alpha = int(s ** 1.2 * 75)
            od.line([(x, top_y), (x, bot_y)], fill=(165, 215, 250, alpha))
        elif t > 0.93:
            s = (t - 0.93) / 0.07
            alpha = int(s ** 1.2 * 60)
            od.line([(x, top_y), (x, bot_y)], fill=(135, 185, 230, alpha))

    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=5))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(int_pts, fill=255)
    clipped = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    clipped.paste(overlay, mask=mask)
    img.alpha_composite(clipped)


def _draw_glass_outline(img):
    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(glass)
    outline = _jar_outline_pts()
    gd.polygon(outline, fill=(200, 228, 252, 5))
    gd.polygon(outline, outline=(130, 195, 238, 185), width=4)
    rim = [(JAR_CX - JAR_RIM_HW, JAR_RIM_TOP), (JAR_CX + JAR_RIM_HW, JAR_RIM_TOP),
           (JAR_CX + JAR_RIM_HW, JAR_RIM_BOT), (JAR_CX - JAR_RIM_HW, JAR_RIM_BOT)]
    gd.polygon(rim, fill=(152, 168, 182, 218))
    gd.polygon(rim, outline=(120, 138, 155, 240), width=2)
    gd.rectangle([JAR_CX - JAR_RIM_HW + 2, JAR_RIM_TOP + 1,
                  JAR_CX + JAR_RIM_HW - 2, JAR_RIM_TOP + 5],
                 fill=(220, 232, 242, 140))
    img.alpha_composite(glass)


def _draw_overflow_coins(img):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    coins = [
        (JAR_CX - 105, JAR_RIM_TOP +  8, 15,  9),
        (JAR_CX -  72, JAR_RIM_TOP - 26, 20,  9),
        (JAR_CX -  36, JAR_RIM_TOP - 50, 22, 10),
        (JAR_CX +   0, JAR_RIM_TOP - 62, 24, 11),
        (JAR_CX +  38, JAR_RIM_TOP - 52, 22, 10),
        (JAR_CX +  74, JAR_RIM_TOP - 28, 20,  9),
        (JAR_CX + 108, JAR_RIM_TOP +  6, 15,  9),
        (JAR_CX -  52, JAR_RIM_TOP - 78, 17,  8),
        (JAR_CX +  52, JAR_RIM_TOP - 80, 17,  8),
        (JAR_CX +   0, JAR_RIM_TOP - 90, 15,  7),
        (JAR_CX -  20, JAR_RIM_TOP - 38, 13,  6),
        (JAR_CX +  20, JAR_RIM_TOP - 40, 13,  6),
    ]
    for cx, cy, rw, rh in coins:
        _draw_coin(draw, cx, cy, rw, rh)
    img.alpha_composite(layer)


def _draw_budget_goal(draw):
    goal_y = JAR_SHLDR_Y + int((JAR_BOT_Y - JAR_SHLDR_Y) * 0.10)
    x = JAR_CX - JAR_BODY_HW - 14
    while x < JAR_CX + JAR_BODY_HW + 14:
        draw.line([(x, goal_y), (min(x + 14, JAR_CX + JAR_BODY_HW + 14), goal_y)],
                  fill=YELLOW, width=3)
        x += 20
    f  = _try_font(13, bold=True)
    lx = JAR_CX + JAR_BODY_HW + 18
    draw.text((lx + 1, goal_y - 7), "BUDGET GOAL", font=f, fill=(0, 0, 0, 160))
    draw.text((lx,     goal_y - 8), "BUDGET GOAL", font=f, fill=YELLOW)


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
    _centered_text(draw, "OVERFLOW!", cx, cy, _try_font(34, bold=True),
                   OVERFLOW_YELL, shadow=(80, 0, 0))


def _draw_left_panels(draw, current_sales, target, growth_pct):
    f_lbl  = _try_font(12, bold=True)
    f_val  = _try_font(24, bold=True)
    f_gval = _try_font(28, bold=True)
    f_sub  = _try_font(11, bold=True)

    draw.rounded_rectangle([15, 78, 248, 162], radius=10,
                            fill=PANEL_BLUE, outline=BORDER_BLUE, width=2)
    draw.text((26, 88), "CURRENT SALES", font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${current_sales:,.0f}", 131, 130, f_val, WHITE, shadow=(0, 0, 0, 160))

    draw.rounded_rectangle([15, 172, 248, 256], radius=10,
                            fill=PANEL_GREEN, outline=BORDER_GREEN, width=2)
    draw.text((26, 182), "SALES TARGET", font=f_lbl, fill=GRAY_LIGHT)
    _centered_text(draw, f"${target:,.0f}", 131, 224, f_val, WHITE, shadow=(0, 0, 0, 160))

    draw.rounded_rectangle([15, 266, 248, 430], radius=10,
                            fill=(12, 45, 112), outline=BORDER_BLUE, width=2)
    draw.text((26, 276), "SALES GROWTH", font=f_lbl, fill=GRAY_LIGHT)

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
    label = f"+{diff:.0f}% ABOVE TARGET!" if diff >= 0 else f"{diff:.0f}% BELOW TARGET"
    _centered_text(draw, label, gcx, gcy + 20, f_sub, GAUGE_GREEN if diff >= 0 else GAUGE_RED)


def generate_image(current_sales, monthly_target):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    _draw_sky_bg(img, draw)

    fill_ratio = current_sales / monthly_target if monthly_target else 0
    growth_pct = fill_ratio * 100

    int_pts = _jar_interior_pts()

    _draw_coins_in_jar(img, fill_ratio)
    _apply_cylindrical_lighting(img, int_pts)
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
