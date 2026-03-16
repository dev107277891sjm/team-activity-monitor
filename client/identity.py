import socket
import logging

import requests

logger = logging.getLogger("TAM.identity")


def detect_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def register_with_server(server_ip: str, server_port: int, display_name: str) -> dict:
    url = f"http://{server_ip}:{server_port}/api/register"
    local_ip = detect_local_ip()

    payload = {
        "display_name": display_name,
        "local_ip": local_ip,
    }

    resp = requests.post(url, json=payload, timeout=10)

    if resp.status_code not in (200, 201):
        raise Exception(f"Registration failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    if "user_id" not in data or "api_key" not in data:
        raise Exception(f"Invalid registration response: {data}")

    return {
        "user_id": data["user_id"],
        "api_key": data["api_key"],
    }


def update_display_name(server_url: str, api_key: str, user_id: str, new_name: str) -> bool:
    try:
        resp = requests.put(
            f"{server_url}/api/users/{user_id}",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"display_name": new_name},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except requests.RequestException as exc:
        logger.error("Failed to update display name: %s", exc)
        return False


def fetch_server_settings(server_url: str, api_key: str) -> dict:
    try:
        resp = requests.get(
            f"{server_url}/api/settings",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch server settings: %s", exc)
    return {}
