import os
import json
import socket
import uuid
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DATA_DIR = r"C:\ProgramData\TAM"

_AES_PASSPHRASE = b"TAM-2025-OceanTeam-Config-Key!@#"

def _get_fernet() -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"TAM_static_salt_v1",
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(_AES_PASSPHRASE))
    return Fernet(key)


def _config_path() -> str:
    return os.path.join(DATA_DIR, "config.json")


def load_config() -> dict | None:
    path = _config_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            encrypted = f.read()
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        return None


def save_config(config: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    fernet = _get_fernet()
    data = json.dumps(config, ensure_ascii=False).encode("utf-8")
    encrypted = fernet.encrypt(data)
    with open(_config_path(), "wb") as f:
        f.write(encrypted)


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _device_id_path() -> str:
    return os.path.join(DATA_DIR, "device_id")


def get_or_create_device_id() -> str:
    """Stable per-installation identifier, independent of local_ip (which can change or
    be reassigned to a different PC by DHCP). Used by the server to tell devices apart
    instead of relying on IP address, which caused users' identities to get mixed up."""
    path = _device_id_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = f.read().strip()
            if existing:
                return existing
    except Exception:
        pass

    new_id = uuid.uuid4().hex
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_id)
    except Exception:
        pass
    return new_id


def is_registered() -> bool:
    cfg = load_config()
    if cfg is None:
        return False
    return all(k in cfg and cfg[k] for k in ("user_id", "api_key", "server_ip"))
