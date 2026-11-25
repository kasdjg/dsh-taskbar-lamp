"""任务栏上的 DSH 小灯：鲸鱼像素标 + 点阵数字 + 马赛克状态灯。

背景完全透明，内容直接压在任务栏上，看起来像任务栏自带的一块。
"""

from PIL import Image, ImageChops, ImageDraw

ICON_PATH = r"E:\DeepSeek Harness\resources\tray.ico"

# 4x5 点阵数字：比 3x5 好认，又不压鲸鱼
GLYPHS = {
    "0": ["0110", "1001", "1001", "1001", "0110"],
    "1": ["0010", "0110", "0010", "0010", "0111"],
    "2": ["0110", "1001", "0010", "0100", "1111"],
    "3": ["1110", "0001", "0110", "0001", "1110"],
    "4": ["0010", "0110", "1010", "1111", "0010"],
    "5": ["1111", "1000", "1110", "0001", "1110"],
    "6": ["0110", "1000", "1110", "1001", "0110"],
    "7": ["1111", "0001", "0010", "0100", "0100"],
    "8": ["0110", "1001", "0110", "1001", "0110"],
    "9": ["0110", "1001", "0111", "0001", "0110"],
    "+": ["0000", "0010", "0111", "0010", "0000"],
}

COLORS_LIGHT = {
    "mark": (61, 95, 240),
    "digit": (26, 26, 26),
    "digit_dim": None,
    "idle": (198, 198, 198),
    "busy": (40, 196, 84),
    "alert": (255, 48, 40),
    "alert_dim": (168, 30, 26),
    "frame": (158, 158, 158),
    "sep": (176, 176, 176),
}
COLORS_DARK = {
    "mark": (120, 150, 255),
    "digit": (246, 246, 246),
    "digit_dim": None,
    "idle": (110, 110, 112),
    "busy": (48, 209, 88),
    "alert": (255, 69, 58),
    "alert_dim": (146, 34, 30),
    "frame": (92, 92, 94),
    "sep": (108, 108, 110),
}

ICON_PATH_KEY = "mark"
GRID_W, GRID_H, CELL_PX = 9, 6, 2
ICON_W, ICON_H = GRID_W * CELL_PX, GRID_H * CELL_PX

DOT, GAP = 2, 1
COLS, ROWS = 4, 5
CELL_W = COLS * DOT + (COLS - 1) * GAP      # 11
CELL_H = ROWS * DOT + (ROWS - 1) * GAP      # 14
DIGIT_GAP = 3
GAP_ICON = 5
CONTENT_H = 16          # 平时内容占的高度
H = 32                  # 窗口高度，留出上下两格给翻牌动画
BASE = (H - CONTENT_H) // 2

_whale_cache = {}


def digits_for(n):
    n = int(n)
    if n > 9:
        return "9+"
    return str(max(0, n))


def width_for(n):
    d = digits_for(n)
    num_w = CELL_W * len(d) + DIGIT_GAP * (len(d) - 1)
    return num_w + GAP_ICON + ICON_W


def height():
    return H


def whale(dark=False):
    """官方托盘图标降采样成 9x6 格子，每格画 2px 方块。

    直接缩到最终尺寸会留下 1px 碎点（毛刺），先缩到小格子再画方块，
    轮廓就和点阵数字同一种颗粒。
    """
    if dark in _whale_cache:
        return _whale_cache[dark]
    color = COLORS_DARK["mark"] if dark else COLORS_LIGHT["mark"]
    img = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        ico = Image.open(ICON_PATH)
        ico.size = (32, 32)
        ico.load()
        rgba = ico.convert("RGBA")
        alpha = rgba.split()[3].point(lambda v: 255 if v > 128 else 0)
        dark_px = rgba.convert("L").point(lambda v: 255 if v < 110 else 0)
        mask = ImageChops.multiply(alpha, dark_px)
        bb = mask.getbbox()
        if not bb:
            raise ValueError("empty mask")
        mask = mask.crop(bb)
        cell = mask.resize((GRID_W, GRID_H), Image.LANCZOS)
        px = cell.load()
        for gy in range(GRID_H):
            for gx in range(GRID_W):
                if px[gx, gy] > 100:
                    x0 = gx * CELL_PX
                    y0 = gy * CELL_PX
                    d.rectangle([x0, y0, x0 + CELL_PX - 1, y0 + CELL_PX - 1], fill=color + (255,))
    except Exception:
        d.rectangle([0, 2, ICON_W - 1, ICON_H - 3], fill=color + (255,))
    _whale_cache[dark] = img
    return img


def _glyph(d, x, y, ch, on, off):
    g = GLYPHS.get(ch)
    if not g:
        return
    for row in range(ROWS):
        for col in range(COLS):
            if g[row][col] not in ("1", "#"):
                if off is None:
                    continue
                color = off
            else:
                color = on
            px = x + col * (DOT + GAP)
            py = y + row * (DOT + GAP)
            d.rectangle([px, py, px + DOT - 1, py + DOT - 1], fill=color)


def _bubbles(d, color, ox, phase):
    """鲸鱼头部（左边）冒泡泡：两颗错开相位，从左上方慢慢飘走。"""
    for i in range(2):
        p = (phase + i * 0.5) % 1.0
        bx = ox + 5 - int(p * 5)
        by = 10 - int(p * 8)
        if 2 <= by <= 22 and bx >= 0:
            d.rectangle([bx, by, bx + 1, by + 1], fill=color + (255,))


def _digits(d, dg, x, y, on, off):
    cur = x
    for ch in dg:
        _glyph(d, cur, y, ch, on, off)
        cur += CELL_W + DIGIT_GAP


def render(running, waiting, blink_on, dark=False, hover=False, anim=None, phase=None):
    """anim = (旧数字, 进度 0~1, 是否向上)；phase = 泡泡动画相位 0~1。"""
    c = COLORS_DARK if dark else COLORS_LIGHT
    n = max(0, int(running))
    dg = digits_for(n)
    num_w = CELL_W * len(dg) + DIGIT_GAP * (len(dg) - 1)
    num_x = 0
    icon_x = num_w + GAP_ICON
    w = icon_x + ICON_W

    img = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    img.alpha_composite(whale(dark), (icon_x, BASE + (CONTENT_H - ICON_H) // 2))

    if phase is not None:
        _bubbles(d, c["mark"], icon_x, phase)


    # 有弹窗等着确认时，数字整体变红并闪动
    if waiting:
        digit_color = c["alert"] if blink_on else c["alert_dim"]
    else:
        digit_color = c["mark"]

    base_y = BASE + (CONTENT_H - CELL_H) // 2
    if anim:
        old_n, t, up = anim
        if up:
            old_y = base_y - int(t * CELL_H)
            new_y = base_y + int((1 - t) * CELL_H)
        else:
            old_y = base_y + int(t * CELL_H)
            new_y = base_y - int((1 - t) * CELL_H)
        _digits(d, digits_for(old_n), num_x, old_y, digit_color, c["digit_dim"])
        _digits(d, dg, num_x, new_y, digit_color, c["digit_dim"])
        # 翻牌只在本来的 16 像素高内容区里发生，超出部分擦掉
        d.rectangle([0, 0, w - 1, BASE - 1], fill=(0, 0, 0, 0))
        d.rectangle([0, BASE + CONTENT_H, w - 1, H - 1], fill=(0, 0, 0, 0))
    else:
        _digits(d, dg, num_x, base_y, digit_color, c["digit_dim"])

    return img
