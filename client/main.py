import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

try:
    from client.activity_tracker import ActivityTracker
    from client.alert_sender import configure as alert_configure, install_crash_handler, send_app_stop
    from client.buffer import LocalBuffer
    from client.capturer import capture_all_screens, compute_screen_hash
    from client.config import (
        DATA_DIR,
        get_local_ip,
        is_registered,
        load_config,
        save_config,
    )
    from client.connection import ConnectionMonitor
    from client.identity import (
        fetch_server_settings,
        register_with_server,
        update_display_name,
    )
    from client.keylogger import KeyLogger
    from client.process_monitor import ProcessMonitor
    from client.tray import TrayIcon
    from client.uploader import Uploader
except ImportError:
    from activity_tracker import ActivityTracker
    from alert_sender import configure as alert_configure, install_crash_handler, send_app_stop
    from buffer import LocalBuffer
    from capturer import capture_all_screens, compute_screen_hash
    from config import (
        DATA_DIR,
        get_local_ip,
        is_registered,
        load_config,
        save_config,
    )
    from connection import ConnectionMonitor
    from identity import (
        fetch_server_settings,
        register_with_server,
        update_display_name,
    )
    from keylogger import KeyLogger
    from process_monitor import ProcessMonitor
    from tray import TrayIcon
    from uploader import Uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"{DATA_DIR}\\tam_client.log", encoding="utf-8", delay=True
        ),
    ],
)
logger = logging.getLogger("TAM.main")

DEFAULT_CAPTURE_INTERVAL = 30
DEFAULT_KEYSTROKE_FLUSH = 60
HEARTBEAT_INTERVAL = 30
CONNECTION_CHECK_INTERVAL = 5
PROCESS_POLL_INTERVAL = 1


def _windows_set_run_key(app_name: str, command: str) -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg  # type: ignore

        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
        return True
    except Exception as exc:
        logger.warning("Auto-start registration failed: %s", exc)
        return False


def _ensure_windows_install_and_autostart_user_app() -> None:
    """
    Install the user app EXE into a fixed system folder and register that installed EXE for auto-start.

    Target:
      C:\\ProgramData\\TAM\\UserApp\\tam_user.exe
    """
    if not sys.platform.startswith("win"):
        return

    exe_path = Path(sys.executable)
    if not exe_path.name.lower().endswith(".exe"):
        return  # running from python, not a built exe

    if "--autostart" in sys.argv:
        logger.info("Launched via Windows auto-start.")

    install_dir = Path(r"C:\ProgramData\TAM\UserApp")
    target_exe = install_dir / "tam_user.exe"

    # Always ensure auto-start points to the installed path.
    run_cmd = f"\"{str(target_exe)}\" --autostart"
    _windows_set_run_key("TAM User", run_cmd)

    # If we're already running from the installed location, nothing to do.
    try:
        if exe_path.resolve() == target_exe.resolve():
            return
    except Exception:
        # Fall back to string comparison if resolve fails for any reason.
        if str(exe_path).lower() == str(target_exe).lower():
            return

    # Avoid infinite relaunch loops.
    if "--installed" in sys.argv:
        return

    try:
        os.makedirs(install_dir, exist_ok=True)

        tmp_exe = install_dir / "tam_user.new.exe"
        shutil.copy2(str(exe_path), str(tmp_exe))
        os.replace(str(tmp_exe), str(target_exe))

        # Relaunch from the installed copy so future updates/auto-start are consistent.
        subprocess.Popen([str(target_exe), "--installed"], close_fds=True)
        sys.exit(0)
    except Exception as exc:
        logger.warning("Failed to install to %s: %s", target_exe, exc)


class TAMClient:
    def __init__(self):
        self._shutdown = threading.Event()
        self._config: dict = {}
        self._server_url = ""
        self._tz_str = "Asia/Seoul"
        self._tz = ZoneInfo(self._tz_str)
        self._capture_interval = DEFAULT_CAPTURE_INTERVAL
        self._image_quality = 60
        self._image_max_width = 1920

        self._buffer: LocalBuffer | None = None
        self._uploader: Uploader | None = None
        self._conn_monitor: ConnectionMonitor | None = None
        self._process_monitor = ProcessMonitor()
        self._keylogger: KeyLogger | None = None
        self._tray: TrayIcon | None = None

        self._last_screen_hash = ""
        self._last_process_info: dict | None = None
        self._capture_lock = threading.Lock()
        self._capture_skip_keyboard_idle_sec = 20
        self._capture_wait_max_sec = 480
        self._activity_tracker: ActivityTracker | None = None
        self._idle_threshold_rest_sec = 180
        self._idle_threshold_idle_sec = 420
        self._mouse_listener = None
        self._pending_process_capture_at: float | None = None

    def _now(self) -> str:
        return datetime.now(self._tz).isoformat()

    def _do_registration(self):
        self._tray = TrayIcon(on_name_change_callback=self._handle_name_change)
        reg_info = self._tray.show_registration_dialog()

        if not reg_info:
            logger.error("Registration cancelled. Exiting.")
            sys.exit(0)

        server_ip = reg_info["server_ip"]
        display_name = reg_info["display_name"]

        logger.info("Registering with server %s as '%s'...", server_ip, display_name)
        result = register_with_server(server_ip, 8007, display_name)

        self._config = {
            "server_ip": server_ip,
            "server_port": 8007,
            "user_id": result["user_id"],
            "api_key": result["api_key"],
            "display_name": display_name,
            "local_ip": get_local_ip(),
        }
        save_config(self._config)
        logger.info("Registered successfully. user_id=%s", result["user_id"])

    def _handle_name_change(self, new_name: str):
        if not new_name:
            return
        success = update_display_name(
            self._server_url,
            self._config["api_key"],
            self._config["user_id"],
            new_name,
        )
        if success:
            self._config["display_name"] = new_name
            save_config(self._config)
            if self._tray:
                self._tray.set_current_name(new_name)
            logger.info("Display name changed to '%s'", new_name)

    def _fetch_settings(self):
        try:
            settings = fetch_server_settings(self._server_url, self._config["api_key"])
            if settings.get("timezone"):
                self._tz_str = settings["timezone"]
                self._tz = ZoneInfo(self._tz_str)
            if settings.get("capture_interval"):
                self._capture_interval = int(settings["capture_interval"])
            if settings.get("image_quality"):
                self._image_quality = int(settings["image_quality"])
            if settings.get("image_max_width"):
                self._image_max_width = int(settings["image_max_width"])
            rest = settings.get("idle_threshold_rest")
            idle = settings.get("idle_threshold_idle")
            if rest is not None:
                self._idle_threshold_rest_sec = int(rest)
            if idle is not None:
                self._idle_threshold_idle_sec = int(idle)
            logger.info(
                "Server settings: timezone=%s, capture_interval=%ds, idle_rest=%ds, idle_idle=%ds",
                self._tz_str,
                self._capture_interval,
                self._idle_threshold_rest_sec,
                self._idle_threshold_idle_sec,
            )
        except Exception as exc:
            logger.warning("Could not fetch server settings: %s", exc)

    def _capture_and_upload(self, trigger: str = "periodic"):
        with self._capture_lock:
            try:
                window_info = self._process_monitor.get_active_window_info()
                if (not window_info.get("process_name")) and self._last_process_info:
                    window_info = self._last_process_info
                browser_title = self._process_monitor.get_browser_url() or ""
                screens = capture_all_screens(
                    quality=self._image_quality,
                    max_width=self._image_max_width,
                )

                for monitor_idx, image_bytes, img_hash in screens:
                    metadata = {
                        "id": uuid.uuid4().hex,
                        "user_id": self._config["user_id"],
                        "captured_at": self._now(),
                        "monitor_index": monitor_idx,
                        "image_filename": f"{uuid.uuid4().hex}.jpg",
                        "trigger": trigger,
                        "active_process": window_info.get("process_name", ""),
                        "active_url": browser_title,
                        "window_title": window_info.get("window_title", ""),
                    }
                    self._uploader.upload_screenshot(image_bytes, metadata)
            except Exception as exc:
                logger.error("Capture error: %s", exc)

    def _screen_capture_thread(self):
        logger.info("Screen capture thread started (interval=%ds)", self._capture_interval)
        wait_sec = self._capture_interval
        min_capture_interval = self._capture_interval
        hard_max_interval = self._capture_wait_max_sec
        last_capture_ts = time.time()
        while not self._shutdown.is_set():
            self._shutdown.wait(wait_sec)
            if self._shutdown.is_set():
                break
            try:
                current_hash = compute_screen_hash()
                if current_hash != self._last_screen_hash:
                    self._last_screen_hash = current_hash
                    keyboard_idle = self._activity_tracker.get_keyboard_idle_seconds() if self._activity_tracker else 0
                    process_unchanged = not self._process_monitor.has_process_changed(self._last_process_info)
                    now_ts = time.time()
                    elapsed_since_capture = now_ts - last_capture_ts
                    if keyboard_idle > self._capture_skip_keyboard_idle_sec and process_unchanged:
                        if elapsed_since_capture >= min_capture_interval * 4:
                            self._capture_and_upload(trigger="periodic")
                            last_capture_ts = now_ts
                            wait_sec = self._capture_interval
                        else:
                            wait_sec = min(wait_sec * 2, hard_max_interval)
                    else:
                        self._capture_and_upload(trigger="periodic")
                        last_capture_ts = now_ts
                        wait_sec = self._capture_interval
            except Exception as exc:
                logger.error("Screen capture thread error: %s", exc)
                wait_sec = self._capture_interval

    def _process_monitor_thread(self):
        logger.info("Process monitor thread started")
        while not self._shutdown.is_set():
            try:
                current_info = self._process_monitor.get_active_window_info()

                if self._process_monitor.has_process_changed(self._last_process_info):
                    now = self._now()

                    if self._last_process_info:
                        activity = {
                            "id": uuid.uuid4().hex,
                            "user_id": self._config["user_id"],
                            "process_name": self._last_process_info.get("process_name", ""),
                            "window_title": self._last_process_info.get("window_title", ""),
                            "url": self._process_monitor.get_browser_url() or "",
                            "started_at": self._last_process_info.get("_started_at", now),
                            "ended_at": now,
                        }
                        self._uploader.upload_activity(activity)

                    current_info["_started_at"] = now
                    self._last_process_info = current_info

                    # Schedule a delayed capture 10 seconds after the process/window change.
                    # If the process/window changes again before that, the pending capture
                    # will be replaced and the short-lived window will not be captured.
                    self._pending_process_capture_at = time.time() + 10.0
                else:
                    # No process/window change detected; if there is a pending capture and
                    # the same process/window is still active after the delay, fire it now.
                    if self._pending_process_capture_at is not None:
                        now_ts = time.time()
                        if now_ts >= self._pending_process_capture_at and self._last_process_info:
                            self._capture_and_upload(trigger="process_change")
                            self._pending_process_capture_at = None
            except Exception as exc:
                logger.error("Process monitor error: %s", exc)

            self._shutdown.wait(PROCESS_POLL_INTERVAL)

    def _keystroke_flush_thread(self):
        logger.info("Keystroke flush thread started (interval=%ds)", DEFAULT_KEYSTROKE_FLUSH)
        while not self._shutdown.is_set():
            self._shutdown.wait(DEFAULT_KEYSTROKE_FLUSH)
            if self._shutdown.is_set():
                break
            try:
                entries = self._keylogger.get_and_clear_buffer()
                if entries:
                    for e in entries:
                        e["user_id"] = self._config["user_id"]
                        if "id" not in e:
                            e["id"] = uuid.uuid4().hex
                    self._uploader.upload_keystrokes(entries)
            except Exception as exc:
                logger.error("Keystroke flush error: %s", exc)

    def _heartbeat_thread(self):
        logger.info("Heartbeat thread started (interval=%ds)", HEARTBEAT_INTERVAL)
        while not self._shutdown.is_set():
            self._shutdown.wait(HEARTBEAT_INTERVAL)
            if self._shutdown.is_set():
                break
            try:
                local_ip = get_local_ip()
                window_info = self._process_monitor.get_active_window_info() if self._process_monitor else {}
                if (not window_info.get("process_name")) and self._last_process_info:
                    window_info = self._last_process_info
                idle_sec = self._activity_tracker.get_idle_seconds() if self._activity_tracker else 0
                if idle_sec >= self._idle_threshold_idle_sec:
                    status = "IDLE"
                elif idle_sec >= self._idle_threshold_rest_sec:
                    status = "REST"
                else:
                    status = "ONLINE"
                self._uploader.send_heartbeat(
                    user_id=self._config["user_id"],
                    local_ip=local_ip,
                    status=status,
                    active_process=window_info.get("process_name", ""),
                    active_window=window_info.get("window_title", ""),
                )
            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)

    def _connection_monitor_thread(self):
        logger.info("Connection monitor thread started (interval=%ds)", CONNECTION_CHECK_INTERVAL)
        while not self._shutdown.is_set():
            try:
                online = self._conn_monitor.check_connection()
                if self._tray:
                    self._tray.set_status("recording" if online else "buffering")
            except Exception as exc:
                logger.error("Connection monitor error: %s", exc)
            self._shutdown.wait(CONNECTION_CHECK_INTERVAL)

    def _sync_thread(self):
        logger.info("Sync thread started")
        while not self._shutdown.is_set():
            self._shutdown.wait(10)
            if self._shutdown.is_set():
                break
            try:
                if self._conn_monitor and self._conn_monitor.was_offline:
                    logger.info("Reconnected - syncing buffered data...")
                    counts = self._uploader.sync_buffered_data()
                    if any(v > 0 for v in counts.values()):
                        logger.info("Sync completed: %s", counts)
                    self._conn_monitor.was_offline = False

                unsynced = self._buffer.get_unsynced_count()
                total = sum(unsynced.values())
                if total > 0:
                    counts = self._uploader.sync_buffered_data()
                    if any(v > 0 for v in counts.values()):
                        logger.info("Background sync: %s", counts)
            except Exception as exc:
                logger.error("Sync thread error: %s", exc)

    def run(self):
        logger.info("TAM Client starting...")

        if not is_registered():
            self._do_registration()
        else:
            self._config = load_config()
            self._tray = TrayIcon(on_name_change_callback=self._handle_name_change)

        self._server_url = (
            f"http://{self._config['server_ip']}:{self._config.get('server_port', 8007)}"
        )
        self._tray.set_current_name(self._config.get("display_name", ""))

        alert_configure(
            self._server_url,
            self._config["api_key"],
            self._config["user_id"],
        )
        install_crash_handler()

        self._fetch_settings()

        self._buffer = LocalBuffer()
        self._uploader = Uploader(self._server_url, self._config["api_key"], self._buffer)
        self._conn_monitor = ConnectionMonitor(self._server_url)
        self._conn_monitor.on_reconnect = lambda: None

        self._activity_tracker = ActivityTracker()

        def _on_activity():
            self._activity_tracker.update()

        def _on_keyboard_activity():
            self._activity_tracker.update_keyboard()

        self._keylogger = KeyLogger(
            timezone_str=self._tz_str,
            process_info_callback=self._process_monitor.get_active_window_info,
            on_activity=_on_keyboard_activity,
        )
        self._keylogger.start()

        try:
            from pynput import mouse
            self._mouse_listener = mouse.Listener(
                on_move=lambda *_: _on_activity(),
                on_click=lambda *_: _on_activity(),
                on_scroll=lambda *_: _on_activity(),
            )
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
        except Exception as exc:
            logger.warning("Mouse listener not started (idle detection keyboard-only): %s", exc)

        start_event = {
            "id": uuid.uuid4().hex,
            "user_id": self._config["user_id"],
            "event_type": "APP_START",
            "timestamp": self._now(),
            "details": f"ip={get_local_ip()}",
        }
        self._uploader.upload_event(start_event)

        threads = [
            threading.Thread(target=self._screen_capture_thread, daemon=True, name="capture"),
            threading.Thread(target=self._process_monitor_thread, daemon=True, name="process"),
            threading.Thread(target=self._keystroke_flush_thread, daemon=True, name="keyflush"),
            threading.Thread(target=self._heartbeat_thread, daemon=True, name="heartbeat"),
            threading.Thread(target=self._connection_monitor_thread, daemon=True, name="connmon"),
            threading.Thread(target=self._sync_thread, daemon=True, name="sync"),
        ]

        for t in threads:
            t.start()
            logger.info("Started thread: %s", t.name)

        logger.info("All threads started. Running tray icon on main thread.")
        try:
            self._tray.run()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            self._shutdown.set()
            try:
                send_app_stop()
            except Exception as exc:
                logger.debug("APP_STOP send failed: %s", exc)
            if self._mouse_listener:
                try:
                    self._mouse_listener.stop()
                except Exception:
                    pass
            if self._keylogger:
                self._keylogger.stop()

            remaining = self._keylogger.get_and_clear_buffer()
            if remaining:
                for e in remaining:
                    e["user_id"] = self._config["user_id"]
                    if "id" not in e:
                        e["id"] = uuid.uuid4().hex
                self._buffer.save_keystrokes(remaining)

            logger.info("TAM Client stopped.")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    _ensure_windows_install_and_autostart_user_app()
    client = TAMClient()
    client.run()


if __name__ == "__main__":
    main()
