<div align="center">

# 🎣 I-Fish

<p align="center">I-Fish is a configurable Windows desktop automation tool for World of Warcraft fishing. Rather than relying on version-specific memory reading or pixel templates tied to one expansion, it works by letting <em>you</em> pick the exact bobber color on screen, then watches for it using tolerance- and hue-based color matching plus the native Windows cursor-icon change that signals a bite. It includes a draggable fishing-zone overlay to limit scanning to just your water, optional auto-buffing with WoW-macro generation for lures, a full keybinding/timing settings suite, an Auto-Stop Timer (with optional auto-close of WoW), and a built-in "Support I-Fish" donation prompt.</p>

[![Stars](https://img.shields.io/github/stars/phoenixsolutions201-max/I-Fish?style=flat-square)](https://github.com/phoenixsolutions201-max/I-Fish/stargazers) [![Issues](https://img.shields.io/github/issues/phoenixsolutions201-max/I-Fish?style=flat-square)](https://github.com/phoenixsolutions201-max/I-Fish/issues) [![Last Commit](https://img.shields.io/github/last-commit/phoenixsolutions201-max/I-Fish?style=flat-square)](https://github.com/phoenixsolutions201-max/I-Fish/commits/main)
![Python](https://img.shields.io/badge/-Python-555?style=flat-square&logo=python) ![Windows](https://img.shields.io/badge/-Windows%20only-555?style=flat-square&logo=windows)

[🐛 Report Bug](https://github.com/phoenixsolutions201-max/I-Fish/issues) · [✨ Request Feature](https://github.com/phoenixsolutions201-max/I-Fish/issues)

### [❤️ Donate — pay what it's worth to you](https://buy.stripe.com/00w14ncFi1Hz7v8gpd7Re00)

</div>

---

> ⚠️ **Automating fishing (or any gameplay) violates World of Warcraft's Terms of Service** and can get your account penalized or banned. This project is shared for educational purposes — understanding color-based screen detection and Windows cursor-state polling — use on a real account entirely at your own risk.

## 📋 Table of Contents

- [✨ Features](#-features)
- [📋 Prerequisites](#-prerequisites)
- [✅ Tested & Working](#-tested--working)
- [🚀 Setup](#-setup)
- [🖥️ GUI Overview](#️-gui-overview)
- [🎯 Using the Bot](#-using-the-bot)
- [🪤 Bite Detection](#-bite-detection)
- [🧰 Troubleshooting](#-troubleshooting)
- [💾 Settings Persistence](#-settings-persistence)
- [📂 Files](#-files)
- [⚠️ Disclaimer](#️-disclaimer)

## ✨ Features

- ✅ **Pick-your-own-color bobber detection** — no version-locked templates, works with any bobber skin or WoW expansion
- ✅ **Hue-tolerant (HSV) matching** — optionally match all shades/brightness of the picked color, so lighting and water tone changes don't break detection
- ✅ **Cursor-icon bite detection** — fires on the native Windows "interactive" cursor change, a color dip, or a splash-covered disappearance, whichever happens first
- ✅ **Draggable/resizable Fishing Zone overlay** — limit scanning to just your water for speed and fewer false positives
- ✅ **Auto-buffing with WoW macro generation** — detects whether your lure buff is active, re-applies it automatically, and generates a ready-to-paste `[equipped:...]` macro so the lure only ever lands on your actual fishing pole
- ✅ **Global Start/Stop hotkey** (default `F8`)
- ✅ **Auto-Stop Timer** — stop after N minutes, with an option to also force-close WoW (handy for unattended/overnight sessions)
- ✅ **Human-like randomized timing** toggle, plus tunable warm-up delay, bite timeout, bounce→click delay, and recast delay
- ✅ **Cast/Catch stats panel** and built-in status log
- ✅ **Settings saved automatically** — keybindings, colors, regions, and every slider persist between launches
- ✅ **Support prompt on launch** — a dismissible "enjoying it? consider donating" popup, not a license gate

## ✅ Tested & Working

Since detection is purely screen-color and cursor-state based (no memory
reading, no version-locked templates), I-Fish isn't tied to one client —
it's been tested and confirmed working on:

- ✅ **Classic**
- ✅ **Retail**
- ✅ **Forever Beta**

If you try it on another version, it should work the same way — the setup
only cares about what's visually on your screen.

## 📋 Prerequisites

- **Windows PC** (uses `win32gui` and screen-space input injection — won't run on macOS/Linux)
- **Python 3.10–3.13** if running from source (3.14 is very new — some dependencies may not have wheels for it yet)
- **World of Warcraft installed and running**, with Autoloot enabled and Click-to-Move disabled
- Your **Fishing** spell/ability bound to a key you know (default assumed: `b`)
- Ideally, a zoomed-in camera and a water patch where the bobber is easy to see

## 🚀 Setup

### 1. Get the bot
- **Easiest:** download `FishingBot.exe` — no Python required.
- **From source:**
  ```
  pip install -r requirements.txt
  ```
  (or `py -3.12 -m pip install -r requirements.txt` if you have multiple Python versions installed)

### 2. Configure WoW
- Bind **Fishing** to a key you'll remember (default assumed: `b`)
- Enable **Autoloot**
- Disable **Click-to-Move**

### 3. Launch
```
python gui.py
```
or just run `FishingBot.exe`.

### 4. Build your own exe (optional)
Run on a Windows machine — PyInstaller doesn't cross-compile:
```
python build_exe.py
```
The output, `FishingBot.exe`, appears in `dist/` with `icon.ico` embedded as its icon.

## 🖥️ GUI Overview

The main window (top to bottom): the **I-FISH** title, the big **Start/Stop**
button, a **Cast/Catch** stats panel, the **Auto-Stop Timer**, and a row of
four tabs at the bottom. Each tab opens its controls in its own popup window:

| Tab | What's in it |
|---|---|
| **Keybindings** | Fishing Key, Buff Key, and the global Stop/Start hotkey (default `F8`) |
| **Fishing Zone** | the draggable/resizable screen-region overlay, or reset to full screen |
| **Bobber Detection** | pick the bobber color, tune tolerance/sensitivity, enable hue-tolerant matching, test the match live |
| **Advanced Settings** | *General* (warm-up delay, bite timeout, hover offset, bounce→click delay, recast delay, randomized timing), *Buff Check* (lure auto-buffing + macro generator), *About* (the ToS disclaimer) |

The **Auto-Stop Timer** lives on the main window rather than behind a tab,
since it's something you'll likely set every session: check "Stop the bot
automatically after a set time", drag the Minutes slider, and it stops
itself (with a live countdown) once that time is up. Check "Also close WoW
when the timer ends" for unattended overnight sessions.

## 🎯 Using the Bot

### Picking the bobber color
1. Open **Bobber Detection**, click **"Pick Color..."**
2. You have 3 seconds to hover your mouse exactly over the brightest part of
   the bobber in-game (the feather, not the water splash) — don't click, just
   hover.
3. When the countdown hits zero, the app samples that pixel and shows a
   swatch + RGB value.

### Tuning
- **Tolerance** — how close a pixel's color must be to the picked color to
  count as a match (per channel, 0–255). Too low and the bot won't find the
  bobber; too high and it'll pick up unrelated objects. Start around 25–35.
- **Min pixels** — how many matching pixels count as "the bobber is here."
  Raise this if the bot falsely triggers on stray pixels.
- **Match all shades of this color** — switches matching from exact-RGB to
  hue-only (HSV), so the same bobber in shadow, sun, or different water
  stays detectable. Use the **Hue tolerance (°)** slider that appears next
  to it; start around 10–15°.
- **Hover offset (px)** — how far below the detected bobber to rest the
  mouse; 28–32 tends to work well, 0 if you want the click to land exactly
  where you picked.
- **Warm-up delay** — pause before the loop starts, so you can alt-tab in.
- **Bite timeout** — how long to wait for a bite before recasting.
- `F8` global hotkey needs the `keyboard` package, which may need
  Administrator rights on some Windows setups to see global key events.

### Setting a Fishing Zone (recommended)
From **Fishing Zone**, click **"Set Search Area..."** to open a draggable,
resizable overlay. Frame just the water patch where your bobber lands, then
**Confirm**. This speeds up scanning a lot and cuts false positives from
stray matching pixels elsewhere on screen. **"Use Full Screen"** clears it.

### Auto-buffing the bobber (optional)
1. Check **"Check for bobber/lure buff before each cast"**.
2. Buff up manually once so the icon is visible on your buff bar.
3. **"Pick Buff Icon..."**, then hover over it during the 3-second countdown.
4. Set **Buff key** to whatever applies the lure.
5. **"Test Buff Check"** any time to confirm detection without waiting for
   the bot to hit that step naturally.

If the buff isn't detected at cast time, the bot presses the buff key, waits
briefly for the animation, then proceeds normally.

#### Making sure the lure lands on the right pole
The bot only *presses* your buff key — it can't write WoW macros for you,
but the **Buff Check** tab generates one: pick your **Fishing pole** and
**Lure/buff item** (dropdowns pre-populated across Classic→retail, or type
a custom name), and it produces real macro syntax, e.g.:
```
#showtooltip Aquadynamic Fish Attractor
/use [equipped:Underlight Angler] Aquadynamic Fish Attractor
/use [equipped:Underlight Angler] 16
```
The `[equipped:...]` check means the macro does nothing unless that exact
pole is equipped, so it can never misapply the lure to the wrong weapon.
**Copy Macro**, paste into WoW, bind it to your Buff key.

## 🪤 Bite Detection

The bot tracks the bobber continuously (fast re-scans of a small box around
its last known position) and fires the catch on whichever happens first:
- the Windows cursor icon changes to the interactive one,
- the tracked color dips past **Bite dip threshold (px)**, or
- the color briefly disappears (splash covering it).

## 🧰 Troubleshooting

**Bites aren't being caught reliably?** In order:
1. Re-pick the bobber color while it's actually cast and floating, zoomed in
   tight on its brightest pixel.
2. Set **Hover offset** to 0 — the click should land exactly where you
   picked unless testing shows otherwise.
3. Use **"Test Match"** while the bobber is on screen to confirm the mouse
   lands exactly on it.
4. Lower **Bite dip threshold** (e.g. 3–4) — some bobbers only dip a couple
   pixels before the cursor changes.
5. Narrow the **Fishing Zone** tightly around just your water.
6. Run as **Administrator** — if WoW is elevated, input injection from a
   non-elevated script can silently fail.

**Bot doesn't find the bobber at all?** Lower tolerance and re-pick while
zoomed in tighter; try **hue-tolerant matching** if lighting varies.

## 💾 Settings Persistence

Every setting — keybindings, picked colors/regions, the Fishing Zone, and
every threshold/slider across all four tabs — saves automatically to
`fishing_bot_settings.json` next to `gui.py` (or next to `FishingBot.exe`).
It's written whenever you pick a color, confirm a zone, click OK, press
Start, or close the window, and loads back in next launch. Delete that JSON
to start fresh.

## 📂 Files

| File | Purpose |
|---|---|
| `fishing_bot_core.py` | bot logic, no GUI (importable/testable on its own) |
| `gui.py` | Tkinter front-end ("I-Fish") — theme, tabs, Auto-Stop Timer |
| `build_exe.py` | PyInstaller script that produces `FishingBot.exe` |
| `icon.ico` / `icon.png` | app icon, bundled into the exe |
| `requirements.txt` | Python dependencies |

## ⚠️ Disclaimer

Automating fishing (or any gameplay) violates World of Warcraft's Terms of
Service and can result in penalties up to a permanent ban. This is provided
for educational purposes — understanding color-based screen detection and
Windows cursor-state polling — use on a real account at your own risk.

---

<div align="center">

### If I-Fish saves you time, consider [chipping in whatever it's worth to you](https://buy.stripe.com/00w14ncFi1Hz7v8gpd7Re00) ❤️

</div>
