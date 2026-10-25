"""
fishing_bot_core.py

Core automation logic for a WoW-style fishing bot.

Technique (Windows only):
  1. Locate the bobber by scanning the screen for a target RGB color
     (picked by the user at runtime, e.g. the bobber's bright feather).
  2. Continuously re-track that color in a small region around its last
     known position (fast re-scans instead of one big scan), following it
     with the mouse the way a real player's eye would.
  3. Detect a bite using whichever of three signals fires first:
       a) the Windows cursor icon changes from idle to interactive
          (win32gui.GetCursorInfo), or
       b) the tracked color dips downward by more than a threshold
          (the visual "bounce"), or
       c) the tracked color briefly disappears (splash covering it).
  4. Right-click (atomically positioned) to loot / reel in, then re-cast.
  5. Optionally, before each cast: check a fixed screen region for a
     lure/bobber buff icon (again via color match). If it's missing,
     press a configured key to use the bobber item on the fishing pole
     before casting.

This module contains no GUI code - it exposes a FishingBot class with
start()/stop() plus a callback hook so any front-end (Tkinter, CLI,
etc.) can drive it and receive log lines.
"""

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np
import pyautogui
import pydirectinput  # more reliable key/click injection into games than pyautogui
import win32gui
from PIL import ImageGrab


@dataclass
class BotConfig:
    target_color: Tuple[int, int, int] = (255, 0, 0)  # RGB color to search for
    color_tolerance: int = 30           # per-channel allowed difference (0-255)
    min_color_pixels: int = 15          # minimum matching pixels to count as a "found" bobber
    fishing_button: str = "b"           # keybind you have "Fishing" cast on
    tune_bait_mouse_under_px: int = 0   # vertical offset from the tracked color to the hover/click point
    edge_reset_x: int = 10
    edge_reset_y: int = 10
    active_after_seconds: float = 2.0   # warm-up delay before the loop starts
    bite_timeout_seconds: float = 30.0  # give up and re-cast if nothing bites
    min_action_delay: float = 0.15      # randomized delay lower bound
    max_action_delay: float = 0.55      # randomized delay upper bound
    press_space_chance: float = 0.10    # chance per loop to tap space (anti-pattern jitter)
    search_region: Optional[Tuple[int, int, int, int]] = None  # (left, top, right, bottom) or None for full screen

    # ---- bite tracking/detection tuning ----
    tracking_margin_px: int = 45        # half-width of the fast re-scan box around the last known position
    bite_poll_interval: float = 0.1     # seconds between tracking polls while waiting for a bite
    bite_dip_threshold_px: int = 6      # downward movement that counts as "the bounce"
    reacquire_after_lost_polls: int = 15  # consecutive tracking misses before doing a full re-locate
    bite_click_delay: float = 0.0       # pause after a bite signal fires, before the loot click
    recast_delay_seconds: float = 1.0   # extra pause before recasting when no bobber/bite was found

    # ---- shade-tolerant color matching ----
    match_shades: bool = False          # match all shades (brightness/saturation) of target_color's hue, not just near-exact RGB
    hue_tolerance: int = 12             # allowed hue difference in degrees (0-180) when match_shades is on
    shade_min_saturation: float = 0.15  # ignore near-gray pixels (0-1) so hue matching doesn't pick up noise
    shade_min_value: float = 0.15       # ignore near-black pixels (0-1) so hue matching doesn't pick up noise

    # ---- bobber/lure buff check ----
    buff_check_enabled: bool = False
    buff_color: Optional[Tuple[int, int, int]] = None
    buff_region: Optional[Tuple[int, int, int, int]] = None  # small box around the buff icon
    buff_tolerance: int = 30
    buff_min_pixels: int = 5
    buff_key: str = ""           # key/macro that uses the bobber/lure on your fishing pole
    buff_apply_wait_seconds: float = 0.5  # wait, then verify the pole-buff icon after applying
    fishing_pole_name: str = ""  # equipped fishing pole, used only to build the suggested macro text
    lure_item_name: str = ""     # lure/buff item name, used only to build the suggested macro text


LogFn = Callable[[str], None]


def build_lure_macro(fishing_pole_name: str, lure_item_name: str) -> str:
    """Build the standard three-line lure macro for a main-hand fishing pole."""
    lure = lure_item_name.strip() or "<Lure/Bobber Item Name>"
    return f"#showtooltip {lure}\n/use {lure}\n/use 16"


def _rgb_to_hsv_array(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized RGB (0-255 int) -> HSV conversion. Returns (h, s, v) where
    h is in degrees [0, 360), s and v are in [0, 1]. No extra dependency
    (no matplotlib/colorsys-per-pixel) so this stays fast on full-screen grabs."""
    f = arr.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]

    maxc = np.max(f, axis=-1)
    minc = np.min(f, axis=-1)
    v = maxc
    delta = maxc - minc

    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(maxc > 0, delta / np.where(maxc == 0, 1, maxc), 0.0)

        rc = np.where(delta == 0, 0, (maxc - r) / np.where(delta == 0, 1, delta))
        gc = np.where(delta == 0, 0, (maxc - g) / np.where(delta == 0, 1, delta))
        bc = np.where(delta == 0, 0, (maxc - b) / np.where(delta == 0, 1, delta))

    h = np.zeros_like(maxc)
    is_r = (maxc == r) & (delta != 0)
    is_g = (maxc == g) & (delta != 0) & ~is_r
    is_b = (maxc == b) & (delta != 0) & ~is_r & ~is_g

    h[is_r] = (bc[is_r] - gc[is_r]) % 6.0
    h[is_g] = 2.0 + rc[is_g] - bc[is_g]
    h[is_b] = 4.0 + gc[is_b] - rc[is_b]
    h = (h * 60.0) % 360.0

    return h, s, v


def scan_for_color(
    target_color: Tuple[int, int, int],
    tolerance: int,
    min_pixels: int,
    region: Optional[Tuple[int, int, int, int]] = None,
    match_shades: bool = False,
    hue_tolerance: int = 12,
    shade_min_saturation: float = 0.15,
    shade_min_value: float = 0.15,
) -> Optional[Tuple[int, int, int]]:
    """Grab the screen (or a region) and look for pixels matching
    target_color. Returns (x, y, matching_pixel_count) in full-screen
    coordinates, or None if fewer than min_pixels matched.

    Two matching modes:
      - RGB mode (match_shades=False, default): per-channel distance
        within `tolerance`, same behavior as before.
      - Shade mode (match_shades=True): converts to HSV and matches any
        pixel whose HUE is within `hue_tolerance` degrees of the target
        color's hue, regardless of how light/dark or how saturated it is.
        This catches the bobber under different lighting, shadow, or
        water-tint conditions where the exact RGB drifts but the color
        family (e.g. "red") stays the same. `shade_min_saturation` /
        `shade_min_value` filter out near-gray/near-black pixels so the
        hue match doesn't false-positive on shadow noise.

    Standalone so it can be reused for live botting, the bobber search,
    the buff-icon check, and one-off testing/debugging from the GUI."""
    bbox = region
    img = ImageGrab.grab(bbox=bbox)
    arr = np.asarray(img.convert("RGB"), dtype=np.int16)

    if match_shades:
        h, s, v = _rgb_to_hsv_array(arr)
        target_h, _, _ = _rgb_to_hsv_array(np.array(target_color, dtype=np.int16).reshape(1, 1, 3))
        target_hue = float(target_h[0, 0])

        hue_diff = np.abs(h - target_hue)
        hue_diff = np.minimum(hue_diff, 360.0 - hue_diff)  # circular distance

        mask = (
            (hue_diff <= hue_tolerance)
            & (s >= shade_min_saturation)
            & (v >= shade_min_value)
        )
    else:
        target = np.array(target_color, dtype=np.int16)
        diff = np.abs(arr - target)
        mask = np.all(diff <= tolerance, axis=2)

    ys, xs = np.where(mask)
    if len(xs) < min_pixels:
        return None

    centroid_x = int(xs.mean())
    centroid_y = int(ys.mean())

    if bbox is not None:
        centroid_x += bbox[0]
        centroid_y += bbox[1]

    return centroid_x, centroid_y, len(xs)


class FishingBot:
    def __init__(self, config: BotConfig, log_fn: Optional[LogFn] = None):
        self.config = config
        self._log_fn = log_fn or (lambda msg: None)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.casts = 0
        self.catches = 0
        self.buffs_applied = 0

    # ---------- public control ----------

    def start(self):
        if self._thread and self._thread.is_alive():
            self._log("Bot is already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._log("Bot started.")

    def stop(self):
        self._stop_event.set()
        self._log("Stop requested; finishing current step...")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---------- internals ----------

    def _log(self, msg: str):
        try:
            self._log_fn(msg)
        except Exception:
            pass

    def _sleep_random(self):
        time.sleep(random.uniform(self.config.min_action_delay, self.config.max_action_delay))

    def _get_cursor_handle(self):
        """Return the current Windows cursor handle, used as a fingerprint
        of which cursor icon is currently shown (arrow vs. interactive)."""
        try:
            _, handle, _ = win32gui.GetCursorInfo()
            return handle
        except Exception:
            return None

    def _reset_cursor_to_edge(self):
        pyautogui.moveTo(self.config.edge_reset_x, self.config.edge_reset_y)

    def _locate_bobber(self):
        """Scan the screen (or configured region) for pixels matching the
        target color within tolerance, and return the centroid of the
        matching pixels, or None if nothing found."""
        try:
            return scan_for_color(
                self.config.target_color,
                self.config.color_tolerance,
                self.config.min_color_pixels,
                self.config.search_region,
                match_shades=self.config.match_shades,
                hue_tolerance=self.config.hue_tolerance,
                shade_min_saturation=self.config.shade_min_saturation,
                shade_min_value=self.config.shade_min_value,
            )
        except Exception as e:
            self._log(f"Color scan error: {e}")
            return None

    def _track_bobber_near(self, x: int, y: int):
        """Fast re-scan of a small box around the last known bobber
        position. Uses a lower min-pixel floor than the full search since
        the box is already tight."""
        margin = self.config.tracking_margin_px
        region = (x - margin, y - margin, x + margin, y + margin)
        min_pixels = max(3, self.config.min_color_pixels // 3)
        try:
            return scan_for_color(
                self.config.target_color,
                self.config.color_tolerance,
                min_pixels,
                region,
                match_shades=self.config.match_shades,
                hue_tolerance=self.config.hue_tolerance,
                shade_min_saturation=self.config.shade_min_saturation,
                shade_min_value=self.config.shade_min_value,
            )
        except Exception as e:
            self._log(f"Tracking scan error: {e}")
            return None

    # ---------- buff check ----------

    def _has_buff(self) -> bool:
        """Return True if the configured buff icon color is currently
        present in the configured region. If buff checking isn't
        configured/enabled, treat this as always satisfied so the loop
        behaves exactly as before."""
        if not self.config.buff_check_enabled or self.config.buff_color is None:
            return True
        try:
            result = scan_for_color(
                self.config.buff_color,
                self.config.buff_tolerance,
                self.config.buff_min_pixels,
                self.config.buff_region,
            )
            return result is not None
        except Exception as e:
            self._log(f"Buff scan error: {e}")
            # Fail safe: assume buffed so we don't spam-press the buff key
            # on a broken scan.
            return True

    def _apply_buff(self):
        if not self.config.buff_key:
            self._log("Buff missing but no buff key configured — skipping.")
            return False
        pydirectinput.press(self.config.buff_key)
        self.buffs_applied += 1
        self._log(f"Bobber buff not detected — used lure on fishing pole (#{self.buffs_applied}).")
        return True

    def _ensure_buff(self):
        if not self.config.buff_check_enabled:
            return
        if self._has_buff():
            return
        if not self._apply_buff():
            return
        # Let WoW update the small pole-buff icon, then verify it before the
        # next pass. This prevents a second lure press while the icon appears.
        time.sleep(self.config.buff_apply_wait_seconds)
        if self._has_buff():
            self._log("Lure buff confirmed after 0.5 seconds.")
        else:
            self._log("Lure buff is not visible yet; continuing without a second use.")

    def _cast_line(self):
        pydirectinput.press(self.config.fishing_button)
        self.casts += 1
        self._log(f"Cast #{self.casts}: pressed '{self.config.fishing_button}'.")

    def _wait_for_bite_and_loot(self) -> bool:
        """Locate the bobber, then continuously track it while watching
        for a bite via cursor-change, a downward dip, or the color
        briefly vanishing (splash). Returns True if a catch was likely
        made."""
        deadline = time.time() + self.config.bite_timeout_seconds

        # Give the splash animation a moment to appear before we search.
        time.sleep(1.0)

        result = self._locate_bobber()
        if result is None:
            self._log("Could not find the target color on screen — check color/tolerance/Fishing Zone.")
            return False

        bobber_x, bobber_y, pixel_count = result
        self._log(f"Bobber located at ({bobber_x}, {bobber_y}) — {pixel_count} matching pixels.")

        hover_x = bobber_x
        hover_y = bobber_y + self.config.tune_bait_mouse_under_px
        pyautogui.moveTo(hover_x, hover_y)

        idle_cursor = self._get_cursor_handle()

        last_known_x, last_known_y = bobber_x, bobber_y
        y_history: List[int] = [bobber_y]
        lost_streak = 0

        def _do_catch(reason: str):
            if self.config.bite_click_delay > 0:
                time.sleep(self.config.bite_click_delay)
            pydirectinput.click(x=hover_x, y=hover_y, button="right")
            self.catches += 1
            self._log(f"Bite detected ({reason}) — looted. Total catches: {self.catches}.")

        while time.time() < deadline:
            if self._stop_event.is_set():
                return False

            # Signal A: Windows cursor icon change.
            current_cursor = self._get_cursor_handle()
            if current_cursor is not None and current_cursor != idle_cursor:
                _do_catch("cursor change")
                self._sleep_random()
                self._reset_cursor_to_edge()
                self._sleep_random()
                return True

            tracked = self._track_bobber_near(last_known_x, last_known_y)

            if tracked is not None:
                tx, ty, _ = tracked
                lost_streak = 0

                # Signal B: downward dip relative to a short rolling baseline.
                if len(y_history) >= 3:
                    baseline = sorted(y_history[-3:])[1]  # median of last 3
                    if ty - baseline >= self.config.bite_dip_threshold_px:
                        _do_catch("dip")
                        self._sleep_random()
                        self._reset_cursor_to_edge()
                        self._sleep_random()
                        return True

                y_history.append(ty)
                if len(y_history) > 6:
                    y_history.pop(0)

                last_known_x, last_known_y = tx, ty
                new_hover_x, new_hover_y = tx, ty + self.config.tune_bait_mouse_under_px
                if abs(new_hover_x - hover_x) > 2 or abs(new_hover_y - hover_y) > 2:
                    hover_x, hover_y = new_hover_x, new_hover_y
                    pyautogui.moveTo(hover_x, hover_y)
            else:
                lost_streak += 1

                # Signal C: color briefly vanished after being solidly
                # tracked — likely a splash covering it.
                if len(y_history) >= 3 and lost_streak == 2:
                    _do_catch("splash (color lost)")
                    self._sleep_random()
                    self._reset_cursor_to_edge()
                    self._sleep_random()
                    return True

                # Lost it for a while (camera moved, drift, etc.) — do a
                # full re-locate instead of endlessly polling an empty box.
                if lost_streak > self.config.reacquire_after_lost_polls:
                    self._log("Lost track of the bobber — re-locating...")
                    reacquired = self._locate_bobber()
                    if reacquired is not None:
                        last_known_x, last_known_y, _ = reacquired
                        hover_x = last_known_x
                        hover_y = last_known_y + self.config.tune_bait_mouse_under_px
                        pyautogui.moveTo(hover_x, hover_y)
                        y_history = [last_known_y]
                    lost_streak = 0

            time.sleep(self.config.bite_poll_interval)

        self._log("No bite detected before timeout — recasting.")
        return False

    def _maybe_press_space(self):
        if random.random() < self.config.press_space_chance:
            pydirectinput.press("space")

    def _run(self):
        self._log(f"Warming up for {self.config.active_after_seconds:.1f}s...")
        time.sleep(self.config.active_after_seconds)

        while not self._stop_event.is_set():
            self._ensure_buff()
            if self._stop_event.is_set():
                break
            self._cast_line()
            self._sleep_random()
            caught = self._wait_for_bite_and_loot()
            if not caught and self.config.recast_delay_seconds > 0 and not self._stop_event.is_set():
                self._log(f"Waiting {self.config.recast_delay_seconds:.1f}s before recasting...")
                time.sleep(self.config.recast_delay_seconds)
            self._maybe_press_space()
            self._sleep_random()

        self._log(
            f"Bot stopped. Casts: {self.casts}, Catches: {self.catches}, "
            f"Buffs applied: {self.buffs_applied}."
        )
