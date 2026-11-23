# Latest I-Fish update

**Upload these two files from the release zip over the copies in this repo:**

- `fishing_bot_core.py`
- `gui.py`

## Food buff (important)
When a food **icon** is captured:
- Icon visible → do **not** re-eat
- Icon missing → eat once (40s idle channel)

The duration **timer no longer forces** a re-eat while the buff is still up.

## Order
1. Food (if needed)
2. Pole lure (if needed)
3. Cast

## Lures window
Scrollable; Close stays at the bottom.

## Run
```
python gui.py
```
