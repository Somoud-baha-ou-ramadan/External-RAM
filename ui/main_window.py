#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import psutil
from threading import Thread, Event
from pathlib import Path
import sys

# Add External RAM system to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from main import SmartSSDVirtualRAM


class SmartSSDMemoryBoosterPro:

    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.geometry("400x220")
        self.root.configure(bg="#0a0a0a")

        self.running = Event()
        self.running.set()

        self.engine = None
        self.engine_thread = None

        # ===== TOP BAR =====
        top_bar = tk.Frame(self.root, bg="#0a0a0a", height=25)
        top_bar.pack(fill=tk.X)

        close_btn = tk.Button(
            top_bar, text="✕", bg="#0a0a0a", fg="#ffffff",
            bd=0, font=("Segoe UI", 11, "bold"),
            command=self.on_closing, cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT, padx=8)

        # ===== ASCII TITLE =====
        ascii_title = r"""
.----..-.  .-..---. .----..----. .-. .-.  .--.  .-.      .----.   .--.  .-.   .-.
| {_   \ \/ /{_   _}| {_  | {}  }|  `| | / {} \ | |      | {}  } / {} \ |  `.'  |
| {__  / /\ \  | |  | {__ | .-. \| |\  |/  /\  \| `--.   | .-. \/  /\  \| |\ /| |
`----'`-'  `-' `-'  `----'`-' `-'`-' `-'`-'  `-'`----'   `-' `-'`-'  `-'`-' ` `-'
"""
        tk.Label(
            self.root,
            text=ascii_title,
            font=("Consolas", 6),
            fg="#ffffff",
            bg="#0a0a0a",
            justify=tk.LEFT
        ).pack(anchor="w", padx=8, pady=(15, 5))

        # ===== DRAG =====
        def start_move(e):
            self.x = e.x
            self.y = e.y

        def do_move(e):
            self.root.geometry(f"+{e.x_root - self.x}+{e.y_root - self.y}")

        top_bar.bind("<Button-1>", start_move)
        top_bar.bind("<B1-Motion>", do_move)

        # ===== CONFIG =====
        self.update_interval = 700  # faster but smooth
        self.ram_history = []
        self.max_points = 50

        self.setup_styles()
        self.build_ui()

        self.start_engine()
        self.update_loop()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # =====================================================
    # ENGINE
    # =====================================================

    def start_engine(self):
        try:
            self.engine = SmartSSDVirtualRAM()

            def run():
                try:
                    self.engine.start()
                except Exception as e:
                    print(f"Engine stopped: {e}")

            self.engine_thread = Thread(target=run, daemon=True)
            self.engine_thread.start()
        except Exception as e:
            print(f"Could not start engine: {e}")

    # =====================================================
    # STYLES
    # =====================================================

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#0a0a0a")
        style.configure("TLabel", background="#0a0a0a", foreground="#ffffff")

    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        dash = ttk.Frame(main)
        dash.pack(fill=tk.X, pady=(0, 8))

        self.ram_val = self.create_card(dash, "SYSTEM RAM")
        self.ssd_val = self.create_card(dash, "DISK CACHE")

        # ===== GRAPH =====
        self.canvas = tk.Canvas(
            main,
            height=60,
            bg="#0a0a0a",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.X)

    def create_card(self, parent, title):
        frame = ttk.Frame(parent)
        frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)

        tk.Label(frame, text=title, font=("Lucida Console", 6),
                 fg="#ffffff", bg="#0a0a0a").pack(anchor="w")

        val = tk.Label(
            frame,
            text="0%",
            font=("Lucida Console", 14),
            fg="#ffffff",
            bg="#0a0a0a"
        )
        val.pack(anchor="w")

        return val

    # =====================================================
    # LOOP
    # =====================================================

    def update_loop(self):
        if not self.running.is_set():
            return

        mem = psutil.virtual_memory()
        self.ram_val.config(text=f"{mem.percent}%")

        self.ram_history.append(mem.percent)
        if len(self.ram_history) > self.max_points:
            self.ram_history.pop(0)

        self.draw_chart()

        # SSD CACHE
        try:
            if self.engine and hasattr(self.engine, "cache_manager"):
                size = self.engine.cache_manager.get_total_size()
                mb = size / (1024 * 1024)
                self.ssd_val.config(text=f"{mb:.1f} MB")
            else:
                self.ssd_val.config(text="0 MB")
        except Exception:
            self.ssd_val.config(text="0 MB")

        self.root.after(self.update_interval, self.update_loop)

    # =====================================================
    # GRAPH (SMOOTH + LIGHT)
    # =====================================================

    def draw_chart(self):
        self.canvas.delete("all")

        if len(self.ram_history) < 2:
            return

        w = max(self.canvas.winfo_width(), 2)
        h = 60
        step = w / max(1, len(self.ram_history) - 1)

        points = []
        for i, val in enumerate(self.ram_history):
            x = i * step
            y = h - (val / 100 * h)
            points.extend((x, y))

        self.canvas.create_line(
            points,
            fill="#ffffff",
            width=1.5,
            smooth=True
        )

    # =====================================================
    # CLOSE
    # =====================================================

    def on_closing(self):
        self.running.clear()
        try:
            if self.engine:
                self.engine.stop()
            if self.engine_thread:
                self.engine_thread.join(timeout=3)  # let the engine clean up its cache
        except Exception as e:
            print(f"Shutdown error: {e}")
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartSSDMemoryBoosterPro(root)
    root.mainloop()