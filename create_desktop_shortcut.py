#!/usr/bin/env python3
"""
Creates a "LeRobot Workshop" shortcut on the Windows desktop that opens
lerobot_teleop_gui_v2.py with a double-click (no terminal window).

Run it once, with the Python of the LeRobot environment:
    .venv\\Scripts\\python.exe create_desktop_shortcut.py

It also draws the app icon (lerobot_workshop.ico, next to this script), which the
shortcut, the window and the taskbar use. Run it again if the project folder moves.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
GUI_SCRIPT = HERE / "lerobot_teleop_gui_v2.py"
ICON_PATH = HERE / "lerobot_workshop.ico"
SHORTCUT_NAME = "LeRobot Workshop.lnk"

PRIMARY = (232, 69, 122, 255)
WHITE = (255, 255, 255, 255)


def draw_icon(size=256):
    """Same robot logo as in the app header (drawn on a 48x48 grid), supersampled for smooth edges."""
    ss = 4
    k = size * ss / 48
    img = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x1, y1, x2, y2):
        return (x1 * k, y1 * k, x2 * k, y2 * k)

    d.rounded_rectangle(box(0, 0, 48, 48), radius=14 * k, fill=PRIMARY)
    d.rounded_rectangle(box(23, 8, 25, 15), radius=1 * k, fill=WHITE)  # antenna
    d.ellipse(box(20.5, 4.5, 27.5, 11.5), fill=WHITE)
    d.rounded_rectangle(box(11, 14, 37, 37), radius=7 * k, fill=WHITE)  # head
    d.ellipse(box(16, 20.5, 22, 26.5), fill=PRIMARY)  # eyes
    d.ellipse(box(26, 20.5, 32, 26.5), fill=PRIMARY)
    d.rounded_rectangle(box(19, 30.5, 29, 33), radius=1.25 * k, fill=PRIMARY)  # mouth
    return img.resize((size, size), Image.LANCZOS)


def desktop_folder():
    # Asks Windows, so it also works when the desktop is redirected (e.g. to OneDrive)
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True, text=True, check=True,
    )
    return Path(out.stdout.strip())


def create_shortcut(shortcut, target, arguments, working_dir, icon):
    def ps_quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(" + ps_quote(shortcut) + ");"
        f"$s.TargetPath = {ps_quote(target)};"
        f"$s.Arguments = {ps_quote(arguments)};"
        f"$s.WorkingDirectory = {ps_quote(working_dir)};"
        f"$s.IconLocation = {ps_quote(icon)};"
        "$s.Description = 'LeRobot Workshop - teleoperation interface';"
        "$s.Save()"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], check=True)


def main():
    if sys.platform != "win32":
        sys.exit("This script creates a Windows shortcut: run it on Windows.")

    # pythonw.exe = same Python, but without opening a terminal window
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        sys.exit(f"pythonw.exe not found next to {sys.executable}")

    # Each size drawn on its own (not shrunk from 256 px), so the small taskbar sizes stay sharp
    sizes = [16, 20, 24, 32, 36, 40, 48, 64, 96, 128, 256]
    images = [draw_icon(size) for size in sizes]
    images[-1].save(ICON_PATH, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[:-1])
    shortcut = desktop_folder() / SHORTCUT_NAME
    create_shortcut(shortcut, pythonw, f'"{GUI_SCRIPT}"', HERE, ICON_PATH)
    print(f"Shortcut created: {shortcut}")
    print(f"  runs: {pythonw} \"{GUI_SCRIPT}\"")


if __name__ == "__main__":
    main()
