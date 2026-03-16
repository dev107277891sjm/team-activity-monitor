import logging
import sys
import threading
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

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


class TAMClient:
    def __init__(self):
        self._shutdown = threading.Event()
        self._config: dict = {}
        self._server_url = ""
        self._tz_str = "Asia/Seoul"
        self._tz = ZoneInfo(self._tz_str)
        self._capture_interval = DEFAULT_CAPTURE_INTERVAL

        self._buffer: LocalBuffer | None = None
        self._uploader: Uploader | None = None
        self._conn_monitor: ConnectionMonitor | None = None
        self._process_monitor = ProcessMonitor()
        self._keylogger: KeyLogger | None = None
        self._tray: TrayIcon | None = None

        self._last_screen_hash = ""
        self._last_process_info: dict | None = None
        self._capture_lock = threading.Lock()

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
            logger.info(
                "Server settings: timezone=%s, capture_interval=%ds",
                self._tz_str,
                self._capture_interval,
            )
        except Exception as exc:
            logger.warning("Could not fetch server settings: %s", exc)

    def _capture_and_upload(self, trigger: str = "periodic"):
        with self._capture_lock:
            try:
                window_info = self._process_monitor.get_active_window_info()
                browser_url = self._process_monitor.get_browser_url() or ""
                screens = capture_all_screens()

                for monitor_idx, image_bytes, img_hash in screens:
                    metadata = {
                        "id": uuid.uuid4().hex,
                        "user_id": self._config["user_id"],
                        "captured_at": self._now(),
                        "monitor_index": monitor_idx,
                        "image_filename": f"{uuid.uuid4().hex}.jpg",
                        "trigger": trigger,
                        "active_process": window_info.get("process_name", ""),
                        "active_url": browser_url,
                        "window_title": window_info.get("window_title", ""),
                    }
                    self._uploader.upload_screenshot(image_bytes, metadata)
            except Exception as exc:
                logger.error("Capture error: %s", exc)

    def _screen_capture_thread(self):
        logger.info("Screen capture thread started (interval=%ds)", self._capture_interval)
        while not self._shutdown.is_set():
            try:
                current_hash = compute_screen_hash()
                if current_hash != self._last_screen_hash:
                    self._last_screen_hash = current_hash
                    self._capture_and_upload(trigger="periodic")
            except Exception as exc:
                logger.error("Screen capture thread error: %s", exc)
            self._shutdown.wait(self._capture_interval)

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

                    self._capture_and_upload(trigger="process_change")
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
                event = {
                    "id": uuid.uuid4().hex,
                    "user_id": self._config["user_id"],
                    "event_type": "HEARTBEAT",
                    "timestamp": self._now(),
                    "details": f"ip={get_local_ip()}",
                }
                self._uploader.upload_event(event)
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

        self._fetch_settings()

        self._buffer = LocalBuffer()
        self._uploader = Uploader(self._server_url, self._config["api_key"], self._buffer)
        self._conn_monitor = ConnectionMonitor(self._server_url)
        self._conn_monitor.on_reconnect = lambda: None

        self._keylogger = KeyLogger(
            timezone_str=self._tz_str,
            process_info_callback=self._process_monitor.get_active_window_info,
        )
        self._keylogger.start()

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
    import os
    os.makedirs(DATA_DIR, exist_ok=True)
    client = TAMClient()
    client.run()


if __name__ == "__main__":
    main()
