import subprocess
import sys
from datetime import datetime

def build():
    date_str = datetime.now().strftime("%Y%m%d")
    name = f"tam_admin_{date_str}"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        f"--name={name}",
        "--add-data", "server/static;server/static",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.lifespan.off",
        "--hidden-import", "email.mime.text",
        "--hidden-import", "email.mime.multipart",
        "--hidden-import", "email.mime.base",
        "server/app.py",
    ]

    print(f"Building {name}.exe ...")
    subprocess.run(cmd, check=True)
    print(f"Done! Output: dist/{name}.exe")

if __name__ == "__main__":
    build()
