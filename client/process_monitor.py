import ctypes
import ctypes.wintypes

import psutil

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def _get_foreground_window():
    return user32.GetForegroundWindow()


def _get_window_text(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_window_pid(hwnd) -> int:
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


class ProcessMonitor:
    _BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}

    _BROWSER_SUFFIXES = [
        " - Google Chrome",
        " - Microsoft​ Edge",
        " - Microsoft Edge",
        " - Mozilla Firefox",
        " - Brave",
        " - Opera",
    ]

    def get_active_window_info(self) -> dict:
        try:
            hwnd = _get_foreground_window()
            if not hwnd:
                return {"process_name": "", "window_title": "", "pid": 0}

            title = _get_window_text(hwnd)
            pid = _get_window_pid(hwnd)

            process_name = ""
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            return {
                "process_name": process_name,
                "window_title": title,
                "pid": pid,
            }
        except Exception:
            return {"process_name": "", "window_title": "", "pid": 0}

    def get_browser_url(self) -> str | None:
        try:
            info = self.get_active_window_info()
            proc_lower = info["process_name"].lower()
            if proc_lower not in self._BROWSER_PROCESSES:
                return None

            title = info["window_title"]
            if not title:
                return None

            for suffix in self._BROWSER_SUFFIXES:
                if title.endswith(suffix):
                    page_title = title[: -len(suffix)]
                    return page_title if page_title else None

            return None
        except Exception:
            return None

    def has_process_changed(self, last_info: dict | None) -> bool:
        if last_info is None:
            return True
        current = self.get_active_window_info()
        return (
            current["process_name"] != last_info.get("process_name", "")
            or current["window_title"] != last_info.get("window_title", "")
        )
