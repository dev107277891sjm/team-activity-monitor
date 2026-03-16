import subprocess
import sys
from datetime import datetime

def build():
    date_str = datetime.now().strftime("%Y%m%d")
    name = f"tam_user_{date_str}"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--name={name}",
        "--hidden-import", "pynput.keyboard._win32",
        "--hidden-import", "pynput.mouse._win32",
        "--hidden-import", "PIL._tkinter_finder",
        "client/main.py",
    ]

    print(f"Building {name}.exe ...")
    subprocess.run(cmd, check=True)
    print(f"Done! Output: dist/{name}.exe")

if __name__ == "__main__":
    build()
