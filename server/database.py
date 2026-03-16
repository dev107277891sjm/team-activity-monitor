"""
TAM – SQLite database manager.
Single database file: DATA_DIR/tam.db
"""

import os
import glob
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt

DATA_DIR = os.environ.get("DATA_DIR", r"E:\TAM_Data")
DB_PATH = os.path.join(DATA_DIR, "tam.db")

_KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(_KST).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "images"), exist_ok=True)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema & defaults
# ---------------------------------------------------------------------------

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    local_ip     TEXT UNIQUE,
    display_name TEXT,
    registered_at TEXT,
    last_seen    TEXT,
    status       TEXT DEFAULT 'OFFLINE'
);

CREATE TABLE IF NOT EXISTS screenshots (
    id             TEXT PRIMARY KEY,
    user_id        TEXT,
    captured_at    TEXT,
    monitor_index  INTEGER,
    image_path     TEXT,
    trigger        TEXT,
    active_process TEXT,
    active_url     TEXT,
    window_title   TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS keystrokes (
    id             TEXT PRIMARY KEY,
    user_id        TEXT,
    timestamp      TEXT,
    key_data       TEXT,
    active_process TEXT,
    active_window  TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS activities (
    id           TEXT PRIMARY KEY,
    user_id      TEXT,
    process_name TEXT,
    window_title TEXT,
    url          TEXT,
    started_at   TEXT,
    ended_at     TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS events (
    id         TEXT PRIMARY KEY,
    user_id    TEXT,
    event_type TEXT,
    timestamp  TEXT,
    details    TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_DEFAULT_SETTINGS: dict[str, str] = {
    "system_timezone": "Asia/Seoul",
    "capture_interval_sec": "30",
    "keylog_batch_interval": "60",
    "image_quality": "60",
    "image_max_width": "1920",
    "idle_threshold_rest": "5",
    "idle_threshold_idle": "15",
    "heartbeat_interval": "30",
    "offline_threshold": "60",
    "retention_days": "90",
    "capture_on_process_change": "true",
    "skip_unchanged_screen": "true",
    "admin_password_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode(),
    "smtp_server": "",
    "smtp_port": "587",
    "smtp_email": "",
    "smtp_password": "",
    "alert_enabled": "false",
}


def init_db() -> None:
    _ensure_dirs()
    conn = get_db()
    try:
        conn.executescript(_TABLES_SQL)
        for key, value in _DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------

def get_setting(key: str) -> Optional[str]:
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def get_all_settings() -> dict[str, str]:
    conn = get_db()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


def update_setting(key: str, value: str) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Users CRUD
# ---------------------------------------------------------------------------

def create_user(local_ip: str, display_name: str) -> dict[str, str]:
    user_id = _new_id()
    now = _now_iso()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (user_id, local_ip, display_name, registered_at, last_seen, status) "
            "VALUES (?, ?, ?, ?, ?, 'ONLINE')",
            (user_id, local_ip, display_name, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"user_id": user_id, "registered_at": now}


def get_user(user_id: str) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_ip(local_ip: str) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE local_ip=?", (local_ip,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_users() -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY display_name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_user_name(user_id: str, display_name: str) -> bool:
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE users SET display_name=? WHERE user_id=?", (display_name, user_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_user_heartbeat(
    user_id: str,
    local_ip: str,
    status: str,
    active_process: str = "",
    active_window: str = "",
) -> bool:
    now = _now_iso()
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE users SET last_seen=?, local_ip=?, status=? WHERE user_id=?",
            (now, local_ip, status, user_id),
        )
        conn.commit()
        if cur.rowcount > 0:
            add_event(user_id, "heartbeat", json.dumps({
                "status": status,
                "active_process": active_process,
                "active_window": active_window,
            }))
        return cur.rowcount > 0
    finally:
        conn.close()


def set_users_offline(threshold_seconds: int) -> list[str]:
    """Mark users as OFFLINE whose last_seen exceeds the threshold. Returns affected user_ids."""
    cutoff = (datetime.now(_KST) - timedelta(seconds=threshold_seconds)).isoformat()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE status != 'OFFLINE' AND last_seen < ?",
            (cutoff,),
        ).fetchall()
        if rows:
            conn.execute(
                "UPDATE users SET status='OFFLINE' WHERE status != 'OFFLINE' AND last_seen < ?",
                (cutoff,),
            )
            conn.commit()
        return [r["user_id"] for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Screenshots CRUD
# ---------------------------------------------------------------------------

def add_screenshot(
    user_id: str,
    captured_at: str,
    monitor_index: int,
    image_path: str,
    trigger: str,
    active_process: str = "",
    active_url: str = "",
    window_title: str = "",
) -> str:
    sid = _new_id()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO screenshots "
            "(id, user_id, captured_at, monitor_index, image_path, trigger, active_process, active_url, window_title) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, user_id, captured_at, monitor_index, image_path, trigger, active_process, active_url, window_title),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


def get_screenshots(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if user_id:
        conditions.append("user_id=?")
        params.append(user_id)
    if date:
        conditions.append("captured_at LIKE ?")
        params.append(f"{date}%")
    if start_time and date:
        conditions.append("captured_at >= ?")
        params.append(f"{date}T{start_time}")
    if end_time and date:
        conditions.append("captured_at <= ?")
        params.append(f"{date}T{end_time}")

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM screenshots{where}", params).fetchone()["cnt"]
        rows = conn.execute(
            f"SELECT * FROM screenshots{where} ORDER BY captured_at DESC LIMIT ? OFFSET ?",
            params + [limit, (page - 1) * limit],
        ).fetchall()
        return [dict(r) for r in rows], total
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Keystrokes CRUD
# ---------------------------------------------------------------------------

def add_keystrokes(user_id: str, entries: list[dict]) -> int:
    conn = get_db()
    try:
        for e in entries:
            conn.execute(
                "INSERT OR IGNORE INTO keystrokes (id, user_id, timestamp, key_data, active_process, active_window) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    e.get("id", _new_id()),
                    user_id,
                    e["timestamp"],
                    e["key_data"],
                    e.get("active_process", ""),
                    e.get("active_window", ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return len(entries)


def get_keystrokes(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if user_id:
        conditions.append("user_id=?")
        params.append(user_id)
    if date:
        conditions.append("timestamp LIKE ?")
        params.append(f"{date}%")
    if start_time and date:
        conditions.append("timestamp >= ?")
        params.append(f"{date}T{start_time}")
    if end_time and date:
        conditions.append("timestamp <= ?")
        params.append(f"{date}T{end_time}")

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM keystrokes{where}", params).fetchone()["cnt"]
        rows = conn.execute(
            f"SELECT * FROM keystrokes{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, (page - 1) * limit],
        ).fetchall()
        return [dict(r) for r in rows], total
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Activities CRUD
# ---------------------------------------------------------------------------

def add_activities(user_id: str, entries: list[dict]) -> int:
    conn = get_db()
    try:
        for e in entries:
            conn.execute(
                "INSERT OR IGNORE INTO activities (id, user_id, process_name, window_title, url, started_at, ended_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    e.get("id", _new_id()),
                    user_id,
                    e.get("process_name", ""),
                    e.get("window_title", ""),
                    e.get("url", ""),
                    e.get("started_at", ""),
                    e.get("ended_at", ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return len(entries)


def get_activities(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if user_id:
        conditions.append("user_id=?")
        params.append(user_id)
    if date:
        conditions.append("(started_at LIKE ? OR ended_at LIKE ?)")
        params.extend([f"{date}%", f"{date}%"])

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM activities{where}", params).fetchone()["cnt"]
        rows = conn.execute(
            f"SELECT * FROM activities{where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
            params + [limit, (page - 1) * limit],
        ).fetchall()
        return [dict(r) for r in rows], total
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Events CRUD
# ---------------------------------------------------------------------------

def add_event(user_id: str, event_type: str, details: str = "") -> str:
    eid = _new_id()
    now = _now_iso()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO events (id, user_id, event_type, timestamp, details) VALUES (?, ?, ?, ?, ?)",
            (eid, user_id, event_type, now, details),
        )
        conn.commit()
    finally:
        conn.close()
    return eid


def add_events_batch(user_id: str, entries: list[dict]) -> int:
    conn = get_db()
    try:
        for e in entries:
            conn.execute(
                "INSERT OR IGNORE INTO events (id, user_id, event_type, timestamp, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    e.get("id", _new_id()),
                    user_id,
                    e.get("event_type", ""),
                    e.get("timestamp", _now_iso()),
                    e.get("details", ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return len(entries)


def get_events(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if user_id:
        conditions.append("user_id=?")
        params.append(user_id)
    if date:
        conditions.append("timestamp LIKE ?")
        params.append(f"{date}%")

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM events{where}", params).fetchone()["cnt"]
        rows = conn.execute(
            f"SELECT * FROM events{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, (page - 1) * limit],
        ).fetchall()
        return [dict(r) for r in rows], total
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Timeline builder
# ---------------------------------------------------------------------------

def get_timeline(user_id: str, date: str) -> list[dict]:
    """Build timeline segments for a user on a given date from heartbeat events."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, details FROM events "
            "WHERE user_id=? AND event_type='heartbeat' AND timestamp LIKE ? "
            "ORDER BY timestamp ASC",
            (user_id, f"{date}%"),
        ).fetchall()
    finally:
        conn.close()

    segments: list[dict] = []
    for row in rows:
        ts = row["timestamp"]
        try:
            info = json.loads(row["details"])
        except (json.JSONDecodeError, TypeError):
            info = {}
        status = info.get("status", "ONLINE")
        process = info.get("active_process", "")

        if segments and segments[-1]["status"] == status and segments[-1]["process"] == process:
            segments[-1]["end"] = ts
        else:
            segments.append({"start": ts, "end": ts, "status": status, "process": process})

    return segments


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_old_data(days: int) -> dict[str, int]:
    cutoff = (datetime.now(_KST) - timedelta(days=days)).isoformat()
    counts: dict[str, int] = {}
    conn = get_db()
    try:
        # Delete old screenshot files first
        old_shots = conn.execute(
            "SELECT image_path FROM screenshots WHERE captured_at < ?", (cutoff,)
        ).fetchall()
        deleted_files = 0
        for row in old_shots:
            path = row["image_path"]
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    deleted_files += 1
                except OSError:
                    pass
        counts["deleted_image_files"] = deleted_files

        for table, col in [
            ("screenshots", "captured_at"),
            ("keystrokes", "timestamp"),
            ("activities", "started_at"),
            ("events", "timestamp"),
        ]:
            cur = conn.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))
            counts[table] = cur.rowcount

        conn.commit()

        # Remove empty date directories inside images/
        images_root = os.path.join(DATA_DIR, "images")
        if os.path.isdir(images_root):
            for ip_dir in glob.glob(os.path.join(images_root, "*")):
                if not os.path.isdir(ip_dir):
                    continue
                for date_dir in glob.glob(os.path.join(ip_dir, "*")):
                    if os.path.isdir(date_dir) and not os.listdir(date_dir):
                        try:
                            os.rmdir(date_dir)
                        except OSError:
                            pass
    finally:
        conn.close()

    return counts


# ---------------------------------------------------------------------------
# Disk usage helper
# ---------------------------------------------------------------------------

def get_disk_usage() -> dict[str, Any]:
    total_size = 0
    file_count = 0
    for dirpath, _dirnames, filenames in os.walk(DATA_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
                file_count += 1
            except OSError:
                pass
    return {
        "data_dir": DATA_DIR,
        "total_bytes": total_size,
        "total_gb": round(total_size / (1024 ** 3), 3),
        "file_count": file_count,
    }
