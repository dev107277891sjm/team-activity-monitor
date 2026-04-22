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
    "idle_threshold_rest": "180",
    "idle_threshold_idle": "420",
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


_TIMELINE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_screenshots_user_captured ON screenshots(user_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_activities_user_started ON activities(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_keystrokes_user_ts ON keystrokes(user_id, timestamp);
"""


def init_db() -> None:
    _ensure_dirs()
    conn = get_db()
    try:
        conn.executescript(_TABLES_SQL)
        conn.executescript(_TIMELINE_INDEX_SQL)
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


def get_screenshot_by_id(screenshot_id: str) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM screenshots WHERE id=?", (screenshot_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_screenshots_for_date(date: str) -> int:
    """COUNT(*) for screenshots on a calendar day (same filter as get_screenshots date=)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM screenshots WHERE captured_at LIKE ?",
            (f"{date}%",),
        ).fetchone()
        return int(row["cnt"] or 0) if row else 0
    finally:
        conn.close()


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


def _parse_iso_naive(ts: str) -> "datetime":
    """Parse ISO timestamp, strip timezone/fractional for comparison."""
    clean = ts.split(".")[0].split("+")[0]
    if clean.endswith("Z"):
        clean = clean[:-1]
    idx = clean.rfind("-")
    if idx > 10:
        clean = clean[:idx]
    return datetime.fromisoformat(clean)


def get_keystrokes_grouped(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Group keystrokes by process+window within 10-second windows."""
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
        rows = conn.execute(
            f"SELECT timestamp, key_data, active_process, active_window FROM keystrokes{where} ORDER BY timestamp ASC",
            params,
        ).fetchall()

        GAP_SEC = 10
        groups: list[dict] = []
        for r in rows:
            ts = r["timestamp"]
            key = r["key_data"] or ""
            proc = r["active_process"] or ""
            win = r["active_window"] or ""

            merged = False
            if groups:
                g = groups[-1]
                if g["active_process"] == proc and g["active_window"] == win:
                    try:
                        t1 = _parse_iso_naive(g["end_time"])
                        t2 = _parse_iso_naive(ts)
                        if (t2 - t1).total_seconds() <= GAP_SEC:
                            g["keys"] += key
                            g["end_time"] = ts
                            g["count"] += 1
                            merged = True
                    except Exception:
                        pass

            if not merged:
                groups.append({
                    "start_time": ts,
                    "end_time": ts,
                    "active_process": proc,
                    "active_window": win,
                    "keys": key,
                    "count": 1,
                })

        groups.reverse()
        total = len(groups)
        offset = (page - 1) * limit
        paged = groups[offset:offset + limit]
        return paged, total
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

_MAX_TIMELINE_SCREENSHOT_POINTS = 1600


def _fetch_timeline_screenshot_rows(conn: sqlite3.Connection, user_id: str, date_prefix: str) -> list[sqlite3.Row]:
    """Return screenshot rows for timeline; subsample when count is huge (same-day captures)."""
    cnt_row = conn.execute(
        "SELECT COUNT(*) AS c FROM screenshots WHERE user_id=? AND captured_at LIKE ?",
        (user_id, date_prefix),
    ).fetchone()
    cnt = int(cnt_row["c"] or 0) if cnt_row else 0
    if cnt <= _MAX_TIMELINE_SCREENSHOT_POINTS:
        return conn.execute(
            "SELECT captured_at, active_process, trigger FROM screenshots "
            "WHERE user_id=? AND captured_at LIKE ? ORDER BY captured_at ASC",
            (user_id, date_prefix),
        ).fetchall()
    # ceil(cnt / max) so step >= 2 when cnt > max (avoid step=1 which would select every row)
    step = (cnt + _MAX_TIMELINE_SCREENSHOT_POINTS - 1) // _MAX_TIMELINE_SCREENSHOT_POINTS
    return conn.execute(
        """
        WITH ordered AS (
            SELECT captured_at, active_process, trigger,
                   ROW_NUMBER() OVER (ORDER BY captured_at ASC) AS rn
            FROM screenshots
            WHERE user_id=? AND captured_at LIKE ?
        ),
        mx AS (SELECT MAX(rn) AS m FROM ordered)
        SELECT ordered.captured_at, ordered.active_process, ordered.trigger
        FROM ordered, mx
        WHERE ordered.rn = 1 OR ordered.rn = mx.m OR ((ordered.rn - 1) % ? = 0)
        ORDER BY ordered.captured_at ASC
        """,
        (user_id, date_prefix, step),
    ).fetchall()


def get_timeline(user_id: str, date: str) -> dict:
    """Build timeline segments and events for a user on a given date from all data sources."""
    date_prefix = f"{date}%"
    day_start_str = f"{date}T00:00:00"
    day_end_str = f"{date}T23:59:59"

    settings = get_all_settings()
    offline_threshold_sec = int(settings.get("offline_threshold") or _DEFAULT_SETTINGS.get("offline_threshold", "60"))
    idle_threshold_rest_sec = int(settings.get("idle_threshold_rest") or _DEFAULT_SETTINGS.get("idle_threshold_rest", "180"))

    conn = get_db()
    keystroke_count = 0
    try:
        timestamps: list[tuple[str, str, str]] = []

        shot_rows = _fetch_timeline_screenshot_rows(conn, user_id, date_prefix)
        for r in shot_rows:
            timestamps.append((r["captured_at"], r["active_process"] or "", "ONLINE"))

        act_rows = conn.execute(
            "SELECT started_at, ended_at, process_name FROM activities "
            "WHERE user_id=? AND ("
            "  started_at LIKE ? OR ended_at LIKE ?"
            "  OR (started_at < ? AND ended_at > ?)"
            ") ORDER BY started_at ASC",
            (user_id, date_prefix, date_prefix, day_start_str, day_start_str),
        ).fetchall()
        for r in act_rows:
            sa = r["started_at"] or ""
            ea = r["ended_at"] or ""
            proc = r["process_name"] or ""
            if sa and sa < day_start_str:
                sa = day_start_str
            if ea and ea > day_end_str:
                ea = day_end_str
            if sa:
                timestamps.append((sa, proc, "ONLINE"))
            if ea:
                timestamps.append((ea, proc, "ONLINE"))

        ks_rows = conn.execute(
            "SELECT MIN(timestamp) as first_ts, MAX(timestamp) as last_ts FROM keystrokes "
            "WHERE user_id=? AND timestamp LIKE ?",
            (user_id, date_prefix),
        ).fetchone()
        if ks_rows and ks_rows["first_ts"]:
            timestamps.append((ks_rows["first_ts"], "", "ONLINE"))
            timestamps.append((ks_rows["last_ts"], "", "ONLINE"))

        hb_rows = conn.execute(
            "SELECT timestamp, details FROM events "
            "WHERE user_id=? AND LOWER(event_type) IN ('heartbeat','app_start') AND timestamp LIKE ? "
            "ORDER BY timestamp ASC",
            (user_id, date_prefix),
        ).fetchall()
        for r in hb_rows:
            det = r["details"] or ""
            try:
                info = json.loads(det) if det.startswith("{") else {}
            except (json.JSONDecodeError, TypeError):
                info = {}
            proc = info.get("active_process", "")
            status = info.get("status", "ONLINE")
            timestamps.append((r["timestamp"], proc, status))

        # Omit heartbeats from marker list (UI skips them; cuts payload size on busy days).
        event_rows = conn.execute(
            "SELECT event_type, timestamp, details FROM events "
            "WHERE user_id=? AND timestamp LIKE ? AND LOWER(event_type) NOT IN ('heartbeat') "
            "ORDER BY timestamp ASC",
            (user_id, date_prefix),
        ).fetchall()
        events_out = [
            {"event_type": r["event_type"], "timestamp": r["timestamp"], "details": r["details"]}
            for r in event_rows
        ]

        keystroke_count = 0
        try:
            kc_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM keystrokes WHERE user_id=? AND timestamp LIKE ?",
                (user_id, date_prefix),
            ).fetchone()
            keystroke_count = kc_row["cnt"] if kc_row else 0
        except Exception:
            pass
    finally:
        conn.close()

    timestamps.sort(key=lambda x: x[0])

    GAP_SECONDS = 180
    raw_segments: list[dict] = []
    for ts, proc, status in timestamps:
        if raw_segments:
            try:
                t1 = _parse_iso_naive(raw_segments[-1]["end"])
                t2 = _parse_iso_naive(ts)
                gap = (t2 - t1).total_seconds()
            except Exception:
                gap = GAP_SECONDS + 1

            prev_status = (raw_segments[-1].get("status") or "ONLINE").upper()
            curr_status = (status or "ONLINE").upper()
            if gap <= GAP_SECONDS and prev_status == curr_status:
                raw_segments[-1]["end"] = ts
                if proc:
                    raw_segments[-1]["process"] = proc
                continue

        raw_segments.append({"start": ts, "end": ts, "status": status, "process": proc})

    day_start_dt = _parse_iso_naive(day_start_str)
    day_end_dt = _parse_iso_naive(day_end_str)

    def _clamp_ts(ts_str: str) -> "datetime":
        try:
            t = _parse_iso_naive(ts_str)
            if t < day_start_dt:
                return day_start_dt
            if t > day_end_dt:
                return day_end_dt
            return t
        except Exception:
            return day_start_dt

    def _ts_to_str(dt: "datetime") -> str:
        return f"{date}T{dt.strftime('%H:%M:%S')}"

    final_segments: list[dict] = []
    for i, seg in enumerate(raw_segments):
        if i > 0:
            prev_end = _clamp_ts(raw_segments[i - 1]["end"])
            seg_start = _clamp_ts(seg["start"])
            gap_sec = (seg_start - prev_end).total_seconds()
            if gap_sec > 0:
                if gap_sec >= offline_threshold_sec:
                    final_segments.append({
                        "start": _ts_to_str(prev_end),
                        "end": _ts_to_str(seg_start),
                        "status": "OFFLINE",
                        "process": "",
                    })
                else:
                    gap_status = "IDLE" if gap_sec >= idle_threshold_rest_sec else "REST"
                    final_segments.append({
                        "start": _ts_to_str(prev_end),
                        "end": _ts_to_str(seg_start),
                        "status": gap_status,
                        "process": "",
                    })
        seg_start = _clamp_ts(seg["start"])
        seg_end = _clamp_ts(seg["end"])
        if seg_end <= seg_start or (seg_end - seg_start).total_seconds() < 30:
            seg_end = min(seg_start + timedelta(seconds=60), day_end_dt)
        if seg_start < seg_end:
            final_segments.append({
                "start": _ts_to_str(seg_start),
                "end": _ts_to_str(seg_end),
                "status": seg.get("status", "ONLINE"),
                "process": seg.get("process", ""),
            })

    work_sec = rest_sec = idle_sec = offline_sec = 0
    for seg in final_segments:
        try:
            s = _parse_iso_naive(seg["start"])
            e = _parse_iso_naive(seg["end"])
            dur = (e - s).total_seconds()
        except Exception:
            dur = 0
        st = (seg.get("status") or "").upper()
        if st in ("WORKING", "ACTIVE", "ONLINE") or "ALERT" in st:
            work_sec += dur
        elif st == "REST":
            rest_sec += dur
        elif st == "IDLE":
            idle_sec += dur
        else:
            offline_sec += dur

    summary = {
        "work_seconds": int(work_sec),
        "rest_seconds": int(rest_sec),
        "idle_seconds": int(idle_sec),
        "offline_seconds": int(offline_sec),
        "keystroke_count": keystroke_count,
    }

    return {"segments": final_segments, "events": events_out, "summary": summary}


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
