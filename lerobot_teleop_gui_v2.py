#!/usr/bin/env python3
"""
LeRobot Workshop - Teleoperation Interface, redesigned (SO-100 / SO-101)
=========================================================================

Same features as `test_lerobot_teleop_gui.py` (teleoperate, record one
episode at a time, replay an episode), with a more modern look:

    - a big round START / STOP button that pulses while the robot moves
    - a colored status pill that always says what the robot is doing
    - "Record" and "Replay" cards with a progress bar and an episode stepper
    - buttons that are greyed out when they can't be used (no "robot busy" pop-ups)
    - a restyled settings window for the teacher
    - a "Joint angles" window showing the follower arm's joints live during teleoperation
      (teleoperation is launched through teleop_joint_stream.py, which streams them)
    - Esc key = emergency stop
    - interface in English, French, German or Italian (Settings > Language), see teleop_gui_i18n.py

Rendering is sharp on high-DPI screens: the window is DPI-aware on Windows, and
every shape (buttons, cards, shadows) is drawn with Pillow using supersampling,
so edges are anti-aliased instead of pixelated.

Needs tkinter and Pillow (already a LeRobot dependency). The configuration file
and the `lerobot-*` commands are shared with `test_lerobot_teleop_gui.py`.

Launch:
    python lerobot_teleop_gui_v2.py
"""

import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

from teleop_gui_i18n import LANGUAGES, get_language, set_language, tr
from test_lerobot_teleop_gui import (
    CONFIG_PATH,
    build_command,
    build_record_command,
    build_replay_command,
    load_config,
    save_config,
)

# Without this, Windows renders the window at 96 DPI and stretches it as a bitmap
# on scaled screens (125%, 150%...), which makes everything blurry.
if sys.platform == "win32":
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        # Own taskbar entry (with the app icon) instead of being grouped under "Python"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LeRobot.Workshop.Teleop")
    except Exception:
        pass

ICON_PATH = Path(__file__).with_name("lerobot_workshop.ico")  # drawn by create_desktop_shortcut.py

# Folder of the running Python (e.g. .venv\Scripts), where the lerobot-* commands are installed
PYTHON_SCRIPTS_DIR = Path(sys.executable).parent


def apply_crisp_icon(window):
    """Give Windows the .ico directly, at the exact sizes it asks for.

    Tk hands Windows a small icon that the taskbar then stretches on scaled screens (125%, 150%...),
    so it looks pixelated. The window/taskbar icon set here comes straight from the .ico file.
    """
    if sys.platform != "win32" or not ICON_PATH.exists():
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        window.update_idletasks()
        hwnd = int(window.wm_frame(), 16)  # the real top-level window (Tk wraps its own)
        # (ICON_BIG, SM_CXICON) is what the taskbar and Alt+Tab use, (ICON_SMALL, SM_CXSMICON) the title bar
        for which, metric in ((1, 11), (0, 49)):
            size = user32.GetSystemMetrics(metric)
            hicon = user32.LoadImageW(None, str(ICON_PATH), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if hicon:
                user32.SendMessageW(hwnd, 0x0080, which, hicon)  # WM_SETICON
    except Exception:
        pass  # keep Tk's icon

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
BG = "#FFF3F7"
SURFACE = "#FFFFFF"
BORDER = "#F1D4DF"
INPUT_BG = "#FFF9FB"
TEXT = "#2B2233"
MUTED = "#8C8091"
TRACK = "#F3E8EE"
SHADOW = "#C2185B28"  # #RRGGBBAA: pinkish, mostly transparent

PRIMARY = "#E8457A"
PRIMARY_HOVER = "#D13367"
PRIMARY_SOFT = "#FCE4EE"
GREEN = "#22C55E"
GREEN_HOVER = "#16A34A"
RED = "#EF4444"
RED_HOVER = "#DC2626"
AMBER = "#F59E0B"
BLUE = "#6366F1"
BLUE_HOVER = "#4F46E5"
DISABLED_BG = "#EDE6EA"
DISABLED_FG = "#B3A9B0"

CONSOLE_BG = "#1F1B24"
CONSOLE_FG = "#E4DDE8"

JOINT_STREAM_SCRIPT = Path(__file__).with_name("teleop_joint_stream.py")


HAND_CONTROL_SCRIPT = Path(__file__).with_name("teleop_mediapipe_hands.py")


def hand_control_command(cfg):
    """Webcam hand control (MediaPipe), with the webcam chosen in the settings."""
    camera = str(int(cfg.get("hand_camera", 0)))
    return [sys.executable, str(HAND_CONTROL_SCRIPT), "--stream-joints", "--camera", camera]


def teleop_command(cfg):
    """`lerobot-teleoperate`, run through teleop_joint_stream.py so the joint angles reach the GUI."""
    return [sys.executable, str(JOINT_STREAM_SCRIPT), *build_command(cfg)[1:]]


ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")  # cursor moves printed by lerobot-teleoperate

# ---------------------------------------------------------------------------
# DPI scaling: all sizes in this file are written for a 96 DPI screen and go through px()
# ---------------------------------------------------------------------------
SCALE = 1.0


def init_scale(root):
    global SCALE
    SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)


def px(value):
    return int(round(value * SCALE))


def blend(c1, c2, t):
    """Mix two #RRGGBB colors: t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Anti-aliased shape rendering (Pillow)
# ---------------------------------------------------------------------------
# A shape is a hashable tuple so rendered images can be cached:
#   ("rrect", (x1, y1, x2, y2), radius, fill, outline, outline_width)
#   ("shadow", (x1, y1, x2, y2), radius, color, blur, 0)
#   ("arc", (x1, y1, x2, y2), start, color, extent, width)
# Coordinates are in screen pixels, colors are "#RRGGBB" or "#RRGGBBAA".
_image_cache = {}


def rrect(box, radius, fill, outline=None, width=0):
    return ("rrect", tuple(box), radius, fill, outline, width)


def oval(box, fill):
    x1, y1, x2, y2 = box
    return rrect(box, min(x2 - x1, y2 - y1) / 2, fill)


def shadow(box, radius, blur, color=SHADOW):
    return ("shadow", tuple(box), radius, color, blur, 0)


def arc(box, start, extent, color, width):
    """Circle arc (angles in degrees, clockwise from 3 o'clock)."""
    return ("arc", tuple(box), start, color, extent, width)


def _rgba(color):
    alpha = int(color[7:9], 16) if len(color) == 9 else 255
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (alpha,)


def shape_image(w, h, bg, shapes):
    """Render `shapes` over a solid `bg` into a w x h PhotoImage, with smooth edges."""
    w, h = max(1, int(w)), max(1, int(h))
    key = (w, h, bg, tuple(shapes))
    cached = _image_cache.get(key)
    if cached is not None:
        return cached

    base = Image.new("RGBA", (w, h), _rgba(bg))

    # Shadows: drawn at 1x then blurred (a blur doesn't need supersampling, and it's much faster)
    for kind, box, r, color, blur, _ in shapes:
        if kind != "shadow":
            continue
        layer = Image.new("RGBA", (w, h), _rgba(color)[:3] + (0,))
        ImageDraw.Draw(layer).rounded_rectangle(box, radius=r, fill=_rgba(color))
        base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))

    # Crisp shapes: drawn at SS x the size, then downsampled -> anti-aliased edges
    ss = 4 if w * h < 250_000 else 2
    layer = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for kind, box, r, fill, outline, width in shapes:
        if kind == "arc":
            draw.arc(tuple(v * ss for v in box), r, r + outline, fill=_rgba(fill), width=int(width * ss))
        if kind != "rrect":
            continue
        x1, y1, x2, y2 = (v * ss for v in box)
        draw.rounded_rectangle(
            (x1, y1, x2 - 1, y2 - 1), radius=r * ss,
            fill=_rgba(fill) if fill else None,
            outline=_rgba(outline) if outline else None,
            width=int(width * ss),
        )
    base.alpha_composite(layer.resize((w, h), Image.LANCZOS))

    if len(_image_cache) > 400:
        _image_cache.clear()
    img = ImageTk.PhotoImage(base)
    _image_cache[key] = img
    return img


_fitted_fonts = {}


def fit_font(font, text, max_width):
    """`font`, or a smaller copy of it, so that the (single-line) `text` fits in `max_width` pixels."""
    size = font.actual("size")
    fitted = font
    while fitted.measure(text) > max_width and size > 6:
        size -= 1
        key = (font.actual("family"), size, font.actual("weight"))
        if key not in _fitted_fonts:
            _fitted_fonts[key] = tkfont.Font(family=key[0], size=size, weight=key[2])
        fitted = _fitted_fonts[key]
    return fitted


def make_fonts(root):
    families = set(tkfont.families(root))
    sans = next(
        (f for f in ("Segoe UI", "SF Pro Display", "Helvetica Neue", "Ubuntu", "DejaVu Sans") if f in families),
        "Helvetica",
    )
    mono = next((f for f in ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono") if f in families), "Courier")
    return {
        "title": tkfont.Font(root, family=sans, size=19, weight="bold"),
        "h2": tkfont.Font(root, family=sans, size=13, weight="bold"),
        "body": tkfont.Font(root, family=sans, size=10),
        "small": tkfont.Font(root, family=sans, size=9),
        "label": tkfont.Font(root, family=sans, size=9, weight="bold"),
        "button": tkfont.Font(root, family=sans, size=11, weight="bold"),
        "status": tkfont.Font(root, family=sans, size=11, weight="bold"),
        "big": tkfont.Font(root, family=sans, size=26, weight="bold"),
        "big_sub": tkfont.Font(root, family=sans, size=10),
        "timer": tkfont.Font(root, family=sans, size=20, weight="bold"),
        "counter": tkfont.Font(root, family=sans, size=22, weight="bold"),
        "mono": tkfont.Font(root, family=mono, size=9),
    }


# ---------------------------------------------------------------------------
# Custom widgets (sizes given at 96 DPI, scaled with px())
# ---------------------------------------------------------------------------
class RoundedButton(tk.Canvas):
    def __init__(self, master, text, command, bg, hover, fg="white", width=200, height=46,
                 radius=12, font=None, parent_bg=SURFACE):
        """`width=None` sizes the button to its text (translations have different lengths)."""
        self._bw = font.measure(text) + px(36) if width is None else px(width)
        self._bh, self._radius = px(height), px(radius)
        super().__init__(master, width=self._bw, height=self._bh, bg=parent_bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.parent_bg = parent_bg
        self.text, self.command = text, command
        self.bg_color, self.hover_color, self.fg_color = bg, hover, fg
        self.font = font
        self.enabled = True
        self._hover = False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def update_style(self, text=None, bg=None, hover=None, fg=None, enabled=None):
        if text is not None:
            self.text = text
        if bg is not None:
            self.bg_color = bg
        if hover is not None:
            self.hover_color = hover
        if fg is not None:
            self.fg_color = fg
        if enabled is not None:
            self.enabled = enabled
            self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _set_hover(self, value):
        self._hover = value
        self._draw()

    def _on_release(self, event):
        if self.enabled and 0 <= event.x <= self._bw and 0 <= event.y <= self._bh:
            self.command()

    def _draw(self):
        self.delete("all")
        if self.enabled:
            fill = self.hover_color if self._hover else self.bg_color
            fg = self.fg_color
        else:
            fill, fg = DISABLED_BG, DISABLED_FG
        self._img = shape_image(self._bw, self._bh, self.parent_bg,
                                [rrect((0, 0, self._bw, self._bh), self._radius, fill)])
        self.create_image(0, 0, anchor="nw", image=self._img)
        font = fit_font(self.font, self.text, self._bw - px(16))
        self.create_text(self._bw / 2, self._bh / 2, text=self.text, fill=fg, font=font)


class BigButton(tk.Canvas):
    """Big round START/STOP button, with a pulsing halo while the robot is moving."""

    SIZE = 210
    RADIUS = 78
    PULSE_STEPS = 24  # the halo size is quantized so rendered frames can be cached
    SPINNER_STEPS = 24  # same for the rotation of the "waiting" spinner

    def __init__(self, master, command, fonts):
        self.size, self.radius = px(self.SIZE), px(self.RADIUS)
        super().__init__(master, width=self.size, height=self.size, bg=SURFACE, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.command = command
        self.fonts = fonts
        self.label, self.sub = "START", "Take control"
        self.color, self.hover_color = GREEN, GREEN_HOVER
        self.enabled = True
        self._hover = False
        self._pulse = False
        self._spinner = False
        self._phase = 0.0
        self._frame = 0
        self._anim_job = None
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def update_style(self, label, sub, color, hover, pulse=False, spinner=False, enabled=True):
        """`pulse`: breathing halo (robot moving). `spinner`: rotating ring (waiting for the robot)."""
        self.label, self.sub = label, sub
        self.color, self.hover_color = color, hover
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._pulse, self._spinner = pulse, spinner
        animated = pulse or spinner
        if animated and self._anim_job is None:
            self._animate()
        elif not animated and self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        self._draw()

    def _set_hover(self, value):
        self._hover = value
        self._draw()

    def _on_release(self, event):
        c = self.size / 2
        if self.enabled and math.hypot(event.x - c, event.y - c) <= self.radius + px(6):
            self.command()

    def destroy(self):
        # A pending after() callback would call a command that Tk deletes along with the widget
        if self._anim_job is not None:
            self.after_cancel(self._anim_job)
        super().destroy()

    def _animate(self):
        self._phase += 2 * math.pi / (2 * self.PULSE_STEPS)
        self._frame = (self._frame + 1) % self.SPINNER_STEPS
        self._draw()
        self._anim_job = self.after(40, self._animate)

    def _draw(self):
        self.delete("all")
        c, r = self.size / 2, self.radius
        if not self.enabled:
            base = DISABLED_BG
        else:
            base = self.hover_color if self._hover else self.color

        if self._pulse:
            grow = round((math.sin(self._phase) + 1) / 2 * self.PULSE_STEPS) / self.PULSE_STEPS
            halo_r = r + px(8 + 16 * grow)
            halo = blend(base, SURFACE, 0.72 + 0.2 * grow)
        else:
            halo_r = r + px(14)
            halo = blend(base, SURFACE, 0.86)

        drop = px(6)
        shadow_color = blend(base, "#000000", 0.35) + ("30" if self.enabled else "18")
        shapes = [
            oval((c - halo_r, c - halo_r, c + halo_r, c + halo_r), halo),
            shadow((c - r, c - r + drop, c + r, c + r + drop), r, px(7), shadow_color),
            oval((c - r, c - r, c + r, c + r), base),
        ]
        if self._spinner:
            ring = r + px(9)
            start = self._frame * 360 / self.SPINNER_STEPS - 90
            shapes.append(arc((c - ring, c - ring, c + ring, c + ring), start, 100, base, px(5)))
        self._img = shape_image(self.size, self.size, SURFACE, shapes)
        self.create_image(0, 0, anchor="nw", image=self._img)

        fg = "#FFFFFF" if self.enabled else DISABLED_FG
        label_font = fit_font(self.fonts["big"], self.label, 1.7 * r)
        sub_font = fit_font(self.fonts["big_sub"], self.sub, 1.75 * r)
        self.create_text(c, c - px(8), text=self.label, fill=fg, font=label_font)
        self.create_text(c, c + px(26), text=self.sub, fill=blend(fg, base, 0.15), font=sub_font)


class StatusPill(tk.Canvas):
    HEIGHT = 36

    def __init__(self, master, font):
        super().__init__(master, height=px(self.HEIGHT), width=px(200), bg=SURFACE, highlightthickness=0, bd=0)
        self.font = font

    def show(self, text, color):
        h = px(self.HEIGHT)
        w = self.font.measure(text) + px(54)
        self.configure(width=w)
        self.delete("all")
        dot = (px(17), h / 2 - px(5), px(27), h / 2 + px(5))
        self._img = shape_image(w, h, SURFACE, [
            rrect((0, 0, w, h), h / 2, blend(color, SURFACE, 0.86)),
            oval(dot, color),
        ])
        self.create_image(0, 0, anchor="nw", image=self._img)
        self.create_text(px(37), h / 2, text=text, anchor="w", fill=blend(color, TEXT, 0.45), font=self.font)


class ProgressBar(tk.Canvas):
    HEIGHT = 8

    def __init__(self, master, width=240, color=RED):
        self._bw, self._bh = px(width), px(self.HEIGHT)
        super().__init__(master, width=self._bw, height=self._bh, bg=SURFACE, highlightthickness=0, bd=0)
        self.color = color
        self.set_fraction(0)

    def set_fraction(self, frac):
        frac = max(0.0, min(1.0, frac))
        w, h = self._bw, self._bh
        shapes = [rrect((0, 0, w, h), h / 2, TRACK)]
        if frac > 0:
            shapes.append(rrect((0, 0, max(h, round(w * frac)), h), h / 2, self.color))
        self.delete("all")
        self._img = shape_image(w, h, SURFACE, shapes)
        self.create_image(0, 0, anchor="nw", image=self._img)


class Card(tk.Canvas):
    """White rounded card with a soft shadow. Put child widgets inside `card.body`."""

    def __init__(self, master, pad=18, radius=18, parent_bg=BG):
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0)
        self.parent_bg = parent_bg
        self.pad, self.radius = px(pad), px(radius)
        self.margin = px(8)  # room around the card for the shadow
        self.body = tk.Frame(self, bg=SURFACE)
        self._win = self.create_window(0, 0, window=self.body, anchor="center")
        self._redraw_job = None
        self.body.bind("<Configure>", self._on_body_resize)
        self.bind("<Configure>", self._schedule_redraw)

    def _on_body_resize(self, event):
        extra = 2 * (self.pad + self.margin)
        self.configure(width=event.width + extra, height=event.height + extra)

    def _schedule_redraw(self, event=None):
        # Debounced: resizing the window fires many <Configure> events in a row
        w, h = self.winfo_width(), self.winfo_height()
        m = self.margin
        self.coords(self._win, w / 2, (h - m) / 2)
        if self._redraw_job is not None:
            self.after_cancel(self._redraw_job)
        self._redraw_job = self.after(15, self._redraw)

    def destroy(self):
        if self._redraw_job is not None:
            self.after_cancel(self._redraw_job)
        super().destroy()

    def _redraw(self):
        self._redraw_job = None
        w, h = self.winfo_width(), self.winfo_height()
        m = self.margin
        if w <= 4 * m or h <= 4 * m:  # not laid out yet
            return
        box = (m, m / 2, w - m, h - m * 1.5)
        shapes = [
            shadow((box[0], box[1] + px(4), box[2], box[3] + px(4)), self.radius, px(6)),
            rrect(box, self.radius, SURFACE, outline=BORDER, width=max(1, px(1))),
        ]
        self._img = shape_image(w, h, self.parent_bg, shapes)
        self.delete("bg")
        self.create_image(0, 0, anchor="nw", image=self._img, tags="bg")
        self.tag_lower("bg")


class Logo(tk.Canvas):
    SIZE = 48

    def __init__(self, master, parent_bg=BG):
        size = px(self.SIZE)
        super().__init__(master, width=size, height=size, bg=parent_bg, highlightthickness=0, bd=0)

        def s(*values):  # logo drawn on a 48x48 grid
            return tuple(v * size / self.SIZE for v in values)

        k = size / self.SIZE
        self._img = shape_image(size, size, parent_bg, [
            rrect(s(0, 0, 48, 48), 14 * k, PRIMARY),
            rrect(s(23, 8, 25, 15), 1 * k, "#FFFFFF"),  # antenna
            oval(s(20.5, 4.5, 27.5, 11.5), "#FFFFFF"),
            rrect(s(11, 14, 37, 37), 7 * k, "#FFFFFF"),  # head
            oval(s(16, 20.5, 22, 26.5), PRIMARY),  # eyes
            oval(s(26, 20.5, 32, 26.5), PRIMARY),
            rrect(s(19, 30.5, 29, 33), 1.25 * k, PRIMARY),  # mouth
        ])
        self.create_image(0, 0, anchor="nw", image=self._img)


def make_entry(parent, var, font, width=22):
    return tk.Entry(
        parent, textvariable=var, font=font, width=width, relief="flat", bg=INPUT_BG, fg=TEXT,
        insertbackground=TEXT, highlightthickness=max(1, px(1)), highlightbackground=BORDER,
        highlightcolor=PRIMARY,
    )


# ---------------------------------------------------------------------------
# Live joint angles window
# ---------------------------------------------------------------------------
# One fixed color per joint (reference categorical palette, in slot order), so a joint
# keeps its color whatever happens. Units differ (degrees vs gripper %), so each joint
# gets its own small chart instead of sharing one axis.
JOINTS = [
    ("shoulder_pan", "#2a78d6"),
    ("shoulder_lift", "#eb6834"),
    ("elbow_flex", "#1baf7a"),
    ("wrist_flex", "#eda100"),
    ("wrist_roll", "#e87ba4"),
    ("gripper", "#008300"),
]
JOINT_WINDOW_S = 10.0  # seconds of history shown in each chart
GRID = "#EFE6EB"


def sparkline_image(w, h, samples, now, color, min_span):
    """Anti-aliased line chart of (time, value) samples over the last JOINT_WINDOW_S seconds."""
    ss = 3
    img = Image.new("RGBA", (w * ss, h * ss), _rgba(SURFACE))
    draw = ImageDraw.Draw(img)
    pad_x, pad_y = px(6), px(8)

    values = [v for _, v in samples]
    lo, hi = min(values), max(values)
    if hi - lo < min_span:  # don't zoom in on sensor noise when the joint is still
        mid = (lo + hi) / 2
        lo, hi = mid - min_span / 2, mid + min_span / 2

    def xy(t, v):
        x = pad_x + (t - (now - JOINT_WINDOW_S)) / JOINT_WINDOW_S * (w - 2 * pad_x)
        y = pad_y + (hi - v) / (hi - lo) * (h - 2 * pad_y)
        return x * ss, y * ss

    # Recessive grid: top / bottom of the current range
    for y in (pad_y, h - pad_y):
        draw.line((pad_x * ss, y * ss, (w - pad_x) * ss, y * ss), fill=_rgba(GRID), width=ss)

    points = [xy(t, v) for t, v in samples]
    if len(points) >= 2:
        draw.line(points, fill=_rgba(color), width=2 * ss * max(1, round(SCALE)), joint="curve")
    x, y = points[-1]
    r = px(4) * ss
    draw.ellipse((x - r - 2 * ss, y - r - 2 * ss, x + r + 2 * ss, y + r + 2 * ss), fill=_rgba(SURFACE))
    draw.ellipse((x - r, y - r, x + r, y + r), fill=_rgba(color))

    return ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS)), lo, hi


class JointWindow(tk.Toplevel):
    """Shows the follower arm's joint angles live, from `app.joint_history`."""

    CHART_W, CHART_H = 196, 54

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        f = app.fonts
        self.title(tr("joints_window"))
        self.configure(bg=BG)
        self.resizable(False, False)

        wrap = tk.Frame(self, bg=BG)
        wrap.pack(padx=px(22), pady=px(18))
        tk.Label(wrap, text=tr("joints_title"), font=f["title"], bg=BG, fg=TEXT).pack(anchor="w")
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(wrap, textvariable=self.status_var, font=f["small"], bg=BG, fg=MUTED)
        self.status_label.pack(anchor="w")

        card = Card(wrap, pad=14)
        card.pack(fill="x", pady=(px(12), 0))
        grid = card.body
        self.rows = {}
        for i, (key, color) in enumerate(JOINTS):
            pady = (0, 0) if i == 0 else (px(6), 0)
            dot = tk.Canvas(grid, width=px(12), height=px(12), bg=SURFACE, highlightthickness=0, bd=0)
            dot_img = shape_image(px(12), px(12), SURFACE, [oval((0, 0, px(12), px(12)), color)])
            dot.create_image(0, 0, anchor="nw", image=dot_img)
            dot.grid(row=i, column=0, padx=(0, px(8)), pady=pady)
            tk.Label(grid, text=tr(f"joint_{key}"), font=f["body"], bg=SURFACE, fg=TEXT, anchor="w").grid(
                row=i, column=1, sticky="w", pady=pady)
            value_var = tk.StringVar(value="–")
            tk.Label(grid, textvariable=value_var, font=f["h2"], bg=SURFACE, fg=TEXT, width=7, anchor="e").grid(
                row=i, column=2, sticky="e", padx=(0, px(10)), pady=pady)
            chart = tk.Canvas(grid, width=px(self.CHART_W), height=px(self.CHART_H), bg=SURFACE,
                              highlightthickness=0, bd=0)
            chart.grid(row=i, column=3, pady=pady)
            range_var = tk.StringVar(value="")
            tk.Label(grid, textvariable=range_var, font=f["small"], bg=SURFACE, fg=MUTED, width=6,
                     justify="left", anchor="w").grid(row=i, column=4, sticky="w", padx=(px(8), 0), pady=pady)
            self.rows[key] = {"value": value_var, "chart": chart, "range": range_var, "color": color,
                              "dot": dot_img}

        tk.Label(wrap, text=tr("joints_note", seconds=f"{JOINT_WINDOW_S:.0f}"),
                 font=f["small"], bg=BG, fg=MUTED, justify="left").pack(anchor="w", pady=(px(10), 0))

        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self._refresh_job = None
        self._refresh()

    def destroy(self):
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        super().destroy()

    def show(self):
        self.deiconify()
        self.lift()

    def _refresh(self):
        history = list(self.app.joint_history)
        live = self.app.mode in ("teleop", "hand") and self.app._robot_moving
        if not history:
            self.status_var.set(tr("joints_waiting") if live else tr("joints_idle", start=tr("big_start")))
        elif live:
            self.status_var.set(tr("joints_live"))
        else:
            self.status_var.set(tr("joints_stopped"))
        self.status_label.config(fg=GREEN_HOVER if live and history else MUTED)

        if history:
            now = time.time() if live else history[-1][0]
            recent = [(t, j) for t, j in history if t >= now - JOINT_WINDOW_S]
            for key, row in self.rows.items():
                samples = [(t, j[key]) for t, j in recent if key in j]
                if not samples:
                    continue
                unit = "%" if key == "gripper" else "°"
                row["value"].set(f"{samples[-1][1]:.1f}{unit}")
                w, h = px(self.CHART_W), px(self.CHART_H)
                img, lo, hi = sparkline_image(w, h, samples, now, row["color"],
                                              min_span=10 if key == "gripper" else 20)
                row["img"] = img  # keep a reference, or Tk drops the image
                row["chart"].delete("all")
                row["chart"].create_image(0, 0, anchor="nw", image=img)
                row["range"].set(f"{hi:.0f}{unit}\n{lo:.0f}{unit}")
        self._refresh_job = self.after(100, self._refresh)


def probe_cameras(max_index=6):
    """(index, RGB thumbnail) for each webcam OpenCV can open. Slow (~1 s per camera): run it in a thread."""
    import cv2

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    found = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index, backend)
        try:
            if not cap.isOpened():
                continue
            frame = None
            for _ in range(5):  # the first frames are often black while the camera adjusts its exposure
                ok, image = cap.read()
                if ok:
                    frame = image
            if frame is not None:
                found.append((index, cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)))  # mirrored, as in hand control
        finally:
            cap.release()
    return found


class CameraTile(tk.Frame):
    """Clickable webcam thumbnail with its name, framed in pink when selected."""

    W, H, FRAME = 104, 78, 3

    def __init__(self, master, rgb, label, font, command):
        super().__init__(master, bg=BG)
        w, h, b = px(self.W), px(self.H), px(self.FRAME)
        self._outer = (w + 2 * b, h + 2 * b, b)
        self._photo = ImageTk.PhotoImage(ImageOps.fit(Image.fromarray(rgb), (w, h)))
        self.canvas = tk.Canvas(self, width=w + 2 * b, height=h + 2 * b, bg=BG, highlightthickness=0, bd=0,
                                cursor="hand2")
        self.canvas.pack()
        self.label = tk.Label(self, text=label, font=font, bg=BG, fg=MUTED, cursor="hand2")
        self.label.pack(pady=(px(3), 0))
        for widget in (self.canvas, self.label):
            widget.bind("<Button-1>", lambda e: command())
        self.set_selected(False)

    def set_selected(self, selected):
        w, h, b = self._outer
        self._frame_img = shape_image(w, h, BG, [rrect((0, 0, w, h), px(8), PRIMARY if selected else BORDER)])
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._frame_img)
        self.canvas.create_image(b, b, anchor="nw", image=self._photo)
        self.label.config(fg=PRIMARY if selected else MUTED)


# ---------------------------------------------------------------------------
# Settings window
# ---------------------------------------------------------------------------
class SettingsWindow(tk.Toplevel):
    def __init__(self, master, cfg, on_save, fonts):
        super().__init__(master)
        self.title(tr("settings_window"))
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(master)
        self.on_save = on_save
        f = fonts

        wrap = tk.Frame(self, bg=BG)
        wrap.pack(padx=px(26), pady=px(20))

        # Header: title on the left, robot model (segmented control) on the right
        header = tk.Frame(wrap, bg=BG)
        header.pack(fill="x")
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left")
        tk.Label(titles, text=tr("settings_title"), font=f["title"], bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(titles, text=tr("settings_help"), font=f["small"], bg=BG, fg=MUTED, wraplength=px(430),
                 justify="left").pack(anchor="w")

        seg = tk.Frame(header, bg=BG)
        seg.pack(side="right", anchor="s")
        self.model = cfg.get("robot_model", "SO-101")
        self.model_buttons = {}
        for model in ("SO-100", "SO-101"):
            btn = RoundedButton(seg, model, lambda m=model: self._select_model(m), bg=SURFACE, hover=SURFACE,
                                width=96, height=36, font=f["button"], parent_bg=BG)
            btn.pack(side="left", padx=(px(8), 0))
            self.model_buttons[model] = btn
        self._select_model(self.model)

        # Language: each one written in its own language, so anyone can find theirs
        lang_row = tk.Frame(wrap, bg=BG)
        lang_row.pack(fill="x", pady=(px(14), 0))
        tk.Label(lang_row, text=tr("language"), font=f["label"], bg=BG, fg=MUTED).pack(side="left",
                                                                                     padx=(0, px(12)))
        self.language = get_language()
        self.language_buttons = {}
        for code, name in LANGUAGES.items():
            btn = RoundedButton(lang_row, name, lambda c=code: self._select_language(c), bg=SURFACE,
                                hover=SURFACE, width=None, height=34, font=f["button"], parent_bg=BG)
            btn.pack(side="left", padx=(0, px(8)))
            self.language_buttons[code] = btn
        self._select_language(self.language)

        # Hand control on/off: when off, its button is not shown in the main window
        hand_row = self.hand_row = tk.Frame(wrap, bg=BG)
        hand_row.pack(fill="x", pady=(px(14), 0))
        tk.Label(hand_row, text=tr("hand_control"), font=f["label"], bg=BG, fg=MUTED).pack(side="left",
                                                                                         padx=(0, px(12)))
        self.hand_enabled = bool(cfg.get("hand_control_enabled", False))
        self.hand_buttons = {}
        for value, key in ((True, "enabled"), (False, "disabled")):
            btn = RoundedButton(hand_row, tr(key), lambda v=value: self._select_hand(v), bg=SURFACE,
                                hover=SURFACE, width=None, height=34, font=f["button"], parent_bg=BG)
            btn.pack(side="left", padx=(0, px(8)))
            self.hand_buttons[value] = btn

        # Webcam for hand control. OpenCV only gives numbers (no camera names), so each camera is
        # shown as a thumbnail to click. Looking for them takes a few seconds: done in a thread.
        self.fonts = f
        cam_row = self.cam_row = tk.Frame(wrap, bg=BG)
        tk.Label(cam_row, text=tr("hand_camera"), font=f["label"], bg=BG, fg=MUTED).pack(
            side="left", anchor="n", padx=(0, px(12)), pady=(px(8), 0))
        self.camera_tiles_frame = tk.Frame(cam_row, bg=BG)
        self.camera_tiles_frame.pack(side="left")
        self.camera = int(cfg.get("hand_camera", 0))
        self.camera_tiles = {}
        self._camera_status = tk.Label(self.camera_tiles_frame, text=tr("camera_searching"), font=f["small"],
                                       bg=BG, fg=MUTED)
        self._camera_status.pack(side="left", pady=px(8))
        self._probe_result = None
        threading.Thread(target=self._probe_cameras, daemon=True).start()
        self._probe_job = self.after(100, self._show_cameras)
        self._select_hand(self.hand_enabled)

        self.vars = {}
        cards = tk.Frame(wrap, bg=BG)
        cards.pack(fill="x", pady=(px(16), 0))

        # Arms
        arms = Card(cards, pad=16)
        arms.pack(side="left", fill="y")
        grid = arms.body
        for col, (side, title, port_hint) in enumerate((
            ("follower", tr("follower_arm"), "COM4 / ttyACM1"),
            ("leader", tr("leader_arm"), "COM3 / ttyACM0"),
        )):
            padx = (px(16), 0) if col else (0, 0)
            tk.Label(grid, text=title, font=f["h2"], bg=SURFACE, fg=TEXT).grid(row=0, column=col, sticky="w",
                                                                              padx=padx)
            self._field(grid, f"{side}_port", f"{tr('usb_port')}  ·  {port_hint}", cfg, f, 1, col, padx)
            self._field(grid, f"{side}_id", tr("arm_id"), cfg, f, 3, col, padx)
            RoundedButton(grid, tr("find_port"), lambda s=side, t=title: self._find_port(s, t), bg=PRIMARY_SOFT,
                          hover=blend(PRIMARY_SOFT, PRIMARY, 0.15), fg=PRIMARY, width=None, height=34,
                          font=f["button"]).grid(row=5, column=col, sticky="w", padx=padx, pady=(px(12), 0))

        # Recording
        rec = Card(cards, pad=16)
        rec.pack(side="left", fill="y", padx=(px(14), 0))
        grid = rec.body
        tk.Label(grid, text=tr("recording"), font=f["h2"], bg=SURFACE, fg=TEXT).grid(row=0, column=0, sticky="w")
        self._field(grid, "dataset_repo_id", tr("dataset_name"), cfg, f, 1, 0)
        self._field(grid, "task_description", tr("task_description"), cfg, f, 3, 0)
        self._field(grid, "episode_time_s", tr("episode_duration"), cfg, f, 5, 0)

        # Actions
        actions = tk.Frame(wrap, bg=BG)
        actions.pack(fill="x", pady=(px(16), 0))
        RoundedButton(actions, tr("save"), self.save, bg=PRIMARY, hover=PRIMARY_HOVER, width=None, height=42,
                      font=f["button"], parent_bg=BG).pack(side="right")
        RoundedButton(actions, tr("cancel"), self.destroy, bg=PRIMARY_SOFT,
                      hover=blend(PRIMARY_SOFT, PRIMARY, 0.15), fg=PRIMARY, width=None, height=42,
                      font=f["button"], parent_bg=BG).pack(side="right", padx=px(8))

        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def _find_port(self, side, arm_name):
        """Same trick as `lerobot-find-port`: the port that disappears when the cable is unplugged."""
        from serial.tools import list_ports

        before = {p.device for p in list_ports.comports()}
        if not messagebox.askokcancel(tr("find_port"), tr("find_port_unplug", arm=arm_name), parent=self):
            return
        time.sleep(0.5)  # let the system release the port
        gone = sorted(before - {p.device for p in list_ports.comports()})
        if len(gone) == 1:
            self.vars[f"{side}_port"].set(gone[0])
            messagebox.showinfo(tr("find_port"), tr("find_port_found", arm=arm_name, port=gone[0]), parent=self)
        else:
            messagebox.showerror(tr("find_port"), tr("find_port_fail"), parent=self)

    def _field(self, grid, key, label, cfg, fonts, row, col, padx=(0, 0)):
        """Small uppercase label with an entry below it, at (row, col) and (row + 1, col)."""
        tk.Label(grid, text=label, font=fonts["label"], bg=SURFACE, fg=MUTED).grid(
            row=row, column=col, sticky="w", padx=padx, pady=(px(10), px(3)))
        var = tk.StringVar(value=cfg.get(key, ""))
        self.vars[key] = var
        make_entry(grid, var, fonts["body"]).grid(row=row + 1, column=col, sticky="ew", padx=padx, ipady=px(5))

    def _select_model(self, model):
        self.model = model
        for name, btn in self.model_buttons.items():
            if name == model:
                btn.update_style(bg=PRIMARY, hover=PRIMARY_HOVER, fg="white")
            else:
                btn.update_style(bg=SURFACE, hover=PRIMARY_SOFT, fg=MUTED)

    def _select_hand(self, enabled):
        self.hand_enabled = enabled
        for value, btn in self.hand_buttons.items():
            if value == enabled:
                btn.update_style(bg=PRIMARY, hover=PRIMARY_HOVER, fg="white")
            else:
                btn.update_style(bg=SURFACE, hover=PRIMARY_SOFT, fg=MUTED)
        # The webcam choice only matters when hand control is on
        if enabled:
            self.cam_row.pack(fill="x", pady=(px(14), 0), after=self.hand_row)
        else:
            self.cam_row.pack_forget()

    def _probe_cameras(self):
        self._probe_result = probe_cameras()  # background thread

    def _show_cameras(self):
        if self._probe_result is None:
            self._probe_job = self.after(100, self._show_cameras)
            return
        self._probe_job = None
        self._camera_status.destroy()
        if not self._probe_result:
            tk.Label(self.camera_tiles_frame, text=tr("camera_none"), font=self.fonts["small"], bg=BG,
                     fg=MUTED).pack(side="left", pady=px(8))
            return
        for index, rgb in self._probe_result:
            tile = CameraTile(self.camera_tiles_frame, rgb, tr("camera_n", n=index), self.fonts["small"],
                              lambda i=index: self._select_camera(i))
            tile.pack(side="left", padx=(0, px(10)))
            self.camera_tiles[index] = tile
        self._select_camera(self.camera)

    def _select_camera(self, index):
        self.camera = index
        for i, tile in self.camera_tiles.items():
            tile.set_selected(i == index)

    def destroy(self):
        # A pending after() callback would call a command that Tk deletes along with the window
        if self._probe_job is not None:
            self.after_cancel(self._probe_job)
        super().destroy()

    def _select_language(self, code):
        self.language = code
        for name, btn in self.language_buttons.items():
            if name == code:
                btn.update_style(bg=PRIMARY, hover=PRIMARY_HOVER, fg="white")
            else:
                btn.update_style(bg=SURFACE, hover=PRIMARY_SOFT, fg=MUTED)

    def save(self):
        new_cfg = {"robot_model": self.model, "language": self.language, "hand_camera": self.camera,
                   "hand_control_enabled": self.hand_enabled}
        for key, var in self.vars.items():
            new_cfg[key] = var.get().strip()
        save_config(new_cfg)
        self.on_save(new_cfg)
        self.destroy()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class TeleopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg=BG)
        if ICON_PATH.exists():
            self.iconbitmap(default=str(ICON_PATH))  # default=: the other windows get it too
        init_scale(self)
        self.fonts = make_fonts(self)

        self.cfg = load_config()
        set_language(self.cfg.get("language", "en"))
        self.title(tr("app_title"))
        self.process = None
        self.mode = None  # None | "teleop" | "record" | "replay"
        self._user_stopped = False
        self._started_at = None  # teleop: when the robot started moving; record: when recording started
        self._launched_at = None
        self._robot_moving = False
        # Set by the reader thread when the robot really starts: first teleop loop line, or the
        # "Recording episode N" line of lerobot-record (it takes several seconds to start up)
        self._moving_event = threading.Event()
        self._pending_repo_id = None
        self.joint_history = deque(maxlen=400)  # (time, {joint: value}), filled by the reader thread
        self.joint_window = None
        self.dataset_repo_id = None  # set after the first successful recording, then reused (resume=true)
        self.episode_count = 0
        self.replay_episode = 0
        self.log_queue = queue.Queue()
        self.log_visible = False
        self._status = ("status_stopped", MUTED, {})  # (text key, color, format args), re-shown on language change
        self._hint = ("hint_idle", False, {})

        self._build_log_window()
        self._build_ui()
        self._refresh_controls()
        self._set_status("status_stopped", MUTED)
        self._set_hint("hint_idle")
        self._poll_log_queue()
        self._tick()
        self._fit_window()
        self.after(50, lambda: apply_crisp_icon(self))

        if not CONFIG_PATH.exists():
            self.after(300, self.open_settings)

        self.bind("<Escape>", lambda e: self.stop_current())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----- UI -------------------------------------------------------------
    def _fit_window(self):
        """Size the window to fit its content (font sizes depend on the screen's DPI and the language)."""
        self.update_idletasks()
        self.minsize(max(px(720), self.winfo_reqwidth()), self.winfo_reqheight())

    def _apply_language(self, code):
        """Rebuild every window with the texts of the new language (the robot is idle at this point)."""
        set_language(code)
        self.title(tr("app_title"))
        self.log_window.title(tr("log_title"))
        reopen_joints = self.joint_window is not None and self.joint_window.state() == "normal"
        if self.joint_window is not None:
            self.joint_window.destroy()
            self.joint_window = None

        self._outer.destroy()
        self._build_ui()
        self.episodes_var.set(str(self.episode_count))
        self._refresh_controls()
        key, color, kwargs = self._status
        self._set_status(key, color, **kwargs)
        key, error, kwargs = self._hint
        self._set_hint(key, error, **kwargs)
        self.log_toggle.config(text=tr("hide_log" if self.log_visible else "show_log"))
        self._fit_window()
        if reopen_joints:
            self.open_joint_window()

    def _build_ui(self):
        f = self.fonts
        outer = self._outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=px(28), pady=px(22))

        # Header
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        Logo(header).pack(side="left")
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", padx=px(12))
        tk.Label(titles, text=tr("app_title"), font=f["title"], bg=BG, fg=TEXT).pack(anchor="w")
        self.subtitle_var = tk.StringVar()
        tk.Label(titles, textvariable=self.subtitle_var, font=f["small"], bg=BG, fg=MUTED).pack(anchor="w")
        self._update_subtitle()
        self.settings_btn = RoundedButton(
            header, tr("btn_settings"), self.open_settings, bg=PRIMARY_SOFT,
            hover=blend(PRIMARY_SOFT, PRIMARY, 0.15), fg=PRIMARY, width=None, height=40, font=f["button"],
            parent_bg=BG,
        )
        self.settings_btn.pack(side="right")
        RoundedButton(
            header, tr("btn_joints"), self.open_joint_window, bg=PRIMARY_SOFT,
            hover=blend(PRIMARY_SOFT, PRIMARY, 0.15), fg=PRIMARY, width=None, height=40, font=f["button"],
            parent_bg=BG,
        ).pack(side="right", padx=(0, px(10)))

        # Main area: big card on the left, record / replay cards stacked on the right
        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True, pady=(px(18), 0))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        main = Card(content)
        main.grid(row=0, column=0, sticky="nsew", padx=(0, px(14)))
        body = main.body
        self.status_pill = StatusPill(body, f["status"])
        self.status_pill.pack(pady=(px(2), px(4)))
        self.big_button = BigButton(body, self.toggle_teleop, f)
        self.big_button.pack()
        self.timer_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self.timer_var, font=f["timer"], bg=SURFACE, fg=TEXT).pack()
        self.hint_label = tk.Label(body, text="", font=f["body"], bg=SURFACE, fg=MUTED, wraplength=px(400),
                                   justify="center", height=3)
        self.hint_label.pack(pady=(0, px(2)))
        self.hand_btn = RoundedButton(body, "", self.toggle_hand, bg=PRIMARY_SOFT,
                                      hover=blend(PRIMARY_SOFT, PRIMARY, 0.15), fg=PRIMARY, width=300, height=40,
                                      font=f["button"])
        self._show_hand_button()

        side = tk.Frame(content, bg=BG)
        side.grid(row=0, column=1, sticky="ns")

        rec = Card(side)
        rec.pack(fill="x")
        self._build_record_card(rec.body)

        rep = Card(side)
        rep.pack(fill="x", pady=(px(12), 0))
        self._build_replay_card(rep.body)

        # Footer + collapsible technical log
        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", pady=(px(14), 0))
        self.log_toggle = tk.Label(footer, text=tr("show_log"), font=f["small"], bg=BG, fg=MUTED, cursor="hand2")
        self.log_toggle.pack(side="left")
        self.log_toggle.bind("<Button-1>", lambda e: self._toggle_log())
        tk.Label(footer, text=tr("esc_hint"), font=f["small"], bg=BG, fg=MUTED).pack(side="right")

    def _build_log_window(self):
        # The technical log lives in its own window: the main window already uses most of the
        # screen height, so there is no room left to show it below the cards. Built once, so the
        # log survives a language change.
        f = self.fonts
        self.log_window = tk.Toplevel(self)
        self.log_window.title(tr("log_title"))
        self.log_window.configure(bg=CONSOLE_BG)
        self.log_window.geometry(f"{px(760)}x{px(320)}")
        self.log_window.protocol("WM_DELETE_WINDOW", self._toggle_log)
        self.log_window.withdraw()  # hidden until the user asks for it
        log_scroll = tk.Scrollbar(self.log_window)
        log_scroll.pack(side="right", fill="y")
        self.log_text = tk.Text(
            self.log_window, bg=CONSOLE_BG, fg=CONSOLE_FG, insertbackground=CONSOLE_FG, relief="flat",
            bd=0, padx=px(12), pady=px(10), font=f["mono"], wrap="word", yscrollcommand=log_scroll.set,
            state="disabled",
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.config(command=self.log_text.yview)

    def _build_record_card(self, body):
        f = self.fonts
        tk.Label(body, text=tr("rec_title"), font=f["h2"], bg=SURFACE, fg=RED).pack(anchor="w")
        tk.Label(body, text=tr("rec_desc"), font=f["small"],
                 bg=SURFACE, fg=MUTED, wraplength=px(250), justify="left").pack(anchor="w", pady=(0, px(4)))

        counter = tk.Frame(body, bg=SURFACE)
        counter.pack(anchor="w")
        self.episodes_var = tk.StringVar(value="0")
        tk.Label(counter, textvariable=self.episodes_var, font=f["counter"], bg=SURFACE, fg=PRIMARY).pack(side="left")
        tk.Label(counter, text=tr("rec_counter"), font=f["small"], bg=SURFACE, fg=MUTED,
                 justify="left").pack(side="left", padx=(px(8), 0))

        self.progress = ProgressBar(body, width=250)
        self.progress.pack(pady=(px(6), px(2)))
        self.progress_var = tk.StringVar(value=" ")
        tk.Label(body, textvariable=self.progress_var, font=f["small"], bg=SURFACE, fg=MUTED).pack(anchor="w")

        self.record_btn = RoundedButton(body, "", self.toggle_record, bg=BLUE, hover=BLUE_HOVER, width=250,
                                        height=44, font=f["button"])
        self.record_btn.pack(pady=(px(4), 0))

    def _build_replay_card(self, body):
        f = self.fonts
        tk.Label(body, text=tr("rep_title"), font=f["h2"], bg=SURFACE, fg=BLUE).pack(anchor="w")
        tk.Label(body, text=tr("rep_desc"), font=f["small"],
                 bg=SURFACE, fg=MUTED, wraplength=px(250), justify="left").pack(anchor="w", pady=(0, px(8)))

        stepper = tk.Frame(body, bg=SURFACE)
        stepper.pack(pady=(0, px(2)))
        soft_hover = blend(PRIMARY_SOFT, PRIMARY, 0.15)
        self.minus_btn = RoundedButton(stepper, "−", lambda: self._step_episode(-1), bg=PRIMARY_SOFT,
                                       hover=soft_hover, fg=PRIMARY, width=40, height=40, font=f["h2"])
        self.minus_btn.pack(side="left")
        self.replay_ep_var = tk.StringVar(value="#0")
        tk.Label(stepper, textvariable=self.replay_ep_var, font=f["counter"], bg=SURFACE, fg=TEXT,
                 width=4).pack(side="left", padx=px(10))
        self.plus_btn = RoundedButton(stepper, "+", lambda: self._step_episode(1), bg=PRIMARY_SOFT,
                                      hover=soft_hover, fg=PRIMARY, width=40, height=40, font=f["h2"])
        self.plus_btn.pack(side="left")

        self.replay_btn = RoundedButton(body, "", self.toggle_replay, bg=BLUE, hover=BLUE_HOVER, width=250,
                                        height=44, font=f["button"])
        self.replay_btn.pack(pady=(px(10), 0))

    # ----- UI state helpers -------------------------------------------------
    def _show_hand_button(self):
        """The hand control button is only in the main window when it is enabled in the settings."""
        if self.cfg.get("hand_control_enabled", False):
            self.hand_btn.pack(pady=(px(4), px(2)))
        else:
            self.hand_btn.pack_forget()

    def _update_subtitle(self):
        c = self.cfg
        self.subtitle_var.set(tr("subtitle", model=c.get("robot_model", "SO-101"),
                                 follower=c.get("follower_port", "?"), leader=c.get("leader_port", "?")))

    def _set_status(self, key, color, **kwargs):
        self._status = (key, color, kwargs)
        self.status_pill.show(tr(key, **kwargs), color)

    def _set_hint(self, key, error=False, **kwargs):
        self._hint = (key, error, kwargs)
        self.hint_label.config(text=tr(key, **kwargs), fg=RED_HOVER if error else MUTED)

    def _refresh_controls(self):
        m = self.mode
        idle = m is None
        has_episodes = self.episode_count > 0

        if m == "teleop" and self._robot_moving:
            self.big_button.update_style(tr("big_stop"), tr("big_stop_sub"), RED, RED_HOVER, pulse=True)
        elif m == "teleop":
            # Still connecting: stays clickable so the connection can be cancelled
            self.big_button.update_style(tr("big_wait"), tr("big_wait_sub"), AMBER,
                                         blend(AMBER, "#000000", 0.12), spinner=True)
        elif idle:
            self.big_button.update_style(tr("big_start"), tr("big_start_sub"), GREEN, GREEN_HOVER)
        else:
            self.big_button.update_style(tr("big_busy"), tr("big_busy_sub"), GREEN, GREEN_HOVER, enabled=False)

        if m == "hand":
            self.hand_btn.update_style(text=tr("hand_stop"), bg=RED, hover=RED_HOVER, fg="white", enabled=True)
        else:
            self.hand_btn.update_style(text=tr("hand_btn"), bg=PRIMARY_SOFT, hover=blend(PRIMARY_SOFT, PRIMARY, 0.15),
                                       fg=PRIMARY, enabled=idle)

        if m == "record":
            self.record_btn.update_style(text=tr("rec_stop"), bg=RED, hover=RED_HOVER, enabled=True)
        else:
            self.record_btn.update_style(text=tr("rec_btn"), bg=BLUE, hover=BLUE_HOVER, enabled=idle)

        if m == "replay":
            self.replay_btn.update_style(text=tr("rep_stop"), bg=RED, hover=RED_HOVER, enabled=True)
        else:
            self.replay_btn.update_style(text=tr("rep_btn"), bg=BLUE, hover=BLUE_HOVER,
                                         enabled=idle and has_episodes)

        self.minus_btn.update_style(enabled=idle and self.replay_episode > 0)
        self.plus_btn.update_style(enabled=idle and self.replay_episode < self.episode_count - 1)
        self.replay_ep_var.set(f"#{self.replay_episode}" if has_episodes else "–")
        self.settings_btn.update_style(enabled=idle)

    def _step_episode(self, delta):
        self.replay_episode = max(0, min(self.episode_count - 1, self.replay_episode + delta))
        self._refresh_controls()

    def _episode_time(self):
        try:
            return max(1.0, float(self.cfg.get("episode_time_s", 10)))
        except (TypeError, ValueError):
            return 10.0

    def _tick(self):
        if self.mode in ("teleop", "record", "hand") and not self._robot_moving and not self._user_stopped:
            if self._moving_event.is_set():
                {"record": self._on_recording_started, "hand": self._on_hand_started,
                 "teleop": self._on_robot_moving}[self.mode]()
            elif time.time() - self._launched_at > 25:
                self._set_hint("hint_slow")
        if self.mode in ("teleop", "hand") and self._started_at is not None:
            elapsed = int(time.time() - self._started_at)
            self.timer_var.set(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        elif self.mode == "record" and self._started_at is not None:
            total = self._episode_time()
            elapsed = time.time() - self._started_at
            self.progress.set_fraction(elapsed / total)
            if elapsed < total:
                self.progress_var.set(tr("rec_progress", elapsed=f"{elapsed:.0f}", total=f"{total:.0f}"))
            else:
                self.progress_var.set(tr("rec_saving"))
        elif self.mode == "record":
            self.progress_var.set(tr("rec_preparing"))
        self.after(200, self._tick)

    def _toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            # Open it next to the main window so it doesn't hide the buttons: on the right if
            # there is room on the screen, otherwise below (or over the bottom of the window).
            self.update_idletasks()
            gap = px(8)
            right_x = self.winfo_rootx() + self.winfo_width() + gap
            room_right = self.winfo_screenwidth() - right_x - gap
            if room_right >= px(420):
                # geometry() positions the outer frame (title bar included), like winfo_y()
                w, h = min(px(760), room_right), self.winfo_height()
                x, y = right_x, self.winfo_y()
            else:
                w, h = px(760), px(320)
                x = self.winfo_rootx()
                y = min(self.winfo_rooty() + self.winfo_height() + gap, self.winfo_screenheight() - h - px(80))
            self.log_window.geometry(f"{w}x{h}+{x}+{max(0, y)}")
            self.log_window.deiconify()
            self.log_window.lift()
            self.log_text.see("end")
            self.log_toggle.config(text=tr("hide_log"))
        else:
            self.log_window.withdraw()
            self.log_toggle.config(text=tr("show_log"))

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _poll_log_queue(self):
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(200, self._poll_log_queue)

    # ----- Joint angles window -------------------------------------------
    def open_joint_window(self):
        if self.joint_window is None:
            self.joint_window = JointWindow(self)
            # Next to the main window, like the technical log
            self.update_idletasks()
            x = self.winfo_rootx() + self.winfo_width() + px(8)
            if x + self.joint_window.winfo_reqwidth() > self.winfo_screenwidth():
                x = max(0, self.winfo_screenwidth() - self.joint_window.winfo_reqwidth() - px(8))
            self.joint_window.geometry(f"+{x}+{self.winfo_y()}")
        self.joint_window.show()

    # ----- Settings -------------------------------------------------------
    def open_settings(self):
        if self.mode is not None:
            messagebox.showinfo(tr("busy_title"), tr("busy_msg"))
            return
        window = SettingsWindow(self, self.cfg, self._settings_saved, self.fonts)
        # Open it aligned with the top of the main window: it is tall, and Windows' default spot
        # can push its Save button under the taskbar
        window.geometry(f"+{self.winfo_x() + px(20)}+{max(0, self.winfo_y())}")

    def _settings_saved(self, new_cfg):
        self.cfg = new_cfg
        if new_cfg.get("language", "en") != get_language():
            self._apply_language(new_cfg["language"])
        self._show_hand_button()
        self._fit_window()
        self._update_subtitle()
        self._set_hint("hint_settings_saved", start=tr("big_start"))

    # ----- Actions --------------------------------------------------------
    def toggle_teleop(self):
        if self.mode == "teleop":
            self.stop_current()
        elif self.mode is None:
            self.start_teleop()

    def toggle_record(self):
        if self.mode == "record":
            self.stop_current()
        elif self.mode is None:
            self.start_record()

    def toggle_replay(self):
        if self.mode == "replay":
            self.stop_current()
        elif self.mode is None:
            self.start_replay()

    def toggle_hand(self):
        if self.mode == "hand":
            self.stop_current()
        elif self.mode is None:
            self.start_hand()

    def start_hand(self):
        self.joint_history.clear()
        if not self._launch_process(hand_control_command(self.cfg), mode="hand"):
            return
        self._set_status("status_hand_starting", AMBER)
        self._set_hint("hint_hand_starting")

    def _on_hand_started(self):
        self._robot_moving = True
        self._started_at = time.time()
        self._set_status("status_hand_running", GREEN)
        self._set_hint("hint_hand_running")
        self._refresh_controls()

    def start_teleop(self):
        self.joint_history.clear()
        if not self._launch_process(teleop_command(self.cfg), mode="teleop"):
            return
        self._set_status("status_connecting", AMBER)
        self._set_hint("hint_connecting")

    def start_record(self):
        if self.dataset_repo_id is None:
            base = (self.cfg.get("dataset_repo_id") or "workshop/my_session").strip()
            self._pending_repo_id = f"{base}_{time.strftime('%Y%m%d_%H%M%S')}"
            resume = False
        else:
            self._pending_repo_id = self.dataset_repo_id
            resume = True

        cmd = build_record_command(self.cfg, self._pending_repo_id, resume)
        if not self._launch_process(cmd, mode="record"):
            return
        # Not recording yet: lerobot-record needs a few seconds to start (loading, connecting the arms).
        # Moving the arm now would be lost, so ask to wait for the "Go!".
        self._set_status("status_record_preparing", AMBER)
        self._set_hint("hint_record_preparing")
        self.progress.set_fraction(0)

    def start_replay(self):
        if self.dataset_repo_id is None:
            return
        episode = self.replay_episode
        if not self._launch_process(build_replay_command(self.cfg, self.dataset_repo_id, episode), mode="replay"):
            return
        self._set_status("status_replaying", BLUE, n=episode)
        self._set_hint("hint_replaying")

    def stop_current(self):
        """Emergency stop for whichever process (teleop/record/replay) is running."""
        if self.process is None:
            return
        self._user_stopped = True
        self._set_status("status_stopping", AMBER)
        if self.mode == "hand":
            # Ask the hand-control script to quit by itself: it brings the arm back to its starting
            # position before disconnecting. Killed only if it doesn't stop within 10 s.
            try:
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
                process = self.process
                self.after(10000, lambda: process.poll() is None and process.terminate())
                return
            except Exception:
                pass
        try:
            self.process.terminate()
        except Exception:
            pass

    # ----- Process management ---------------------------------------------
    def _launch_process(self, cmd, mode):
        """Start `cmd` as the exclusive robot-controlling process. Returns True on success."""
        # Started from the desktop shortcut, the virtualenv isn't activated: its Scripts folder (where
        # lerobot-record, lerobot-replay... live) isn't on the PATH, so look there first.
        search_path = os.pathsep.join([str(PYTHON_SCRIPTS_DIR), os.environ.get("PATH", "")])
        command_name = cmd[0]
        cmd = [shutil.which(command_name, path=search_path) or command_name, *cmd[1:]]
        self._append_log(f"\n$ {' '.join(cmd)}\n")
        try:
            # Unbuffered output: otherwise Python holds the child's prints in a buffer and we would
            # only learn that the robot moves several seconds late.
            self.process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=dict(os.environ, PYTHONUNBUFFERED="1", PATH=search_path),
                # Launched from the desktop shortcut (pythonw, no terminal), each lerobot command
                # would otherwise pop up its own black console window
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except FileNotFoundError:
            messagebox.showerror(tr("notfound_title"), tr("notfound_msg", cmd=command_name))
            self._append_log(f"Error: '{command_name}' command not found.\n")
            return False

        self.mode = mode
        self._user_stopped = False
        self._launched_at = time.time()
        # teleop / record: set when the robot really starts (see _moving_event); replay: right away
        self._started_at = None if mode in ("teleop", "record", "hand") else self._launched_at
        self._robot_moving = False
        self._moving_event.clear()
        self._refresh_controls()

        threading.Thread(target=self._watch_process, args=(self.process,), daemon=True).start()

        # Some commands pause on startup waiting for Enter (e.g. a calibration-mismatch
        # confirmation). Kids can't see that prompt here, so send newlines automatically.
        self.after(800, self._send_enter)
        self.after(2500, self._send_enter)
        return True

    def _send_enter(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def _on_recording_started(self):
        self._robot_moving = True
        self._started_at = time.time()  # the progress bar measures the real recording time
        self._set_status("status_recording", RED, n=self.episode_count)
        self._set_hint("hint_recording")

    def _on_robot_moving(self):
        self._robot_moving = True
        self._started_at = time.time()
        self._set_status("status_running", GREEN)
        self._set_hint("hint_running")
        self._refresh_controls()

    def _watch_process(self, process):
        output_lines = []
        loop_lines = 0
        for line in process.stdout:
            line = ANSI_ESCAPE.sub("", line)
            if not line.strip():  # teleop_joint_stream.py starts each JOINTS line with a newline
                continue
            if line.startswith("JOINTS "):  # printed by teleop_joint_stream.py, ~15 per second
                try:
                    self.joint_history.append((time.time(), json.loads(line[len("JOINTS "):])))
                except ValueError:
                    pass
                continue
            # lerobot-teleoperate prints this on every loop iteration, i.e. only once both arms are
            # connected and the follower is actually tracking the leader.
            if "HAND_CONTROL_READY" in line:  # printed by teleop_mediapipe_hands.py once the camera runs
                self._moving_event.set()
            if "Recording episode" in line:  # logged by lerobot-record when the episode starts
                self._moving_event.set()
            if "Teleop loop time" in line:
                self._moving_event.set()
                loop_lines += 1
                if loop_lines > 1:  # ~30 lines per second: keep only the first one in the log
                    continue
            output_lines.append(line)
            self.log_queue.put(line)
        return_code = process.wait()
        self.after(0, lambda: self._process_ended(return_code, output_lines))

    def _process_ended(self, return_code, output_lines):
        mode = self.mode
        user_stopped = self._user_stopped
        self.process = None
        self.mode = None
        self._started_at = None
        self.timer_var.set("")
        self.progress.set_fraction(0)
        self.progress_var.set(" ")
        self._append_log(f"(process ended, exit code: {return_code})\n")

        success = return_code == 0 and not user_stopped
        if mode == "record" and success:
            self.dataset_repo_id = self._pending_repo_id
            self.episode_count += 1
            self.replay_episode = self.episode_count - 1
            self.episodes_var.set(str(self.episode_count))
            self._set_status("status_recorded", GREEN, n=self.episode_count - 1)
            self._set_hint("hint_recorded")
        elif mode == "replay" and success:
            self._set_status("status_replay_done", GREEN)
            self._set_hint("hint_replay_done")
        elif user_stopped or return_code in (0, None):
            self._set_status("status_stopped", MUTED)
            self._set_hint("hint_record_early" if mode == "record" else "hint_idle")
        else:
            self._set_status("status_error", RED)
            self._set_hint("hint_error", error=True)
            if not self.log_visible:
                self._toggle_log()

        self._refresh_controls()

    def _on_close(self):
        self.stop_current()
        self.destroy()


if __name__ == "__main__":
    app = TeleopApp()
    app.mainloop()
