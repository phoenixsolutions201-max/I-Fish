Latest working bot files (food-then-lure, no early reapply when buff icons are active, scrollable Lures window, full-icon matching):

Replace fishing_bot_core.py and gui.py from the latest release zip if this commit does not include the full sources.

Behavior:
1. Food first (idle channel), then pole lure, then cast
2. If food/lure icon is already visible on restart, do not reapply
3. Timer + minimum gap prevents double food on startup
