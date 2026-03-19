"""
TAM – FastAPI server application.
Run from project root:  python -m server.app
"""

import asyncio
import json
import os
import secrets
import shutil
import sys
import uuid
from pathlib import Path
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from server.database import (
        DATA_DIR, add_activities, add_events_batch, add_keystrokes,
        add_screenshot, cleanup_old_data, create_user, get_activities,
        get_all_settings, get_all_users, get_disk_usage, get_events,
        get_keystrokes, get_keystrokes_grouped, get_screenshots,
        get_setting, get_timeline,
        get_user, get_user_by_ip, init_db, set_users_offline,
        update_setting, update_user_heartbeat, update_user_name,
    )
except ImportError:
    from database import (
        DATA_DIR, add_activities, add_events_batch, add_keystrokes,
        add_screenshot, cleanup_old_data, create_user, get_activities,
        get_all_settings, get_all_users, get_disk_usage, get_events,
        get_keystrokes, get_keystrokes_grouped, get_screenshots,
        get_setting, get_timeline,
        get_user, get_user_by_ip, init_db, set_users_offline,
        update_setting, update_user_heartbeat, update_user_name,
    )

_KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# API key store  (persisted to DATA_DIR/api_keys.json)
# ---------------------------------------------------------------------------
_API_KEYS_PATH = os.path.join(DATA_DIR, "api_keys.json")
_api_keys: dict[str, str] = {}  # api_key -> user_id


def _load_api_keys() -> None:
    global _api_keys
    if os.path.isfile(_API_KEYS_PATH):
        with open(_API_KEYS_PATH, "r", encoding="utf-8") as f:
            _api_keys = json.load(f)
    else:
        _api_keys = {}


def _save_api_keys() -> None:
    os.makedirs(os.path.dirname(_API_KEYS_PATH), exist_ok=True)
    with open(_API_KEYS_PATH, "w", encoding="utf-8") as f:
        json.dump(_api_keys, f, indent=2)


def _generate_api_key(user_id: str) -> str:
    key = secrets.token_hex(32)
    _api_keys[key] = user_id
    _save_api_keys()
    return key


# ---------------------------------------------------------------------------
# Session store  (in-memory)
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}  # token -> {"created": iso}


def _create_session() -> str:
    token = secrets.token_hex(32)
    _sessions[token] = {"created": datetime.now(_KST).isoformat()}
    return token


def _verify_session(token: Optional[str]) -> bool:
    return token is not None and token in _sessions


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def require_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Returns the user_id linked to the API key."""
    if not x_api_key or x_api_key not in _api_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return _api_keys[x_api_key]


def require_admin(tam_session: Optional[str] = Cookie(None)) -> bool:
    if not _verify_session(tam_session):
        raise HTTPException(status_code=401, detail="Admin login required")
    return True


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _offline_checker() -> None:
    """Periodically mark users offline when heartbeat lapses."""
    while True:
        try:
            threshold = int(get_setting("offline_threshold") or "60")
            went_offline = set_users_offline(threshold)
            if went_offline:
                alert_enabled = get_setting("alert_enabled") == "true"
                if alert_enabled:
                    _send_offline_alert(went_offline)
        except Exception:
            pass
        await asyncio.sleep(30)


async def _daily_cleanup() -> None:
    """Delete data older than retention_days once per day."""
    while True:
        try:
            days = int(get_setting("retention_days") or "90")
            cleanup_old_data(days)
        except Exception:
            pass
        await asyncio.sleep(86400)


def _send_offline_alert(user_ids: list[str]) -> None:
    """Placeholder: send email alerts for users that went offline."""
    smtp_server = get_setting("smtp_server") or ""
    if not smtp_server:
        return
    # Email sending can be implemented when SMTP settings are configured.


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _load_api_keys()

    os.makedirs(os.path.join(DATA_DIR, "images"), exist_ok=True)

    task_offline = asyncio.create_task(_offline_checker())
    task_cleanup = asyncio.create_task(_daily_cleanup())

    print("=" * 60)
    print("  TAM Server running")
    print(f"  URL:  http://0.0.0.0:8007")
    print(f"  Data: {DATA_DIR}")
    print("=" * 60)

    yield

    task_offline.cancel()
    task_cleanup.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="TAM Server", version="1.0.0", lifespan=lifespan)

# Static files — handle PyInstaller _MEIPASS for bundled .exe
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
_STATIC_DIR = os.path.join(_BASE, "server", "static") if hasattr(sys, "_MEIPASS") else os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_STATIC_DIR, exist_ok=True)

_IMAGES_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(_IMAGES_DIR, exist_ok=True)

app.mount("/images", StaticFiles(directory=_IMAGES_DIR), name="images")

# Mount static last so API routes take precedence
# (deferred to after all routes are registered — see bottom of file)


# ===================================================================
#  PUBLIC / USER-APP ROUTES
# ===================================================================

@app.get("/ping")
async def ping():
    tz = get_setting("system_timezone") or "Asia/Seoul"
    return {"status": "ok", "timestamp": datetime.now(_KST).isoformat(), "timezone": tz}


@app.post("/api/register")
async def register(request: Request):
    body = await request.json()
    local_ip: str = body.get("local_ip", "")
    display_name: str = body.get("display_name", local_ip)

    if not local_ip:
        raise HTTPException(status_code=400, detail="local_ip is required")

    existing = get_user_by_ip(local_ip)
    if existing:
        # Re-register: return existing credentials
        for key, uid in _api_keys.items():
            if uid == existing["user_id"]:
                return {"user_id": existing["user_id"], "api_key": key}
        api_key = _generate_api_key(existing["user_id"])
        return {"user_id": existing["user_id"], "api_key": api_key}

    result = create_user(local_ip, display_name)
    api_key = _generate_api_key(result["user_id"])
    return {"user_id": result["user_id"], "api_key": api_key}


@app.put("/api/users/{user_id}/name")
async def change_name(user_id: str, request: Request, _uid: str = Depends(require_api_key)):
    body = await request.json()
    display_name = body.get("display_name", "")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")
    if not update_user_name(user_id, display_name):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@app.get("/api/settings")
async def public_settings(_uid: str = Depends(require_api_key)):
    settings = get_all_settings()
    # Strip sensitive keys
    safe = {k: v for k, v in settings.items() if "password" not in k and "smtp" not in k}
    return safe


@app.post("/api/heartbeat")
async def heartbeat(request: Request, _uid: str = Depends(require_api_key)):
    body = await request.json()
    user_id = body.get("user_id", "")
    local_ip = body.get("local_ip", "")
    status = body.get("status", "ONLINE")
    active_process = body.get("active_process", "")
    active_window = body.get("active_window", "")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not update_user_heartbeat(user_id, local_ip, status, active_process, active_window):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@app.post("/api/screenshots")
async def upload_screenshot(
    image: UploadFile = File(...),
    metadata: str = Form(...),
    _uid: str = Depends(require_api_key),
):
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    user_id = meta.get("user_id", "")
    captured_at = meta.get("captured_at", datetime.now(_KST).isoformat())
    monitor_index = meta.get("monitor_index", 0)
    trigger = meta.get("trigger", "interval")
    active_process = meta.get("active_process", "")
    active_url = meta.get("active_url", "")
    window_title = meta.get("window_title", "")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required in metadata")

    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    local_ip = user["local_ip"].replace(".", "_").replace(":", "_")

    try:
        ts = datetime.fromisoformat(captured_at)
    except ValueError:
        ts = datetime.now(_KST)

    date_str = ts.strftime("%Y-%m-%d")
    time_str = ts.strftime("%H%M%S")

    save_dir = os.path.join(DATA_DIR, "images", local_ip, date_str)
    os.makedirs(save_dir, exist_ok=True)

    filename = f"{time_str}_mon{monitor_index}.jpg"
    save_path = os.path.join(save_dir, filename)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    relative_path = f"/images/{local_ip}/{date_str}/{filename}"

    sid = add_screenshot(
        user_id=user_id,
        captured_at=captured_at,
        monitor_index=monitor_index,
        image_path=relative_path,
        trigger=trigger,
        active_process=active_process,
        active_url=active_url,
        window_title=window_title,
    )
    return {"ok": True, "screenshot_id": sid, "path": relative_path}


@app.post("/api/keystrokes")
async def upload_keystrokes(request: Request, _uid: str = Depends(require_api_key)):
    body = await request.json()
    user_id = body.get("user_id", "")
    entries = body.get("entries", [])
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    count = add_keystrokes(user_id, entries)
    return {"ok": True, "count": count}


@app.post("/api/activities")
async def upload_activities(request: Request, _uid: str = Depends(require_api_key)):
    body = await request.json()
    user_id = body.get("user_id", "")
    entries = body.get("entries", [])
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    count = add_activities(user_id, entries)
    return {"ok": True, "count": count}


@app.post("/api/events")
async def upload_events(request: Request, _uid: str = Depends(require_api_key)):
    body = await request.json()
    user_id = body.get("user_id", "")
    entries = body.get("entries", [])
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    count = add_events_batch(user_id, entries)
    return {"ok": True, "count": count}


# ===================================================================
#  ADMIN ROUTES
# ===================================================================

@app.post("/api/admin/login")
async def admin_login(request: Request):
    body = await request.json()
    password = body.get("password", "")
    stored_hash = get_setting("admin_password_hash") or ""

    if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = _create_session()
    resp = JSONResponse({"ok": True})
    resp.set_cookie(key="tam_session", value=token, httponly=True, samesite="lax", max_age=86400)
    return resp


@app.get("/api/admin/logout")
async def admin_logout(tam_session: Optional[str] = Cookie(None)):
    if tam_session and tam_session in _sessions:
        del _sessions[tam_session]
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("tam_session")
    return resp


@app.get("/api/admin/users")
async def admin_users(_admin: bool = Depends(require_admin)):
    return get_all_users()


@app.get("/api/admin/timeline/{user_id}")
async def admin_timeline(
    user_id: str,
    date: str = "",
    _admin: bool = Depends(require_admin),
):
    if not date:
        date = datetime.now(_KST).strftime("%Y-%m-%d")
    return get_timeline(user_id, date)


@app.get("/api/admin/screenshots")
async def admin_screenshots(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    _admin: bool = Depends(require_admin),
):
    items, total = get_screenshots(user_id, date, start_time, end_time, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.get("/api/admin/keystrokes")
async def admin_keystrokes(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    grouped: bool = True,
    page: int = 1,
    limit: int = 50,
    _admin: bool = Depends(require_admin),
):
    if grouped:
        items, total = get_keystrokes_grouped(user_id, date, page, limit)
    else:
        items, total = get_keystrokes(user_id, date, start_time, end_time, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.get("/api/admin/activities")
async def admin_activities(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    _admin: bool = Depends(require_admin),
):
    items, total = get_activities(user_id, date, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.get("/api/admin/events")
async def admin_events(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    _admin: bool = Depends(require_admin),
):
    items, total = get_events(user_id, date, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.get("/api/admin/stats")
async def admin_stats(_admin: bool = Depends(require_admin)):
    users = get_all_users()
    today = datetime.now(_KST).strftime("%Y-%m-%d")

    online = sum(1 for u in users if u["status"] == "ONLINE")
    idle = sum(1 for u in users if u["status"] in ("IDLE", "REST"))
    offline = sum(1 for u in users if u["status"] == "OFFLINE")

    shots_today, _ = get_screenshots(date=today, page=1, limit=1)
    _, total_today = get_screenshots(date=today, page=1, limit=1)

    disk = get_disk_usage()
    return {
        "total_users": len(users),
        "online_count": online,
        "idle_count": idle,
        "offline_count": offline,
        "disk_usage_gb": disk["total_gb"],
        "total_screenshots_today": total_today,
    }


@app.get("/api/admin/settings")
async def admin_get_settings(_admin: bool = Depends(require_admin)):
    settings = get_all_settings()
    settings.pop("admin_password_hash", None)
    return settings


@app.put("/api/admin/settings")
async def admin_update_settings(request: Request, _admin: bool = Depends(require_admin)):
    body = await request.json()
    for key, value in body.items():
        if key == "admin_password_hash":
            continue  # disallow direct hash manipulation
        if key == "admin_password":
            hashed = bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()
            update_setting("admin_password_hash", hashed)
        else:
            update_setting(key, str(value))
    return {"ok": True}


@app.get("/api/admin/disk-usage")
async def admin_disk_usage(_admin: bool = Depends(require_admin)):
    return get_disk_usage()


# ---------------------------------------------------------------------------
# Mount static files last (so /api and /images routes take priority)
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")

def _windows_set_run_key(app_name: str, command: str) -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg  # type: ignore

        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
        return True
    except Exception:
        return False


def _ensure_windows_autostart_admin_app() -> None:
    """
    Install the admin app EXE into a fixed system folder and register that installed EXE for auto-start.

    Target:
      C:\\ProgramData\\TAM\\AdminApp\\tam_admin.exe
    """
    if not sys.platform.startswith("win"):
        return

    exe_path = Path(sys.executable)
    if not exe_path.name.lower().endswith(".exe"):
        return

    if "--autostart" in sys.argv:
        # No console in the frozen build; still useful if redirected to a log.
        try:
            print("Launched via Windows auto-start.")
        except Exception:
            pass

    install_dir = Path(r"C:\ProgramData\TAM\AdminApp")
    target_exe = install_dir / "tam_admin.exe"

    run_cmd = f"\"{str(target_exe)}\" --autostart"
    _windows_set_run_key("TAM Admin", run_cmd)

    try:
        if exe_path.resolve() == target_exe.resolve():
            return
    except Exception:
        if str(exe_path).lower() == str(target_exe).lower():
            return

    if "--installed" in sys.argv:
        return

    try:
        os.makedirs(install_dir, exist_ok=True)

        tmp_exe = install_dir / "tam_admin.new.exe"
        shutil.copy2(str(exe_path), str(tmp_exe))
        os.replace(str(tmp_exe), str(target_exe))

        subprocess.Popen([str(target_exe), "--installed"], close_fds=True)
        sys.exit(0)
    except Exception:
        # If install fails (permissions, etc.), still allow app to run from current location.
        return


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    _ensure_windows_autostart_admin_app()
    uvicorn.run(
    app,
    host="0.0.0.0",
    port=8007,
    reload=False,
    log_config=None,      # <— key change: avoid DefaultFormatter
    access_log=False,     # optional: reduces noise
)
