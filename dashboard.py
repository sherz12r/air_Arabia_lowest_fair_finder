"""
VFS Global Automation — configuration dashboard.

Collects all config.json and billing.json fields, writes them on start,
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
BILLING_PATH = "billing.json"

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
            text="VFS Global Automation",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Configure settings below, then start the bot. Files are saved before each run.",
            foreground="#555",
        ).pack(anchor=tk.W, pady=(2, 0))

        mode_frame = ttk.LabelFrame(self, text="Automation mode", padding=8)
        mode_frame.pack(fill=tk.X, padx=12, pady=(8, 0))

        self.mode_var = tk.StringVar(value="full")
        ttk.Radiobutton(
            mode_frame,
            text="Full automation — runs through payment (steps 1–14)",
            variable=self.mode_var,
            value="full",
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            mode_frame,
            text="Half automation — stops after slot booking (step 10); complete payment manually",
            variable=self.mode_var,
            value="half",
        ).pack(anchor=tk.W, pady=(4, 0))
        
        self.run_infinite = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            mode_frame,
            text="Run bot unlimited times until slot is found",
            variable=self.run_infinite,
        ).pack(anchor=tk.W)

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
        self._add_tab(notebook, "Applicant form", self._applicant_fields())
        self._add_tab(notebook, "Slot date range", self._slot_fields())
        self._add_tab(notebook, "Billing & payment", self._billing_fields())

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
            ("vfs_email1", "VFS login email1", ""),
            ("vfs_password1", "VFS login password1", "", True),
            ("vfs_email2", "VFS login email2", ""),
            ("vfs_password2", "VFS login password2", "", True),
            ("vfs_email3", "VFS login email3", ""),
            ("vfs_password3", "VFS login password3", "", True),
        ]

    def _applicant_fields(self):
        return [
            ("app_first_name", "First name", ""),
            ("app_last_name", "Last name", ""),
            ("app_gender", "Gender (e.g. Male / Female)", "Male"),
            ("app_date_of_birth", "Date of birth (DDMMYYYY)", ""),
            ("app_nationality", "Nationality", ""),
            ("app_passport_number", "Passport number", ""),
            ("app_passport_expiry", "Passport expiry (DDMMYYYY)", ""),
            ("app_country_code", "Phone country code", "92"),
            ("app_phone", "Phone number", ""),
            ("app_email", "Applicant email", ""),
        ]

    def _slot_fields(self):
        return [
            ("slot_date_from", "Earliest slot date (DD/MM/YYYY)", "23/07/2026"),
            ("slot_date_to", "Latest slot date (DD/MM/YYYY)", "23/07/2026"),
            ("check_for_days", "Check for days", "30"),
        ]

    def _billing_fields(self):
        return [
            ("bill_first_name", "Billing first name", ""),
            ("bill_last_name", "Billing last name", ""),
            ("bill_address1", "Address line 1", ""),
            ("bill_address2", "Address line 2", ""),
            ("bill_city", "City", ""),
            ("bill_country", "Country code (e.g. AE)", "AE"),
            ("bill_postal", "Postal code", ""),
            ("bill_phone", "Billing phone", ""),
            ("bill_email", "Billing email", ""),
            ("card_type", "Card type — 001 Visa, 002 Mastercard", "001"),
            ("card_number", "Card number", ""),
            ("expiry_month", "Expiry month (MM)", "12"),
            ("expiry_year", "Expiry year (YYYY)", "2027"),
            ("cvn", "CVN / CVV", "", True),
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
        billing = self._read_json(BILLING_PATH)
        app = config.get("application_from_data", {})

        self.mode_var.set("full" if config.get("full_automation", False) else "half")

        self.run_infinite.set(bool(config.get("run_infinite", False)))

        self.headless_var.set(bool(config.get("headless", False)))

        slot_range = config.get("slot_date_range", {})
        mapping = {
            "from_airport": config.get("from_airport", ""),
            "to_airport": config.get("to_airport", ""),
            "vfs_email": config.get("email", ""),
            "vfs_password": config.get("password", ""),
            "vfs_email1": config.get("email1", ""),
            "vfs_password1": config.get("password1", ""),
            "vfs_email2": config.get("email2", ""),
            "vfs_password2": config.get("password2", ""),
            "vfs_email3": config.get("email3", ""),
            "vfs_password3": config.get("password3", ""),
            "slot_date_from": slot_range.get("from", ""),
            "slot_date_to": slot_range.get("to", ""),
            "check_for_days": slot_range.get("check_for_days", ""),
            "app_first_name": app.get("first_name", ""),
            "app_last_name": app.get("last_name", ""),
            "app_gender": app.get("gender", "Male"),
            "app_date_of_birth": app.get("date_of_birth", ""),
            "app_nationality": app.get("nationality", ""),
            "app_passport_number": app.get("passport_number", ""),
            "app_passport_expiry": app.get("passport_expiry_data", ""),
            "app_country_code": app.get("country_code", ""),
            "app_phone": app.get("phone", ""),
            "app_email": app.get("email", ""),
            "bill_first_name": billing.get("first_name", ""),
            "bill_last_name": billing.get("last_name", ""),
            "bill_address1": billing.get("address_line1", ""),
            "bill_address2": billing.get("address_line2", ""),
            "bill_city": billing.get("city", ""),
            "bill_country": billing.get("country", "AE"),
            "bill_postal": billing.get("postal_code", ""),
            "bill_phone": billing.get("phone", ""),
            "bill_email": billing.get("email", ""),
            "card_type": billing.get("card_type", "001"),
            "card_number": billing.get("card_number", ""),
            "expiry_month": billing.get("expiry_month", ""),
            "expiry_year": billing.get("expiry_year", ""),
            "cvn": billing.get("cvn", ""),
        }
        for key, value in mapping.items():
            if key in self.vars:
                self.vars[key].set(str(value) if value is not None else "")

        if not silent:
            self._log(f"Loaded {CONFIG_PATH} and {BILLING_PATH}.")

    def _open_log_viewer(self):
        LogViewerWindow(self, SCRIPT_DIR)

    def _collect_config(self):
        config = self._read_json(CONFIG_PATH)
        return {
            "full_automation": self.mode_var.get() == "full",
            "run_infinite": self.run_infinite.get(),
            "headless": self.headless_var.get(),
            "from_airport": self.vars["from_airport"].get().strip(),
            "to_airport": self.vars["to_airport"].get().strip(),
            "email": self.vars["vfs_email"].get().strip(),
            "password": self.vars["vfs_password"].get(),
            "email1": self.vars["vfs_email1"].get().strip(),
            "password1": self.vars["vfs_password1"].get(),
            "email2": self.vars["vfs_email2"].get().strip(),
            "password2": self.vars["vfs_password2"].get(),
            "email3": self.vars["vfs_email3"].get().strip(),
            "password3": self.vars["vfs_password3"].get(),
            "slot_check_interval_minutes": config.get("slot_check_interval_minutes", "60"),
            "slot_date_range": {
                "from": self.vars["slot_date_from"].get().strip(),
                "to": self.vars["slot_date_to"].get().strip(),
                "check_for_days": self.vars["check_for_days"].get().strip(),
            },
            "application_from_data": {
                "first_name": self.vars["app_first_name"].get().strip(),
                "last_name": self.vars["app_last_name"].get().strip(),
                "gender": self.vars["app_gender"].get().strip(),
                "date_of_birth": self.vars["app_date_of_birth"].get().strip(),
                "nationality": self.vars["app_nationality"].get().strip(),
                "passport_number": self.vars["app_passport_number"].get().strip(),
                "passport_expiry_data": self.vars["app_passport_expiry"].get().strip(),
                "country_code": self.vars["app_country_code"].get().strip(),
                "phone": self.vars["app_phone"].get().strip(),
                "email": self.vars["app_email"].get().strip(),
            },
        }

    def _collect_billing(self):
        return {
            "first_name": self.vars["bill_first_name"].get().strip(),
            "last_name": self.vars["bill_last_name"].get().strip(),
            "address_line1": self.vars["bill_address1"].get().strip(),
            "address_line2": self.vars["bill_address2"].get().strip(),
            "city": self.vars["bill_city"].get().strip(),
            "country": self.vars["bill_country"].get().strip(),
            "postal_code": self.vars["bill_postal"].get().strip(),
            "phone": self.vars["bill_phone"].get().strip(),
            "email": self.vars["bill_email"].get().strip(),
            "card_type": self.vars["card_type"].get().strip(),
            "card_number": self.vars["card_number"].get().strip(),
            "expiry_month": self.vars["expiry_month"].get().strip(),
            "expiry_year": self.vars["expiry_year"].get().strip(),
            "cvn": self.vars["cvn"].get().strip(),
        }

    def _validate(self, config, billing):
        required_config = [
            ("from_airport", config["from_airport"]),
            ("to_airport", config["to_airport"]),
            ("VFS login email", config["email"]),
            ("VFS login password", config["password"]),
        ]
        for label, value in required_config:
            if not value:
                return f"Missing: {label}"

        app = config["application_from_data"]
        for key in app:
            if not app[key]:
                return f"Missing applicant field: {key.replace('_', ' ')}"

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

        if config["full_automation"]:
            billing_required = [
                "first_name",
                "last_name",
                "address_line1",
                "city",
                "country",
                "phone",
                "email",
                "card_type",
                "card_number",
                "expiry_month",
                "expiry_year",
                "cvn",
            ]
            for key in billing_required:
                if not billing.get(key):
                    return f"Missing billing field: {key.replace('_', ' ')} (required for full automation)"

        return None

    def _write_json_files(self, config, billing):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        with open(BILLING_PATH, "w", encoding="utf-8") as f:
            json.dump(billing, f, indent=4, ensure_ascii=False)
            f.write("\n")

    def _save_only(self):
        config = self._collect_config()
        billing = self._collect_billing()
        err = self._validate(config, billing)
        if err and config["full_automation"]:
            messagebox.showwarning("Validation", err)
            return
        if err and not config["full_automation"]:
            if messagebox.askyesno(
                "Validation",
                f"{err}\n\nSave anyway? (Half automation may not need billing.)",
            ):
                pass
            else:
                return
        try:
            self._write_json_files(config, billing)
            self._log(f"Saved {CONFIG_PATH} and {BILLING_PATH}.")
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
        billing = self._collect_billing()
        err = self._validate(config, billing)
        if err:
            messagebox.showwarning("Validation", err)
            return

        try:
            self._write_json_files(config, billing)
        except OSError as exc:
            messagebox.showerror("Error", f"Could not save files:\n{exc}")
            return

        mode_label = "FULL" if config["full_automation"] else "HALF"
        browser_label = "headless" if config.get("headless") else "visible"
        self._log(f"Starting {mode_label} automation ({browser_label} browser) …")
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
