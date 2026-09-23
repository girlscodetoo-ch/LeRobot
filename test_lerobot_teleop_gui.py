#!/usr/bin/env python3
"""
My Robot - Simple LeRobot Teleoperation Interface (SO-100 / SO-101)
=========================================================================

A very simple application with ONE big button to start/stop the
teleoperation of a LeRobot robotic arm. Designed to be used by
kids during a class: no command line, no jargon.

The teacher sets up the USB ports and arm IDs once (button in the
bottom right corner), and after that the kids just have to click the
big green button.

Prerequisites (to be done once, by the teacher, in a terminal):
    pip install -e ".[feetech]"      # install LeRobot
    lerobot-find-port                # to find the USB ports
    lerobot-setup-motors ...         # configure the motors
    lerobot-calibrate ...            # calibrate the arms

This application simply calls the `lerobot-teleoperate` command on
your behalf, using the settings you provided.

Launch:
    python lerobot_teleop_gui.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

CONFIG_PATH = Path.home() / ".lerobot_teleop_gui.json"

DEFAULT_CONFIG = {
    "robot_model": "SO-101",       # "SO-100" or "SO-101"
    "follower_port": "/dev/ttyACM1",
    "follower_id": "my_follower_arm",
    "leader_port": "/dev/ttyACM0",
    "leader_id": "my_leader_arm",
}

COLOR_BG = "#FAC5D7"
COLOR_START = "#03B64E"
COLOR_START_HOVER = "#0E6A35"
COLOR_STOP = "#E53935"
COLOR_STOP_HOVER = "#D32F2F"
COLOR_TEXT = "#000000"
COLOR_CARD = "#FAC5D7"
COLOR_ACCENT = "#5B8DEF"


def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def build_command(cfg):
    model = cfg.get("robot_model", "SO-101")
    prefix = "so101" if model == "SO-101" else "so100"
    return [
        "lerobot-teleoperate",
        f"--robot.type={prefix}_follower",
        f"--robot.port={cfg['follower_port']}",
        f"--robot.id={cfg['follower_id']}",
        f"--teleop.type={prefix}_leader",
        f"--teleop.port={cfg['leader_port']}",
        f"--teleop.id={cfg['leader_id']}",
    ]


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, cfg, on_save):
        super().__init__(master)
        self.title("Settings (teacher)")
        self.configure(bg=COLOR_BG)
        self.resizable(False, False)
        self.cfg = cfg
        self.on_save = on_save

        pad = {"padx": 14, "pady": 6}
        label_font = tkfont.Font(size=11)
        entry_font = tkfont.Font(size=11)

        tk.Label(
            self, text="Robot settings", bg=COLOR_BG, fg=COLOR_TEXT,
            font=tkfont.Font(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=2, pady=(16, 10))

        tk.Label(
            self,
            text=("These settings only need to be set once. Use\n"
                  "'lerobot-find-port' in a terminal to find the\n"
                  "USB ports for both arms."),
            bg=COLOR_BG, fg="#777777", font=tkfont.Font(size=9),
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=14, sticky="w")

        row = 2
        tk.Label(self, text="Robot model", bg=COLOR_BG, fg=COLOR_TEXT,
                  font=label_font).grid(row=row, column=0, sticky="w", **pad)
        self.model_var = tk.StringVar(value=cfg["robot_model"])
        model_menu = tk.OptionMenu(self, self.model_var, "SO-100", "SO-101")
        model_menu.config(font=entry_font)
        model_menu.grid(row=row, column=1, sticky="ew", **pad)

        self.entries = {}
        fields = [
            ("follower_port", "USB port - follower arm", "/dev/ttyACM1 (or COM4)"),
            ("follower_id", "ID - follower arm", "my_follower_arm"),
            ("leader_port", "USB port - leader arm", "/dev/ttyACM0 (or COM3)"),
            ("leader_id", "ID - leader arm", "my_leader_arm"),
        ]
        for key, label, placeholder in fields:
            row += 1
            tk.Label(self, text=label, bg=COLOR_BG, fg=COLOR_TEXT,
                      font=label_font).grid(row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(value=cfg.get(key, ""))
            entry = tk.Entry(self, textvariable=var, font=entry_font, width=24)
            entry.grid(row=row, column=1, sticky="ew", **pad)
            self.entries[key] = var

        row += 1
        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=16)

        tk.Button(
            btn_frame, text="Save", command=self.save,
            bg=COLOR_ACCENT, fg="white", font=tkfont.Font(size=11, weight="bold"),
            relief="flat", padx=16, pady=6, cursor="hand2",
        ).pack(side="left", padx=6)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg="#EEEEEE", fg=COLOR_TEXT, font=tkfont.Font(size=11),
            relief="flat", padx=16, pady=6, cursor="hand2",
        ).pack(side="left", padx=6)

        self.grab_set()

    def save(self):
        new_cfg = {"robot_model": self.model_var.get()}
        for key, var in self.entries.items():
            new_cfg[key] = var.get().strip()
        save_config(new_cfg)
        self.on_save(new_cfg)
        self.destroy()


class TeleopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("My Robot")
        self.configure(bg=COLOR_BG)
        self.geometry("600x480")
        self.minsize(480, 400)

        self.cfg = load_config()
        self.process = None
        self.running = False
        self.log_queue = queue.Queue()
        self.log_visible = False

        self._build_ui()
        self._poll_log_queue()

        if not CONFIG_PATH.exists():
            self.after(300, self.open_settings)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        title_font = tkfont.Font(size=26, weight="bold")
        subtitle_font = tkfont.Font(size=12)
        status_font = tkfont.Font(size=13)

        tk.Label(
            self, text="🤖 LeRobot Workshop 🤖", bg=COLOR_BG, fg=COLOR_TEXT, font=title_font
        ).pack(pady=(28, 4))

        tk.Label(
            self, text="Click the button to take control of the arm !",
            bg=COLOR_BG, fg="#000000", font=subtitle_font
        ).pack(pady=(0, 20))

        card = tk.Frame(self, bg=COLOR_CARD, highlightbackground="#FAC5D7",
                          highlightthickness=1)
        card.pack(pady=6, padx=40, fill="both", expand=True)

        # Inner frame that stays centered (both horizontally and vertically)
        # inside the card as the window is resized/maximized.
        content = tk.Frame(card, bg=COLOR_CARD)
        content.place(relx=0.5, rely=0.5, anchor="center")

        self.status_var = tk.StringVar(value="X Robot stopped")
        self.status_label = tk.Label(
            content, textvariable=self.status_var, bg=COLOR_CARD, fg=COLOR_TEXT,
            font=status_font
        )
        self.status_label.pack(pady=(24, 10))

        self.big_button = tk.Button(
            content, text="START", command=self.toggle,
            bg=COLOR_START, fg="white", activebackground=COLOR_START_HOVER,
            font=tkfont.Font(size=20, weight="bold"),
            relief="flat", width=14, height=3, cursor="hand2",
        )
        self.big_button.pack(pady=16)

        self.hint_var = tk.StringVar(value="")
        tk.Label(
            content, textvariable=self.hint_var, bg=COLOR_CARD, fg="#B00020",
            font=tkfont.Font(size=10), wraplength=420, justify="center",
        ).pack(pady=(0, 16))

        # Collapsible technical log panel (for troubleshooting)
        self.toggle_log_var = tk.StringVar(value="Show technical details ▾")
        self.toggle_log_btn = tk.Button(
            self, textvariable=self.toggle_log_var, command=self._toggle_log,
            bg=COLOR_BG, fg="#999999", relief="flat", font=tkfont.Font(size=9),
            cursor="hand2", bd=0, highlightthickness=0,
        )
        self.toggle_log_btn.pack(pady=(6, 0))

        self.log_frame = tk.Frame(self, bg=COLOR_BG)
        log_scroll = tk.Scrollbar(self.log_frame)
        log_scroll.pack(side="right", fill="y")
        self.log_text = tk.Text(
            self.log_frame, height=7, bg="#1E1E1E", fg="#D4D4D4",
            font=tkfont.Font(family="Courier", size=9), wrap="word",
            yscrollcommand=log_scroll.set, state="disabled",
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.config(command=self.log_text.yview)
        # log_frame is not packed yet: hidden until the user asks for it

        # Settings gear button, tucked in the corner
        gear = tk.Button(
            self, text="⚙️", command=self.open_settings, bg=COLOR_BG,
            relief="flat", font=tkfont.Font(size=14), cursor="hand2",
            highlightthickness=0, bd=0,
        )
        gear.place(relx=1.0, rely=1.0, anchor="se", x=-14, y=-14)

    def _toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_frame.pack(pady=(6, 10), padx=20, fill="both", expand=False)
            self.toggle_log_var.set("Hide technical details ▴")
        else:
            self.log_frame.pack_forget()
            self.toggle_log_var.set("Show technical details ▾")

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        self.after(200, self._poll_log_queue)

    def open_settings(self):
        if self.running:
            messagebox.showinfo(
                "Robot running",
                "Stop the robot first before changing the settings."
            )
            return
        SettingsWindow(self, self.cfg, self._settings_saved)

    def _settings_saved(self, new_cfg):
        self.cfg = new_cfg
        self.hint_var.set("")

    def toggle(self):
        if self.running:
            self.stop_teleop()
        else:
            self.start_teleop()

    def start_teleop(self):
        self.hint_var.set("")
        cmd = build_command(self.cfg)
        self._append_log(f"\n$ {' '.join(cmd)}\n")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            messagebox.showerror(
                "Command not found",
                "The 'lerobot-teleoperate' command was not found.\n\n"
                "Check that LeRobot is properly installed and that this\n"
                "application is launched from the same environment\n"
                "(e.g. the same conda/virtualenv environment)."
            )
            self._append_log("Error: 'lerobot-teleoperate' command not found.\n")
            return

        self.running = True
        self.status_var.set("🟡 Connecting to the robot...")
        self.big_button.config(text="STOP", bg=COLOR_STOP,
                                 activebackground=COLOR_STOP_HOVER)

        self._monitor_thread = threading.Thread(
            target=self._watch_process, daemon=True
        )
        self._monitor_thread.start()

        # Some versions of lerobot-teleoperate pause on startup waiting for
        # Enter (e.g. a calibration-mismatch confirmation). Since children
        # can't see that prompt in this app, send a couple of newlines
        # automatically so it's never silently stuck waiting for a key press.
        self.after(800, self._send_enter)
        self.after(2500, self._send_enter)

        # After a short delay, assume connection succeeded if process is alive
        self.after(2500, self._confirm_running)

    def _send_enter(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def _confirm_running(self):
        if self.running and self.process and self.process.poll() is None:
            self.status_var.set("🟢 Robot running - move the leader arm!")

    def _watch_process(self):
        # Read process output; if it exits on its own, reflect that in the UI
        if self.process is None:
            return
        output_lines = []
        for line in self.process.stdout:
            output_lines.append(line)
            self.log_queue.put(line)
        return_code = self.process.wait()
        self.after(0, lambda: self._process_ended(return_code, output_lines))

    def _process_ended(self, return_code, output_lines):
        was_running = self.running
        self.running = False
        self.process = None
        self.big_button.config(text="START", bg=COLOR_START,
                                 activebackground=COLOR_START_HOVER)
        self.status_var.set("🔴 Robot stopped")
        self._append_log(f"(process ended, exit code: {return_code})\n")

        if was_running and return_code not in (0, None) and return_code != -15 \
                and return_code != -9:
            tail = "".join(output_lines[-15:])
            self.hint_var.set(
                "The robot stopped because of a problem.\n"
                "Check the USB connections, then try again.\n"
                "(Ask the teacher for help if needed.)"
            )
            print(tail, file=sys.stderr)

    def stop_teleop(self):
        self.status_var.set("🔴 Robot stopped")
        self.big_button.config(text="START", bg=COLOR_START,
                                 activebackground=COLOR_START_HOVER)
        self.running = False
        if self.process is not None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def _on_close(self):
        self.stop_teleop()
        self.destroy()


if __name__ == "__main__":
    app = TeleopApp()
    app.mainloop()