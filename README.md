# I-Fish

A Tkinter GUI wrapper around a simple WoW-style fishing automation loop.
Locates the bobber by scanning the screen for a target color you pick
yourself at startup, then watches the Windows cursor handle for the
"interactive" icon change that signals a bite.

**Windows only** (relies on `win32gui` and screen-space input injection).

## Files

- `fishing_bot_core.py` — bot logic, no GUI (importable/testable on its own)
- `gui.py` — Tkinter front-end ("I-Fish"): dark chrome/blue/red theme,
  Start/Stop, Cast/Catch stats, Auto-Stop Timer, and a bottom tab bar
  (Keybindings / Fishing Zone / Bobber Detection / Advanced Settings)
- `build_exe.py` — PyInstaller script to produce `FishingBot.exe`
- `icon.ico` — app icon (bundled into the exe)
- `requirements.txt` — Python dependencies

## Settings persistence

Every setting — keybindings, the picked bobber/buff colors and regions,
the Fishing Zone, and every threshold/slider across all four tabs — is
saved automatically to `fishing_bot_settings.json` next to `gui.py` (or
next to `FishingBot.exe` if you're running the built version). It's
written whenever you pick a color, confirm a Fishing Zone, click Ok in
Advanced Settings, press Start, or close the window, and is loaded back
in automatically the next time you launch — so you don't have to re-pick
your color or re-tune thresholds every session. Delete that JSON file if
you ever want to start over from scratch.

## GUI overview

The main window (top to bottom) is just: the **I-FISH** title, the big
**Start/Stop** button, a **Cast/Catch** stats panel, the **Auto-Stop
Timer**, and a row of four tabs at the bottom. Each tab opens its
controls in its own popup window, the same way Advanced Settings always
worked:

- **Keybindings** — Fishing Key, Buff Key, and a global Stop/Start hotkey
  (default `f8`). Click "Set" after changing the hotkey to re-register
  it, or "Delete" to remove it.
- **Fishing Zone** — opens the draggable/resizable overlay to frame the
  screen region to search (see below), or reset to full screen.
- **Bobber Detection** — pick the bobber color, tune tolerance/sensitivity,
  turn on shade-tolerant (HSV hue) matching for bobbers under changing
  light, and test the match live.
- **Advanced Settings** — General / Buff Check / About tabs:
  - *General*: warm-up delay, bite timeout, hover offset, a **bounce→click
    delay** slider (pause between a detected bite and the loot click — add
    a little if you want it to look less instant), a **recast delay**
    slider (extra time to wait before casting again when the bobber
    wasn't found or nothing bit, giving you more time to look/react), and
    a toggle for human-like randomized timing (turn it off for fixed,
    fast, robotic timing; leave it on for varied delays).
  - *Buff Check*: enable/disable the lure-buff check, pick the buff icon,
    set the buff key, and pick your **fishing pole** from the dropdown
    (or type a custom one) plus your lure/buff item name to get a
    suggested WoW macro that only applies the lure when that exact pole
    is equipped — see "Auto-buffing the bobber" below.
  - *About*: the ToS/ban-risk disclaimer.

The **Auto-Stop Timer** stays on the main window rather than behind a
tab, since it's something you'll likely set every session: check "Stop
the bot automatically after a set time", drag the Minutes slider to how
long you want it to run, and it stops itself (with a live countdown)
once that time is up. Check "Also close WoW when the timer ends" if you
want the game force-closed right after the bot stops — useful for
unattended overnight sessions.

## Setup

1. Install Python 3.10–3.13 on Windows (3.14 is very new — some dependencies
   may not have wheels for it yet).
2. From this folder:
   ```
   pip install -r requirements.txt
   ```
   (or `py -3.12 -m pip install -r requirements.txt` if you have multiple
   Python versions installed and want to target a specific one)
3. In WoW: bind your Fishing cast to a key (default assumed: `b`), enable
   Autoloot, and disable Click-to-Move.

## Run without building an exe

```
python gui.py
```

## Build a Windows .exe with the icon

Run this step on a Windows machine (PyInstaller doesn't cross-compile):

```
python build_exe.py
```

The output executable, `FishingBot.exe`, appears in `dist/` with `icon.ico`
as its taskbar/file icon.

## Using the GUI

### Picking the bobber color
1. Open the **Bobber Detection** tab, then click **"Pick Color..."**
2. You have 3 seconds to move your mouse so it's hovering exactly over the
   brightest part of the bobber (e.g. the red or blue feather) in-game —
   don't click, just hover.
3. When the countdown hits zero, the app samples that exact pixel's color
   and shows a swatch + RGB value.

### Tuning
- **Tolerance** — how close a pixel's color must be to the picked color to
  count as a match (per color channel, 0–255). Too low and the bot won't
  find the bobber at all; too high and it'll pick up unrelated red/blue
  objects in the scene. Start around 25–35 and adjust.
- **Min pixels** — how many matching pixels must be found before the bot
  treats it as "the bobber is here" rather than noise. Raise this if the
  bot falsely triggers on small stray pixels elsewhere on screen.
- **Match all shades of this color** — switches matching from exact-RGB to
  hue-only (HSV). A bobber in shadow, in bright sun, or against darker/
  lighter water is usually still the *same hue*, just a different
  brightness/saturation — this catches all of those instead of only the
  one exact shade you picked. Turn it on and use the **Hue tolerance (°)**
  slider that appears next to it; leave Tolerance/Min pixels as-is, they
  still apply when this is off. Start around hue tolerance 10–15° and
  widen it only if matches are still being missed.
- **Fishing key** — the key you bound your Fishing cast to.
- **Hover offset (px)** — how far below the detected bobber to rest the
  mouse; 28–32 tends to work well.
- **Warm-up delay** — pause before the loop starts, so you have time to
  alt-tab into the game.
- **Bite timeout** — how long to wait for a bite before giving up and
  recasting.
- **F8** — global start/stop hotkey (requires the `keyboard` package,
  which needs to run as Administrator on some Windows setups to see
  global key events).

### Setting a search area (optional but recommended)
From the **Fishing Zone** tab, click **"Set Search Area..."** to open a
draggable, resizable green-bordered box overlay. Position it over just
the patch of water where your bobber lands, then click **Confirm** in its
toolbar. This does two things:
- Speeds up scanning a lot, since only that region gets checked instead of
  your whole screen.
- Reduces false positives from stray matching pixels elsewhere on screen.

Click **"Use Full Screen"** at any time to clear the region and go back to
scanning everything.

### Tips for picking a good color
- Zoom your camera in so the bobber is large and easy to hover precisely.
- Pick a color that's distinctive against water — the bobber's feather
  tends to work better than the water splash itself, which varies a lot.
- If the bot keeps missing, lower the tolerance and re-pick while zoomed
  in tighter so you land exactly on the brightest pixel of the feather.
- Full-screen color scanning checks every pixel each time it searches, so
  on very high resolutions the scan takes a bit longer — this is normal.

### Auto-buffing the bobber (optional)
If you use a lure/bobber item on your fishing pole, the bot can check for
that buff before every cast and re-apply it automatically when it's missing:

1. Check **"Check for bobber/lure buff before each cast"**.
2. Buff up manually once so the icon is visible on your buff bar.
3. Click **"Pick Buff Icon..."**, then hover exactly over that icon during
   the 3-second countdown (same idea as picking the bobber color).
4. Set **"Buff key"** to whatever key/macro applies the lure to your
   fishing pole.
5. Use **"Test Buff Check"** any time to confirm detection is working
   without waiting for the bot to hit that step naturally.

If the buff icon isn't detected when it's time to cast, the bot presses the
buff key, waits briefly for the animation, and then proceeds as normal.

#### Making sure the lure lands on the right pole

The bot only *presses* your buff key — it can't create or edit macros
inside WoW. To make sure that keypress always applies the lure to the
correct pole (not whatever else you might have equipped), the Buff Check
tab gives you:
- A **Fishing pole** dropdown pre-populated with well-known poles across
  Classic/TBC/WotLK/Cata/retail (it's not exhaustive — type a custom name
  if yours isn't listed).
- A **Lure/buff item name** dropdown pre-populated with dozens of known
  lures/baits across expansions (also editable — type a custom name if
  yours isn't listed).
- A **Suggested macro** box showing real WoW macro syntax — three lines:
  ```
  #showtooltip Aquadynamic Fish Attractor
  /use [equipped:Underlight Angler] Aquadynamic Fish Attractor
  /use [equipped:Underlight Angler] 16
  ```
  The first line only sets the macro icon. Line 2 uses the lure (which
  normally just puts you into "click a weapon to apply" mode); line 3
  immediately applies it to inventory slot 16 — the main-hand slot,
  where an equipped fishing pole sits — so it completes with no click
  needed. The `[equipped:...]` check on both action lines means the macro
  does nothing at all if that exact pole
  isn't equipped, instead of misapplying the lure to whatever weapon
  you do have out. Click **Copy Macro**, paste both lines into a new
  macro in WoW, and bind that macro to whatever key you set as the
  Buff key.

## Bite detection

The bot now tracks the bobber continuously (fast re-scans of a small box
around its last known position) and fires the catch on whichever of these
happens first:
- the Windows cursor icon changes to the interactive one,
- the tracked color dips downward past **Bite dip threshold (px)**, or
- the color briefly disappears (splash covering it).

If the bot isn't finding or catching bites reliably, try in this order:
1. **Re-pick the bobber color** while the bobber is actually cast and
   floating, zoomed in tight on its brightest pixel.
2. **Set Hover offset to 0** in Advanced Settings — it defaults to 0 now
   since you want the click to land directly where you picked the color,
   not offset from it. Only add an offset if testing shows the real click
   target is a few pixels away from where you picked.
3. **Use "Test Match"** while the bobber is on screen to confirm the mouse
   lands exactly on it.
4. **Lower Bite dip threshold** (e.g. to 3–4) if bites aren't being
   caught — some bobbers only dip a couple pixels before the cursor
   changes.
5. **Narrow the Fishing Zone** tightly around just the water where you
   fish — it speeds up tracking and avoids false matches elsewhere on
   screen.
6. Run as **Administrator** — if WoW is elevated, input injection from a
   non-elevated script can silently fail.

## Disclaimer

Automating fishing (or any gameplay) violates World of Warcraft's Terms of
Service and can result in penalties up to a permanent ban. This is provided
for educational purposes — understanding color-based screen detection and
Windows cursor-state polling — use on a real account at your own risk.
