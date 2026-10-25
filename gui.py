"""
gui.py

Tkinter front-end for fishing_bot_core.FishingBot — "I-Fish".

Layout (top to bottom): title, Start/Stop, Cast/Catch stats, Auto-Stop
Timer, then a bottom tab bar (Keybindings / Fishing Zone / Bobber
Detection / Advanced Settings) — each tab opens its controls in its own
popup dialog, same pattern as Advanced Settings did before.

Theme: dark chrome panel look with blue (primary/start) and red
(stop/danger) accents, glossy pill-shaped buttons drawn on Canvas
(Tkinter has no native rounded-button widget, so PillButton fakes one
with a smoothed polygon). There's no way to drop in an actual photo as
a live widget background in stock Tkinter without it fighting every
packed widget on top of it, so the "sci-fi panel" feel is done with
color/line accents instead of a literal image.

Settings (keybindings, picked color, thresholds, buff config, timer,
etc.) are saved to fishing_bot_settings.json next to this script (or
next to the built .exe) and reloaded automatically on the next launch.

Run with:  python gui.py
Build to a Windows .exe with an icon using build_exe.py (PyInstaller).
"""

import json
import os
import queue
import subprocess
import sys
import time
import tkinter as tk
import webbrowser
from collections import Counter
from tkinter import messagebox, ttk
from theme import *

import pyautogui

from fishing_bot_core import BotConfig, FishingBot, build_lure_macro, scan_for_color

# A starter list of well-known WoW fishing poles across expansions (Classic
# through retail) for the "Fishing Pole" dropdown. Not exhaustive — the
# dropdown is editable, so you can type any pole name that isn't listed.
KNOWN_FISHING_POLES = [
    "Fishing Pole",
    "Strong Fishing Pole",
    "Darkwood Fishing Pole",
    "Big Iron Fishing Pole",
    "Blump Family Fishing Pole",
    "Nat Pagle's Extreme Angler FC-5000",
    "Arcanite Fishing Pole",
    "Mastercraft Kalu'ak Fishing Pole",
    "Seth's Graphite Fishing Pole",
    "Jeweled Fishing Pole",
    "Volatile Fishing Pole",
    "Draenic Fishing Pole",
    "Underlight Angler",
    "Enormous Fishing Pole",
]

# Fishing lures/baits across expansions (compiled from Warcraft Wiki's
# "Fishing lures" category) for the "Lure/buff item" dropdown. Not
# exhaustive — the dropdown is editable, so you can type a custom name.
KNOWN_FISHING_LURES = [
    "Aquadynamic Fish Attractor",
    "Aquadynamic Fish Lens",
    "Bright Baubles",
    "Shiny Bauble",
    "Nightcrawlers",
    "Nightmare Nightcrawler",
    "Flesh Eating Worm",
    "Glow Worm",
    "Frost Worm",
    "Worm Supreme",
    "Ravenous Fly",
    "Arcane Lure",
    "Enchanted Lure",
    "Salmon Lure",
    "Mudskunk Lure",
    "Axefish Lure",
    "Aurelid Lure",
    "\"Fragrant\" Pheromone Fish",
    "Abyssal Gulper Eel Bait",
    "Aileron Seamoth Lure",
    "Arathor Hammerfish Lure",
    "Aromatic Murloc Slime",
    "Blackwater Whiptail Bait",
    "Blind Lake Sturgeon Bait",
    "Blood Hunter Lure",
    "Cerulean Spinefish Lure",
    "Day-Old Darkmoon Doughnut",
    "Decayed Whale Blubber",
    "Demonic Detritus",
    "Dornish Pike Lure",
    "Drowned Thistleleaf",
    "Elysian Thade Bait",
    "Fat Sleeper Bait",
    "Feathered Lure",
    "Felmouth Frenzy Bait",
    "Fire Ammonite Bait",
    "Fishing Hat Lure",
    "Funky Sea Snail",
    "Glass Fishing Bobber",
    "Heat-Treated Spinning Lure",
    "Hundred-Fathom Lure",
    "Iridescent Amberjack Bait",
    "Islefin Dorado Lure",
    "Jawless Skulker Bait",
    "Lava Spices",
    "Lost Sole Bait",
    "Lucky Loa Lure",
    "Message in a Beer Bottle",
    "Moosehorn Hook",
    "Ominous Octopus Lure",
    "Pearlescent Conch",
    "Pocked Bonefish Bait",
    "Precursor Placoderm Bait",
    "Quiet River Bass Lure",
    "Roaring Anglerseeker Lure",
    "Rotten Fishbone",
    "Rusty Queenfish Brooch",
    "Scalebelly Mackerel Lure",
    "Scarlet Herring Lure",
    "Sea Scorpion Bait",
    "Sharpened Fish Hook",
    "Silvergill Pike Bait",
    "Silverscale Minnow",
    "Skrog Toenail",
    "Sleeping Murloc",
    "Soggy Drakescale",
    "Specular Rainbowfish Lure",
    "Spinefin Piranha Bait",
    "Stunned, Angry Shark",
    "Swollen Murloc Egg",
    "Temporal Dragonhead Lure",
    "Thousandbite Piranha Lure",
    "Weather-Beaten Fishing Hat",
    "Nat's Hat",
    "Nat's Drinking Hat",
]

try:
    import keyboard  # global hotkey support (Windows)
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

APP_TITLE = "I-Fish"

# ---------------------------------------------------------------------------
# Theme: dark chrome panel with blue (primary) / red (stop) accents
# ---------------------------------------------------------------------------
#THEME_PANEL_BG = "#131a24"      # card / dialog background
#THEME_FIELD_BG = "#1b232f"      # entry/combobox/scale trough background
#THEME_BORDER = "#3a4756"        # chrome-ish panel border
#THEME_CHROME = "#aeb8c4"        # chrome/silver accent (rings, dividers)
#THEME_TEXT = "#e8edf3"          # primary text
#THEME_TEXT_DIM = "#7c8797"      # secondary/dim text
#THEME_BLUE = "#1f6fe5"          # primary accent (start / nav tabs)
#THEME_BLUE_DARK = "#123a78"
#THEME_RED = "#e0311e"           # stop / danger accent
#THEME_RED_DARK = "#7a1810"
#THEME_STATUS_OK = "#3ecf7e"
#THEME_STATUS_WARN = "#e0311e"


def _lighten(hex_color: str, factor: float) -> str:
    """Blend a hex color toward white by `factor` (0..1)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color: str, factor: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r, g, b = int(r * (1 - factor)), int(g * (1 - factor)), int(b * (1 - factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rounded_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def apply_dark_theme(root: tk.Tk):
    """Configure a dark chrome/blue ttk theme, applied once and shared by
    every ttk widget in the app (main window and every Toplevel dialog)."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=THEME_PANEL_BG, foreground=THEME_TEXT,
                     fieldbackground=THEME_FIELD_BG, bordercolor=THEME_BORDER,
                     lightcolor=THEME_BORDER, darkcolor=THEME_BORDER)
    style.configure("TFrame", background=THEME_PANEL_BG)
    style.configure("TLabel", background=THEME_PANEL_BG, foreground=THEME_TEXT)
    style.configure("TCheckbutton", background=THEME_PANEL_BG, foreground=THEME_TEXT)
    style.map("TCheckbutton", background=[("active", THEME_PANEL_BG)])
    style.configure("TButton", background=THEME_BLUE_DARK, foreground=THEME_TEXT,
                     borderwidth=1, focusthickness=0, padding=4)
    style.map("TButton",
              background=[("active", THEME_BLUE), ("disabled", "#22293380")],
              foreground=[("disabled", THEME_TEXT_DIM)])
    style.configure("TEntry", fieldbackground=THEME_FIELD_BG, foreground=THEME_TEXT,
                     insertcolor=THEME_TEXT)
    style.configure("TSpinbox", fieldbackground=THEME_FIELD_BG, foreground=THEME_TEXT,
                     arrowcolor=THEME_TEXT)
    style.configure("TCombobox", fieldbackground=THEME_FIELD_BG, foreground=THEME_TEXT,
                     background=THEME_FIELD_BG, arrowcolor=THEME_TEXT)
    style.map("TCombobox", fieldbackground=[("readonly", THEME_FIELD_BG)])
    style.configure("Horizontal.TScale", background=THEME_PANEL_BG, troughcolor=THEME_FIELD_BG)
    style.configure("TNotebook", background=THEME_PANEL_BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=THEME_BLUE_DARK, foreground=THEME_TEXT,
                     padding=(12, 5), borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", THEME_BLUE)])
    style.configure("TSeparator", background=THEME_BORDER)

    # ttk.Combobox's dropdown list is a plain Tk listbox under the hood.
    root.option_add("*TCombobox*Listbox.background", THEME_FIELD_BG)
    root.option_add("*TCombobox*Listbox.foreground", THEME_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", THEME_BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", THEME_TEXT)


class PillButton(tk.Canvas):
    """A glossy, chrome-bordered pill-shaped button (Tkinter has no native
    rounded-button widget, so this draws one on a Canvas)."""

    def __init__(self, parent, text, command=None, width=140, height=42,
                 base_color=THEME_BLUE, text_color=THEME_TEXT,
                 font=("Segoe UI", 11, "bold"), icon_ring=False, bg=None):
        # ``tk.Canvas`` uses ``_w`` internally for its Tcl widget name.  Keep
        # our requested drawing dimensions in separate attributes; otherwise
        # Tkinter overwrites ``_w`` with a string during ``super().__init__``.
        self._button_width, self._button_height = width, height
        bg = bg or (parent.cget("bg") if "bg" in parent.keys() else THEME_BG)
        super().__init__(parent, width=width, height=height, bg=bg,
                          highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.text = text
        self.base_color = base_color
        self.text_color = text_color
        self.font = font
        self.icon_ring = icon_ring
        self._hovering = False
        self._render()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._on_click)

    def _set_hover(self, val):
        self._hovering = val
        self._render()

    def _on_click(self, _event):
        if self.command:
            self.command()

    def set_appearance(self, text=None, base_color=None):
        if text is not None:
            self.text = text
        if base_color is not None:
            self.base_color = base_color
        self._render()

    def _render(self):
        self.delete("all")
        w, h = self._button_width, self._button_height
        r = h // 2
        color = _lighten(self.base_color, 0.12) if self._hovering else self.base_color
        pts = _rounded_points(2, 2, w - 2, h - 2, r)
        self.create_polygon(pts, smooth=True, fill=color, outline=THEME_CHROME, width=2)

        # glossy highlight band across the upper portion
        sheen = _lighten(color, 0.22)
        self.create_oval(max(6, r * 0.4), 3, w - max(6, r * 0.4), h * 0.55,
                          fill=sheen, outline="")

        if self.icon_ring:
            cx, cy, rr = r, h // 2, int(h * 0.28)
            self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=THEME_CHROME, width=2)
            self.create_oval(cx - rr * 0.4, cy - rr * 0.4, cx + rr * 0.4, cy + rr * 0.4,
                              fill=THEME_CHROME, outline="")
            self.create_text(r * 2 + 12, h // 2, text=self.text, fill=self.text_color,
                              font=self.font, anchor="w")
        else:
            self.create_text(w // 2, h // 2, text=self.text, fill=self.text_color, font=self.font)


class GradientBar(tk.Canvas):
    """A thin horizontal red\u2192blue gradient strip, used as a chrome
    accent under the app title."""

    def __init__(self, parent, width, height, color_start=THEME_RED, color_end=THEME_BLUE, bg=None):
        bg = bg or THEME_BG
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        r1, g1, b1 = int(color_start[1:3], 16), int(color_start[3:5], 16), int(color_start[5:7], 16)
        r2, g2, b2 = int(color_end[1:3], 16), int(color_end[3:5], 16), int(color_end[5:7], 16)
        steps = max(2, width)
        for i in range(steps):
            t = i / (steps - 1)
            r, g, b = int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t)
            self.create_line(i, 0, i, height, fill=f"#{r:02x}{g:02x}{b:02x}")


# ---------------------------------------------------------------------------
# Windows-only helpers (WoW process closing, unrelated to the UI theme)
# ---------------------------------------------------------------------------

def _settings_base_dir() -> str:
    """Directory to store fishing_bot_settings.json in. When frozen into a
    PyInstaller exe, sys.executable is the real exe location (not the
    temp extraction folder), so settings persist next to the exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_PATH = os.path.join(_settings_base_dir(), "fishing_bot_settings.json")

# Common WoW executable names across retail/Classic/PTR/beta clients.
WOW_PROCESS_NAMES = [
    "Wow.exe", "Wow-64.exe", "WowClassic.exe", "WowClassicT.exe",
    "WowClassicB.exe", "WowT.exe", "WowB.exe",
]


def close_wow_processes() -> bool:
    """Force-close any running WoW client via taskkill (Windows only).
    Returns True if at least one matching process was found and closed."""
    closed_any = False
    for name in WOW_PROCESS_NAMES:
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                closed_any = True
        except Exception:
            pass
    return closed_any


class SearchAreaOverlay(tk.Toplevel):
    """A high-contrast, draggable selection frame for the bobber scan area.

    Drag anywhere inside the frame to move it.  Every edge and corner has a
    generous resize hit area, so the selected region is easy to adjust even
    while it is displayed over a moving game window.
    """

    MIN_SIZE = 100
    EDGE_HIT = 18
    TRANSPARENT_KEY = "black"
    BORDER_COLOR = "#00e5ff"
    HANDLE_COLOR = "#ffb000"

    def __init__(self, master, on_confirm, initial_bounds=None):
        super().__init__(master)
        self.on_confirm = on_confirm

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # Transparent-colour windows let mouse clicks pass through their empty
        # areas on Windows. A translucent opaque window remains fully usable.
        self.attributes("-alpha", 0.58)
        self.lift()
        self.focus_force()
        self.grab_set()

        if initial_bounds:
            l, t, r, b = initial_bounds
            w, h = max(self.MIN_SIZE, r - l), max(self.MIN_SIZE, b - t)
        else:
            sw, sh = master.winfo_screenwidth(), master.winfo_screenheight()
            w, h = 400, 300
            l, t = (sw - w) // 2, (sh - h) // 2

        self.geometry(f"{w}x{h}+{l}+{t}")
        self.config(bg=self.TRANSPARENT_KEY)

        self.toolbar = tk.Frame(self, bg="#063b52", height=34,
                                highlightbackground=self.BORDER_COLOR,
                                highlightthickness=2)
        self.toolbar.pack(side="top", fill="x")
        tk.Label(
            self.toolbar,
            text="FISHING ZONE  \u2022  Drag inside to move  \u2022  Drag any edge or corner to resize",
            bg="#063b52", fg="white", font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=6)
        tk.Button(self.toolbar, text="Confirm", command=self._confirm,
                  bg="#00a9d6", fg="white", activebackground="#00e5ff",
                  activeforeground="black", relief="flat", padx=9).pack(
                      side="right", padx=(3, 5), pady=4
                  )
        tk.Button(self.toolbar, text="Cancel", command=self._cancel,
                  bg="#4a1f2a", fg="white", activebackground="#ff6b6b",
                  relief="flat", padx=9).pack(side="right", pady=4)

        self.toolbar.bind("<ButtonPress-1>", self._start_move)
        self.toolbar.bind("<B1-Motion>", self._do_move)

        self.canvas = tk.Canvas(self, bg=self.TRANSPARENT_KEY, highlightthickness=0,
                                cursor="fleur")
        self.canvas.pack(fill="both", expand=True)

        self.border_rect = self.canvas.create_rectangle(0, 0, 0, 0, outline=self.BORDER_COLOR, width=4)
        self.corner_marks = [self.canvas.create_line(0, 0, 0, 0, fill=self.HANDLE_COLOR, width=5)
                             for _ in range(8)]
        self.canvas.bind("<ButtonPress-1>", self._canvas_press)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Motion>", self._update_cursor)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.bind("<Escape>", lambda _event: self._cancel())

        self._drag_start = None
        self._resize_start = None

    def _start_move(self, event):
        self._drag_start = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def _do_move(self, event):
        if not self._drag_start:
            return
        start_ex, start_ey, start_x, start_y = self._drag_start
        dx = event.x_root - start_ex
        dy = event.y_root - start_ey
        self.geometry(f"+{start_x + dx}+{start_y + dy}")

    def _canvas_press(self, event):
        edges = self._edges_at(event.x, event.y)
        if edges:
            self._resize_start = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y(),
                                  self.winfo_width(), self.winfo_height(), edges)
        else:
            self._start_move(event)

    def _canvas_drag(self, event):
        if self._resize_start:
            start_ex, start_ey, start_x, start_y, start_w, start_h, edges = self._resize_start
            dx, dy = event.x_root - start_ex, event.y_root - start_ey
            new_x, new_y, new_w, new_h = start_x, start_y, start_w, start_h
            if "left" in edges:
                new_w = max(self.MIN_SIZE, start_w - dx)
                new_x = start_x + start_w - new_w
            elif "right" in edges:
                new_w = max(self.MIN_SIZE, start_w + dx)
            if "top" in edges:
                new_h = max(self.MIN_SIZE, start_h - dy)
                new_y = start_y + start_h - new_h
            elif "bottom" in edges:
                new_h = max(self.MIN_SIZE, start_h + dy)
            self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
        else:
            self._do_move(event)

    def _end_drag(self, _event):
        self._drag_start = None
        self._resize_start = None

    def _edges_at(self, x, y):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        edges = []
        if x <= self.EDGE_HIT:
            edges.append("left")
        elif x >= w - self.EDGE_HIT:
            edges.append("right")
        if y <= self.EDGE_HIT:
            edges.append("top")
        elif y >= h - self.EDGE_HIT:
            edges.append("bottom")
        return tuple(edges)

    def _update_cursor(self, event):
        edges = set(self._edges_at(event.x, event.y))
        if edges == {"left", "top"} or edges == {"right", "bottom"}:
            cursor = "size_nw_se"
        elif edges == {"right", "top"} or edges == {"left", "bottom"}:
            cursor = "size_ne_sw"
        elif "left" in edges or "right" in edges:
            cursor = "sb_h_double_arrow"
        elif "top" in edges or "bottom" in edges:
            cursor = "sb_v_double_arrow"
        else:
            cursor = "fleur"
        self.canvas.configure(cursor=cursor)

    def _on_canvas_resize(self, event):
        w, h = event.width, event.height
        inset, mark = 3, 26
        self.canvas.coords(self.border_rect, inset, inset, w - inset, h - inset)
        lines = (
            (inset, mark, inset, inset, mark, inset), (w - mark, inset, w - inset, inset, w - inset, mark),
            (inset, h - mark, inset, h - inset, mark, h - inset), (w - mark, h - inset, w - inset, h - inset, w - inset, h - mark),
            (w // 2 - 10, inset, w // 2 + 10, inset), (w // 2 - 10, h - inset, w // 2 + 10, h - inset),
            (inset, h // 2 - 10, inset, h // 2 + 10), (w - inset, h // 2 - 10, w - inset, h // 2 + 10),
        )
        for item, coords in zip(self.corner_marks, lines):
            self.canvas.coords(item, *coords)

    def _confirm(self):
        x, y = self.winfo_x(), self.winfo_y()
        w, h = self.winfo_width(), self.winfo_height()
        bounds = (x, y + self.toolbar.winfo_height(), x + w, y + h)
        self.grab_release()
        self.destroy()
        self.on_confirm(bounds)

    def _cancel(self):
        self.grab_release()
        self.destroy()


class _ThemedDialog(tk.Toplevel):
    """Common setup shared by every bottom-tab popup dialog: dark chrome
    background, centered-ish placement, non-resizable by default."""

    def __init__(self, master, app: "FishingBotApp", title: str):
        super().__init__(master)
        self.app = app
        self.title(title)
        self.configure(bg=THEME_PANEL_BG)
        self.transient(master)
        self.resizable(False, False)


class DonationDialog(tk.Toplevel):
    """Shown once per launch, after the main window is up. Pay-what-you-want
    Stripe Payment Link -- same one used on Luna's own donate button, a
    public checkout page with no secret key involved, safe to hardcode."""

    DONATE_URL = "https://buy.stripe.com/00w14ncFi1Hz7v8gpd7Re00"

    def __init__(self, parent):
        super().__init__(parent)
        self.configure(bg=THEME_BG)
        self.title("Support I-Fish")
        self.geometry("380x210")
        self.resizable(False, False)
        self.transient(parent)

        # grab_set() before the window is actually mapped can lose the
        # race with the parent window finishing its own layout, which
        # pushes this behind it right after it draws -- looks exactly
        # like "flashes then disappears" even though it's still open.
        # Force it to the front and wait for it to be real before grabbing.
        self.lift()
        self.focus_force()
        self.wait_visibility()
        self.grab_set()

        tk.Label(
            self, text="ENJOYING I-FISH?", bg=THEME_BG, fg=THEME_TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(pady=(20, 6))

        tk.Label(
            self,
            text="This tool is free to use. If it's saving you time,\n"
                 "consider chipping in whatever it's worth to you.",
            bg=THEME_BG, fg=THEME_TEXT_DIM, font=("Segoe UI", 10),
            justify="center",
        ).pack(pady=(0, 16))

        tk.Button(
            self, text="DONATE", command=self._donate,
            bg=THEME_BLUE, fg="white", activebackground=THEME_BLUE,
            activeforeground="white", relief="flat",
            font=("Segoe UI", 10, "bold"), width=18,
        ).pack(pady=4)

        tk.Button(
            self, text="Maybe later", command=self.destroy,
            bg=THEME_BG, fg=THEME_TEXT_DIM, activebackground=THEME_BG,
            activeforeground=THEME_TEXT, relief="flat",
            font=("Segoe UI", 9), bd=0,
        ).pack(pady=(6, 10))

    def _donate(self):
        webbrowser.open(self.DONATE_URL)
        self.destroy()


class KeybindingsDialog(_ThemedDialog):
    """Fishing key / Buff key / global Stop-Start hotkey."""

    def __init__(self, master, app: "FishingBotApp"):
        super().__init__(master, app, "Keybindings")
        self.geometry("360x260")
        self.grab_set()

        pad = dict(padx=14, pady=6)

        def kb_row(label, var):
            row = tk.Frame(self, bg=THEME_PANEL_BG)
            row.pack(fill="x", **pad)
            tk.Label(row, text=label, width=16, anchor="w", bg=THEME_PANEL_BG,
                     fg=THEME_TEXT).pack(side="left")
            ttk.Entry(row, textvariable=var, width=14).pack(side="left")

        tk.Label(self, text="Keybindings", bg=THEME_PANEL_BG, fg=THEME_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))

        kb_row("Fishing Key:", app.fish_key_var)
        kb_row("Buff Key:", app.buff_key_var)

        stop_row = tk.Frame(self, bg=THEME_PANEL_BG)
        stop_row.pack(fill="x", **pad)
        tk.Label(stop_row, text="Stop/Start Key:", width=16, anchor="w",
                 bg=THEME_PANEL_BG, fg=THEME_TEXT).pack(side="left")
        ttk.Entry(stop_row, textvariable=app.stop_hotkey_var, width=10).pack(side="left")
        ttk.Button(stop_row, text="Set", command=app.apply_stop_key, width=5).pack(
            side="left", padx=(4, 2)
        )
        ttk.Button(stop_row, text="Delete", command=app.clear_stop_key, width=6).pack(side="left")

        tk.Label(self, textvariable=app.hotkey_status_var, fg=THEME_STATUS_OK,
                 bg=THEME_PANEL_BG, font=("Segoe UI", 8), wraplength=320,
                 justify="left").pack(anchor="w", padx=14, pady=(4, 4))

        if not HAS_KEYBOARD:
            tk.Label(
                self,
                text="Install the 'keyboard' package for global hotkeys "
                     "(pip install keyboard).",
                fg=THEME_TEXT_DIM, bg=THEME_PANEL_BG, font=("Segoe UI", 8),
                wraplength=320, justify="left",
            ).pack(anchor="w", padx=14, pady=(0, 8))

        ttk.Button(self, text="Close", command=self.destroy).pack(
            anchor="e", padx=14, pady=(10, 14)
        )


class FishingZoneDialog(_ThemedDialog):
    """Frame the on-screen region the bot scans for the bobber."""

    def __init__(self, master, app: "FishingBotApp"):
        super().__init__(master, app, "Fishing Zone")
        self.geometry("360x200")

        tk.Label(self, text="Fishing Zone", bg=THEME_PANEL_BG, fg=THEME_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))

        tk.Label(
            self,
            text="Frame just the patch of water where your bobber lands. "
                 "This speeds up scanning and cuts down false matches.",
            fg=THEME_TEXT_DIM, bg=THEME_PANEL_BG, font=("Segoe UI", 8),
            wraplength=320, justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        btn_row = tk.Frame(self, bg=THEME_PANEL_BG)
        btn_row.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Button(btn_row, text="Set Search Area...", command=app.open_search_area_overlay).pack(side="left")
        ttk.Button(btn_row, text="Use Full Screen", command=self._use_full_screen).pack(
            side="left", padx=(6, 0)
        )

        tk.Label(self, textvariable=app.search_area_label_var, fg=THEME_TEXT_DIM,
                 bg=THEME_PANEL_BG, font=("Segoe UI", 8), wraplength=320,
                 justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        ttk.Button(self, text="Close", command=self.destroy).pack(
            anchor="e", padx=14, pady=(10, 14)
        )

    def _use_full_screen(self):
        self.app.search_region = None
        self.app.search_area_label_var.set("Full screen")
        self.app._save_settings()


class BobberDetectionDialog(_ThemedDialog):
    """Pick the bobber color, tune tolerance/sensitivity, and enable
    shade-tolerant (HSV hue) matching. Owns the whole color-pick /
    test-match flow (previously lived on the main window)."""

    def __init__(self, master, app: "FishingBotApp"):
        super().__init__(master, app, "Bobber Detection")
        self.geometry("400x420")

        tk.Label(self, text="Bobber Detection", bg=THEME_PANEL_BG, fg=THEME_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))

        pick_row = tk.Frame(self, bg=THEME_PANEL_BG)
        pick_row.pack(fill="x", padx=14, pady=(4, 4))
        self.pick_btn = ttk.Button(pick_row, text="Pick Color...", command=self.start_color_pick)
        self.pick_btn.pack(side="left")
        self.test_btn = ttk.Button(pick_row, text="Test Match", command=self.test_color_match)
        self.test_btn.pack(side="left", padx=(6, 0))

        self.color_swatch = tk.Canvas(pick_row, width=26, height=18, bg="#888888",
                                       highlightthickness=1, highlightbackground=THEME_CHROME)
        self.color_swatch.pack(side="left", padx=(10, 6))

        color_label_text = "No color picked"
        if app.picked_color:
            r, g, b = app.picked_color
            self.color_swatch.config(bg=f"#{r:02x}{g:02x}{b:02x}")
            color_label_text = f"RGB({r}, {g}, {b})"
        self.color_label_var = tk.StringVar(value=color_label_text)
        tk.Label(pick_row, textvariable=self.color_label_var, bg=THEME_PANEL_BG,
                 fg=THEME_TEXT, font=("Segoe UI", 8)).pack(side="left")

        app._slider_row(self, "Tolerance:", app.tolerance_var, 1, 150)
        app._slider_row(self, "Sensitivity (min px):", app.min_pixels_var, 1, 200)

        shades_row = tk.Frame(self, bg=THEME_PANEL_BG)
        shades_row.pack(fill="x", padx=14, pady=(6, 0))
        ttk.Checkbutton(
            shades_row, text="Match all shades of this color (lighting/shadow tolerant)",
            variable=app.match_shades_var, command=self._on_toggle_match_shades,
        ).pack(anchor="w")

        self.hue_slider_row = app._slider_row(self, "Hue tolerance (\u00b0):", app.hue_tolerance_var, 1, 60)
        self._set_hue_slider_enabled(app.match_shades_var.get())

        tk.Label(
            self,
            text=(
                "When enabled, tolerance/sensitivity above still control the RGB match; "
                "hue tolerance instead matches any brightness/shade of the same color "
                "(e.g. bobber in shadow vs. in sun) by comparing hue only."
            ),
            fg=THEME_TEXT_DIM, bg=THEME_PANEL_BG, font=("Segoe UI", 7),
            wraplength=370, justify="left",
        ).pack(anchor="w", padx=14, pady=(4, 4))

        self.pick_status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.pick_status_var, fg=THEME_STATUS_OK,
                 bg=THEME_PANEL_BG, font=("Segoe UI", 8), wraplength=370,
                 justify="left").pack(anchor="w", padx=14, pady=(2, 8))

        ttk.Button(self, text="Close", command=self.destroy).pack(
            anchor="e", padx=14, pady=(4, 14)
        )

    def _on_toggle_match_shades(self):
        self._set_hue_slider_enabled(self.app.match_shades_var.get())
        self.app._save_settings()

    def _set_hue_slider_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try:
            self.hue_slider_row.scale_widget.config(state=state)
        except Exception:
            pass

    # ---- color picking (dialog-owned) ----

    def start_color_pick(self):
        self.pick_btn.config(state="disabled")
        self._color_pick_countdown(3)

    def _color_pick_countdown(self, seconds_left: int):
        if not self.winfo_exists():
            return
        if seconds_left > 0:
            self.pick_status_var.set(f"Hover over the bobber... sampling in {seconds_left}")
            self.after(1000, lambda: self._color_pick_countdown(seconds_left - 1))
        else:
            self._sample_color_at_cursor()

    def _sample_color_at_cursor(self):
        try:
            x, y = pyautogui.position()
            r, g, b = pyautogui.pixel(x, y)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not sample color:\n{e}")
            self.pick_btn.config(state="normal")
            self.pick_status_var.set("")
            return

        self.app.picked_color = (r, g, b)
        self.color_swatch.config(bg=f"#{r:02x}{g:02x}{b:02x}")
        self.color_label_var.set(f"RGB({r}, {g}, {b})")
        self.pick_status_var.set("Color captured.")
        self.pick_btn.config(state="normal")
        self.app._save_settings()

    def test_color_match(self):
        app = self.app
        if app.picked_color is None:
            messagebox.showerror(APP_TITLE, "Pick a color first.")
            return

        self.pick_status_var.set("Scanning screen...")
        self.update_idletasks()

        try:
            result = scan_for_color(
                app.picked_color,
                int(app.tolerance_var.get()),
                int(app.min_pixels_var.get()),
                app.search_region,
                match_shades=app.match_shades_var.get(),
                hue_tolerance=int(app.hue_tolerance_var.get()),
            )
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Scan failed:\n{e}")
            self.pick_status_var.set("")
            return

        if result is None:
            self.pick_status_var.set(
                "No match found \u2014 try raising tolerance, re-picking the color, "
                "or check your Fishing Zone covers the bobber."
            )
            return

        x, y, count = result
        pyautogui.moveTo(x, y)
        self.pick_status_var.set(f"Match found at ({x}, {y}) \u2014 {count} pixels.")


class AdvancedSettingsDialog(_ThemedDialog):
    """Keybindings / General / About tabs."""

    def __init__(self, master, app: "FishingBotApp"):
        super().__init__(master, app, "Advanced Settings")
        self.geometry("440x560")

        self._snapshot = {
            "warmup": app.warmup_var.get(),
            "timeout": app.timeout_var.get(),
            "hover": app.tune_px_var.get(),
            "dip": app.dip_threshold_var.get(),
            "margin": app.tracking_margin_var.get(),
            "human_like": app.human_like_var.get(),
            "buff_enabled": app.buff_enabled_var.get(),
            "buff_tolerance": app.buff_tolerance_var.get(),
            "buff_min_pixels": app.buff_min_pixels_var.get(),
            "buff_key": app.buff_key_var.get(),
            "bite_click_delay": app.bite_click_delay_var.get(),
            "recast_delay": app.recast_delay_var.get(),
            "fishing_pole": app.fishing_pole_var.get(),
            "lure_item": app.lure_item_var.get(),
        }

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        keybindings_tab = ttk.Frame(notebook)
        notebook.add(keybindings_tab, text="Keybindings")
        self._build_keybindings_tab(keybindings_tab)

        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text="General")
        self._build_general_tab(general_tab)

        about_tab = ttk.Frame(notebook)
        notebook.add(about_tab, text="About")
        self._build_about_tab(about_tab)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btn_row, text="Defaults", command=self._restore_defaults).pack(side="left")
        ttk.Button(btn_row, text="Cancel", command=self._cancel).pack(side="right", padx=(4, 0))
        ttk.Button(btn_row, text="Ok", command=self._ok).pack(side="right")

    def _ok(self):
        self.app._save_settings()
        self.destroy()

    def _add_entry(self, parent, label, var):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=4)
        ttk.Label(row, text=label, width=24).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)

    def _build_keybindings_tab(self, parent):
        app = self.app
        ttk.Label(parent, text="Configure the keys used by I-Fish.").pack(
            anchor="w", padx=12, pady=(14, 8)
        )

        def key_row(label, var, width=14):
            row = ttk.Frame(parent)
            row.pack(fill="x", padx=12, pady=5)
            ttk.Label(row, text=label, width=17).pack(side="left")
            ttk.Entry(row, textvariable=var, width=width).pack(side="left", fill="x", expand=True)

        key_row("Fishing key:", app.fish_key_var)
        key_row("Lure key:", app.buff_key_var)

        stop_row = ttk.Frame(parent)
        stop_row.pack(fill="x", padx=12, pady=5)
        ttk.Label(stop_row, text="Stop/Start key:", width=17).pack(side="left")
        ttk.Entry(stop_row, textvariable=app.stop_hotkey_var, width=10).pack(side="left")
        ttk.Button(stop_row, text="Set", command=app.apply_stop_key, width=5).pack(side="left", padx=(5, 2))
        ttk.Button(stop_row, text="Delete", command=app.clear_stop_key, width=6).pack(side="left")

        ttk.Label(parent, textvariable=app.hotkey_status_var, foreground=THEME_STATUS_OK,
                  wraplength=390, justify="left").pack(anchor="w", padx=12, pady=(6, 4))

    def _build_general_tab(self, parent):
        app = self.app
        self._add_entry(parent, "Warm-up delay (s):", app.warmup_var)
        self._add_entry(parent, "Bite timeout (s):", app.timeout_var)
        self._add_entry(parent, "Hover offset (px):", app.tune_px_var)
        self._add_entry(parent, "Bite dip threshold (px):", app.dip_threshold_var)
        self._add_entry(parent, "Tracking margin (px):", app.tracking_margin_var)

        app._float_slider_row(
            parent, "Bounce\u2192click delay:", app.bite_click_delay_var, 0.0, 2.0, resolution=0.05
        )
        app._float_slider_row(
            parent, "Recast delay (not found):", app.recast_delay_var, 0.0, 15.0, resolution=0.5
        )
        ttk.Label(
            parent,
            text=(
                "Bounce\u2192click delay pauses briefly after a bite is detected before "
                "right-clicking to loot. Recast delay is extra time to wait before "
                "casting again after the bobber wasn't found or nothing bit."
            ),
            foreground=THEME_TEXT_DIM, wraplength=380, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        ttk.Checkbutton(
            parent, text="Human-like randomized timing (delays + occasional space tap)",
            variable=app.human_like_var,
        ).pack(anchor="w", padx=10, pady=(12, 4))
        ttk.Label(
            parent,
            text="When off, the bot uses fixed short delays instead of randomized ones.",
            foreground=THEME_TEXT_DIM, wraplength=380, justify="left",
        ).pack(anchor="w", padx=10)
        ttk.Label(
            parent,
            text=(
                "Hover offset shifts the click point relative to the tracked color \u2014 "
                "start at 0 if you picked the color directly on the bobber. Dip threshold "
                "is how far (in pixels) the bobber must visibly bounce down to count as a bite."
            ),
            foreground=THEME_TEXT_DIM, wraplength=380, justify="left",
        ).pack(anchor="w", padx=10, pady=(10, 0))

    def _build_buff_tab(self, parent):
        app = self.app
        ttk.Checkbutton(
            parent, text="Check for bobber/lure buff before each cast",
            variable=app.buff_enabled_var,
        ).pack(anchor="w", padx=10, pady=(10, 6))

        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(row, text="Capture Pole Buff...", command=app.start_buff_pick).pack(side="left")
        ttk.Button(row, text="Test Buff Check", command=app.test_buff_check).pack(side="left", padx=(6, 0))

        swatch = tk.Canvas(row, width=24, height=18, bg="#888888",
                            highlightthickness=1, highlightbackground=THEME_CHROME)
        swatch.pack(side="left", padx=(10, 6))
        app.buff_swatch = swatch
        if app.buff_color:
            r, g, b = app.buff_color
            swatch.config(bg=f"#{r:02x}{g:02x}{b:02x}")
        ttk.Label(row, textvariable=app.buff_color_label_var).pack(side="left")

        ttk.Label(parent, textvariable=app.buff_status_var, foreground=THEME_STATUS_OK).pack(
            anchor="w", padx=10, pady=(0, 6)
        )

        tune_row = ttk.Frame(parent)
        tune_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(tune_row, text="Tolerance:").pack(side="left")
        ttk.Spinbox(tune_row, from_=1, to=150, textvariable=app.buff_tolerance_var, width=6).pack(
            side="left", padx=(4, 16)
        )
        ttk.Label(tune_row, text="Min pixels:").pack(side="left")
        ttk.Spinbox(tune_row, from_=1, to=5000, textvariable=app.buff_min_pixels_var, width=6).pack(
            side="left", padx=(4, 0)
        )

        key_row = ttk.Frame(parent)
        key_row.pack(fill="x", padx=10, pady=(4, 4))
        ttk.Label(key_row, text="Buff key:", width=22).pack(side="left")
        ttk.Entry(key_row, textvariable=app.buff_key_var).pack(side="left", fill="x", expand=True)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=(8, 8))

        ttk.Label(
            parent, text="Apply lure to the equipped main-hand fishing pole",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=10)

        lure_row = ttk.Frame(parent)
        lure_row.pack(fill="x", padx=10, pady=(6, 6))
        ttk.Label(lure_row, text="Lure/buff item name:", width=22).pack(side="left")
        lure_combo = ttk.Combobox(
            lure_row, textvariable=app.lure_item_var, values=KNOWN_FISHING_LURES, width=28
        )
        lure_combo.pack(side="left", fill="x", expand=True)
        lure_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_macro_preview())
        lure_combo.bind("<KeyRelease>", lambda e: self._refresh_macro_preview())

        macro_label_row = ttk.Frame(parent)
        macro_label_row.pack(fill="x", padx=10, pady=(4, 0))
        ttk.Label(macro_label_row, text="Suggested macro (3 lines):").pack(anchor="w")

        self.macro_preview_text = tk.Text(
            parent, height=3, width=40, font=("Consolas", 9), wrap="none",
            bg=THEME_FIELD_BG, fg=THEME_TEXT, insertbackground=THEME_TEXT,
            relief="solid", borderwidth=1, highlightbackground=THEME_BORDER,
        )
        self.macro_preview_text.pack(fill="x", padx=10, pady=(2, 2))
        self.macro_preview_text.config(state="disabled")

        ttk.Button(parent, text="Copy Macro", command=self._copy_macro).pack(
            anchor="e", padx=10, pady=(2, 4)
        )

        ttk.Label(
            parent,
            text=(
                "Create a new macro in WoW and paste all three lines in, then bind it to "
                "the Buff key above. The first line only sets the icon. Line 2 selects "
                "the lure; line 3 (\"/use 16\") immediately applies it to your main-hand "
                "slot, where your fishing pole must be equipped, so no click is needed. "
                "The bot itself just presses the Buff "
                "key \u2014 it can't create or edit macros inside the game."
            ),
            foreground=THEME_TEXT_DIM, wraplength=390, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        self._refresh_macro_preview()

    def _refresh_macro_preview(self):
        app = self.app
        macro_text = build_lure_macro(app.fishing_pole_var.get(), app.lure_item_var.get())
        app.macro_preview_var.set(macro_text)
        self.macro_preview_text.config(state="normal")
        self.macro_preview_text.delete("1.0", "end")
        self.macro_preview_text.insert("1.0", macro_text)
        self.macro_preview_text.config(state="disabled")

    def _copy_macro(self):
        self.clipboard_clear()
        self.clipboard_append(self.app.macro_preview_var.get())

    def _build_about_tab(self, parent):
        text = (
            "Automating fishing violates World of Warcraft's Terms of "
            "Service and can result in an account ban. Use at your own risk.\n\n"
            "Brought to you by Freeelf."
        )
        ttk.Label(parent, text=text, wraplength=390, justify="left").pack(padx=10, pady=10, anchor="w")

    def _restore_defaults(self):
        app = self.app
        app.warmup_var.set(2.0)
        app.timeout_var.set(30.0)
        app.tune_px_var.set(0)
        app.dip_threshold_var.set(6)
        app.tracking_margin_var.set(45)
        app.human_like_var.set(True)
        app.buff_enabled_var.set(False)
        app.buff_tolerance_var.set(30)
        app.buff_min_pixels_var.set(5)
        app.buff_key_var.set("")
        app.bite_click_delay_var.set(0.0)
        app.recast_delay_var.set(1.0)
        app.fishing_pole_var.set("")
        app.lure_item_var.set("")
        self._refresh_macro_preview()

    def _cancel(self):
        app = self.app
        s = self._snapshot
        app.warmup_var.set(s["warmup"])
        app.timeout_var.set(s["timeout"])
        app.tune_px_var.set(s["hover"])
        app.dip_threshold_var.set(s["dip"])
        app.tracking_margin_var.set(s["margin"])
        app.human_like_var.set(s["human_like"])
        app.buff_enabled_var.set(s["buff_enabled"])
        app.buff_tolerance_var.set(s["buff_tolerance"])
        app.buff_min_pixels_var.set(s["buff_min_pixels"])
        app.buff_key_var.set(s["buff_key"])
        app.bite_click_delay_var.set(s["bite_click_delay"])
        app.recast_delay_var.set(s["recast_delay"])
        app.fishing_pole_var.set(s["fishing_pole"])
        app.lure_item_var.set(s["lure_item"])
        self.destroy()


class LuresDialog(_ThemedDialog):
    """Standalone lure/buff configuration window."""

    # Reuse the established lure controls while keeping Lures independent
    # from the Advanced Settings notebook.
    _build_lures_content = AdvancedSettingsDialog._build_buff_tab
    _refresh_macro_preview = AdvancedSettingsDialog._refresh_macro_preview
    _copy_macro = AdvancedSettingsDialog._copy_macro

    def __init__(self, master, app: "FishingBotApp"):
        super().__init__(master, app, "Lures")
        self.geometry("440x560")
        self._build_lures_content(self)
        ttk.Button(self, text="Close", command=self.destroy).pack(
            anchor="e", padx=10, pady=(2, 10)
        )


class FishingBotApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=THEME_BG)
        self.geometry("420x900")
        self.resizable(False, True)

        apply_dark_theme(self)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self.bot: FishingBot | None = None
        self.picked_color: tuple[int, int, int] | None = None
        self.search_region: tuple[int, int, int, int] | None = None
        self.buff_color: tuple[int, int, int] | None = None
        self.buff_region: tuple[int, int, int, int] | None = None
        self._registered_hotkey: str | None = None
        self._timer_after_id: str | None = None
        self._timer_end_time: float | None = None
        self._open_dialogs: dict[str, tk.Toplevel] = {}

        self._build_widgets()
        self._load_settings()

        self.update_idletasks()
        self.geometry(f"420x{self.winfo_reqheight()}")

        self._poll_log_queue()

        if HAS_KEYBOARD:
            self.apply_stop_key()

    
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Shown once per launch, after the main window exists so it has
        # something to be a child of. Dismissible either way -- this is
        # an ask, not the old activation gate.
        self.after(300, lambda: DonationDialog(self))

    # ---------- UI construction ----------

    def _panel(self, title=None):
        outer = tk.Frame(self, highlightbackground=THEME_BORDER, highlightthickness=1,
                          bg=THEME_PANEL_BG)
        outer.pack(fill="x", padx=14, pady=6)
        if title:
            tk.Label(outer, text=title, font=("Segoe UI", 9, "bold"), bg=THEME_PANEL_BG,
                     fg=THEME_CHROME, anchor="w").pack(fill="x", padx=8, pady=(6, 0))
        return outer

    def _build_widgets(self):
        # ---- Header: centered "I-FISH" title + red\u2192blue chrome bar ----
        header = tk.Frame(self, bg=THEME_BG)
        header.pack(fill="x", padx=14, pady=(16, 4))
        tk.Label(header, text="I-FISH", font=("Segoe UI", 26, "bold"),
                 bg=THEME_BG, fg=THEME_TEXT, anchor="center").pack(fill="x")
        GradientBar(header, width=392, height=4).pack(pady=(4, 0))

        # ---- Start/Stop (glossy pill button) ----
        self.toggle_btn = PillButton(
            self, text="START", command=self._toggle_bot, width=392, height=56,
            base_color=THEME_BLUE, font=("Segoe UI", 15, "bold"), icon_ring=True,
        )
        self.toggle_btn.pack(padx=14, pady=(10, 8))

        # ---- Cast/Catch stats ----
        stats = self._panel("Cast / Catch")
        self.stats_label = tk.Label(stats, text="Casts: 0    Catches: 0    Buffs applied: 0",
                                     bg=THEME_PANEL_BG, fg=THEME_TEXT, font=("Segoe UI", 9))
        self.stats_label.pack(anchor="w", padx=8, pady=8)

        # ---- Auto-Stop Timer ----
        timer_card = self._panel("Auto-Stop Timer")

        self.timer_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            timer_card, text="Stop the bot automatically after a set time",
            variable=self.timer_enabled_var, command=self._on_toggle_timer_enabled,
        ).pack(anchor="w", padx=8, pady=(6, 0))

        self.timer_minutes_var = tk.IntVar(value=30)
        self.timer_slider_row = self._slider_row(timer_card, "Minutes:", self.timer_minutes_var, 1, 240)
        self._set_timer_slider_enabled(False)

        self.close_wow_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            timer_card, text="Also close WoW when the timer ends",
            variable=self.close_wow_var,
        ).pack(anchor="w", padx=8, pady=(2, 4))

        self.timer_status_var = tk.StringVar(value="Timer not running")
        tk.Label(timer_card, textvariable=self.timer_status_var, fg=THEME_TEXT_DIM,
                 bg=THEME_PANEL_BG, font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(0, 8))

        # ---- Bottom tab bar: Fishing Zone / Lures / Bobber Detection / Advanced Settings ----
        tab_bar = tk.Frame(self, bg=THEME_BG)
        tab_bar.pack(side="bottom", fill="x", padx=14, pady=(6, 14))

        tabs = [
            ("Fishing Zone", self.open_fishing_zone_dialog),
            ("Lures", self.open_lures_dialog),
            ("Bobber\nDetection", self.open_bobber_detection_dialog),
            ("Advanced\nSettings", self.open_advanced_settings),
        ]
        for i, (label, cmd) in enumerate(tabs):
            btn = PillButton(
                tab_bar, text=label, command=cmd, width=90, height=48,
                base_color=THEME_BLUE_DARK, font=("Segoe UI", 8, "bold"),
            )
            btn.grid(row=0, column=i, padx=3, sticky="ew")
            tab_bar.grid_columnconfigure(i, weight=1)

        disclaimer = (
            "Automating fishing violates World of Warcraft's Terms of Service "
            "and can get your account banned. Use at your own risk."
        )
        tk.Label(self, text=disclaimer, fg=THEME_RED, bg=THEME_BG, wraplength=390,
                 justify="left", font=("Segoe UI", 8)).pack(
            side="bottom", fill="x", padx=14, pady=(0, 4)
        )

    def _slider_row(self, parent, label, var, frm, to):
        row = tk.Frame(parent, bg=THEME_PANEL_BG)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, width=18, anchor="w", bg=THEME_PANEL_BG,
                 fg=THEME_TEXT, font=("Segoe UI", 8)).pack(side="left")
        value_label = tk.Label(row, text=str(var.get()), width=4, bg=THEME_PANEL_BG,
                                fg=THEME_TEXT, font=("Segoe UI", 8))
        value_label.pack(side="right")

        def _on_change(v):
            var.set(int(float(v)))
            value_label.config(text=str(var.get()))

        scale = ttk.Scale(row, from_=frm, to=to, orient="horizontal", command=_on_change)
        scale.set(var.get())
        scale.pack(side="left", fill="x", expand=True, padx=(6, 6))
        row.scale_widget = scale
        return row

    def _float_slider_row(self, parent, label, var, frm, to, resolution=0.05):
        """Like _slider_row but for a DoubleVar, showing seconds to 2 decimals."""
        row = tk.Frame(parent, bg=THEME_PANEL_BG)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, width=26, anchor="w", bg=THEME_PANEL_BG,
                 fg=THEME_TEXT, font=("Segoe UI", 8)).pack(side="left")
        value_label = tk.Label(row, text=f"{var.get():.2f}s", width=6, bg=THEME_PANEL_BG,
                                fg=THEME_TEXT, font=("Segoe UI", 8))
        value_label.pack(side="right")

        def _on_change(v):
            snapped = round(float(v) / resolution) * resolution
            var.set(round(snapped, 2))
            value_label.config(text=f"{var.get():.2f}s")

        scale = ttk.Scale(row, from_=frm, to=to, orient="horizontal", command=_on_change)
        scale.set(var.get())
        scale.pack(side="left", fill="x", expand=True, padx=(6, 6))
        row.scale_widget = scale
        return row

    def _on_toggle_timer_enabled(self):
        self._set_timer_slider_enabled(self.timer_enabled_var.get())
        self._save_settings()

    def _set_timer_slider_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try:
            self.timer_slider_row.scale_widget.config(state=state)
        except Exception:
            pass

    # ---------- dialog openers (bottom tab bar) ----------

    def _toggle_dialog(self, name, factory):
        dialog = self._open_dialogs.get(name)
        if dialog is not None and dialog.winfo_exists():
            dialog.destroy()
            return

        dialog = factory()
        self._open_dialogs[name] = dialog
        dialog.lift()
        dialog.focus_force()

        def forget_destroyed(event, window=dialog, key=name):
            if event.widget is window:
                self._open_dialogs.pop(key, None)

        dialog.bind("<Destroy>", forget_destroyed, add="+")

    def open_lures_dialog(self):
        self._toggle_dialog("lures", lambda: LuresDialog(self, self))

    def open_fishing_zone_dialog(self):
        self._toggle_dialog("fishing_zone", lambda: FishingZoneDialog(self, self))

    def open_bobber_detection_dialog(self):
        self._toggle_dialog("bobber_detection", lambda: BobberDetectionDialog(self, self))

    def open_advanced_settings(self):
        self._toggle_dialog("advanced_settings", lambda: AdvancedSettingsDialog(self, self))

    # ---------- keybindings ----------

    def _register_hotkey(self, key: str):
        if not HAS_KEYBOARD:
            return
        self._unregister_hotkey()
        key = key.strip()
        if not key:
            return
        try:
            keyboard.add_hotkey(key, self._toggle_bot)
            self._registered_hotkey = key
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not register hotkey '{key}':\n{e}")

    def _unregister_hotkey(self):
        if HAS_KEYBOARD and self._registered_hotkey:
            try:
                keyboard.remove_hotkey(self._registered_hotkey)
            except Exception:
                pass
            self._registered_hotkey = None

    def apply_stop_key(self):
        self._register_hotkey(self.stop_hotkey_var.get())
        if self._registered_hotkey:
            self.hotkey_status_var.set(f"Hotkey set: {self._registered_hotkey}")
        elif HAS_KEYBOARD:
            self.hotkey_status_var.set("No global hotkey set.")
        self._save_settings()

    def clear_stop_key(self):
        self._unregister_hotkey()
        self.stop_hotkey_var.set("")
        self.hotkey_status_var.set("No global hotkey set.")
        self._save_settings()

    # ---------- search area overlay ----------

    def open_search_area_overlay(self):
        SearchAreaOverlay(self, on_confirm=self._on_search_area_confirmed, initial_bounds=self.search_region)

    def _on_search_area_confirmed(self, bounds):
        self.search_region = bounds
        l, t, r, b = bounds
        self.search_area_label_var.set(f"({l}, {t}) to ({r}, {b})  [{r - l}\u00d7{b - t}]")
        self._save_settings()

    # ---------- buff picking (used by AdvancedSettingsDialog) ----------

    def start_buff_pick(self):
        self._buff_pick_countdown(3)

    def _buff_pick_countdown(self, seconds_left: int):
        if seconds_left > 0:
            self.buff_status_var.set(
                f"Hover over the visible pole-buff icon or green timer... sampling in {seconds_left}"
            )
            self.after(1000, lambda: self._buff_pick_countdown(seconds_left - 1))
        else:
            self._sample_buff_at_cursor()

    def _sample_buff_at_cursor(self):
        try:
            x, y = pyautogui.position()
            # Use the most common vivid color near the cursor instead of one
            # possibly-black pixel. This makes the small purple/green pole-buff
            # icon much more reliable to identify.
            image = pyautogui.screenshot(region=(x - 14, y - 14, 28, 28)).convert("RGB")
            vivid = [pixel for pixel in image.getdata()
                     if max(pixel) >= 90 and max(pixel) - min(pixel) >= 55]
            if vivid:
                r, g, b = Counter(vivid).most_common(1)[0][0]
            else:
                r, g, b = pyautogui.pixel(x, y)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not sample color:\n{e}")
            self.buff_status_var.set("")
            return

        self.buff_color = (r, g, b)
        # The icon and its green remaining-time text together fit within this
        # stable local region, while excluding the rest of the UI.
        margin = 32
        self.buff_region = (x - margin, y - margin, x + margin, y + margin)
        if hasattr(self, "buff_swatch"):
            self.buff_swatch.config(bg=f"#{r:02x}{g:02x}{b:02x}")
        self.buff_color_label_var.set(f"Pole buff RGB({r}, {g}, {b}) at ({x}, {y})")
        self.buff_status_var.set("Pole buff captured. Test it while the green timer is visible.")
        self._save_settings()

    def test_buff_check(self):
        if self.buff_color is None:
            messagebox.showerror(APP_TITLE, "Pick the buff icon first.")
            return

        self.buff_status_var.set("Scanning for buff icon...")
        self.update_idletasks()

        try:
            result = scan_for_color(
                self.buff_color,
                int(self.buff_tolerance_var.get()),
                int(self.buff_min_pixels_var.get()),
                self.buff_region,
            )
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Scan failed:\n{e}")
            self.buff_status_var.set("")
            return

        if result is None:
            self.buff_status_var.set("Buff NOT detected \u2014 the bot would use the lure now.")
        else:
            x, y, count = result
            self.buff_status_var.set(f"Buff detected at ({x}, {y}) \u2014 {count} pixels.")

    # ---------- lazily-created state (persist regardless of which dialog is open) ----------

    @property
    def fish_key_var(self):
        if not hasattr(self, "_fish_key_var"):
            self._fish_key_var = tk.StringVar(value="b")
        return self._fish_key_var

    @property
    def buff_key_var(self):
        if not hasattr(self, "_buff_key_var"):
            self._buff_key_var = tk.StringVar(value="")
        return self._buff_key_var

    @property
    def stop_hotkey_var(self):
        if not hasattr(self, "_stop_hotkey_var"):
            self._stop_hotkey_var = tk.StringVar(value="f8")
        return self._stop_hotkey_var

    @property
    def hotkey_status_var(self):
        if not hasattr(self, "_hotkey_status_var"):
            default = "Hotkey set: f8" if HAS_KEYBOARD else "Install 'keyboard' package for global hotkeys."
            self._hotkey_status_var = tk.StringVar(value=default)
        return self._hotkey_status_var

    @property
    def search_area_label_var(self):
        if not hasattr(self, "_search_area_label_var"):
            self._search_area_label_var = tk.StringVar(value="Full screen")
        return self._search_area_label_var

    @property
    def tolerance_var(self):
        if not hasattr(self, "_tolerance_var"):
            self._tolerance_var = tk.IntVar(value=30)
        return self._tolerance_var

    @property
    def min_pixels_var(self):
        if not hasattr(self, "_min_pixels_var"):
            self._min_pixels_var = tk.IntVar(value=15)
        return self._min_pixels_var

    @property
    def match_shades_var(self):
        if not hasattr(self, "_match_shades_var"):
            self._match_shades_var = tk.BooleanVar(value=False)
        return self._match_shades_var

    @property
    def hue_tolerance_var(self):
        if not hasattr(self, "_hue_tolerance_var"):
            self._hue_tolerance_var = tk.IntVar(value=12)
        return self._hue_tolerance_var

    @property
    def warmup_var(self):
        if not hasattr(self, "_warmup_var"):
            self._warmup_var = tk.DoubleVar(value=2.0)
        return self._warmup_var

    @property
    def timeout_var(self):
        if not hasattr(self, "_timeout_var"):
            self._timeout_var = tk.DoubleVar(value=30.0)
        return self._timeout_var

    @property
    def tune_px_var(self):
        if not hasattr(self, "_tune_px_var"):
            self._tune_px_var = tk.IntVar(value=0)
        return self._tune_px_var

    @property
    def dip_threshold_var(self):
        if not hasattr(self, "_dip_threshold_var"):
            self._dip_threshold_var = tk.IntVar(value=6)
        return self._dip_threshold_var

    @property
    def tracking_margin_var(self):
        if not hasattr(self, "_tracking_margin_var"):
            self._tracking_margin_var = tk.IntVar(value=45)
        return self._tracking_margin_var

    @property
    def human_like_var(self):
        if not hasattr(self, "_human_like_var"):
            self._human_like_var = tk.BooleanVar(value=True)
        return self._human_like_var

    @property
    def buff_enabled_var(self):
        if not hasattr(self, "_buff_enabled_var"):
            self._buff_enabled_var = tk.BooleanVar(value=False)
        return self._buff_enabled_var

    @property
    def buff_tolerance_var(self):
        if not hasattr(self, "_buff_tolerance_var"):
            self._buff_tolerance_var = tk.IntVar(value=30)
        return self._buff_tolerance_var

    @property
    def buff_min_pixels_var(self):
        if not hasattr(self, "_buff_min_pixels_var"):
            self._buff_min_pixels_var = tk.IntVar(value=5)
        return self._buff_min_pixels_var

    @property
    def bite_click_delay_var(self):
        if not hasattr(self, "_bite_click_delay_var"):
            self._bite_click_delay_var = tk.DoubleVar(value=0.0)
        return self._bite_click_delay_var

    @property
    def recast_delay_var(self):
        if not hasattr(self, "_recast_delay_var"):
            self._recast_delay_var = tk.DoubleVar(value=1.0)
        return self._recast_delay_var

    @property
    def fishing_pole_var(self):
        if not hasattr(self, "_fishing_pole_var"):
            self._fishing_pole_var = tk.StringVar(value="")
        return self._fishing_pole_var

    @property
    def lure_item_var(self):
        if not hasattr(self, "_lure_item_var"):
            self._lure_item_var = tk.StringVar(value="")
        return self._lure_item_var

    @property
    def macro_preview_var(self):
        if not hasattr(self, "_macro_preview_var"):
            self._macro_preview_var = tk.StringVar(value=build_lure_macro("", ""))
        return self._macro_preview_var

    @property
    def buff_color_label_var(self):
        if not hasattr(self, "_buff_color_label_var"):
            self._buff_color_label_var = tk.StringVar(value="No buff icon picked yet")
        return self._buff_color_label_var

    @property
    def buff_status_var(self):
        if not hasattr(self, "_buff_status_var"):
            self._buff_status_var = tk.StringVar(value="")
        return self._buff_status_var

    # ---------- bot control ----------

    def _build_config(self) -> BotConfig:
        human_like = self.human_like_var.get()
        return BotConfig(
            target_color=self.picked_color,
            color_tolerance=int(self.tolerance_var.get()),
            min_color_pixels=int(self.min_pixels_var.get()),
            fishing_button=self.fish_key_var.get() or "b",
            tune_bait_mouse_under_px=int(self.tune_px_var.get()),
            active_after_seconds=float(self.warmup_var.get()),
            bite_timeout_seconds=float(self.timeout_var.get()),
            search_region=self.search_region,
            bite_dip_threshold_px=int(self.dip_threshold_var.get()),
            tracking_margin_px=int(self.tracking_margin_var.get()),
            buff_check_enabled=self.buff_enabled_var.get(),
            buff_color=self.buff_color,
            buff_region=self.buff_region,
            buff_tolerance=int(self.buff_tolerance_var.get()),
            buff_min_pixels=int(self.buff_min_pixels_var.get()),
            buff_key=self.buff_key_var.get().strip(),
            min_action_delay=0.15 if human_like else 0.05,
            max_action_delay=0.55 if human_like else 0.10,
            press_space_chance=0.10 if human_like else 0.0,
            bite_click_delay=float(self.bite_click_delay_var.get()),
            recast_delay_seconds=float(self.recast_delay_var.get()),
            match_shades=self.match_shades_var.get(),
            hue_tolerance=int(self.hue_tolerance_var.get()),
            fishing_pole_name=self.fishing_pole_var.get().strip(),
            lure_item_name=self.lure_item_var.get().strip(),
        )

    def _toggle_bot(self):
        if self.bot and self.bot.is_running():
            self.stop_bot()
        else:
            self.start_bot()

    def start_bot(self):
        if self.picked_color is None:
            messagebox.showerror(
                APP_TITLE,
                "Pick a bobber color first.\n\n"
                "Open the Bobber Detection tab, click \"Pick Color...\", then hover "
                "over the bobber in-game during the 3-second countdown.",
            )
            return

        if self.buff_enabled_var.get():
            if self.buff_color is None:
                messagebox.showerror(
                    APP_TITLE,
                    "Buff check is enabled but no buff icon has been picked.\n\n"
                    "Open Advanced Settings \u2192 Buff Check to pick one, "
                    "or turn the option off.",
                )
                return
            if not self.buff_key_var.get().strip():
                messagebox.showerror(
                    APP_TITLE,
                    "Buff check is enabled but no buff key is set.\n\n"
                    "Enter the key that uses your lure/bobber on the fishing pole.",
                )
                return

        config = self._build_config()
        self.bot = FishingBot(config, log_fn=self._log_queue.put)
        self.bot.start()
        self.toggle_btn.set_appearance(text="STOP", base_color=THEME_RED)
        self._update_stats_loop()
        self._save_settings()
        self._start_auto_stop_timer()

    def stop_bot(self):
        if self.bot:
            self.bot.stop()
        self.toggle_btn.set_appearance(text="START", base_color=THEME_BLUE)
        self._cancel_auto_stop_timer()

    # ---------- auto-stop timer ----------

    def _start_auto_stop_timer(self):
        self._cancel_auto_stop_timer()
        if not self.timer_enabled_var.get():
            self.timer_status_var.set("Timer not running")
            return
        minutes = max(1, int(self.timer_minutes_var.get()))
        self._timer_end_time = time.time() + minutes * 60
        self._tick_auto_stop_timer()

    def _tick_auto_stop_timer(self):
        if self._timer_end_time is None:
            return
        remaining = self._timer_end_time - time.time()
        if remaining <= 0:
            self._timer_end_time = None
            self._timer_after_id = None
            self._on_timer_expired()
            return
        mins, secs = divmod(int(remaining), 60)
        self.timer_status_var.set(f"Auto-stop in {mins:02d}:{secs:02d}")
        self._timer_after_id = self.after(1000, self._tick_auto_stop_timer)

    def _cancel_auto_stop_timer(self):
        if getattr(self, "_timer_after_id", None) is not None:
            try:
                self.after_cancel(self._timer_after_id)
            except Exception:
                pass
        self._timer_after_id = None
        self._timer_end_time = None
        self.timer_status_var.set("Timer not running")

    def _on_timer_expired(self):
        self.stop_bot()  # also cancels/resets the timer state above
        if self.close_wow_var.get():
            self.timer_status_var.set("Timer elapsed \u2014 bot stopped, closing WoW...")
            self.update_idletasks()
            closed = close_wow_processes()
            self.timer_status_var.set(
                "Timer elapsed \u2014 bot stopped, WoW closed." if closed
                else "Timer elapsed \u2014 bot stopped (no running WoW process found)."
            )
        else:
            self.timer_status_var.set("Timer elapsed \u2014 bot stopped.")

    # ---------- background polling ----------

    def _poll_log_queue(self):
        # There's no in-window log panel; the bot still reports progress
        # through this queue (used for stats/errors), so we keep draining
        # it to avoid an unbounded backlog.
        while True:
            try:
                self._log_queue.get_nowait()
            except queue.Empty:
                break
        self.after(150, self._poll_log_queue)

    def _update_stats_loop(self):
        if self.bot:
            self.stats_label.config(
                text=f"Casts: {self.bot.casts}    Catches: {self.bot.catches}    "
                     f"Buffs applied: {self.bot.buffs_applied}"
            )
            if self.bot.is_running():
                self.after(500, self._update_stats_loop)
            else:
                self.toggle_btn.set_appearance(text="START", base_color=THEME_BLUE)

    # ---------- persisted settings ----------

    def _collect_settings(self) -> dict:
        """Everything that should survive a restart: keybindings, the
        picked bobber/buff colors and regions, and every threshold/slider
        in the main window and Advanced Settings."""
        return {
            "fish_key": self.fish_key_var.get(),
            "buff_key": self.buff_key_var.get(),
            "stop_hotkey": self.stop_hotkey_var.get(),
            "picked_color": list(self.picked_color) if self.picked_color else None,
            "search_region": list(self.search_region) if self.search_region else None,
            "tolerance": int(self.tolerance_var.get()),
            "min_pixels": int(self.min_pixels_var.get()),
            "match_shades": bool(self.match_shades_var.get()),
            "hue_tolerance": int(self.hue_tolerance_var.get()),
            "buff_color": list(self.buff_color) if self.buff_color else None,
            "buff_region": list(self.buff_region) if self.buff_region else None,
            "warmup": float(self.warmup_var.get()),
            "timeout": float(self.timeout_var.get()),
            "tune_px": int(self.tune_px_var.get()),
            "dip_threshold": int(self.dip_threshold_var.get()),
            "tracking_margin": int(self.tracking_margin_var.get()),
            "human_like": bool(self.human_like_var.get()),
            "buff_enabled": bool(self.buff_enabled_var.get()),
            "buff_tolerance": int(self.buff_tolerance_var.get()),
            "buff_min_pixels": int(self.buff_min_pixels_var.get()),
            "bite_click_delay": float(self.bite_click_delay_var.get()),
            "recast_delay": float(self.recast_delay_var.get()),
            "fishing_pole": self.fishing_pole_var.get(),
            "lure_item": self.lure_item_var.get(),
            "timer_enabled": bool(self.timer_enabled_var.get()),
            "timer_minutes": int(self.timer_minutes_var.get()),
            "close_wow": bool(self.close_wow_var.get()),
        }

    def _save_settings(self):
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._collect_settings(), f, indent=2)
        except Exception:
            pass  # settings are a convenience; never let a save failure crash the bot

    def _load_settings(self):
        """Populate app-level state (Vars + plain attributes) from disk.
        Deliberately touches no widget objects here — the bottom-tab
        dialogs are built on demand and read this same state fresh each
        time they're opened, so there's nothing to keep in sync eagerly."""
        if not os.path.exists(SETTINGS_PATH):
            return
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        self.fish_key_var.set(data.get("fish_key", self.fish_key_var.get()))
        self.buff_key_var.set(data.get("buff_key", self.buff_key_var.get()))
        self.stop_hotkey_var.set(data.get("stop_hotkey", self.stop_hotkey_var.get()))

        picked = data.get("picked_color")
        if picked:
            self.picked_color = tuple(picked)

        region = data.get("search_region")
        if region:
            self.search_region = tuple(region)
            l, t, r, b = self.search_region
            self.search_area_label_var.set(f"({l}, {t}) to ({r}, {b})  [{r - l}\u00d7{b - t}]")

        if "tolerance" in data:
            self.tolerance_var.set(data["tolerance"])
        if "min_pixels" in data:
            self.min_pixels_var.set(data["min_pixels"])
        if "match_shades" in data:
            self.match_shades_var.set(data["match_shades"])
        if "hue_tolerance" in data:
            self.hue_tolerance_var.set(data["hue_tolerance"])

        buff_color = data.get("buff_color")
        if buff_color:
            self.buff_color = tuple(buff_color)
            r, g, b = self.buff_color
            self.buff_color_label_var.set(f"RGB({r}, {g}, {b})")
        buff_region = data.get("buff_region")
        if buff_region:
            self.buff_region = tuple(buff_region)

        for key, var_name in (
            ("warmup", "warmup_var"), ("timeout", "timeout_var"),
            ("tune_px", "tune_px_var"), ("dip_threshold", "dip_threshold_var"),
            ("tracking_margin", "tracking_margin_var"), ("human_like", "human_like_var"),
            ("buff_enabled", "buff_enabled_var"), ("buff_tolerance", "buff_tolerance_var"),
            ("buff_min_pixels", "buff_min_pixels_var"), ("bite_click_delay", "bite_click_delay_var"),
            ("recast_delay", "recast_delay_var"), ("fishing_pole", "fishing_pole_var"),
            ("lure_item", "lure_item_var"),
        ):
            if key in data:
                getattr(self, var_name).set(data[key])

        if "timer_enabled" in data:
            self.timer_enabled_var.set(data["timer_enabled"])
            self._set_timer_slider_enabled(data["timer_enabled"])
        if "timer_minutes" in data:
            self.timer_minutes_var.set(data["timer_minutes"])
        if "close_wow" in data:
            self.close_wow_var.set(data["close_wow"])

    def _on_close(self):
        self._save_settings()
        self._cancel_auto_stop_timer()
        if self.bot and self.bot.is_running():
            self.bot.stop()
        self.destroy()


if __name__ == "__main__":
    app = FishingBotApp()
    app.mainloop()
