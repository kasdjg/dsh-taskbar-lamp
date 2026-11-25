"""DSH 任务栏灯：贴任务栏的一条搜索栏风格胶囊，显示在跑的会话数，等待确认时红灯闪。"""

import ctypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import render
from state import Monitor

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".dsh", "dsh-lamp.json")
KEY = "#ff00fe"
KEY_RGB = (255, 0, 254)
POLL_MS = 500
BLINK_MS = 420
ANIM_S = 1.0
BUBBLE_MS = 100


def enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def single_instance():
    """已经开着一个就安静退出，避免任务栏上出现两条灯。"""
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\DshTaskbarLamp")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def screen_metrics():
    u = ctypes.windll.user32
    sw = u.GetSystemMetrics(0)
    sh = u.GetSystemMetrics(1)

    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]

    r = RECT()
    u.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    return sw, sh, r.l, r.t, r.r, r.b


def is_light_theme():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        v, _ = winreg.QueryValueEx(k, "SystemUsesLightTheme")
        return bool(v)
    except Exception:
        return True


def taskbar_box():
    sw, sh, wl, wt, wr, wb = screen_metrics()
    th = sh - wb if 0 < wb < sh else 48
    return (0, sh - th, sw, sh), th


def find_empty_x(width):
    """在任务栏的空白段里找一个位置，优先靠中间偏右。"""
    from PIL import ImageGrab
    box, _ = taskbar_box()
    try:
        im = ImageGrab.grab(bbox=box)
    except Exception:
        return None
    y = min(im.height - 2, int(im.height * 0.55))
    cols = [im.getpixel((x, y))[:3] for x in range(im.width)]
    block = 6
    quiet = []
    for bx in range(0, im.width - block, block):
        seg = cols[bx:bx + block]
        ref = seg[0]
        d = max(max(abs(c[i] - ref[i]) for i in range(3)) for c in seg)
        quiet.append(d < 14)
    need = (width + 36) // block
    spans = []
    run = 0
    start = 0
    for i, q in enumerate(quiet):
        if q:
            if run == 0:
                start = i
            run += 1
        else:
            if run >= need:
                spans.append((start * block, i * block))
            run = 0
    if run >= need:
        spans.append((start * block, len(quiet) * block))
    if not spans:
        return None
    target = im.width * 0.55
    best = min(spans, key=lambda s: abs((s[0] + s[1]) / 2 - target))
    x = int((best[0] + best[1]) / 2 - width / 2)
    x = max(best[0] + 6, min(x, best[1] - width - 6))
    return x


def load_pos():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_pos(data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


LOG_PATH = os.path.join(os.path.expanduser("~"), ".dsh", "dsh-lamp.log")


def log_error(what):
    """把异常写进日志文件：插件以无窗口方式启动，报错否则完全看不见。"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(what) + "\n")
    except Exception:
        pass


class LampApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=KEY)
        try:
            self.root.wm_attributes("-transparentcolor", KEY)
        except Exception:
            pass
        self.root.report_callback_exception = lambda et, ev, tb: log_error(f"callback {et.__name__}: {ev}")

        self.w, self.h = render.width_for(0), render.height()
        self.snap = {"running": 0, "waiting": 0, "items": [], "waiting_items": []}
        self.lock = threading.Lock()
        self.monitor = Monitor()
        self.blink = True
        self.dark = self._theme_is_dark()
        self.hover = False
        self._photo = None
        self.anim = None

        self.label = tk.Label(self.root, bd=0, highlightthickness=0, bg=KEY)
        self.label.pack(fill="both", expand=True)

        self._place_window()
        self._bind()
        self._draw()

        threading.Thread(target=self._poll_loop, daemon=True).start()
        self._blink_tick()
        self._ui_tick()
        self._anim_tick()
        self._bubble_tick()

    # ---------- 主题 ----------
    @staticmethod
    def _theme_is_dark():
        """深浅色由插件配置通过环境变量传进来；没设就跟随系统。"""
        choice = (os.environ.get("DSH_LAMP_THEME") or "auto").strip().lower()
        if choice == "dark":
            return True
        if choice == "light":
            return False
        return not is_light_theme()

    # ---------- 位置 ----------
    def _clamp(self, x, y):
        """把位置限制在任务栏的高度范围内，横向不出屏幕。"""
        sw, sh, wl, wt, wr, wb = screen_metrics()
        _, th = taskbar_box()
        top = sh - th
        x = max(0, min(x, sw - self.w))
        y = max(top, min(y, sh - self.h))
        return x, y

    def _place_window(self):
        sw, sh, wl, wt, wr, wb = screen_metrics()
        _, th = taskbar_box()
        cfg = load_pos()
        x = cfg.get("x")
        if x is None:
            x = find_empty_x(self.w)
            if x is None:
                x = 880
        y = cfg.get("y")
        if y is None:
            y = sh - th + max(0, (th - self.h) // 2)
        x, y = self._clamp(x, y)
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

    def _on_drag(self, e):
        self._drag_dx = e.x_root - self.root.winfo_x()
        self._drag_dy = e.y_root - self.root.winfo_y()

    def _on_move(self, e):
        if not getattr(self, "_dragging", False):
            return
        x = e.x_root - self._drag_dx
        y = e.y_root - self._drag_dy
        x, y = self._clamp(x, y)
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, e):
        self._dragging = False
        save_pos({"x": self.root.winfo_x(), "y": self.root.winfo_y()})

    def _bind(self):
        for w in (self.root, self.label):
            w.bind("<Enter>", lambda e: self._set_hover(True))
            w.bind("<Leave>", lambda e: self._set_hover(False))
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_move)
            w.bind("<ButtonRelease-1>", self._on_release)

    def _start_drag(self, e):
        self._dragging = True
        self._on_drag(e)

    def _set_hover(self, v):
        if self.hover != v:
            self.hover = v
            self._draw()

    # ---------- 绘制 ----------
    def _draw(self):
        anim = None
        if self.anim:
            t = (time.time() - self.anim[1]) / ANIM_S
            if t >= 1:
                self.anim = None
            else:
                anim = (self.anim[0], t, self.anim[2])
        running = self.snap.get("running", 0)
        phase = (time.time() / 3.2) % 1.0 if running > 0 else None
        img = render.render(running, self.snap.get("waiting", 0),
                            self.blink, dark=self.dark, hover=self.hover,
                            anim=anim, phase=phase)
        bg = Image.new("RGB", img.size, KEY_RGB)
        bg.paste(img, (0, 0), img)
        self._photo = ImageTk.PhotoImage(bg)
        self.label.configure(image=self._photo)
        if img.size[0] != self.w:
            self.w = img.size[0]
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

    def _blink_tick(self):
        if self.snap.get("waiting", 0) > 0:
            self.blink = not self.blink
            self._draw()
        else:
            self.blink = True
        self.root.after(BLINK_MS, self._blink_tick)

    def _anim_tick(self):
        if self.anim:
            self._draw()
        self.root.after(16, self._anim_tick)

    def _bubble_tick(self):
        # 有任务在跑时鲸鱼吐泡泡，10 帧每秒就够
        if not self.anim and self.snap.get("running", 0) > 0 and not self.snap.get("waiting", 0):
            self._draw()
        self.root.after(BUBBLE_MS, self._bubble_tick)

    def _poll_loop(self):
        while True:
            try:
                s = self.monitor.snapshot()
                with self.lock:
                    self.snap = s
            except Exception as ex:
                with self.lock:
                    self.snap = {"running": 0, "waiting": 0, "items": [], "waiting_items": [], "error": str(ex)}
            time.sleep(POLL_MS / 1000.0)

    def _ui_tick(self):
        changed = False
        # 任务栏本身是最顶层窗口，点它会盖住胶囊，这里定期顶回来
        try:
            if self.root.winfo_viewable():
                self.root.lift()
        except Exception:
            pass
        with self.lock:
            new_running = self.snap.get("running")
            old_running = getattr(self, "_shown_running", None)
            if new_running != old_running or \
               self.snap.get("waiting") != getattr(self, "_shown_waiting", None):
                # 任务数变化时翻牌：变多向上，变少向下
                if old_running is not None and new_running is not None and new_running != old_running:
                    self.anim = (old_running, time.time(), new_running > old_running)
                self._shown_running = new_running
                self._shown_waiting = self.snap.get("waiting")
                changed = True
        if changed:
            self._draw()
        self.root.after(350, self._ui_tick)

    # ---------- 运行 ----------
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    enable_dpi()
    _mutex = single_instance()
    if _mutex is None:
        sys.exit(0)
    LampApp().run()
