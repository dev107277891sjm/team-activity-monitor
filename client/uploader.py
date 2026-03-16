import os
import logging

import requests

try:
    from client.buffer import LocalBuffer
except ImportError:
    from buffer import LocalBuffer

logger = logging.getLogger("TAM.uploader")


class Uploader:
    def __init__(self, server_url: str, api_key: str, buffer: LocalBuffer):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.buffer = buffer
        self._timeout = 15

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def send_heartbeat(self, user_id: str, local_ip: str, status: str = "ONLINE",
                       active_process: str = "", active_window: str = "") -> bool:
        try:
            resp = requests.post(
                f"{self.server_url}/api/heartbeat",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "user_id": user_id,
                    "local_ip": local_ip,
                    "status": status,
                    "active_process": active_process,
                    "active_window": active_window,
                },
                timeout=self._timeout,
            )
            return resp.status_code in (200, 201)
        except requests.RequestException as exc:
            logger.debug("Heartbeat error: %s", exc)
            return False

    def upload_screenshot(self, image_bytes: bytes, metadata: dict) -> bool:
        import json as _json
        try:
            files = {"image": (metadata.get("image_filename", "screen.jpg"), image_bytes, "image/jpeg")}
            meta_json = _json.dumps({k: v for k, v in metadata.items() if k != "image_filename"})
            resp = requests.post(
                f"{self.server_url}/api/screenshots",
                headers=self._headers(),
                files=files,
                data={"metadata": meta_json},
                timeout=self._timeout,
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning("Screenshot upload failed: %s %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.warning("Screenshot upload error: %s", exc)

        self.buffer.save_screenshot(metadata, image_bytes)
        return False

    def upload_keystrokes(self, entries: list[dict]) -> bool:
        if not entries:
            return True
        user_id = entries[0].get("user_id", "") if entries else ""
        try:
            resp = requests.post(
                f"{self.server_url}/api/keystrokes",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"user_id": user_id, "entries": entries},
                timeout=self._timeout,
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning("Keystroke upload failed: %s %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.warning("Keystroke upload error: %s", exc)

        self.buffer.save_keystrokes(entries)
        return False

    def upload_activity(self, entry: dict) -> bool:
        user_id = entry.get("user_id", "")
        try:
            resp = requests.post(
                f"{self.server_url}/api/activities",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"user_id": user_id, "entries": [entry]},
                timeout=self._timeout,
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning("Activity upload failed: %s %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.warning("Activity upload error: %s", exc)

        self.buffer.save_activity(entry)
        return False

    def upload_event(self, entry: dict) -> bool:
        user_id = entry.get("user_id", "")
        try:
            resp = requests.post(
                f"{self.server_url}/api/events",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"user_id": user_id, "entries": [entry]},
                timeout=self._timeout,
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning("Event upload failed: %s %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.warning("Event upload error: %s", exc)

        self.buffer.save_event(entry)
        return False

    def sync_buffered_data(self) -> dict:
        import json as _json
        counts = {"screenshots": 0, "keystrokes": 0, "activities": 0, "events": 0}

        for meta, img_path in self.buffer.get_unsynced_screenshots(limit=10):
            try:
                if not os.path.exists(img_path):
                    self.buffer.mark_synced("buffered_screenshots", [meta["id"]])
                    continue
                with open(img_path, "rb") as f:
                    image_bytes = f.read()
                files = {"image": (meta.get("image_filename", "screen.jpg"), image_bytes, "image/jpeg")}
                meta_json = _json.dumps({k: v for k, v in meta.items() if k not in ("image_filename", "synced")})
                resp = requests.post(
                    f"{self.server_url}/api/screenshots",
                    headers=self._headers(),
                    files=files,
                    data={"metadata": meta_json},
                    timeout=self._timeout,
                )
                if resp.status_code in (200, 201):
                    self.buffer.mark_synced("buffered_screenshots", [meta["id"]])
                    counts["screenshots"] += 1
            except Exception as exc:
                logger.debug("Sync screenshot error: %s", exc)
                break

        for entry in self.buffer.get_unsynced_keystrokes(limit=50):
            try:
                payload = {k: v for k, v in entry.items() if k != "synced"}
                user_id = payload.get("user_id", "")
                resp = requests.post(
                    f"{self.server_url}/api/keystrokes",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"user_id": user_id, "entries": [payload]},
                    timeout=self._timeout,
                )
                if resp.status_code in (200, 201):
                    self.buffer.mark_synced("buffered_keystrokes", [entry["id"]])
                    counts["keystrokes"] += 1
            except Exception as exc:
                logger.debug("Sync keystroke error: %s", exc)
                break

        for entry in self.buffer.get_unsynced_activities(limit=50):
            try:
                payload = {k: v for k, v in entry.items() if k != "synced"}
                user_id = payload.get("user_id", "")
                resp = requests.post(
                    f"{self.server_url}/api/activities",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"user_id": user_id, "entries": [payload]},
                    timeout=self._timeout,
                )
                if resp.status_code in (200, 201):
                    self.buffer.mark_synced("buffered_activities", [entry["id"]])
                    counts["activities"] += 1
            except Exception as exc:
                logger.debug("Sync activity error: %s", exc)
                break

        for entry in self.buffer.get_unsynced_events(limit=50):
            try:
                payload = {k: v for k, v in entry.items() if k != "synced"}
                user_id = payload.get("user_id", "")
                resp = requests.post(
                    f"{self.server_url}/api/events",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"user_id": user_id, "entries": [payload]},
                    timeout=self._timeout,
                )
                if resp.status_code in (200, 201):
                    self.buffer.mark_synced("buffered_events", [entry["id"]])
                    counts["events"] += 1
            except Exception as exc:
                logger.debug("Sync event error: %s", exc)
                break

        self.buffer.delete_synced()
        return counts
