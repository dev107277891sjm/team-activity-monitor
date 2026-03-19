# Team Activity Monitor (TAM)

Team Activity Monitor is an admin-server and user-client application for monitoring team activity. The admin server provides a web dashboard for viewing activity data, while the user client runs silently on workstations to collect and report activity metrics.

## Prerequisites

- Python 3.11+

## Setup

1. **Install server dependencies:**
   ```bash
   pip install -r requirements_server.txt
   ```

2. **Install client dependencies:**
   ```bash
   pip install -r requirements_client.txt
   ```

## Running the Application

**Server (admin):**
```bash
python -m server.app
```
or
```bash
python server/app.py
```

**Client (user):**
```bash
python -m client.main
```

## Building Executables

**Admin server .exe:**
```bash
python build_admin.py
```

**User client .exe:**
```bash
python build_user.py
```

Output files are placed in the `dist/` folder with date-stamped names (e.g., `tam_admin_20250316.exe`, `tam_user_20250316.exe`).

## Install location & auto-start (Windows)

### Installed system folders
When you run the built EXEs, TAM will copy itself into fixed **system folders** (so auto-start always points to a stable path):

- **User App**: `C:\ProgramData\TAM\UserApp\tam_user.exe`
- **Admin App**: `C:\ProgramData\TAM\AdminApp\tam_admin.exe`

These folders are intentionally different so the Admin and User apps never share the same install directory.

### Auto-start without admin rights (logon startup)
Without elevation, Windows does **not** allow true boot-time (“before login”) startup. TAM therefore uses the per-user Run key (starts **after** a user logs in):

- `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
  - `TAM User` → `"C:\ProgramData\TAM\UserApp\tam_user.exe" --autostart`
  - `TAM Admin` → `"C:\ProgramData\TAM\AdminApp\tam_admin.exe" --autostart`

### Why the User App can’t run pre-login
The User App depends on the interactive desktop session (tray icon, active window/process, screenshots). Before login there is no user desktop session to capture, so even if started pre-login it would not function as intended.

### Optional (requires admin): true boot-time startup
If you need the **Admin App** running before any user logs in, use **Task Scheduler** with an **At startup** trigger:

- Create a task that runs `C:\ProgramData\TAM\AdminApp\tam_admin.exe`
- Trigger: **At startup**
- Security options: run as `SYSTEM` (or an admin account), “Run whether user is logged on or not”

The User App should still be configured “At log on” (interactive), because it needs the desktop session.

#### Example commands (run in an elevated PowerShell)
Admin App (boot/startup time, no login required):

```powershell
schtasks /Create /TN "TAM Admin (Startup)" /SC ONSTART /RL HIGHEST /RU "SYSTEM" `
  /TR "\"C:\ProgramData\TAM\AdminApp\tam_admin.exe\" --autostart"
```

User App (starts at logon; interactive session):

```powershell
schtasks /Create /TN "TAM User (Logon)" /SC ONLOGON /RL HIGHEST `
  /TR "\"C:\ProgramData\TAM\UserApp\tam_user.exe\" --autostart"
```

## Configuration

- **Default admin password:** admin123
- **Server URL:** http://localhost:8007
- **Server data directory:** E:\TAM_Data
- **Client data directory:** C:\ProgramData\TAM
