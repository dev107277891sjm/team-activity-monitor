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

## Configuration

- **Default admin password:** admin123
- **Server URL:** http://localhost:8007
- **Server data directory:** E:\TAM_Data
- **Client data directory:** C:\ProgramData\TAM
