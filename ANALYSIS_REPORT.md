# Team Activity Monitor — System Analysis Report

**Project Name:** Team Activity Monitor (TAM)  
**Date:** March 16, 2026  
**Prepared for:** Admin (Team Manager)  
**Team Size:** Dynamic (users can be added at any time)  
**Platform:** Windows 11  
**Language:** Python  
**Server:** Local (Admin PC acts as server on LAN)  
**Cost:** $0 (no cloud services required)  

---

## 1. Purpose Analysis

### 1.1 Primary Goal

Build a **persistent employee activity monitoring system** that runs silently and continuously on each team member's Windows PC, capturing:

- Periodic screenshots (all monitors)
- Keyboard input logs
- Active process names and browser URLs
- System events (boot, shutdown, app start/stop)

All data is uploaded over the **local area network (LAN)** to the **admin's PC**, which acts as a local server. The admin views all data through a **web-based dashboard** accessible from the same PC. No cloud services or internet connection is required.

### 1.2 Core Principles

| Principle | Description |
|-----------|-------------|
| **Persistence** | The User App must auto-start on boot and resist being closed or killed by the user. |
| **Continuity** | Every gap in monitoring (reboot, crash, intentional stop) must be logged and visible to admin. |
| **Identity** | Each user is uniquely identified by their **Local IP Address** (immutable) + **Display Name** (mutable). |
| **Stealth** | The monitoring is fully silent — users are NOT notified that monitoring is active. |
| **Transparency (Admin)** | Admin can see real-time status and historical activity of every team member. |
| **Configurability** | Admin controls capture interval, monitoring parameters, and can manage users remotely. |
| **Scalability** | Users can be added at any time — the system is not limited to a fixed number. |

### 1.3 Key Monitoring Dimensions

1. **Visual** — Periodic screenshots of all connected monitors
2. **Input** — Keystroke logging (what was typed, when)
3. **Context** — Which application/process is active, which URL is open in the browser
4. **Temporal** — Timeline of work/rest/offline status throughout the day
5. **System** — Boot events, app start/stop events, connectivity status

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              ADMIN PC (Your PC — Server + Dashboard)            │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  REST API    │  │  Database    │  │  Screenshot Storage   │  │
│  │  (FastAPI)   │  │  (SQLite)    │  │  (Local Disk Folder)  │  │
│  │  Port: 8000  │  │              │  │  E:\TAM_Data\images\  │  │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         └────────────────┼──────────────────────┘               │
│  ┌─────────────┐  ┌──────────────┐                              │
│  │  Web UI      │  │  Alert       │                              │
│  │  (Dashboard) │  │  (Email/SMTP)│                              │
│  │  Port: 8000  │  │              │                              │
│  └─────────────┘  └──────────────┘                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │ LAN (HTTP)
          ┌───────────────┼───────────────┐
          │               │               │
   ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
   │  User App   │ │  User App   │ │  User App   │
   │  (PC #1)    │ │  (PC #2)    │ │  (PC #N)    │
   │  - Capture  │ │  - Capture  │ │  - Capture  │
   │  - Keylog   │ │  - Keylog   │ │  - Keylog   │
   │  - Process  │ │  - Process  │ │  - Process  │
   │  - Upload   │ │  - Upload   │ │  - Upload   │
   └─────────────┘ └─────────────┘ └─────────────┘
```

**Key:** The admin's PC runs everything — the API server, database, file storage, and the web dashboard. User Apps connect to it over the office LAN. No internet or cloud services required.

### 2.2 Component Breakdown

#### A. User App (Runs on each team member's PC)

| Module | Responsibility |
|--------|---------------|
| **Screen Capturer** | Captures all monitors at configured intervals; also triggers on process change |
| **Keyboard Logger** | Records all keystrokes with timestamps |
| **Process Monitor** | Tracks active foreground process name and window title |
| **URL Tracker** | Extracts browser URL from supported browsers (Chrome, Edge, Firefox) |
| **Event Logger** | Logs boot, shutdown, app start, app stop, and connectivity events |
| **Data Uploader** | Compresses and uploads screenshots + logs to admin's local server via LAN |
| **Local Buffer** | **Primary storage when server is unreachable** — all data (screenshots, keystrokes, process logs, events) is saved to local SQLite DB + local image folder. Automatically syncs everything to server when connection is restored. |
| **Connection Monitor** | Continuously checks if admin server is reachable; manages transitions between online (upload directly) and offline (buffer locally) modes |
| **Self-Protection** | Prevents user from closing, killing, or disabling the app |
| **Auto-Start** | Registers as Windows service / startup task to survive reboots |
| **Identity Manager** | Detects local IP, manages user registration and name changes |

#### B. Admin App (Runs on manager's PC)

| Module | Responsibility |
|--------|---------------|
| **Dashboard** | Overview of all users with real-time status indicators |
| **Timeline Viewer** | Color-coded timeline bars showing each user's activity status |
| **Screenshot Viewer** | Browse, search, and zoom into captured screenshots by user/date/time |
| **Keystroke Log Viewer** | View keystroke logs with timestamps |
| **Process/URL History** | View what apps and websites each user accessed |
| **Event Log** | View system events (boots, shutdowns, app restarts) |
| **Settings Panel** | Configure capture interval, manage users, set alert rules |
| **User Management** | View registered users, their names, IP addresses, and status |

#### C. Local Server (runs on Admin PC)

| Module | Responsibility |
|--------|---------------|
| **REST API (FastAPI)** | Receives data from User Apps over LAN, serves data to Admin Dashboard |
| **Database (SQLite)** | Stores metadata, logs, user profiles, events, settings — single file on local disk |
| **File Storage (Local Disk)** | Stores screenshot images in organized folder structure (e.g., `E:\TAM_Data\images\{user_ip}\{date}\`) |
| **Web Dashboard** | Served by FastAPI on the same port — admin opens browser to `http://localhost:8000` |
| **Authentication** | API key for User Apps; single admin password for Dashboard login |
| **Data Cleanup** | Scheduled task to auto-delete data older than 90 days |

---

## 3. Timezone Policy

All team members may have different timezone settings on their local PCs. To ensure consistent timestamps across the entire system:

| Rule | Description |
|------|-------------|
| **Unified timezone** | All timestamps (screenshots, keystrokes, events, logs) are stored and displayed in a **single timezone** configured by admin |
| **Default timezone** | **GMT+9 (Asia/Seoul)** |
| **Admin-configurable** | Admin can change the system timezone from the Settings panel |
| **User App behavior** | Regardless of the user PC's local timezone, the User App converts all timestamps to the system timezone before storing or uploading |
| **Server behavior** | The server stores all DateTime values in the configured timezone |
| **Dashboard display** | All times shown on the admin dashboard use the configured timezone |

**How it works:**

```
User PC (timezone: GMT+7)              Admin Server (system timezone: GMT+9)
─────────────────────────              ─────────────────────────────────────
Screen captured at local 14:00  ──►    Stored as 16:00 (GMT+9)
Keystroke logged at local 14:05 ──►    Stored as 16:05 (GMT+9)
```

The User App always reads the system timezone setting from the server and applies the conversion. If the admin changes the timezone, all **new** data uses the new timezone. Historical data retains its original timestamps.

---

## 4. Data Model

**All DateTime fields below use the admin-configured timezone (default: GMT+9).**

### 4.1 User Profile

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | UUID | Auto-generated unique ID |
| `local_ip` | String | Local IP address (primary identifier, immutable by user) |
| `display_name` | String | User-chosen name (mutable) |
| `registered_at` | DateTime | First registration timestamp |
| `last_seen` | DateTime | Last heartbeat timestamp |
| `status` | Enum | ONLINE / IDLE / OFFLINE |

### 4.2 Screenshot Record

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique screenshot ID |
| `user_id` | FK → User | Who captured it |
| `captured_at` | DateTime | When captured |
| `monitor_index` | Integer | Which monitor (0, 1, 2...) |
| `image_path` | String | Relative path on local disk (e.g., `images/192.168.1.45/2026-03-16/103200_mon0.jpg`) |
| `trigger` | Enum | PERIODIC / PROCESS_CHANGE |
| `active_process` | String | Process name at capture time |
| `active_url` | String | Browser URL at capture time (if applicable) |
| `window_title` | String | Active window title |

### 4.3 Keystroke Log

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique log entry ID |
| `user_id` | FK → User | Who typed it |
| `timestamp` | DateTime | When the key was pressed |
| `key_data` | Text | Keystroke data (batched per interval) |
| `active_process` | String | Which app was focused |
| `active_window` | String | Window title |

### 4.4 Process/URL Activity Log

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique log entry ID |
| `user_id` | FK → User | User reference |
| `process_name` | String | e.g., "chrome.exe", "code.exe" |
| `window_title` | String | Window title text |
| `url` | String | Browser URL (if applicable) |
| `started_at` | DateTime | When user switched to this process |
| `ended_at` | DateTime | When user switched away |

### 4.5 System Event Log

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique event ID |
| `user_id` | FK → User | User reference |
| `event_type` | Enum | PC_BOOT / PC_SHUTDOWN / APP_START / APP_STOP / APP_CRASH / NETWORK_LOST / NETWORK_RESTORED / SERVER_UNREACHABLE / SERVER_RECONNECTED / SYNC_STARTED / SYNC_COMPLETED |
| `timestamp` | DateTime | When event occurred |
| `details` | JSON | Additional context |

### 4.6 Admin Settings

| Field | Type | Description |
|-------|------|-------------|
| `system_timezone` | String | Timezone for all timestamps (default: `Asia/Seoul` GMT+9). Admin can change this. |
| `capture_interval_sec` | Integer | Screenshot interval in seconds (default: 30) |
| `keylog_batch_interval` | Integer | How often keystrokes are batched and sent (default: 60) |
| `image_quality` | Integer | JPEG compression quality 1-100 (default: 60) |
| `image_max_width` | Integer | Max pixel width per screenshot (default: 1920) |

---

## 5. UI/UX Design — User App

### 5.1 Design Philosophy

The User App should be **minimal and unobtrusive**. It runs in the **system tray** (notification area) and has very limited user interaction.

### 5.2 System Tray Icon

```
┌─────────────────────────────────────┐
│  System Tray Icon: [TAM]            │
│                                     │
│  Right-click menu:                  │
│  ┌───────────────────────────┐      │
│  │  Status: ● Recording      │      │
│  │  ─────────────────────── │      │
│  │  Change Name...           │      │
│  │  About                    │      │
│  └───────────────────────────┘      │
│                                     │
│  Note: NO "Exit" or "Stop" option   │
└─────────────────────────────────────┘
```

- **Green dot** = actively recording and uploading
- **Yellow dot** = recording but upload pending (network issue)
- **Red dot** = error state

### 5.3 Registration Screen (First Run Only)

```
┌─────────────────────────────────────────┐
│         Team Activity Monitor           │
│─────────────────────────────────────────│
│                                         │
│   Welcome! Please enter your name       │
│   to register this workstation.         │
│                                         │
│   Your Name: [____________________]     │
│                                         │
│   Local IP:  192.168.1.45 (detected)    │
│                                         │
│   Server:    192.168.1.100:8000 (LAN)   │
│              ● Connected                │
│                                         │
│              [ Register ]               │
│                                         │
└─────────────────────────────────────────┘
```

### 5.4 Name Change Dialog

```
┌─────────────────────────────────────────┐
│         Change Display Name             │
│─────────────────────────────────────────│
│                                         │
│   Current Name:  John Kim               │
│   New Name:      [____________________] │
│                                         │
│   Local IP:  192.168.1.45 (read-only)   │
│                                         │
│        [ Cancel ]    [ Save ]           │
│                                         │
└─────────────────────────────────────────┘
```

### 5.5 User App — Behavioral Rules

| Rule | Implementation |
|------|---------------|
| Cannot close from Task Manager | Run as Windows Service + watchdog process |
| Cannot close from system tray | No "Exit" menu option |
| Auto-starts on boot | Windows Service + Task Scheduler backup |
| Logs its own restarts | Writes APP_START event on launch |
| Survives user logoff | Runs as SYSTEM-level service |
| **Never stops capturing** | If admin server is off or LAN is down, all data buffers to local SQLite + image folder |
| **Auto-syncs when server returns** | Background sync uploads all buffered data (oldest first) when server becomes reachable |

---

## 6. UI/UX Design — Admin App

### 6.1 Design Philosophy

The Admin App is a **local web application** running on the admin's PC. The FastAPI server hosts both the REST API and the dashboard web UI. The admin simply opens a browser to `http://localhost:8000` to access the full dashboard. No internet required.

### 6.2 Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TEAM ACTIVITY MONITOR — Admin Dashboard                    [Settings] [👤] │
│─────────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  TODAY: Monday, March 16, 2026                    ◀ Prev Day | Next Day ▶  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ TEAM OVERVIEW                                              N Members  │ │
│  │                                                                       │ │
│  │  ● ONLINE: 3    ● IDLE: 1    ● OFFLINE: 1                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─ USER TIMELINE BARS ─────────────────────────────────────────────────┐   │
│  │                                                                       │  │
│  │  Time:  08:00  09:00  10:00  11:00  12:00  13:00  14:00  15:00  ... │  │
│  │         |      |      |      |      |      |      |      |          │  │
│  │                                                                       │  │
│  │  John Kim (192.168.1.45) ● ONLINE                                    │  │
│  │  [██████████████████████░░░░░░████████████████████████████████████]   │  │
│  │                                                                       │  │
│  │  Sara Lee (192.168.1.46) ● ONLINE                                    │  │
│  │  [████████████████████████████░░░░░░░░████████████████████████████]   │  │
│  │                                                                       │  │
│  │  Mike Park (192.168.1.47) ● IDLE                                     │  │
│  │  [████████████████████████████████████████████████████▒▒▒▒▒▒▒▒▒▒▒]   │  │
│  │                                                                       │  │
│  │  Amy Choi (192.168.1.48) ● ONLINE                                    │  │
│  │  [████████████████████████████████████████████████████████████████]   │  │
│  │                                                                       │  │
│  │  Tom Han  (192.168.1.49) ● OFFLINE                                   │  │
│  │  [████████████████████████████████████████████████░░░░            ]   │  │
│  │                                                                       │  │
│  │  LEGEND:                                                              │  │
│  │  ██ Working (green)   ░░ Rest/Break (yellow)   ▒▒ Idle (orange)      │  │
│  │     Offline (gray)    !! Alert/App Stopped (red)                      │  │
│  │  ▲▲ PC Boot (blue marker)  ▼▼ PC Shutdown (blue marker)              │  │
│  │  ◆◆ App Restart (red marker)                                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  Click on any user's timeline to view detailed activity below               │
│                                                                             │
│  ┌─ SELECTED USER DETAIL ───────────────────────────────────────────────┐   │
│  │  John Kim — 192.168.1.45 — Status: ● ONLINE                         │  │
│  │                                                                       │  │
│  │  [Screenshots] [Keystrokes] [Processes/URLs] [Events]                │  │
│  │                                                                       │  │
│  │  ┌─ Screenshots (10:30 AM ~ 11:00 AM) ─────────────────────────┐    │  │
│  │  │                                                               │    │  │
│  │  │  10:30:00   10:30:30   10:31:00   10:31:30   10:32:00        │    │  │
│  │  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐          │    │  │
│  │  │  │ img  │  │ img  │  │ img  │  │ img  │  │ img  │          │    │  │
│  │  │  │      │  │      │  │      │  │      │  │      │          │    │  │
│  │  │  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘          │    │  │
│  │  │                                                               │    │  │
│  │  │  Click thumbnail to view full-size image                      │    │  │
│  │  └───────────────────────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Timeline Bar — Color Coding Detail

| Color | Status | Condition |
|-------|--------|-----------|
| **Green** (██) | Working | User App is running, user is actively using keyboard/mouse |
| **Yellow** (░░) | Rest / Break | User App is running, but no keyboard/mouse input for > 5 min |
| **Orange** (▒▒) | Idle | User App is running, but no input for > 15 min |
| **Gray** ( ) | Offline / PC Off | No heartbeat received from User App |
| **Red** (!!) | Alert | User App was forcefully stopped or crashed |
| **Blue marker** (▲▼) | Boot/Shutdown | PC boot or shutdown event detected |
| **Red marker** (◆) | App Restart | User App was restarted (suspicious if frequent) |

### 6.4 Timeline Bar — Interactive Behavior

- **Hover** on any segment → tooltip shows: time range, status, active process
- **Click** on any segment → jumps to that time in the detail panel below
- **Drag** to select a range → filters screenshots/logs to that range
- **Zoom** with scroll wheel → expand/collapse the time axis
- Event markers (boot, shutdown, app restart) appear as **small icons above the bar**

### 6.5 Screenshot Viewer

```
┌─────────────────────────────────────────────────────────────────┐
│  Screenshot Viewer — John Kim — March 16, 2026                  │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
│  Time: 10:32:00 AM        Monitor: 1 of 2        ◀  ▶  ⏩       │
│  Process: chrome.exe      URL: https://github.com/...           │
│  Trigger: Periodic (30s interval)                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐      │
│  │                                                        │      │
│  │              [ Full-size Screenshot ]                   │      │
│  │                                                        │      │
│  │              Monitor 1                                  │      │
│  │                                                        │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐      │
│  │                                                        │      │
│  │              [ Full-size Screenshot ]                   │      │
│  │                                                        │      │
│  │              Monitor 2                                  │      │
│  │                                                        │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                  │
│  ◀ Previous Capture     [Play Slideshow]     Next Capture ▶     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.6 Keystroke Log Viewer

```
┌─────────────────────────────────────────────────────────────────┐
│  Keystroke Log — John Kim — March 16, 2026                      │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
│  Filter: [All Apps ▼]  Time: [10:00 ▼] ~ [11:00 ▼]  [Search]  │
│                                                                  │
│  ┌───────────┬──────────────────┬────────────────────────────┐  │
│  │ Time      │ Application      │ Keystrokes                 │  │
│  ├───────────┼──────────────────┼────────────────────────────┤  │
│  │ 10:02:15  │ chrome.exe       │ "how to use python f..."  │  │
│  │ 10:05:32  │ code.exe         │ "def capture_screen()..." │  │
│  │ 10:08:44  │ slack.exe        │ "meeting at 3pm toda..."  │  │
│  │ 10:12:01  │ code.exe         │ "import mss[Enter]fr..."  │  │
│  │ ...       │ ...              │ ...                        │  │
│  └───────────┴──────────────────┴────────────────────────────┘  │
│                                                                  │
│  Click any row to see full keystroke content                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.7 Process / URL History

```
┌─────────────────────────────────────────────────────────────────┐
│  Process & URL History — John Kim — March 16, 2026              │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
│  ┌───────────┬───────────┬────────────────┬────────────────────┐│
│  │ Start     │ End       │ Process        │ URL / Window Title ││
│  ├───────────┼───────────┼────────────────┼────────────────────┤│
│  │ 09:00:00  │ 09:15:23  │ chrome.exe     │ Gmail - Inbox      ││
│  │ 09:15:23  │ 09:45:10  │ code.exe       │ main.py - VSCode   ││
│  │ 09:45:10  │ 09:50:00  │ chrome.exe     │ stackoverflow.com  ││
│  │ 09:50:00  │ 10:30:00  │ code.exe       │ server.py - VSCode ││
│  │ 10:30:00  │ 10:35:00  │ slack.exe      │ #general - Slack   ││
│  │ ...       │ ...       │ ...            │ ...                ││
│  └───────────┴───────────┴────────────────┴────────────────────┘│
│                                                                  │
│  Summary: chrome.exe 35% | code.exe 50% | slack.exe 15%        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.8 System Events Log

```
┌─────────────────────────────────────────────────────────────────┐
│  System Events — John Kim — March 16, 2026                      │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
│  ┌───────────┬────────────────────┬────────────────────────────┐│
│  │ Time      │ Event              │ Details                    ││
│  ├───────────┼────────────────────┼────────────────────────────┤│
│  │ 08:55:00  │ ▲ PC BOOT          │ Windows started            ││
│  │ 08:55:12  │ ◆ APP START        │ TAM User App v1.0 started  ││
│  │ 12:00:00  │ ░ IDLE START       │ No input for 5 minutes     ││
│  │ 12:15:00  │ █ ACTIVE RESUME    │ User returned              ││
│  │ 17:30:00  │ ▼ PC SHUTDOWN      │ Normal shutdown            ││
│  │ ...       │ ...                │ ...                        ││
│  └───────────┴────────────────────┴────────────────────────────┘│
│                                                                  │
│  ⚠ ALERTS:                                                      │
│  │ 14:22:00  │ !! APP KILLED     │ Process terminated by user ││
│  │ 14:22:05  │ ◆ APP RESTART     │ Watchdog restarted app     ││
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.9 Admin Settings Panel

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings                                                        │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
│  SYSTEM TIMEZONE                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Timezone:  [ Asia/Seoul (GMT+9) ▼ ]                 │       │
│  │  Note: All timestamps use this timezone.             │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  CAPTURE SETTINGS                                                │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Screenshot Interval:     [ 30 ] seconds             │       │
│  │  Image Quality:           [ 60 ] % (JPEG)            │       │
│  │  Max Image Width:         [ 1920 ] px                │       │
│  │  Capture on Process Change: [✓] Enabled              │       │
│  │  Skip if Screen Unchanged: [✓] Enabled              │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  ACTIVITY DETECTION                                              │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Idle Threshold (Rest):   [ 5 ] minutes              │       │
│  │  Idle Threshold (Idle):   [ 15 ] minutes             │       │
│  │  Heartbeat Interval:      [ 30 ] seconds             │       │
│  │  Offline Threshold:       [ 60 ] seconds             │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  KEYSTROKE LOGGING                                               │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Batch Upload Interval:   [ 60 ] seconds             │       │
│  │  Log Special Keys:        [✓] Enabled                │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  DATA RETENTION                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Keep Screenshots:        [ 90 ] days                │       │
│  │  Keep Keystroke Logs:     [ 90 ] days                │       │
│  │  Keep Event Logs:         [ 90 ] days                │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  USER MANAGEMENT                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  # │ Name      │ Local IP       │ Status  │ Action  │       │
│  │  1 │ John Kim  │ 192.168.1.45   │ Online  │ [View]  │       │
│  │  2 │ Sara Lee  │ 192.168.1.46   │ Online  │ [View]  │       │
│  │  3 │ Mike Park │ 192.168.1.47   │ Idle    │ [View]  │       │
│  │  4 │ Amy Choi  │ 192.168.1.48   │ Online  │ [View]  │       │
│  │  5 │ Tom Han   │ 192.168.1.49   │ Offline │ [View]  │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│              [ Save Settings ]    [ Reset Defaults ]             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Technical Implementation Plan

### 7.1 Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| **User App** | Python 3.11+ | Required by project spec |
| **Screen Capture** | `mss` library | Fast, cross-monitor screenshot capture |
| **Keyboard Logging** | `pynput` | Reliable keyboard hook on Windows |
| **Process/URL Detection** | `psutil` + `pygetwindow` + Windows API | Active window, process, browser URL extraction |
| **Auto-Start** | `pywin32` (Windows Service) | Runs before user login, survives logoff |
| **Self-Protection** | Watchdog process + service recovery | Restarts if killed |
| **Local Server** | FastAPI (Python) | High-performance async REST API + serves web dashboard |
| **Database** | SQLite | Zero-config, single-file DB, no installation needed, handles our scale easily |
| **File Storage** | Local disk folder | Screenshots saved as JPEG files in organized directory structure |
| **Admin Dashboard** | HTML + CSS + JavaScript (served by FastAPI) | Rich interactive web UI; admin opens `http://localhost:8000` |
| **Image Compression** | Pillow (PIL) | JPEG compression before upload |
| **Networking** | HTTP over LAN + API Keys | Fast local transfer; no internet needed |
| **Alert System** | Email notification via SMTP (Gmail/Outlook) | Notifies admin when user app goes down |
| **Local Buffer (User)** | SQLite | Offline data buffering on user PC when server unavailable |
| **Auto-Cleanup** | Scheduled task (APScheduler) | Deletes data older than 90 days from disk + DB |

### 7.2 User App — Execution Strategy

```
┌─────────────────────────────────────────────┐
│          WINDOWS SERVICE (SYSTEM)           │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Main Process (TAM Service)          │   │
│  │  ├── Screen Capture Thread           │   │
│  │  ├── Keyboard Logger Thread          │   │
│  │  ├── Process Monitor Thread          │   │
│  │  ├── Data Upload Thread              │   │
│  │  ├── Heartbeat Thread                │   │
│  │  └── Watchdog Thread                 │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Tray Icon Process (USER session)    │   │
│  │  └── System tray UI                  │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  Recovery: If service stops, Windows SCM    │
│  auto-restarts it. Task Scheduler as backup.│
└─────────────────────────────────────────────┘
```

### 7.3 Data Flow

```
User PCs (on LAN)                       Admin PC (Server + Dashboard)
─────────────────                       ─────────────────────────────

1. Capture screenshot ───── LAN ──────► FastAPI receives image ──► Saved to local disk
2. Log keystrokes ───────── LAN ──────► FastAPI receives data ──► Saved to SQLite DB
3. Track process change ─── LAN ──────► FastAPI receives data ──► Saved to SQLite DB
4. Send heartbeat ────────  LAN ──────► FastAPI updates status ─► SQLite DB updated
5. Log system event ─────── LAN ──────► FastAPI receives event ─► SQLite DB + alert check
                                                                    ↓
                                                            (If app-down detected)
                                                            SMTP → Email alert to Admin

                                        Admin opens browser to http://localhost:8000:
                                        ├── Dashboard ──────► SQLite (select)
                                        ├── Timeline ───────► SQLite (select)
                                        ├── Screenshots ────► Local disk (read files)
                                        ├── Keystroke Logs ─► SQLite (select)
                                        ├── Event Log ──────► SQLite (select)
                                        └── Settings ───────► SQLite (update)
```

### 7.4 Capture Trigger Logic

```python
# Pseudocode for capture decision
last_screen_hash = None

while running:
    current_process = get_active_process()

    if current_process != last_process:
        # Process changed — always capture (screen definitely changed)
        capture_all_screens(trigger="PROCESS_CHANGE")
        last_screen_hash = compute_screen_hash()
        log_process_change(last_process, current_process)
        last_process = current_process

    elif time_since_last_capture >= capture_interval:
        current_hash = compute_screen_hash()
        if current_hash != last_screen_hash:
            # Screen content changed — capture
            capture_all_screens(trigger="PERIODIC")
            last_screen_hash = current_hash
        else:
            # Screen unchanged — skip capture, save storage
            log_skipped_capture(reason="SCREEN_UNCHANGED")

    sleep(0.5)  # Check every 500ms
```

**Screen Change Detection:** Before saving a periodic screenshot, the app computes a lightweight hash (perceptual hash or downscaled pixel comparison) of the current screen and compares it to the previous capture. If the screen content is identical (e.g., user is reading a document, screen is locked, or an idle application is displayed), the capture is **skipped**. This significantly reduces storage — typically by 30-60%.

| Capture Trigger | Skip If Unchanged? | Reason |
|----------------|--------------------|----|
| **Process change** | No — always capture | New process = new context worth recording |
| **Periodic interval** | **Yes — skip if screen unchanged** | Avoids storing duplicate images |

### 7.5 Identity & Registration Flow

```
FIRST RUN:
1. Detect local IP address (e.g., 192.168.1.45)
2. Show registration dialog → user enters name + admin server IP (e.g., 192.168.1.100)
3. Send POST http://192.168.1.100:8000/api/register { local_ip, display_name }
4. Server creates user profile, returns user_id + API key
5. Store user_id + API key + server_ip locally (encrypted)

SUBSEQUENT RUNS:
1. Read stored user_id + API key + server_ip
2. Detect current local IP
3. Send heartbeat to server with user_id + local_ip
4. If server unreachable → buffer data locally → retry periodically

NAME CHANGE:
1. User selects "Change Name" from tray menu
2. Enter new name → Send PUT http://{server_ip}:8000/api/users/{id}/name { new_name }
3. Server updates display_name, keeps local_ip unchanged
```

---

## 8. Self-Protection Strategy

### 8.1 Multi-Layer Protection

| Layer | Method | Description |
|-------|--------|-------------|
| **Layer 1** | Windows Service | Runs as SYSTEM; cannot be stopped by standard users |
| **Layer 2** | Service Recovery | Windows SCM restarts service on failure (1s, 5s, 30s) |
| **Layer 3** | Task Scheduler | Backup: checks every 1 min if service is running, restarts if not |
| **Layer 4** | Watchdog Thread | Internal thread monitors all other threads, restarts if frozen |
| **Layer 5** | Event Logging | Every start/stop/crash is logged to server with timestamp |
| **Layer 6** | Admin Alert | Dashboard shows red alert if app was killed/stopped |

### 8.2 What Gets Detected

| User Action | System Response |
|-------------|-----------------|
| Kill process in Task Manager | Service auto-restarts in 1-5 seconds; event logged |
| Stop Windows Service | Requires admin password; if stopped, Task Scheduler restarts |
| Delete from Task Scheduler | Service still runs; only loses backup layer |
| Disable network | Data buffered locally; uploads when reconnected |
| Uninstall the app | Requires admin password; final event sent if possible |

---

## 9. Offline Buffering & Auto-Sync Strategy

This is a critical feature: **monitoring never stops**, regardless of whether the admin server is reachable.

### 9.1 Core Principle

The User App operates in two modes:

| Mode | Condition | Behavior |
|------|-----------|----------|
| **Online Mode** | Admin server is reachable on LAN | Data is captured and uploaded to server immediately |
| **Offline Mode** | Admin server is unreachable (PC off, LAN down, etc.) | Data is captured and saved to **local buffer** on user's PC |

The transition between modes is **automatic and seamless**. The user app never pauses or stops capturing.

### 9.2 When Does Offline Mode Activate?

| Scenario | What Happens |
|----------|-------------|
| Admin PC is **turned off** | User App detects server unreachable → switches to offline mode → buffers all data locally |
| Admin PC is **turned on** | User App detects server is back → switches to online mode → **syncs all buffered data** → resumes live upload |
| **LAN cable unplugged** or Wi-Fi lost | Same as above — offline mode activates immediately |
| **LAN restored** | Same as above — auto-sync begins immediately |
| Admin server **crashes or restarts** | Momentary offline → auto-reconnect when server is back |

### 9.3 Local Buffer Architecture (on User PC)

```
User PC — Local Buffer
─────────────────────────────────────────────────
C:\ProgramData\TAM\
├── buffer.db            ← SQLite: keystroke logs, process logs, events, heartbeats
├── config.json          ← Server IP, user_id, API key (encrypted)
└── images\              ← Buffered screenshots (not yet sent to server)
    ├── 2026-03-16_103000_mon0.jpg
    ├── 2026-03-16_103000_mon1.jpg
    ├── 2026-03-16_103030_mon0.jpg
    └── ...
```

| Buffer Component | What's Stored |
|-----------------|---------------|
| `buffer.db` (SQLite) | Keystroke logs, process/URL activity, system events, heartbeats — all with timestamps and `synced = false` flag |
| `images/` folder | Screenshot JPEG files waiting to be uploaded |
| Each record has a `synced` flag | `false` = not yet sent to server, `true` = successfully sent (then deleted from buffer) |

### 9.4 Auto-Sync Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  USER APP — CONNECTION MONITOR (runs every 5 seconds)           │
│                                                                  │
│  1. Try to reach admin server: GET http://{server_ip}:8000/ping │
│     │                                                            │
│     ├── SUCCESS (server is online)                               │
│     │   │                                                        │
│     │   ├── If was previously OFFLINE:                           │
│     │   │   ├── Log event: SERVER_RECONNECTED                   │
│     │   │   ├── Start BACKGROUND SYNC of all buffered data      │
│     │   │   │   ├── Upload buffered screenshots (oldest first)  │
│     │   │   │   ├── Upload buffered keystroke logs               │
│     │   │   │   ├── Upload buffered process/URL logs             │
│     │   │   │   ├── Upload buffered system events                │
│     │   │   │   └── Mark each record as synced=true, then delete│
│     │   │   └── Switch to ONLINE mode                           │
│     │   │                                                        │
│     │   └── If already ONLINE:                                   │
│     │       └── Upload new data directly to server (normal flow) │
│     │                                                            │
│     └── FAILURE (server unreachable)                             │
│         │                                                        │
│         ├── If was previously ONLINE:                            │
│         │   ├── Log event: SERVER_UNREACHABLE                   │
│         │   └── Switch to OFFLINE mode                          │
│         │                                                        │
│         └── If already OFFLINE:                                  │
│             └── Continue buffering locally (no action needed)    │
│                                                                  │
│  2. Regardless of mode: CAPTURE NEVER STOPS                     │
│     - Screenshots are always taken at configured interval        │
│     - Keystrokes are always logged                               │
│     - Processes/URLs are always tracked                          │
│     - Events are always recorded                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.5 Sync Details

| Aspect | Behavior |
|--------|----------|
| **Sync order** | Oldest data first (chronological) — ensures timeline continuity on admin dashboard |
| **Sync speed** | Background thread — does not block new captures; uploads in parallel with live monitoring |
| **Large backlog** | If user was offline for days, sync may take minutes; progress is logged |
| **Partial sync** | If connection drops mid-sync, completed items stay synced; remaining items retry later |
| **Duplicate prevention** | Each record has a unique ID; server rejects duplicates (idempotent upload) |
| **Disk cleanup** | After successful sync, buffered screenshots are deleted from user PC to free space |
| **Sync confirmation** | Server returns HTTP 200 for each accepted batch; User App only deletes buffer after confirmation |

### 9.6 Admin Dashboard — Offline Indicator

When the admin views the dashboard, they can clearly see which users are buffering offline:

| User Status | Dashboard Display |
|-------------|------------------|
| Online, uploading live | **Green** — "Online" |
| Offline, buffering locally | **Gray** — "Offline (buffering)" |
| Just reconnected, syncing backlog | **Blue** — "Syncing..." with progress |
| Data gap (user PC was also off) | **Dark gray** — gap in timeline |

### 9.7 What Triggers Each Scenario

```
SCENARIO 1: Admin PC turns off at 5:00 PM, turns on at 9:00 AM next day
─────────────────────────────────────────────────────────────────────────
5:00 PM  — User Apps detect server unreachable → switch to offline mode
5:00 PM ~ 9:00 AM — All data buffered locally on each user's PC
         (If user PCs were on overnight, captures continue into buffer)
         (If user PCs shut down, buffer waits on disk until next boot)
9:00 AM  — Admin PC boots → FastAPI server starts automatically
9:00 ~   — User Apps detect server is back → auto-sync begins
           All buffered screenshots, logs, events upload to server
           Admin dashboard shows complete timeline (no gaps in data)

SCENARIO 2: LAN switch fails for 2 hours
─────────────────────────────────────────
10:00 AM — LAN goes down → User Apps switch to offline mode
10:00 ~ 12:00 — All data buffered locally
12:00 PM — LAN restored → User Apps detect server → sync begins
           2 hours of buffered data uploads to server
           Timeline on dashboard fills in seamlessly

SCENARIO 3: User PC reboots while offline
─────────────────────────────────────────
- Buffer is on disk (SQLite + image files) → survives reboot
- On reboot, User App starts → checks buffer → finds unsynced data
- Tries to reach server → if reachable, syncs → if not, continues buffering
```

### 9.8 Local Buffer Storage Estimate (User PC)

| Offline Duration | Screenshots (30s, 8h work) | Logs | Total per User |
|-----------------|---------------------------|------|----------------|
| 1 hour | ~120 images × 100KB = ~12 MB | ~1 MB | ~13 MB |
| 1 day (8h work) | ~960 images = ~96 MB | ~7 MB | ~103 MB |
| 3 days | ~2,880 images = ~288 MB | ~21 MB | ~309 MB |
| 1 week (5 days) | ~4,800 images = ~480 MB | ~35 MB | ~515 MB |

Even a week of offline buffering uses only ~500 MB per user — negligible on any modern PC.

---

## 10. Local Server Storage Requirements (Admin PC)

### 10.1 Estimated Storage

**Worst case (no skip optimization):**

| Data Type | Size per User per Day | 5 Users per Day | 90 Days (5 Users) |
|-----------|----------------------|-----------------|-------------------|
| Screenshots (30s interval, 8h) | ~960 images × 100KB = ~96 MB | ~480 MB | ~43.2 GB |
| Keystroke logs | ~5 MB | ~25 MB | ~2.25 GB |
| Process/URL logs | ~2 MB | ~10 MB | ~900 MB |
| SQLite database file | — | — | ~3 GB |
| **Total (worst case)** | **~103 MB** | **~515 MB** | **~49.4 GB** |

**Realistic estimate (with unchanged-screen skipping — default):**

Skipping unchanged screens typically saves 30-60% of screenshots. Realistic estimate:

| Data Type | Size per User per Day | 5 Users per Day | 90 Days (5 Users) |
|-----------|----------------------|-----------------|-------------------|
| Screenshots (after skip) | ~400-670 images × 100KB = ~40-67 MB | ~200-335 MB | ~18-30 GB |
| Keystroke logs | ~5 MB | ~25 MB | ~2.25 GB |
| Process/URL logs | ~2 MB | ~10 MB | ~900 MB |
| SQLite database file | — | — | ~3 GB |
| **Total (realistic)** | **~47-74 MB** | **~235-370 MB** | **~24-36 GB** |

*Note: With JPEG compression at 60% quality and 1920px max width, each screenshot averages ~100KB.*

### 10.2 Local Disk — Capacity Check

| Your Disk | Typical Size | 90 Days (5 Users) | Fits? |
|-----------|-------------|-------------------|-------|
| 256 GB SSD | 256 GB | ~49 GB (19% used) | Yes, comfortably |
| 512 GB SSD | 512 GB | ~49 GB (10% used) | Yes, very comfortable |
| 1 TB HDD/SSD | 1,000 GB | ~49 GB (5% used) | Yes, plenty of room |
| 2 TB HDD | 2,000 GB | ~49 GB (2.5% used) | Yes, massive headroom |

**Result:** A local server can easily handle 90 days of data for 5+ users. Even a 256 GB drive has more than enough room. No cloud limits, no monthly fees, no API rate limits.

### 10.3 Storage Management

| Feature | Implementation |
|---------|---------------|
| **Auto-cleanup** | Scheduled task deletes screenshots + DB records older than 90 days |
| **Folder structure** | `TAM_Data/images/{local_ip}/{YYYY-MM-DD}/{HHMMSS}_mon{N}.jpg` |
| **DB file** | Single SQLite file: `TAM_Data/tam.db` |
| **Disk space monitor** | Admin dashboard shows current disk usage and warns if < 20 GB free |

### 10.4 Built-in Optimization: Skip Unchanged Screens

The system **skips periodic captures when the screen has not changed** (see Section 7.4). This is enabled by default and typically reduces screenshot storage by **30-60%**, bringing the realistic 90-day estimate closer to **~20-35 GB** instead of ~49 GB.

### 10.5 Additional Optimization (if disk space is tight)

| Strategy | Impact |
|----------|--------|
| Increase capture interval to 60s | Cuts storage by ~50% |
| Lower JPEG quality to 40% | Cuts screenshot size by ~40% |
| Reduce max resolution to 1280px | Cuts screenshot size by ~30% |
| Reduce retention to 60 days | Cuts total by ~33% |

---

## 11. Security Considerations

| Concern | Mitigation |
|---------|------------|
| Data in transit | HTTP over LAN only — data never leaves the office network |
| API authentication | Each User App gets a unique API key at registration |
| Admin authentication | Single admin password to access the web dashboard |
| Stored screenshots | Stored on admin's local disk — physical access control |
| Keystroke data (full capture) | **All keystrokes captured including passwords** — only admin can view via dashboard |
| Local data buffer (user PC) | Encrypted SQLite database on user PC |
| API key storage on user PC | Stored in Windows Credential Manager or encrypted config file |
| User stealth | App runs silently; users are **not notified** about monitoring activity |
| Admin access | **Single admin only** — no multi-admin support needed |
| Network scope | All traffic stays on **LAN only** — no internet exposure, no cloud, no external attack surface |
| Server PC security | Admin's PC should have a strong Windows login password; the TAM data folder should have restricted permissions |

---

## 12. Development Phases

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Set up local server: FastAPI + SQLite database + local disk folder structure
- [ ] Build User App: screen capture + upload to local server via LAN
- [ ] Build User App: registration + identity (local IP detection, server IP config)
- [ ] Build User App: **local buffer system** (SQLite + image folder on user PC)
- [ ] Build User App: **connection monitor** (online/offline mode switching)
- [ ] Build User App: **auto-sync** (upload buffered data when server becomes reachable)
- [ ] Basic Admin Dashboard: user list + screenshot viewer (web UI)

### Phase 2: Full Monitoring (Week 3-4)
- [ ] User App: full keyboard logging (including passwords)
- [ ] User App: process/URL tracking
- [ ] User App: process-change-triggered capture
- [ ] User App: heartbeat + status reporting
- [ ] Admin Dashboard: timeline bar with color coding
- [ ] Admin Dashboard: offline/syncing status indicator per user

### Phase 3: Persistence & Protection (Week 5)
- [ ] User App: Windows Service implementation (silent, no user notification)
- [ ] User App: auto-start on boot
- [ ] User App: self-protection (watchdog, recovery)
- [ ] User App: SERVER_UNREACHABLE / SERVER_RECONNECTED event logging
- [ ] Event logging (boot, shutdown, app start/stop)

### Phase 4: Admin Dashboard Polish (Week 6)
- [ ] Admin Dashboard: interactive timeline (hover, click, zoom)
- [ ] Admin Dashboard: keystroke log viewer (full capture display)
- [ ] Admin Dashboard: process/URL history
- [ ] Admin Dashboard: system event log with alerts
- [ ] Admin Dashboard: settings panel (single admin login)
- [ ] Email alert system via SMTP (Gmail/Outlook)
- [ ] Auto-cleanup: scheduled task to delete data older than 90 days
- [ ] Disk space monitor: warn admin if free space < 20 GB

### Phase 5: Testing & Deployment (Week 7)
- [ ] End-to-end testing with team members on LAN
- [ ] Performance optimization (LAN transfer speed, image compression)
- [ ] Installer creation (User App — silent install with server IP config)
- [ ] Server auto-start: set up FastAPI server as Windows service on admin PC
- [ ] Documentation

---

## 13. Confirmed Decisions (Manager Responses)

| # | Question | Decision |
|---|----------|----------|
| 1 | Server Architecture | **Local server** on admin's PC (changed from Supabase) |
| 2 | Budget | **$0** — no cloud services, everything runs locally |
| 3 | Data Retention | **90 days** for all data (screenshots, keystroke logs, event logs) |
| 4 | Keystroke Privacy | **Fully captured** — no masking, including passwords |
| 5 | User Notification | **Silent** — users are NOT informed that monitoring is active |
| 6 | Admin Access | **Single admin only** (the manager) |
| 7 | Remote Access | **No** — Admin Dashboard accessed via `http://localhost:8000` |
| 8 | Alert Notifications | **Yes** — email notification via SMTP when a user's app goes down |
| 9 | User Scalability | **Dynamic** — users can be added at any time, no fixed limit |
| 10 | Storage | **Local disk** — ~49 GB for 5 users / 90 days (easily fits on any modern drive) |
| 11 | Offline Buffering | **User Apps buffer all data locally** when admin PC is off or LAN is down; auto-sync when reconnected |
| 12 | Timezone | **GMT+9 (Asia/Seoul)** as default for all timestamps; admin can change it from Settings |

---

## 14. Summary

This system consists of **two applications running on the office LAN:**

1. **User App** (installed on each team member's PC) — A persistent, silent Windows service that captures screenshots (all monitors), logs all keystrokes (including passwords), tracks active processes/URLs, and uploads everything to the admin's local server over the LAN. It auto-starts on boot, resists being stopped, and runs without notifying the user. New users can be added at any time by installing the app on a new PC. **When the admin server is unreachable (PC off or LAN down), the User App continues capturing and buffers all data locally. When the server comes back, all buffered data is automatically synced — no data is ever lost.**

2. **Admin Server + Dashboard** (runs on the manager's PC) — A FastAPI local server with SQLite database and local disk storage. It receives all monitoring data from User Apps (including backlogged data from offline periods), stores screenshots as JPEG files on the local hard drive, and serves a web-based dashboard at `http://localhost:8000`. The dashboard shows real-time user status through color-coded timeline bars, with detailed viewers for screenshots, keystroke logs, process history, and system events. Email alerts notify the admin when a user's app goes down.

**Key characteristics:**
- **Zero cost:** No cloud services, no subscriptions — everything runs locally
- **Never loses data:** User Apps buffer locally when server is down; auto-sync when reconnected
- **Smart capture:** Skips screenshots when screen is unchanged — saves 30-60% storage
- **90-day retention:** Realistically ~24-36 GB for 5 users — fits easily on any modern hard drive
- **Identity:** Each user identified by local IP (immutable) + display name (mutable)
- **Stealth:** Users are not informed about monitoring activity
- **Full capture:** All keystrokes including passwords are logged
- **Resilience:** Every monitoring gap (reboot, crash, intentional stop) is detected and alerted
- **Scalable:** New users can be added at any time
- **No internet required:** All data stays within the office LAN

---

*End of Analysis Report — Updated March 16, 2026 (Revised: Local Server + Offline Buffering)*
