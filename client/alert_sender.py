"""Sends APP_STOP, APP_CRASH, APP_KILLED events. Works during shutdown/crash when Uploader may be unavailable."""
import logging
import sys
import threading
import uuid

import requests

try:
    from client.config import load_config, get_local_ip
except ImportError:
    from config import load_config, get_local_ip

logger = logging.getLogger("TAM.alert")

_server_url = ""
_api_key = ""
_user_id = ""


def configure(server_url: str, api_key: str, user_id: str) -> None:
    """Store credentials for sending alert events."""
    global _server_url, _api_key, _user_id
    _server_url = (server_url or "").rstrip("/")
    _api_key = api_key or ""
    _user_id = user_id or ""


def _send_event(event_type: str, details: str) -> bool:
    """Send event to server. Returns True if sent successfully."""
    server_url = _server_url
    api_key = _api_key
    user_id = _user_id

    if not all([server_url, api_key, user_id]):
        cfg = load_config()
        if not cfg:
            return False
        server_url = f"http://{cfg.get('server_ip', '')}:{cfg.get('server_port', 8007)}"
        api_key = cfg.get("api_key", "")
        user_id = cfg.get("user_id", "")

    if not all([server_url, api_key, user_id]):
        return False

    entry = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": _now(),
        "details": details,
    }

    try:
        resp = requests.post(
            f"{server_url}/api/events",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"user_id": user_id, "entries": [entry]},
            timeout=3,
        )
        return resp.status_code in (200, 201)
    except Exception as exc:
        logger.debug("Alert send failed: %s", exc)
        return False


def _now() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat()


def send_app_stop() -> bool:
    """Send APP_STOP (graceful shutdown)."""
    return _send_event("APP_STOP", f"ip={get_local_ip()}")


def send_app_crash(exc_type=None, exc_value=None, exc_tb=None) -> bool:
    """Send APP_CRASH (unhandled exception)."""
    details = f"ip={get_local_ip()}"
    if exc_type and exc_value:
        details += f" | {exc_type.__name__}: {exc_value}"
    return _send_event("APP_CRASH", details[:500])


_original_excepthook = sys.excepthook
_original_thread_excepthook = getattr(threading, "excepthook", None)


def _crash_excepthook(exc_type, exc_value, exc_tb):
    """Called on unhandled exception in main thread."""
    send_app_crash(exc_type, exc_value, exc_tb)
    if _original_excepthook:
        _original_excepthook(exc_type, exc_value, exc_tb)


def _thread_excepthook(args):
    """Called on unhandled exception in a thread (Python 3.8+)."""
    send_app_crash(args.exc_type, args.exc_value, None)
    if _original_thread_excepthook:
        _original_thread_excepthook(args)


def install_crash_handler() -> None:
    """Install global exception handlers to send APP_CRASH on unhandled exceptions."""
    sys.excepthook = _crash_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook
