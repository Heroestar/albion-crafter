"""
Albion Reaper — Bot Launcher
"""

import tkinter as tk
from tkinter import ttk
import threading
import sys
import os
import itertools

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

BG      = "#0d1117"
SURFACE = "#161b22"
BORDER  = "#21262d"
GOLD    = "#d4a017"
TEXT    = "#e6edf3"
MUTED   = "#7d8590"
GREEN   = "#3fb950"
RED     = "#f85149"
PURPLE  = "#6e40c9"

CITIES = [
    "Brecilien", "Bridgewatch", "Caerleon",
    "Fort Sterling", "Lymhurst", "Martlock", "Thetford",
]

class Launcher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Albion Reaper")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.geometry("420x600")

        self._bot_thread  = None
        self._running     = False
        self._cal         = None
        self._spinner     = itertools.cycle(["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"])
        self._spin_job    = None
        self._scan_count  = 0
        self._scan_total  = 0

        self._build_ui()
        self.root.mainloop()

    def _build_ui(self):
        r = self.root

        # Logo
        logo_frame = tk.Frame(r, bg=BG)
        logo_frame.pack(pady=(24, 8))

        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path  = os.path.join(script_dir, "..", "logo.png")
        if PIL_OK and os.path.exists(logo_path):
            img = Image.open(logo_path).convert("RGBA")
            img.thumbnail((260, 130), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(img)
            tk.Label(logo_frame, image=self._logo_img, bg=BG).pack()
        else:
            tk.Label(logo_frame, text="Albion Reaper",
                     font=("Segoe UI", 22, "bold"), fg=GOLD, bg=BG).pack()

        # Stad
        tk.Label(r, text="Selecteer stad", font=("Segoe UI", 10),
                 fg=MUTED, bg=BG).pack(pady=(16, 4))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox",
            fieldbackground=SURFACE, background=SURFACE,
            foreground=TEXT, selectbackground=SURFACE,
            selectforeground=TEXT, bordercolor=BORDER, arrowcolor=GOLD,
        )
        self.city_var = tk.StringVar(value="Fort Sterling")
        ttk.Combobox(r, textvariable=self.city_var, values=CITIES,
                     state="readonly", width=22, font=("Segoe UI", 12)).pack()

        # Kalibreren
        self.cal_btn = tk.Button(
            r, text="⚙  Kalibreren",
            font=("Segoe UI", 10), fg=TEXT, bg=SURFACE,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", bd=0, padx=18, pady=7,
            cursor="hand2", command=self._start_calibrate,
        )
        self.cal_btn.pack(pady=(18, 0))

        # Start
        self.start_btn = tk.Button(
            r, text="▶   Start Scan",
            font=("Segoe UI", 14, "bold"), fg="#130e05", bg=GOLD,
            activebackground="#b8860b", activeforeground="#130e05",
            relief="flat", bd=0, padx=40, pady=14,
            cursor="hand2", command=self._start_scan,
        )
        self.start_btn.pack(pady=(10, 0))

        # Stop — groot en rood zodat het opvalt
        self.stop_btn = tk.Button(
            r, text="⏹   STOP SCAN",
            font=("Segoe UI", 13, "bold"), fg=TEXT, bg=RED,
            activebackground="#c0392b", activeforeground=TEXT,
            relief="flat", bd=0, padx=40, pady=14,
            cursor="hand2", command=self._stop_scan,
            state="disabled",
        )
        self.stop_btn.pack(pady=(8, 0))

        # Voortgang
        prog_frame = tk.Frame(r, bg=BG)
        prog_frame.pack(fill="x", padx=30, pady=(18, 0))

        self.spinner_lbl = tk.Label(prog_frame, text="", font=("Consolas", 14),
                                    fg=GOLD, bg=BG, width=2)
        self.spinner_lbl.pack(side="left")

        self.status_var = tk.StringVar(value="Klaar om te starten")
        tk.Label(prog_frame, textvariable=self.status_var,
                 font=("Segoe UI", 10), fg=MUTED, bg=BG,
                 anchor="w", justify="left").pack(side="left", padx=6)

        # Teller
        self.counter_var = tk.StringVar(value="")
        tk.Label(r, textvariable=self.counter_var,
                 font=("Segoe UI", 9), fg=MUTED, bg=BG).pack()

        # Log
        log_outer = tk.Frame(r, bg=SURFACE, bd=0, highlightthickness=1,
                             highlightbackground=BORDER)
        log_outer.pack(fill="both", expand=True, padx=24, pady=(12, 20))

        self.log = tk.Text(log_outer, bg=SURFACE, fg=TEXT,
                           font=("Consolas", 9), bd=0, relief="flat",
                           state="disabled", wrap="word",
                           insertbackground=TEXT)
        scroll = tk.Scrollbar(log_outer, command=self.log.yview, bg=SURFACE,
                              troughcolor=SURFACE, bd=0)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)

        self.log.tag_configure("green",  foreground=GREEN)
        self.log.tag_configure("red",    foreground=RED)
        self.log.tag_configure("gold",   foreground=GOLD)
        self.log.tag_configure("muted",  foreground=MUTED)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _log(self, msg, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", tag or "")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, msg, color=MUTED):
        self.status_var.set(msg)

    def _set_counter(self, done, total):
        if total:
            self.counter_var.set(f"{done} / {total} items gescand")
        else:
            self.counter_var.set("")

    def _start_spinner(self):
        self.spinner_lbl.configure(fg=GOLD)
        def tick():
            if self._running:
                self.spinner_lbl.configure(text=next(self._spinner))
                self._spin_job = self.root.after(80, tick)
            else:
                self.spinner_lbl.configure(text="")
        tick()

    def _stop_spinner(self):
        if self._spin_job:
            self.root.after_cancel(self._spin_job)
            self._spin_job = None
        self.spinner_lbl.configure(text="")

    def _toggle_buttons(self, scanning):
        on  = "disabled" if scanning else "normal"
        off = "normal"   if scanning else "disabled"
        self.start_btn.configure(state=on,
            bg="#555" if scanning else GOLD,
            fg=MUTED  if scanning else "#130e05")
        self.cal_btn.configure(state=on)
        self.stop_btn.configure(state=off)

    # ── Kalibratie ────────────────────────────────────────────────────────────
    def _start_calibrate(self):
        def run():
            self.root.after(0, lambda: self._toggle_buttons(True))
            self.root.after(0, lambda: self._set_status("Kalibratie loopt..."))
            self._running = True
            self.root.after(0, self._start_spinner)
            try:
                import market_bot
                self._cal = market_bot.calibrate()
                self.root.after(0, lambda: self._log("✓ Kalibratie opgeslagen", "green"))
                self.root.after(0, lambda: self._set_status("Kalibratie klaar ✓", GREEN))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Fout: {e}", "red"))
            finally:
                self._running = False
                self.root.after(0, self._stop_spinner)
                self.root.after(0, lambda: self._toggle_buttons(False))
        threading.Thread(target=run, daemon=True).start()

    # ── Scan ──────────────────────────────────────────────────────────────────
    def _start_scan(self):
        city = self.city_var.get()
        self._running = True
        self._scan_count = 0
        self._scan_total = 0
        self._toggle_buttons(scanning=True)
        self._set_status(f"Scannen in {city}...")
        self._start_spinner()
        self._log(f"▶ Start scan — {city}", "gold")

        gui = self

        class GUIStream:
            """Vangt print() van de bot op en toont het in het log."""
            def write(self, msg):
                msg = msg.rstrip()
                if not msg:
                    return
                tag = None
                if "geen prijs" in msg.lower() or "fout" in msg.lower():
                    tag = "muted"
                elif "silver" in msg.lower() or "→" in msg:
                    tag = "green"
                elif "[" in msg and "/" in msg:
                    # voortgangslijn: [15/200]
                    try:
                        part = msg[msg.index("[")+1:msg.index("]")]
                        done, total = part.split("/")
                        gui._scan_count = int(done.strip())
                        gui._scan_total = int(total.strip())
                        gui.root.after(0, lambda d=gui._scan_count, t=gui._scan_total:
                                       gui._set_counter(d, t))
                    except Exception:
                        pass
                    tag = "muted"
                gui.root.after(0, lambda m=msg, t=tag: gui._log(m, t))

            def flush(self):
                pass

        def run():
            old_stdout = sys.stdout
            sys.stdout = GUIStream()
            try:
                import market_bot as mb
                cal = self._cal or mb.load_calibration(silent=True)
                self._cal = cal
                cal["_current_city"] = city
                mb.scan_all_with_cal(cal)
                self.root.after(0, lambda: self._log("✓ Scan klaar!", "green"))
                self.root.after(0, lambda: self._set_status("Scan klaar ✓"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Gestopt: {e}", "red"))
                self.root.after(0, lambda: self._set_status("Gestopt"))
            finally:
                sys.stdout = old_stdout
                self._running = False
                self.root.after(0, self._stop_spinner)
                self.root.after(0, lambda: self._toggle_buttons(False))

        self._bot_thread = threading.Thread(target=run, daemon=True)
        self._bot_thread.start()

    def _stop_scan(self):
        import pyautogui
        self._running = False
        try:
            pyautogui.moveTo(0, 0)
        except Exception:
            pass
        self._stop_spinner()
        self._set_status("Gestopt")
        self._log("⏹ Scan gestopt.", "red")
        self._toggle_buttons(scanning=False)


if __name__ == "__main__":
    Launcher()
