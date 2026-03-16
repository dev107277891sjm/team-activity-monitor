import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from client.identity import detect_local_ip


def _create_icon(color: str = "green", size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    colors = {
        "green": (34, 197, 94),
        "yellow": (234, 179, 8),
        "red": (239, 68, 68),
    }
    rgb = colors.get(color, colors["green"])

    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(*rgb, 255),
    )
    highlight_size = size // 6
    highlight_offset = size // 3
    draw.ellipse(
        [
            highlight_offset,
            highlight_offset,
            highlight_offset + highlight_size,
            highlight_offset + highlight_size,
        ],
        fill=(255, 255, 255, 100),
    )
    return img


class TrayIcon:
    def __init__(self, on_name_change_callback: Callable | None = None):
        self._on_name_change = on_name_change_callback
        self._tray: pystray.Icon | None = None
        self._status = "recording"
        self._current_name = ""

    def _build_menu(self):
        status_text = {
            "recording": "Status: Recording",
            "buffering": "Status: Buffering (offline)",
            "error": "Status: Error",
        }.get(self._status, f"Status: {self._status}")

        return pystray.Menu(
            pystray.MenuItem(status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Change Name...", self._on_change_name),
            pystray.MenuItem("About", self._on_about),
        )

    def _status_color(self) -> str:
        return {"recording": "green", "buffering": "yellow", "error": "red"}.get(
            self._status, "green"
        )

    def run(self):
        self._tray = pystray.Icon(
            "TAM",
            icon=_create_icon(self._status_color()),
            title="Team Activity Monitor",
            menu=self._build_menu(),
        )
        self._tray.run()

    def set_status(self, status: str):
        self._status = status
        if self._tray:
            self._tray.icon = _create_icon(self._status_color())
            self._tray.menu = self._build_menu()
            self._tray.update_menu()

    def set_current_name(self, name: str):
        self._current_name = name

    def _on_change_name(self, icon, item):
        result = self.show_name_change_dialog(self._current_name)
        if result and self._on_name_change:
            self._on_name_change(result)

    def _on_about(self, icon, item):
        def _show():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "Team Activity Monitor",
                "TAM User App v1.0\n\nTeam Activity Monitor client.\nCaptures screen, keystrokes, and process activity.",
            )
            root.destroy()

        threading.Thread(target=_show, daemon=True).start()

    def show_registration_dialog(self) -> dict | None:
        result = {}
        local_ip = detect_local_ip()

        def _dialog():
            root = tk.Tk()
            root.title("TAM - Registration")
            root.resizable(False, False)
            root.attributes("-topmost", True)

            frame = ttk.Frame(root, padding=20)
            frame.grid(sticky="nsew")

            ttk.Label(frame, text="Team Activity Monitor", font=("Segoe UI", 14, "bold")).grid(
                row=0, column=0, columnspan=2, pady=(0, 15)
            )

            ttk.Label(frame, text="Server IP:").grid(row=1, column=0, sticky="w", pady=5)
            server_entry = ttk.Entry(frame, width=30)
            server_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

            ttk.Label(frame, text="Display Name:").grid(row=2, column=0, sticky="w", pady=5)
            name_entry = ttk.Entry(frame, width=30)
            name_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

            ttk.Label(frame, text="Local IP:").grid(row=3, column=0, sticky="w", pady=5)
            ip_label = ttk.Label(frame, text=local_ip, foreground="gray")
            ip_label.grid(row=3, column=1, sticky="w", pady=5, padx=(10, 0))

            def on_register():
                server_ip = server_entry.get().strip()
                display_name = name_entry.get().strip()
                if not server_ip:
                    messagebox.showwarning("Input Error", "Server IP is required.", parent=root)
                    return
                if not display_name:
                    messagebox.showwarning("Input Error", "Display name is required.", parent=root)
                    return
                result["server_ip"] = server_ip
                result["display_name"] = display_name
                root.destroy()

            def on_cancel():
                root.destroy()

            btn_frame = ttk.Frame(frame)
            btn_frame.grid(row=4, column=0, columnspan=2, pady=(15, 0))
            ttk.Button(btn_frame, text="Register", command=on_register).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=5)

            root.update_idletasks()
            w = root.winfo_width()
            h = root.winfo_height()
            x = (root.winfo_screenwidth() // 2) - (w // 2)
            y = (root.winfo_screenheight() // 2) - (h // 2)
            root.geometry(f"+{x}+{y}")

            root.mainloop()

        thread = threading.Thread(target=_dialog)
        thread.start()
        thread.join()

        return result if result else None

    def show_name_change_dialog(self, current_name: str) -> str | None:
        result = {}

        def _dialog():
            root = tk.Tk()
            root.title("TAM - Change Name")
            root.resizable(False, False)
            root.attributes("-topmost", True)

            frame = ttk.Frame(root, padding=20)
            frame.grid(sticky="nsew")

            ttk.Label(frame, text="Current Name:").grid(row=0, column=0, sticky="w", pady=5)
            ttk.Label(frame, text=current_name, foreground="gray").grid(
                row=0, column=1, sticky="w", pady=5, padx=(10, 0)
            )

            ttk.Label(frame, text="New Name:").grid(row=1, column=0, sticky="w", pady=5)
            name_entry = ttk.Entry(frame, width=30)
            name_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

            def on_save():
                new_name = name_entry.get().strip()
                if not new_name:
                    messagebox.showwarning("Input Error", "Name cannot be empty.", parent=root)
                    return
                result["name"] = new_name
                root.destroy()

            def on_cancel():
                root.destroy()

            btn_frame = ttk.Frame(frame)
            btn_frame.grid(row=2, column=0, columnspan=2, pady=(15, 0))
            ttk.Button(btn_frame, text="Save", command=on_save).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=5)

            root.update_idletasks()
            w = root.winfo_width()
            h = root.winfo_height()
            x = (root.winfo_screenwidth() // 2) - (w // 2)
            y = (root.winfo_screenheight() // 2) - (h // 2)
            root.geometry(f"+{x}+{y}")

            root.mainloop()

        thread = threading.Thread(target=_dialog)
        thread.start()
        thread.join()

        return result.get("name")
