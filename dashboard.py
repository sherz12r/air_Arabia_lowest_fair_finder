"""
VFS Global Automation — configuration dashboard.

Collects all config.json fields, writes them on start,
then runs main.Automation without modifying the bot.
"""

import json
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

from app_paths import get_app_dir
from session_logger import (
    RETENTION_DAYS,
    SessionLog,
    append_log_line,
    ensure_stdio,
    list_log_files,
    prune_old_logs,
    read_log_file,
    today_log_path,
)

CONFIG_PATH = "config.json"

SCRIPT_DIR = get_app_dir()


def _chdir_to_script():
    os.chdir(SCRIPT_DIR)


class LogViewerWindow(tk.Toplevel):
    """Browse daily log files kept for the last 7 days."""

    def __init__(self, parent, base_dir: str):
        super().__init__(parent)
        self.base_dir = base_dir
        self.title(f"Log history (last {RETENTION_DAYS} days)")
        self.geometry("760x520")
        self.minsize(560, 400)

        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Select a day:").pack(side=tk.LEFT)
        self.day_var = tk.StringVar()
        self.day_combo = ttk.Combobox(
            top, textvariable=self.day_var, state="readonly", width=28
        )
        self.day_combo.pack(side=tk.LEFT, padx=(8, 0))
        self.day_combo.bind("<<ComboboxSelected>>", self._on_day_selected)

        ttk.Button(top, text="Refresh", command=self._refresh_list).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Open logs folder", command=self._open_folder).pack(side=tk.LEFT)

        self.content = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED
        )
        self.content.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._log_paths: dict[str, str] = {}
        self._refresh_list()

    def _refresh_list(self):
        prune_old_logs(self.base_dir)
        paths = list_log_files(self.base_dir)
        self._log_paths.clear()

        labels = []
        for path in paths:
            name = os.path.basename(path)
            day = name.replace(".log", "")
            try:
                dt = datetime.strptime(day, "%Y-%m-%d")
                label = dt.strftime("%A, %d %b %Y")
            except ValueError:
                label = day
            labels.append(label)
            self._log_paths[label] = path

        self.day_combo["values"] = labels
        if labels:
            self.day_combo.current(0)
            self._show_file(self._log_paths[labels[0]])
        else:
            self.day_var.set("")
            self._show_text(
                f"No log files yet.\n\nLogs are created when you run automation from the dashboard.\n"
                f"Files older than {RETENTION_DAYS} days are removed automatically."
            )

    def _on_day_selected(self, _event=None):
        path = self._log_paths.get(self.day_var.get())
        if path:
            self._show_file(path)

    def _show_file(self, path: str):
        text = read_log_file(path)
        header = f"File: {path}\n{'=' * 60}\n\n"
        self._show_text(header + text)

    def _show_text(self, text: str):
        self.content.configure(state=tk.NORMAL)
        self.content.delete("1.0", tk.END)
        self.content.insert(tk.END, text)
        self.content.see(tk.END)
        self.content.configure(state=tk.DISABLED)

    def _open_folder(self):
        folder = os.path.join(self.base_dir, "logs")
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            os.system(f'open "{folder}"')
        else:
            os.system(f'xdg-open "{folder}"')


class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        _chdir_to_script()

        self.title("VFS Global Automation — Dashboard")
        self.minsize(720, 580)
        self.geometry("820x660")

        self._running = False
        prune_old_logs(SCRIPT_DIR)
        self._build_ui()
        self._load_from_files(silent=True)
        self._log(f"Log file: {today_log_path(SCRIPT_DIR)}")

    def _build_ui(self):
        header = ttk.Frame(self, padding=(12, 10, 12, 0))
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text="Air Arabia Automation",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Configure settings below, then start the bot. Files are saved before each run.",
            foreground="#555",
        ).pack(anchor=tk.W, pady=(2, 0))

        options_frame = ttk.LabelFrame(self, text="Browser options", padding=8)
        options_frame.pack(fill=tk.X, padx=12, pady=(6, 0))

        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Run browser in headless mode (no visible window — runs in the background)",
            variable=self.headless_var,
        ).pack(anchor=tk.W)

        bottom = ttk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        btn_frame = ttk.Frame(bottom, padding=(0, 0, 0, 0))
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        log_frame = ttk.LabelFrame(bottom, text="Log", padding=6)
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(0, 8))
        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=9, state=tk.DISABLED, font=("Consolas", 9)
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

        form_frame = ttk.Frame(self, height=268)
        form_frame.pack(fill=tk.X, padx=12, pady=(6, 4))
        form_frame.pack_propagate(False)

        notebook = ttk.Notebook(form_frame, padding=2)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.vars = {}
        self._add_tab(notebook, "Login & countries", self._login_fields())
        self._add_tab(notebook, "Slot date range", self._slot_fields())

        ttk.Button(btn_frame, text="Reload from files", command=self._load_from_files).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frame, text="Save JSON only", command=self._save_only).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btn_frame, text="View logs (7 days)", command=self._open_log_viewer).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        self.start_btn = ttk.Button(
            btn_frame, text="Start automation", command=self._start_automation
        )
        self.start_btn.pack(side=tk.RIGHT)

    def _login_fields(self):
        return [
            ("from_airport", "From airport (first dropdown)", "UAE - UAE"),
            ("to_airport", "Visiting country (second dropdown)", "Turkiye"),
            ("vfs_email", "VFS login email", ""),
            ("vfs_password", "VFS login password", "", True),
        ]


    def _slot_fields(self):
        return [
            ("slot_date_from", "Earliest slot date (DD/MM/YYYY)", "23/07/2026"),
            ("slot_date_to", "Latest slot date (DD/MM/YYYY)", "23/07/2026"),
            ("check_for_days", "Check for days", "30"),
        ]

    def _add_tab(self, notebook, title, fields):
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, padding=12)

        inner.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(_event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        for i, field in enumerate(fields):
            key = field[0]
            label = field[1]
            default = field[2] if len(field) > 2 else ""
            is_secret = len(field) > 3 and field[3]

            ttk.Label(inner, text=label).grid(row=i, column=0, sticky=tk.W, pady=(0, 2))
            var = tk.StringVar(value=default)
            self.vars[key] = var
            entry = ttk.Entry(inner, textvariable=var, width=52, show="*" if is_secret else "")
            entry.grid(row=i, column=1, sticky=tk.EW, pady=(0, 10))
        inner.columnconfigure(1, weight=1)

    def _log(self, message, save_to_file=True):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, line + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)
        if save_to_file:
            try:
                append_log_line(message, SCRIPT_DIR)
            except OSError:
                pass

    def _log_from_bot(self, message):
        self.after(0, lambda: self._log(message, save_to_file=False))

    def _read_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_from_files(self, silent=False):
        config = self._read_json(CONFIG_PATH)
        app = config.get("application_from_data", {})

        self.headless_var.set(bool(config.get("headless", False)))

        slot_range = config.get("slot_date_range", {})
        mapping = {
            "from_airport": config.get("from_airport", ""),
            "to_airport": config.get("to_airport", ""),
            "vfs_email": config.get("email", ""),
            "vfs_password": config.get("password", ""),
            "slot_date_from": slot_range.get("from", ""),
            "slot_date_to": slot_range.get("to", ""),
            "check_for_days": slot_range.get("check_for_days", ""),
        }
        for key, value in mapping.items():
            if key in self.vars:
                self.vars[key].set(str(value) if value is not None else "")

        if not silent:
            self._log(f"Loaded {CONFIG_PATH}.")

    def _open_log_viewer(self):
        LogViewerWindow(self, SCRIPT_DIR)

    def _collect_config(self):
        config = self._read_json(CONFIG_PATH)
        return {
            "headless": self.headless_var.get(),
            "from_airport": self.vars["from_airport"].get().strip(),
            "to_airport": self.vars["to_airport"].get().strip(),
            "email": self.vars["vfs_email"].get().strip(),
            "password": self.vars["vfs_password"].get(),
            "slot_date_range": {
                "from": self.vars["slot_date_from"].get().strip(),
                "to": self.vars["slot_date_to"].get().strip(),
                "check_for_days": self.vars["check_for_days"].get().strip(),
            },
           
        }

    def _validate(self, config):
        required_config = [
            ("from_airport", config["from_airport"]),
            ("to_airport", config["to_airport"]),
            ("VFS login email", config["email"]),
            ("VFS login password", config["password"]),
        ]
        for label, value in required_config:
            if not value:
                return f"Missing: {label}"

        slot_range = config.get("slot_date_range", {})
        date_from = slot_range.get("from", "")
        date_to = slot_range.get("to", "")
        if not date_from or not date_to:
            return "Missing slot date range (from and to are required)"
        try:
            from datetime import datetime

            d_from = datetime.strptime(date_from, "%d/%m/%Y").date()
            d_to = datetime.strptime(date_to, "%d/%m/%Y").date()
        except ValueError:
            return "Slot dates must be valid and use DD/MM/YYYY format (e.g. 01/0612026)"
        if d_from > d_to:
            return "Slot date 'from' must be on or before 'to'"

        return None

    def _write_json_files(self, config):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def _save_only(self):
        config = self._collect_config()
        err = self._validate(config)
        try:
            self._write_json_files(config)
            self._log(f"Saved {CONFIG_PATH}.")
            messagebox.showinfo("Saved", "Configuration files written successfully.")
        except OSError as exc:
            messagebox.showerror("Error", f"Could not save files:\n{exc}")

    def _set_running(self, running):
        self._running = running
        state = tk.DISABLED if running else tk.NORMAL
        self.start_btn.configure(state=state)

    def _start_automation(self):
        if self._running:
            return

        config = self._collect_config()
        err = self._validate(config)
        if err:
            messagebox.showwarning("Validation", err)
            return

        try:
            self._write_json_files(config)
        except OSError as exc:
            messagebox.showerror("Error", f"Could not save files:\n{exc}")
            return

        browser_label = "headless" if config.get("headless") else "visible"
        self._log(f"Starting automation ({browser_label} browser) …")
        self._set_running(True)

        thread = threading.Thread(target=self._run_bot, daemon=True)
        thread.start()

    def _run_bot(self):
        try:
            if getattr(sys, "frozen", False):
                bundle_dir = getattr(sys, "_MEIPASS", SCRIPT_DIR)
                if bundle_dir not in sys.path:
                    sys.path.insert(0, bundle_dir)
            if SCRIPT_DIR not in sys.path:
                sys.path.insert(0, SCRIPT_DIR)
            _chdir_to_script()

            from main import Automation

            with SessionLog(SCRIPT_DIR, on_line=self._log_from_bot):
                Automation()
            self.after(0, lambda: self._on_bot_finished(None))
        except Exception as exc:
            self.after(0, lambda: self._on_bot_finished(exc))

    def _on_bot_finished(self, error):
        self._set_running(False)
        if error:
            self._log(f"Automation ended with error: {error}")
            messagebox.showerror("Automation error", str(error))
        else:
            self._log("Automation finished.")


def main():
    ensure_stdio()
    app = DashboardApp()
    app.mainloop()
    


if __name__ == "__main__":
    main()
