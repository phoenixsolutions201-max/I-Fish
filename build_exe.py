"""
build_exe.py

Convenience wrapper around PyInstaller that builds a single-file
Windows executable ("FishingBot.exe") with icon.ico as its app icon.

Run this ON WINDOWS (PyInstaller builds platform-native executables,
it can't cross-compile from Linux/Mac to a .exe):

    pip install -r requirements.txt
    python build_exe.py

The finished exe will be in the dist/ folder.
"""

import PyInstaller.__main__

PyInstaller.__main__.run([
    "gui.py",
    "--name=FishingBot",
    "--onefile",
    "--windowed",          # no console window behind the GUI
    "--icon=icon.ico",
    "--add-data=icon.ico;.",   # bundle the icon so iconbitmap() finds it at runtime
])
